"""Locate (or fetch) FFmpeg and check the GPU.

The remix engine time-stretches with FFmpeg's `rubberband` filter, so the FFmpeg
we use must include librubberband. The BtbN "gpl" builds do (gyan.dev's
"essentials" build does not), and BtbN publishes checksums.sha256 next to them.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from playlistkit.util import NO_WINDOW, PlaylistKitError, app_home, log

FFMPEG_RELEASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
FFMPEG_ZIP = "ffmpeg-master-latest-win64-gpl.zip"
_EXE = ".exe" if os.name == "nt" else ""


@dataclass(frozen=True)
class FFmpeg:
    ffmpeg: Path
    ffprobe: Path

    @property
    def folder(self) -> Path:
        return self.ffmpeg.parent


def _pair(folder: Path) -> FFmpeg | None:
    ff, fp = folder / f"ffmpeg{_EXE}", folder / f"ffprobe{_EXE}"
    return FFmpeg(ff, fp) if ff.is_file() and fp.is_file() else None


def has_rubberband(ffmpeg: Path) -> bool:
    try:
        out = subprocess.run([str(ffmpeg), "-hide_banner", "-filters"], capture_output=True, text=True,
                             timeout=30, creationflags=NO_WINDOW).stdout
        return " rubberband " in out
    except (OSError, subprocess.TimeoutExpired):
        return False


def _candidates() -> list[Path]:
    folders: list[Path] = []
    if os.environ.get("PLAYLISTKIT_FFMPEG"):
        folders.append(Path(os.environ["PLAYLISTKIT_FFMPEG"]).expanduser())
    if getattr(sys, "frozen", False):  # installer build: ffmpeg ships next to the exe
        exe_dir = Path(sys.executable).parent
        folders += [exe_dir / "ffmpeg", exe_dir]
    folders.append(app_home() / "ffmpeg" / "bin")
    return folders


@lru_cache(maxsize=1)
def find_ffmpeg(auto_download: bool = True) -> FFmpeg:
    for folder in _candidates():
        found = _pair(folder)
        if found:
            return found
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ff and fp and has_rubberband(Path(ff)):
        return FFmpeg(Path(ff), Path(fp))
    if auto_download and os.name == "nt":
        return _download_ffmpeg()
    if ff and fp:
        return FFmpeg(Path(ff), Path(fp))
    raise PlaylistKitError("FFmpeg not found. Install it (winget install Gyan.FFmpeg) and try again.")


def _download_ffmpeg() -> FFmpeg:
    target = app_home() / "ffmpeg"
    archive = app_home() / "ffmpeg-download.zip"
    log("FFmpeg not found, downloading a build with rubberband (about 200 MB, one time only)...")
    try:
        sums = urllib.request.urlopen(f"{FFMPEG_RELEASE}/checksums.sha256", timeout=30).read().decode()
        expected = next((line.split()[0].lower() for line in sums.splitlines()
                         if line.strip().endswith(FFMPEG_ZIP)), "")
        if not expected:
            raise PlaylistKitError("FFmpeg checksums file has no entry for the Windows build.")
        digest = hashlib.sha256()
        with urllib.request.urlopen(f"{FFMPEG_RELEASE}/{FFMPEG_ZIP}", timeout=60) as resp, open(archive, "wb") as out:
            while chunk := resp.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
    except OSError as exc:
        raise PlaylistKitError(f"FFmpeg download failed: {exc}. Install it manually: winget install Gyan.FFmpeg") from exc
    if digest.hexdigest() != expected:
        archive.unlink(missing_ok=True)
        raise PlaylistKitError("Downloaded FFmpeg does not match its SHA-256 checksum; discarded for safety.")
    shutil.rmtree(target, ignore_errors=True)
    (target / "bin").mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            base = Path(name).name
            if base in (f"ffmpeg{_EXE}", f"ffprobe{_EXE}") and "/bin/" in name:
                (target / "bin" / base).write_bytes(zf.read(name))
    archive.unlink(missing_ok=True)
    found = _pair(target / "bin")
    if not found:
        raise PlaylistKitError("Could not extract FFmpeg: ffmpeg.exe not found in the download.")
    log(f"FFmpeg installed to {found.folder}")
    return found


@lru_cache(maxsize=1)
def nvenc_available(ffmpeg: Path) -> bool:
    """True when h264_nvenc actually works on this machine (not just compiled in)."""
    try:
        proc = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "color=c=black:s=320x240:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=30, creationflags=NO_WINDOW)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@lru_cache(maxsize=1)
def nvidia_gpu() -> str:
    """Name of the NVIDIA GPU ('' if none). Used to pick the CUDA or CPU build of PyTorch."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                             timeout=20, creationflags=NO_WINDOW).stdout.strip()
        return out.splitlines()[0] if out else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def tool_env() -> dict:
    """Environment for child processes: our FFmpeg first on PATH."""
    env = dict(os.environ)
    try:
        env["PATH"] = str(find_ffmpeg().folder) + os.pathsep + env.get("PATH", "")
    except PlaylistKitError:
        pass
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env
