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


HAS_PACKAGES = ("import importlib.util as u; "
                "print('found' if all(u.find_spec(m) for m in ('torch', 'demucs')) else 'missing')")


def _same(a: str | Path, b: str | Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def candidates() -> list[Path]:
    """Pythons on this PC that might hold torch + demucs: our own install first, then PATH, the py launcher,
    python.org installs, conda/miniforge and the active venv."""
    seen: set[str] = set()
    out: list[Path] = []

    def add(p) -> None:
        if not p:
            return
        p = Path(p)
        try:
            key = str(p.resolve()).lower()
        except OSError:
            return
        if key in seen or "windowsapps" in key or not p.is_file():  # skip the Microsoft Store stub
            return
        seen.add(key)
        out.append(p)

    exe = "python.exe" if os.name == "nt" else "python"
    scripts = "Scripts" if os.name == "nt" else "bin"
    add(managed_python())
    for var in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        if os.environ.get(var):
            add(Path(os.environ[var]) / scripts / exe)
            add(Path(os.environ[var]) / exe)
    for name in ("python", "python3"):
        add(shutil.which(name))
    if os.name == "nt":
        try:
            proc = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
            for m in re.finditer(r"([A-Za-z]:\\[^\r\n*]*?python\.exe)", proc.stdout):
                add(m.group(1).strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        for p in sorted(local.glob("Programs/Python/Python3*/python.exe"), reverse=True):
            add(p)
    for base in (Path.home(), Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))):
        for conda in ("miniforge3", "miniconda3", "anaconda3", "mambaforge"):
            for p in sorted((base / conda / "envs").glob(f"*/{exe}")):
                add(p)
            add(base / conda / exe)
    return out


def has_packages(py: str | Path) -> bool:
    """Fast pre-check (no torch import): are torch and demucs installed in this Python?"""
    try:
        proc = subprocess.run([str(py), "-c", HAS_PACKAGES], capture_output=True, text=True, timeout=20,
                              creationflags=NO_WINDOW, env=tool_env())
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "found" in proc.stdout


def detect(search: bool = True, skip: str = "") -> dict | None:
    """The first working AI Python on this PC: {'python', 'torch', 'cuda', 'managed'} or None.
    search=False only looks at PlaylistKit's own install (fast)."""
    pool = candidates() if search else [managed_python()]
    for py in pool:
        if (skip and _same(py, skip)) or not py.is_file():
            continue
        if search and not has_packages(py):
            continue
        res = check_python(py)
        if res["ok"]:
            return {"python": str(py), "torch": res["torch"], "cuda": res["cuda"],
                    "managed": _same(py, managed_python())}
    return None


def status(setting: str = "", search: bool = False) -> dict:
    """Where the AI runtime stands. state:
    ready     - the AI Python setting points at a working Python
    found     - a working install exists but the setting does not point at it (offer to set it)
    broken    - the setting points at a Python that does not work, and nothing else was found
    missing   - nothing set, nothing installed
    """
    base = {"ok": False, "setting": setting, "gpu": nvidia_gpu(), "dir": str(ai_dir()),
            "managed_path": str(managed_python()), "searched": search, "found": None, "error": ""}
    if setting:
        info = check_python(setting)
        if info["ok"]:
            return {**base, **info, "state": "ready", "python": setting, "managed": _same(setting, managed_python())}
        base["error"] = info["error"]
    found = detect(search, skip=setting)
    if found:
        return {**base, "state": "found", "found": found}
    if setting:
        return {**base, "state": "broken"}
    return {**base, "state": "missing", "error": "not installed"}


def find_python(setting: str = "") -> Path | None:
    """The Python the remix should use: the setting when it works, else a found install."""
    st = status(setting)
    if st["ok"]:
        return Path(st["python"])
    return Path(st["found"]["python"]) if st["found"] else None


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
    # DJ settings (see DJ_KEYS in gui.py); a missing one keeps the style's own sound
    if opts.get("order") in ("smart", "keep", "files"):
        cmd += ["--order", opts["order"]]
    if opts.get("transition_type") in ("beat", "fade", "echo"):
        cmd += ["--transition-type", opts["transition_type"]]
    for key, flag in (("speed", "--speed"), ("reverb", "--reverb"), ("duck", "--duck"), ("lufs", "--lufs"),
                      ("gain_drums", "--gain-drums"), ("gain_bass", "--gain-bass"),
                      ("gain_other", "--gain-other"), ("gain_vocals", "--gain-vocals")):
        if opts.get(key) is not None:
            cmd += [flag, str(float(opts[key]))]
    if opts.get("lofi") is not None:
        cmd += ["--lofi", "on" if opts["lofi"] else "off"]
    if opts.get("demo"):
        cmd += ["--demo", str(int(opts["demo"]))]
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
