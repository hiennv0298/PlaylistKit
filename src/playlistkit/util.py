"""Small helpers shared by every step."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


class PlaylistKitError(RuntimeError):
    """An error we can explain to the user without a traceback."""


class Cancelled(PlaylistKitError):
    """The user pressed Stop."""

    def __init__(self, message: str = "Stopped by user.") -> None:
        super().__init__(message)


_cancel = threading.Event()
_log_sinks: list[Callable[[str], None]] = []
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".webm", ".wma", ".aiff", ".aif"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def request_cancel() -> None:
    _cancel.set()


def reset_cancel() -> None:
    _cancel.clear()


def cancelled() -> bool:
    return _cancel.is_set()


def check_cancel() -> None:
    """Raise Cancelled if Stop was pressed; long steps call this regularly."""
    if _cancel.is_set():
        raise Cancelled()


def add_log_sink(sink: Callable[[str], None]) -> None:
    """Also send every log line to `sink` (the app window uses this)."""
    _log_sinks.append(sink)


def app_home() -> Path:
    """Folder for settings, downloaded tools and the AI runtime (not for user output)."""
    override = os.environ.get("PLAYLISTKIT_HOME")
    if override:
        path = Path(override)
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PlaylistKit"
    else:
        path = Path.home() / ".playlistkit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_projects_dir() -> Path:
    music = Path.home() / "Music"
    return (music if music.is_dir() else Path.home()) / "PlaylistKit"


def log(message: str = "") -> None:
    try:
        print(message, flush=True)
    except (AttributeError, OSError, ValueError):
        pass  # no console (started without one)
    for sink in _log_sinks:
        sink(message)


def fmt_ts(seconds: float) -> str:
    """YouTube chapter style: 4:05, 1:02:09."""
    seconds = max(0, int(round(float(seconds))))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_ts(value: str) -> float:
    """Parse '75', '1:15' or '1:02:09' into seconds."""
    value = value.strip()
    if not value:
        raise ValueError("empty timestamp")
    parts = value.split(":")
    if len(parts) > 3:
        raise ValueError(f"bad timestamp: {value}")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def human_duration(seconds: float) -> str:
    """'55 phút', '1 giờ 7 phút' (the playlist title format)."""
    minutes = int(seconds // 60)
    h, m = divmod(minutes, 60)
    if h:
        return f"{h} giờ {m} phút" if m else f"{h} giờ"
    return f"{m} phút"


def fold(text: str) -> str:
    """Lower-case ASCII form used to compare names: 'Đừng Gặp' -> 'dung gap'."""
    text = unicodedata.normalize("NFKC", text).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def slugify(text: str, max_len: int = 48) -> str:
    """ASCII file-name-safe slug; Vietnamese diacritics are folded (đ -> d)."""
    return (fold(text).replace(" ", "-")[:max_len].strip("-")) or "playlist"


def safe_filename(text: str, max_len: int = 120) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = " ".join(text.split()).strip(" .")
    return text[:max_len].rstrip(" .") or "track"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if default is not None:
            return default
        raise


def audio_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT
                  and not any(part.startswith("_") for part in p.relative_to(folder).parts[:-1]))


def run(cmd: Sequence[str], cwd: Path | None = None, env: dict | None = None,
        on_line: Callable[[str], None] | None = None) -> subprocess.CompletedProcess:
    """Run a command; raise PlaylistKitError with the tail of its output on failure.

    With on_line, stdout+stderr are streamed line by line (for long jobs).
    Stop (request_cancel) kills the command instead of waiting for it.
    """
    args = list(map(str, cmd))
    if on_line is None:
        proc = subprocess.Popen(args, cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", creationflags=NO_WINDOW)
        while True:
            try:
                out, err = proc.communicate(timeout=0.3)
                break
            except subprocess.TimeoutExpired:
                if _cancel.is_set():
                    _kill(proc)
                    raise Cancelled() from None
        if proc.returncode != 0:
            tail = "\n".join((err or out or "").strip().splitlines()[-15:])
            raise PlaylistKitError(f"Command failed ({Path(args[0]).name}):\n{tail}")
        return subprocess.CompletedProcess(args, proc.returncode, out, err)

    proc = subprocess.Popen(args, cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", bufsize=1, creationflags=NO_WINDOW)
    tail: list[str] = []
    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(0.3):
            if _cancel.is_set():
                _kill(proc)
                return

    threading.Thread(target=watch, daemon=True).start()
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            tail = (tail + [line])[-20:]
            on_line(line)
        proc.wait()
    finally:
        stop.set()
    if _cancel.is_set():
        raise Cancelled()
    if proc.returncode != 0:
        raise PlaylistKitError(f"Command failed ({Path(args[0]).name}):\n" + "\n".join(tail[-15:]))
    return subprocess.CompletedProcess(args, proc.returncode, "", "")


def _kill(proc: subprocess.Popen) -> None:
    """Kill a process and its children (Demucs runs as a child of the engine)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=NO_WINDOW)
    else:
        proc.kill()
    try:
        proc.communicate(timeout=10)
    except (subprocess.TimeoutExpired, ValueError):
        pass


def setup_console() -> None:
    """Make Vietnamese text print correctly on the Windows console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def recycle(path: Path) -> None:
    """Move a file or folder to the Recycle Bin on Windows (deleted elsewhere)."""
    if not path.exists():
        return
    if os.name == "nt":
        try:
            _recycle_windows(path)
            return
        except OSError:
            pass
    if path.is_dir():
        import shutil
        shutil.rmtree(path)
    else:
        path.unlink()


def _recycle_windows(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 3, 0x40, 0x10, 0x4, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, str(path.resolve()) + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI, False, None, None)
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0 or path.exists():
        raise OSError(f"could not recycle {path}")
