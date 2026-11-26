"""Give the app window its own taskbar button on Windows.

The window is Edge/Chrome in app mode, so Windows groups it with every other
Edge app window (ClipKit, CommentKit, web apps...) under one taskbar button. Setting our own
AppUserModelID on the window (through its property store) gives PlaylistKit a
separate button with its own icon, and makes "Pin to taskbar" pin PlaylistKit.
Edge keeps setting its own ID (from the window's host), so keep_window_tagged() puts
ours back for as long as the app runs, and gui.py opens the window at its own host
(playlistkit.localhost) so even Edge's ID is PlaylistKit's alone.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from ctypes import POINTER, WINFUNCTYPE, Structure, byref, c_ubyte, c_ulong, c_ushort, c_void_p, c_wchar_p, wintypes
from pathlib import Path

APP_ID = "hiennv0298.PlaylistKit"
TITLE = "PlaylistKit"


class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]


class PROPERTYKEY(Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class PROPVARIANT(Structure):
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                ("p", c_void_p), ("p2", c_void_p)]


def _guid(d1, d2, d3, d4) -> GUID:
    return GUID(d1, d2, d3, (c_ubyte * 8)(*d4))


IID_IPropertyStore = _guid(0x886D8EEB, 0x8CF2, 0x4446, (0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
_AUMID_FMT = (0x9F4C2855, 0x9F79, 0x4B39, (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3))
PKEY_RELAUNCH_COMMAND = PROPERTYKEY(_guid(*_AUMID_FMT), 2)
PKEY_RELAUNCH_ICON = PROPERTYKEY(_guid(*_AUMID_FMT), 3)
PKEY_RELAUNCH_NAME = PROPERTYKEY(_guid(*_AUMID_FMT), 4)
PKEY_APP_ID = PROPERTYKEY(_guid(*_AUMID_FMT), 5)
VT_LPWSTR = 31


def set_window_app_id(hwnd: int, app_id: str, relaunch: str = "", icon: str = "", name: str = "") -> bool:
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    store = c_void_p()
    if shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), byref(IID_IPropertyStore), byref(store)) != 0:
        return False
    vtbl = ctypes.cast(ctypes.cast(store, POINTER(c_void_p))[0], POINTER(c_void_p))
    set_value = WINFUNCTYPE(ctypes.HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(vtbl[6])
    commit = WINFUNCTYPE(ctypes.HRESULT, c_void_p)(vtbl[7])
    release = WINFUNCTYPE(c_ulong, c_void_p)(vtbl[2])
    keep = []

    def put(key: PROPERTYKEY, text: str) -> None:
        s = c_wchar_p(text)
        keep.append(s)
        pv = PROPVARIANT(VT_LPWSTR, 0, 0, 0, ctypes.cast(s, c_void_p), None)
        set_value(store, byref(key), byref(pv))

    try:
        # relaunch details first: the shell reads them when the ID is set
        if relaunch and icon and name:
            put(PKEY_RELAUNCH_COMMAND, relaunch)
            put(PKEY_RELAUNCH_ICON, icon)
            put(PKEY_RELAUNCH_NAME, name)
        put(PKEY_APP_ID, app_id)
        commit(store)
        return True
    except OSError:
        return False
    finally:
        release(store)


def get_window_app_id(hwnd: int) -> str | None:
    """The window's AppUserModelID ('' when it has none, None when it cannot be read)."""
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    store = c_void_p()
    if shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), byref(IID_IPropertyStore), byref(store)) != 0:
        return None
    vtbl = ctypes.cast(ctypes.cast(store, POINTER(c_void_p))[0], POINTER(c_void_p))
    get_value = WINFUNCTYPE(ctypes.HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(vtbl[5])
    release = WINFUNCTYPE(c_ulong, c_void_p)(vtbl[2])
    pv = PROPVARIANT()
    try:
        get_value(store, byref(PKEY_APP_ID), byref(pv))
        value = ctypes.wstring_at(pv.p) if pv.vt == VT_LPWSTR and pv.p else ""
        ole32.PropVariantClear(byref(pv))
        return value
    except OSError:
        return None
    finally:
        release(store)


def _find_windows(title: str, since: float = 0.0) -> list[int]:
    """Visible browser windows (Chrome_WidgetWin*: Edge or Chrome) with this exact title. The class check keeps
    out a File Explorer window of a folder that happens to be called PlaylistKit."""
    user32 = ctypes.windll.user32
    found: list[int] = []

    @WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title:
                cls = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(hwnd, cls, 64)
                if cls.value.startswith("Chrome_WidgetWin"):
                    found.append(int(hwnd))
        return True

    user32.EnumWindows(each, 0)
    return found


def relaunch_target() -> tuple[str, str]:
    """(command, icon) used when the window is pinned to the taskbar."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        app = exe.with_name("PlaylistKitApp.exe")
        target = app if app.is_file() else exe
        return f'"{target}"', f"{target},0"
    ico = Path(__file__).with_name("webui") / "playlistkit.ico"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.is_file() else sys.executable}" -m playlistkit', str(ico)


_TAGGING = threading.Event()


def keep_window_tagged(fast_for: float = 20.0, every: float = 2.0) -> None:
    """Give PlaylistKit's windows their own taskbar identity, and keep giving it while the app runs.

    Tagging once is not enough: Edge sets an app window's ID from the address's host and path
    (MSEdge.127.0.0.1_/ when the window is at 127.0.0.1), after we tagged it and again later. Every
    app on 127.0.0.1 then shares one taskbar button. So this checks every few seconds and puts our
    ID back when it has changed. It looks quickly at first, while the window opens."""
    if os.name != "nt" or _TAGGING.is_set():
        return
    _TAGGING.set()

    def work() -> None:
        start = time.time()
        cmd, icon = relaunch_target()
        while True:
            try:
                for hwnd in _find_windows(TITLE):
                    if get_window_app_id(hwnd) != APP_ID:
                        set_window_app_id(hwnd, APP_ID, cmd, icon, TITLE)
            except OSError:
                pass
            time.sleep(0.4 if time.time() - start < fast_for else every)

    threading.Thread(target=work, name="taskbar-id", daemon=True).start()


tag_window_later = keep_window_tagged  # the name used up to 0.2.7
