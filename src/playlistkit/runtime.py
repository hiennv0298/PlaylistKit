"""The AI runtime for the remix engine (PyTorch + Demucs), installed on first use.

PyTorch with CUDA is about 2.5 GB, far too big for the installer, so the app
ships without it. "Install AI" downloads uv (Astral's Python package manager,
checked against its published SHA-256), lets uv fetch a private Python 3.12 and
installs PyTorch (CUDA 12.4 build when an NVIDIA GPU is present, CPU build
otherwise), Demucs, librosa and the other engine packages into
%LOCALAPPDATA%\\PlaylistKit\\ai. Nothing is installed system-wide.

You can also point Settings > "AI Python" at an existing Python that already has
torch + demucs (for example a project venv).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from playlistkit.deps import nvidia_gpu, tool_env
from playlistkit.util import NO_WINDOW, PlaylistKitError, app_home, log, run

UV_URL = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
TORCH_CUDA = ["torch==2.6.0", "torchaudio==2.6.0"]
TORCH_INDEX_CUDA = "https://download.pytorch.org/whl/cu124"
TORCH_INDEX_CPU = "https://download.pytorch.org/whl/cpu"
ENGINE_PACKAGES = ["demucs==4.0.1", "librosa>=0.10", "soundfile>=0.12", "pyloudnorm>=0.1.1", "scipy>=1.11",
                   "numpy>=1.24,<2.3"]
CHECK = "import torch, demucs, librosa, soundfile, pyloudnorm, scipy; print('ok', torch.__version__, torch.cuda.is_available())"
ENGINE = Path(__file__).with_name("engine") / "remix_engine.py"


def ai_dir() -> Path:
    return app_home() / "ai"


def managed_python() -> Path:
    venv = ai_dir() / "venv"
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_python(py: str | Path) -> dict:
    """{'ok': bool, 'torch': '2.6.0+cu124', 'cuda': True, 'error': ''}"""
    py = Path(py)
    if not py.is_file():
        return {"ok": False, "error": f"{py} not found"}
    try:
        proc = subprocess.run([str(py), "-c", CHECK], capture_output=True, text=True, timeout=180,
                              creationflags=NO_WINDOW, env=tool_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    m = re.search(r"ok (\S+) (True|False)", proc.stdout)
    if not m:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["unknown error"]
        return {"ok": False, "error": tail[0]}
    return {"ok": True, "torch": m.group(1), "cuda": m.group(2) == "True", "error": ""}


def find_python(setting: str = "") -> Path | None:
    for cand in [setting, str(managed_python())]:
        if cand and Path(cand).is_file():
            return Path(cand)
    return None


def status(setting: str = "") -> dict:
    py = find_python(setting)
    info = check_python(py) if py else {"ok": False, "error": "not installed"}
    return {**info, "python": str(py or ""), "managed": bool(py and Path(py) == managed_python()),
            "gpu": nvidia_gpu(), "dir": str(ai_dir())}


def _uv() -> Path:
    exe = ai_dir() / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    if exe.is_file():
        return exe
    found = shutil.which("uv")
    if found:
        return Path(found)
    if os.name != "nt":
        raise PlaylistKitError("Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh")
    exe.parent.mkdir(parents=True, exist_ok=True)
    archive = exe.parent / "uv.zip"
    log("Downloading uv (the package installer, about 20 MB)...")
    expected = urllib.request.urlopen(UV_URL + ".sha256", timeout=30).read().decode().split()[0].lower()
    digest = hashlib.sha256()
    with urllib.request.urlopen(UV_URL, timeout=60) as resp, open(archive, "wb") as out:
        while chunk := resp.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected:
        archive.unlink(missing_ok=True)
        raise PlaylistKitError("The uv download does not match its SHA-256 checksum; discarded for safety.")
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if Path(name).name in ("uv.exe", "uvx.exe"):
                (exe.parent / Path(name).name).write_bytes(zf.read(name))
    archive.unlink(missing_ok=True)
    if not exe.is_file():
        raise PlaylistKitError("uv.exe was not found in the download.")
    return exe


def install(on_line=log) -> dict:
    """Create %LOCALAPPDATA%\\PlaylistKit\\ai\\venv with torch + demucs. Takes 5-15 minutes (2.5 GB)."""
    uv = _uv()
    venv = ai_dir() / "venv"
    env = tool_env()
    env["UV_PYTHON_INSTALL_DIR"] = str(ai_dir() / "python")
    env["UV_CACHE_DIR"] = str(ai_dir() / "cache")
    gpu = nvidia_gpu()
    on_line(f"GPU: {gpu or 'none found, installing the CPU build (remixing will be much slower)'}")
    if not managed_python().is_file():
        on_line("Creating a private Python 3.12 ...")
        run([uv, "venv", "--python", "3.12", str(venv)], env=env, on_line=on_line)
    py = str(managed_python())
    on_line("Installing PyTorch (about 2.5 GB with CUDA) ...")
    run([uv, "pip", "install", "--python", py, *TORCH_CUDA, "--index-url", TORCH_INDEX_CUDA if gpu else TORCH_INDEX_CPU],
        env=env, on_line=on_line)
    on_line("Installing Demucs, librosa and the other engine packages ...")
    run([uv, "pip", "install", "--python", py, *ENGINE_PACKAGES, *TORCH_CUDA,
         "--extra-index-url", TORCH_INDEX_CUDA if gpu else TORCH_INDEX_CPU, "--index-strategy", "unsafe-best-match"],
        env=env, on_line=on_line)
    res = check_python(py)
    if not res["ok"]:
        raise PlaylistKitError(f"The AI runtime was installed but does not start: {res['error']}")
    on_line(f"AI runtime ready: torch {res['torch']}, CUDA {'yes' if res['cuda'] else 'no'}")
    return res


def engine_cmd(python: Path, songs: Path, work: Path, out: Path, slug: str, style: str, opts: dict) -> list[str]:
    cmd = [str(python), "-u", str(ENGINE), str(songs), "--styles", style, "--work", str(work), "--out", str(out),
           "--slug", slug, "--device", opts.get("device") or "cuda"]
    if not opts.get("keyshift", True):
        cmd.append("--no-keyshift")
    if opts.get("max_stretch") is not None:
        cmd += ["--max-stretch", str(opts["max_stretch"])]
    if opts.get("reorder", True):
        cmd.append("--reorder")
    if opts.get("transition"):
        cmd += ["--transition", str(opts["transition"])]
    if not opts.get("low_priority", True):
        cmd.append("--normal-priority")
    return cmd


def run_engine(python: Path, songs: Path, work: Path, out: Path, slug: str, style: str, opts: dict,
               on_line=log) -> None:
    if not ENGINE.is_file():
        raise PlaylistKitError(f"Remix engine missing: {ENGINE}")
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    run(engine_cmd(python, songs, work, out, slug, style, opts), env=tool_env(), on_line=on_line)


if __name__ == "__main__":  # python -m playlistkit.runtime  -> install
    sys.exit(0 if install().get("ok") else 1)
