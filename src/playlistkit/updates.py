"""Find newer PlaylistKit releases on GitHub and install them.

* The app checks https://api.github.com/repos/<repo>/releases/latest at most once a
  day (no account, nothing about the user is sent) and caches the answer.
* Installer builds can update in one click: the new PlaylistKit-Setup-*.exe is
  downloaded, checked against the release's SHA256SUMS.txt, run silently, and the
  installer reopens the app when it is done (see installer/playlistkit.iss).
* Portable and pip installs are told where to get the new version instead.

PLAYLISTKIT_REPO (owner/name) and PLAYLISTKIT_UPDATE_URL (a URL returning a release JSON)
override where releases are read from, for forks and for testing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playlistkit import __version__
from playlistkit.util import PlaylistKitError, app_home, read_json, write_json

REPO = os.environ.get("PLAYLISTKIT_REPO", "hiennv0298/PlaylistKit")
CHECK_EVERY = 3600  # a cached answer is reused for an hour (app restarts do not hit GitHub again)
RECHECK_EVERY = 6 * 3600  # while the app stays open
STATE_FILE = "update-check.json"
_lock = threading.Lock()
PROGRESS = {"phase": "idle", "progress": 0.0, "error": ""}  # idle | downloading | verifying | restarting | error


def parse_version(text: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d+", str(text).lstrip("vV").split("-")[0].split("+")[0])[:3]]
    return tuple(nums + [0] * (3 - len(nums)))  # type: ignore[return-value]


def install_mode() -> str:
    """installer | portable | python (pip, pipx, install.ps1, run.cmd)."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        return "installer" if any(exe_dir.glob("unins*.exe")) else "portable"
    return "python"


def _load() -> dict:
    try:
        data = read_json(app_home() / STATE_FILE)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    try:
        write_json(app_home() / STATE_FILE, data)
    except OSError:
        pass


def _get(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": f"PlaylistKit/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - https GitHub URLs or the test override


def _release_url(tag: str | None = None) -> str:
    if tag is None and os.environ.get("PLAYLISTKIT_UPDATE_URL"):
        return os.environ["PLAYLISTKIT_UPDATE_URL"]
    base = f"https://api.github.com/repos/{REPO}/releases"
    return f"{base}/tags/{tag}" if tag else f"{base}/latest"


def _release_info(rel: dict) -> dict:
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in rel.get("assets") or []}
    installer = next((n for n in assets if n.startswith("PlaylistKit-Setup-") and n.endswith(".exe")), "")
    return {"latest": str(rel.get("tag_name") or "").lstrip("vV"), "notes": rel.get("body") or "",
            "page": rel.get("html_url") or f"https://github.com/{REPO}/releases/latest",
            "installer": installer, "installer_url": assets.get(installer, ""),
            "sums_url": assets.get("SHA256SUMS.txt", "")}


def check(force: bool = False) -> dict:
    """Ask GitHub for the latest release (cached for a day unless forced)."""
    with _lock:
        state = _load()
        now = time.time()
        # an answer older than the running version came from an older install: never trust it
        fresh = (state.get("latest") and parse_version(state["latest"]) >= parse_version(__version__)
                 and now - float(state.get("checked_at") or 0) < CHECK_EVERY)
        if force or not fresh:
            try:
                with _get(_release_url()) as resp:
                    rel = json.loads(resp.read().decode("utf-8"))
                state.update(_release_info(rel), error="")
            except (OSError, ValueError) as exc:
                state["error"] = f"Could not check for updates: {exc}"
            state["checked_at"] = now
        _note_whats_new(state)  # also right after an update, when the cached answer is still fresh
        _save(state)
        return state


def _note_whats_new(state: dict) -> None:
    """After an update, keep the notes of the version now running for the What's new window."""
    seen = state.get("seen_version")
    if not seen:
        state["seen_version"] = __version__  # first run ever: nothing to announce
        return
    if seen == __version__ or (state.get("whats_new") or {}).get("version") == __version__:
        return
    notes = state.get("notes", "") if state.get("latest") == __version__ else ""
    if not notes:
        try:
            with _get(_release_url(f"v{__version__}")) as resp:
                notes = json.loads(resp.read().decode("utf-8")).get("body") or ""
        except (OSError, ValueError):
            notes = ""
    state["whats_new"] = {"version": __version__, "notes": notes}


def mark_seen() -> None:
    with _lock:
        state = _load()
        state["seen_version"] = __version__
        state.pop("whats_new", None)
        _save(state)


def status() -> dict:
    state = _load()
    latest = state.get("latest", "")
    newer = bool(latest) and parse_version(latest) > parse_version(__version__)
    mode = install_mode()
    whats_new = state.get("whats_new") if state.get("seen_version") != __version__ else None
    return {"current": __version__, "latest": latest, "newer": newer, "notes": state.get("notes", ""),
            "page": state.get("page") or f"https://github.com/{REPO}/releases/latest", "mode": mode,
            "can_install": newer and mode == "installer" and bool(state.get("installer_url") and state.get("sums_url")),
            "checked_at": state.get("checked_at", 0), "error": state.get("error", ""),
            "whats_new": whats_new, "progress": dict(PROGRESS),
            "repo": REPO}


def _expected_hash(sums_url: str, name: str) -> str:
    with _get(sums_url) as resp:
        for line in resp.read().decode("utf-8", "replace").splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].lstrip("*") == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                return parts[0].lower()
    raise PlaylistKitError(f"SHA256SUMS.txt has no entry for {name}.")


def download_and_install(on_launched, before_launch=lambda: None) -> None:
    """Download the new installer, verify it, call before_launch(), start it silently, then call on_launched().
    The installer may force close this process at once, so anything to save goes in before_launch."""
    state = _load()
    st = status()
    if not st["can_install"]:
        raise PlaylistKitError("This copy of PlaylistKit cannot update itself. Download the new version from the Releases page.")
    name = state["installer"]
    folder = app_home() / "updates"
    folder.mkdir(exist_ok=True)
    for old in folder.glob("*"):
        try:
            old.unlink()
        except OSError:
            pass
    dest = folder / name
    PROGRESS.update(phase="downloading", progress=0.0, error="")
    try:
        expected = _expected_hash(state["sums_url"], name)
        digest = hashlib.sha256()
        tmp = dest.with_suffix(".part")
        with _get(state["installer_url"], timeout=60) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total:
                    PROGRESS["progress"] = round(done * 100 / total, 1)
        PROGRESS.update(phase="verifying", progress=100.0)
        if digest.hexdigest() != expected:
            tmp.unlink(missing_ok=True)
            raise PlaylistKitError("The downloaded installer does not match its published SHA-256 fingerprint, "
                               "so it was deleted. Try again later or download it from the Releases page.")
        tmp.replace(dest)
        before_launch()
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([str(dest), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                          "/RELAUNCH=1"], creationflags=flags, close_fds=True)
        PROGRESS.update(phase="restarting")
    except PlaylistKitError as exc:
        PROGRESS.update(phase="error", error=str(exc))
        raise
    except OSError as exc:
        PROGRESS.update(phase="error", error=f"Update failed: {exc}")
        raise PlaylistKitError(f"Update failed: {exc}") from exc
    on_launched()


def start_background_check(enabled=lambda: True) -> None:
    """Check now, then again every few hours while the app is open (when enabled() still says so)."""
    def loop() -> None:
        while True:
            if enabled():
                check()
            time.sleep(RECHECK_EVERY)

    threading.Thread(target=loop, daemon=True).start()
