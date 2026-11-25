"""Give the app window its own taskbar button on Windows.

The window is Edge/Chrome in app mode, so Windows groups it with every other
Edge app window (ClipKit, web apps...) under one taskbar button. Setting our own
AppUserModelID on the window (through its property store) gives PlaylistKit a
separate button with its own icon, and makes "Pin to taskbar" pin PlaylistKit.
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


def _find_windows(title: str, since: float) -> list[int]:
    user32 = ctypes.windll.user32
    found: list[int] = []

    @WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == title:
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


def tag_window_later(timeout: float = 20.0) -> None:
    """Wait for the app window to appear, then give it PlaylistKit's own taskbar identity."""
    if os.name != "nt":
        return

    def work() -> None:
        start = time.time()
        done: set[int] = set()
        cmd, icon = relaunch_target()
        while time.time() - start < timeout:
            for hwnd in _find_windows(TITLE, start):
                if hwnd not in done and set_window_app_id(hwnd, APP_ID, cmd, icon, TITLE):
                    done.add(hwnd)
            if done:
                return
            time.sleep(0.4)

    threading.Thread(target=work, daemon=True).start()
