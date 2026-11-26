"""PlaylistKit desktop app: a small local web server plus an app window.

The page (webui/index.html) talks to this server over a JSON API bound to
127.0.0.1. One job (search, download, check, remix, video, cut, AI install)
runs at a time on a background thread; the page polls /api/state. The window
is Edge or Chrome in app mode (no address bar), else the default browser.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playlistkit import __version__, genres, updates
from playlistkit import project as projects
from playlistkit.backlog import Backlog
from playlistkit.genres import GENRES, STYLES
from playlistkit.util import (IMAGE_EXT, Cancelled, PlaylistKitError, add_log_sink, app_home, default_projects_dir,
                              log, read_json, recycle, request_cancel, reset_cancel, write_json)

WEBUI = Path(__file__).with_name("webui")
SETTINGS_FILE = "settings.json"
SERVER_FILE = "app-server.json"
DEFAULTS = {"projects_dir": str(default_projects_dir()), "backlog_path": "", "banned_artists": "",
            "jamendo_client_id": "", "ai_python": "", "device": "cuda", "low_priority": True,
            "check_updates": True, "sources": "soundcloud,audius,jamendo,archive,ccmixter", "count": 30,
            "allow_used_artists": False, "video_res": "720p"}
SERVER: ThreadingHTTPServer | None = None
IDLE_EXIT = 150
MEDIA_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg",
               ".opus": "audio/ogg", ".webm": "audio/webm", ".flac": "audio/flac", ".aac": "audio/aac",
               ".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"}
REMIX_STEPS = {"1)": (0, 12), "2)": (12, 1), "3)": (13, 50), "4)": (63, 24), "5)": (87, 13)}


# ---------------------------------------------------------------- settings

def load_settings() -> dict:
    settings = dict(DEFAULTS)
    saved = read_json(app_home() / SETTINGS_FILE, {})
    for k, v in (saved.items() if isinstance(saved, dict) else []):
        if k not in DEFAULTS:
            continue
        d = DEFAULTS[k]
        if isinstance(d, bool):
            ok = isinstance(v, bool)
        elif isinstance(d, (int, float)):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        else:
            ok = isinstance(v, str)
        if ok:
            settings[k] = v
    if not settings["projects_dir"]:
        settings["projects_dir"] = DEFAULTS["projects_dir"]
    return settings


def save_settings(new: dict) -> dict:
    settings = load_settings()
    for k, d in DEFAULTS.items():
        if k not in new:
            continue
        v = new[k]
        if isinstance(d, bool):
            v = bool(v)
        elif isinstance(d, int):
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                raise PlaylistKitError(f"'{k}' must be a number.") from None
        else:
            v = str(v).strip().strip('"')
        settings[k] = v
    write_json(app_home() / SETTINGS_FILE, settings)
    return settings


def root() -> Path:
    p = Path(load_settings()["projects_dir"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def backlog() -> Backlog:
    s = load_settings()
    return Backlog(Path(s["backlog_path"]) if s["backlog_path"] else root() / "backlog.tsv")


def banned() -> list[str]:
    return [a.strip() for a in re.split(r"[,;\n]", load_settings()["banned_artists"]) if a.strip()]


def get_project(pid: str) -> projects.Project:
    return projects.load(root(), pid)


# ---------------------------------------------------------------- job state

class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.busy = False
        self.phase = "idle"
        self.label = ""
        self.progress = 0.0
        self.status = "Ready."
        self.error = ""
        self.project = ""
        self.result: dict = {}
        self.log: list[str] = []
        self.last_seen = time.monotonic()
        self.seen = False
        self.bye_at = 0.0

    def touch(self) -> None:
        self.last_seen = time.monotonic()
        self.seen = True

    def on_log(self, line: str) -> None:
        with self.lock:
            self.log = (self.log + [line])[-400:]

    def set(self, frac: float, status: str | None = None) -> None:
        with self.lock:
            self.progress = round(max(0.0, min(1.0, frac)) * 100, 1)
            if status:
                self.status = status

    def snapshot(self) -> dict:
        with self.lock:
            return {"busy": self.busy, "phase": self.phase, "label": self.label, "progress": self.progress,
                    "status": self.status, "error": self.error, "project": self.project, "result": self.result,
                    "log": self.log[-200:]}


STATE = AppState()


def start_job(phase: str, label: str, pid: str, job, *args) -> None:
    with STATE.lock:
        if STATE.busy:
            raise PlaylistKitError("PlaylistKit is already working. Wait for it to finish or press Stop.")
        reset_cancel()
        STATE.busy, STATE.phase, STATE.label, STATE.project = True, phase, label, pid
        STATE.error, STATE.progress, STATE.log, STATE.result, STATE.status = "", 0.0, [], {}, label + "..."

    def guard() -> None:
        try:
            result = job(*args) or {}
            with STATE.lock:
                STATE.phase, STATE.status, STATE.progress, STATE.result = "done", "Done.", 100.0, result
        except Cancelled:
            _finish("stopped", "Stopped.")
        except PlaylistKitError as exc:
            _finish("error", "Something went wrong.", str(exc))
        except Exception:  # noqa: BLE001 - show anything in the app instead of dying silently
            _finish("error", "Something went wrong.", traceback.format_exc())
        finally:
            with STATE.lock:
                STATE.busy = False

    threading.Thread(target=guard, daemon=True).start()


def _finish(phase: str, status: str, error: str = "") -> None:
    if error:
        log("ERROR: " + error)
    with STATE.lock:
        STATE.phase, STATE.status, STATE.error = phase, status, error


def _frac(i: int, n: int) -> None:
    STATE.set(i / n if n else 1.0, f"{i} / {n}")


# ---------------------------------------------------------------- jobs

def job_find(pid: str, sources: list[str], count: int, extra: str, allow_used: bool) -> dict:
    from playlistkit import sources as src

    p = get_project(pid)
    g = GENRES[p.genre]
    log(f"Searching {', '.join(src.SOURCES.get(s, s) for s in sources)} for {count} {g.name} songs")
    steps = {"n": 0}

    def progress(msg: str) -> None:
        log(msg)
        steps["n"] += 1
        STATE.set(min(0.95, steps["n"] / (len(sources) * 6 + 2)), msg)

    cands = src.search(g, sources, count, load_settings(), extra, progress)
    picked = src.pick(cands, g, count, backlog(), banned(), allow_used_artists=allow_used,
                      allow_distributed=bool(extra))
    write_json(p.file("candidates.json"), [c.to_dict() for c in picked])
    n_sel = sum(c.selected for c in picked)
    n_ok = sum(not c.skip for c in picked)
    log(f"Found {len(picked)} songs, {n_ok} pass the filters, {n_sel} selected.")
    return {"selected": n_sel, "found": len(picked)}


def job_download(pid: str) -> dict:
    from playlistkit.download import download_selected
    from playlistkit.screen import screen_project
    from playlistkit.sources import Candidate

    p = get_project(pid)
    cands = [Candidate.from_dict(d) for d in read_json(p.file("candidates.json"), [])]
    if not any(c.selected for c in cands):
        raise PlaylistKitError("Tick at least one song to download.")
    new = download_selected(p, cands, backlog(), progress=lambda i, n: STATE.set(0.85 * i / max(1, n), f"Downloading {i}/{n}"))
    log("Checking the songs ...")
    screen_project(p, progress=lambda i, n: STATE.set(0.85 + 0.15 * i / max(1, n), "Checking"))
    return {"downloaded": len(new)}


def job_screen(pid: str) -> dict:
    from playlistkit.screen import screen_project

    p = get_project(pid)
    log(f"Checking {len(p.song_files())} songs ...")
    res = screen_project(p, progress=_frac)
    return {"checked": len(res)}


def job_remix(pid: str, style: str, opts: dict) -> dict:
    from playlistkit import meta, runtime

    p = get_project(pid)
    files = p.song_files()
    if len(files) < 2:
        raise PlaylistKitError("Add at least 2 songs first.")
    s = load_settings()
    st = runtime.status(s["ai_python"])
    if not st["ok"] and st["found"]:  # installed but the setting does not point at it: set it now
        save_settings({"ai_python": st["found"]["python"]})
        log(f"AI Python set to {st['found']['python']}")
        st = {**st["found"], "ok": True}
    if not st["ok"]:
        if st["state"] == "broken":
            raise PlaylistKitError(f"The AI Python in Settings does not work ({st['error']}). "
                                   "Open Settings and fix it, or press Install AI.")
        raise PlaylistKitError("The AI runtime (PyTorch + Demucs) is not installed yet. "
                               "Open Settings and press Install AI, or set an existing AI Python.")
    py = Path(st["python"])
    p.data["style"] = style
    p.save()
    g = GENRES[p.genre]
    eng = {**g.engine, **opts, "device": s["device"] if st.get("cuda") else "cpu", "low_priority": s["low_priority"]}
    log(f"Remixing {len(files)} songs, style {style}, device {eng['device']}")
    cur = {"base": 0.0, "width": 0.0, "n": 0, "sep_total": 0, "sep_done": 0}

    def on_line(line: str) -> None:
        log(line)
        m = re.search(r"\]\s+(\d\))", line)
        if m and m.group(1) in REMIX_STEPS:
            cur["base"], cur["width"] = REMIX_STEPS[m.group(1)]
            STATE.set(cur["base"] / 100, line.split("] ", 1)[-1].strip())
            return
        m = re.search(r"tach stem (\d+) bai", line)
        if m:
            cur["sep_total"] = int(m.group(1))
        if "Separating track" in line and cur["sep_total"]:
            cur["sep_done"] += 1
            STATE.set((cur["base"] + cur["width"] * (cur["sep_done"] - 1) / cur["sep_total"]) / 100,
                      f"Separating stems {cur['sep_done']}/{cur['sep_total']}")
            return
        m = re.search(r"\[(\d+)/(\d+)\]", line)
        if m:
            i, n = int(m.group(1)), int(m.group(2))
            STATE.set((cur["base"] + cur["width"] * i / n) / 100, f"Matching tempo and key {i}/{n}")

    runtime.run_engine(py, p.songs, p.work, p.out, p.id, style, eng, on_line)
    info = meta.make_for_project(p)
    # the songs of this mix are now used
    from playlistkit.download import song_info

    bl = backlog()
    bl.mark_many(p.id, [(song_info(p, f)["artist"] or "?", song_info(p, f)["title"]) for f in p.song_files()],
                 "used", only_from={"downloaded"})
    return {"title": info["title"], "duration": info["duration"]}


def job_video(pid: str, image: str, audio: str, resolutions: list[str], out_dir: str) -> dict:
    from playlistkit.video import make_video

    if pid:
        p = get_project(pid)
        mix = p.mix()
        audio = audio or str(mix.get("wav") or mix.get("mp3") or "")
        image = image or str(p.data.get("thumb") or "")
        out = p.out
        base = p.id
    else:
        out = Path(out_dir) if out_dir else Path(audio).parent
        base = Path(audio).stem
    made = []
    for i, res in enumerate(resolutions):
        def prog(f: float, i: int = i) -> None:
            STATE.set((i + f) / len(resolutions), f"Encoding {res}  {int(f * 100)}%")
        made.append(str(make_video(Path(image), Path(audio), out / f"{base}_{res}.mp4", res, prog)))
    return {"videos": made}


def job_export(pid: str, edit: dict) -> dict:
    from playlistkit import editor

    p = get_project(pid)
    out = editor.export(p, edit, progress=lambda f: STATE.set(f, f"Exporting {edit['res']}  {int(f * 100)}%"))
    return {"videos": [str(out)]}


def job_cut(pid: str, text: str) -> dict:
    from playlistkit import cut, meta

    p = get_project(pid)
    tracks, duration = cut.current_tracks(p)
    plan = cut.plan_cut(tracks, duration, cut.parse_claims(text))
    STATE.set(0.1, "Cutting the mix")
    res = cut.apply_cut(p, plan, backlog())
    STATE.set(0.9, "Updating the description")
    info = meta.make_for_project(p, name=p.data.get("title_name", ""))
    return {**res, "title": info["title"]}


def job_install_ai() -> dict:
    from playlistkit import runtime

    def on_line(line: str) -> None:
        log(line)
        if line and not line.startswith(" "):
            STATE.set(min(0.95, STATE.progress / 100 + 0.01), line[:120])

    res = runtime.install(on_line)
    save_settings({"ai_python": str(runtime.managed_python())})
    on_line(f"AI Python set to {runtime.managed_python()}")
    return res


# ---------------------------------------------------------------- project detail

def project_detail(pid: str) -> dict:
    from playlistkit.download import song_info

    p = get_project(pid)
    screen = read_json(p.file("screen.json"), {})
    songs = []
    for f in p.song_files():
        info = song_info(p, f)
        sc = screen.get(f.name, {})
        songs.append({"file": f.name, **info, "duration": sc.get("duration", 0), "sub_db": sc.get("sub_db"),
                      "cutoff_khz": sc.get("cutoff_khz"), "flags": sc.get("flags", []),
                      "checked": f.name in screen})
    meta_path = p.out / "youtube_meta.txt"
    mix = p.mix()
    from playlistkit.meta import clean_track_name, read_tracklist
    from playlistkit.util import fmt_ts

    tracks = [{"ts": fmt_ts(t), "name": clean_track_name(n)} for t, n in read_tracklist(mix["tracklist"])] \
        if "tracklist" in mix else []
    outputs = sorted((x.name for x in p.out.iterdir() if x.is_file() and not x.name.startswith("_")),
                     key=str.lower) if p.out.is_dir() else []
    g = GENRES.get(p.genre)
    return {**p.summary(), "candidates": read_json(p.file("candidates.json"), []), "song_list": songs,
            "meta_text": meta_path.read_text(encoding="utf-8") if meta_path.is_file() else "",
            "tracks": tracks, "outputs": outputs, "thumb": p.data.get("thumb", ""),
            "title_name": p.data.get("title_name", ""), "risk_text": genres.RISK_TEXT[g.risk] if g else "",
            "mix": {k: v.name for k, v in mix.items()}}


def remove_song(pid: str, name: str, reason: str) -> dict:
    from playlistkit.download import song_info

    p = get_project(pid)
    f = p.songs / name
    if not f.is_file() or f.resolve().parent != p.songs.resolve():
        raise PlaylistKitError("Song not found.")
    info = song_info(p, f)
    status = {"bad-quality": "bad-quality", "duplicate": "duplicate", "banned": "not-fit"}.get(reason, "not-fit")
    note = {"bad-quality": "low quality", "duplicate": "duplicate"}.get(reason, reason if reason != "not-fit" else "")
    backlog().mark(p.id, info["artist"] or "?", info["title"], status, note)
    if reason == "banned" and info["artist"]:
        backlog().ban_artist(info["artist"], "removed from " + p.id)
    recycle(f)
    screen = read_json(p.file("screen.json"), {})
    screen.pop(name, None)
    write_json(p.file("screen.json"), screen)
    return {"ok": True}


# ---------------------------------------------------------------- dialogs

_dialog_lock = threading.Lock()


def pick(kind: str, initial: str = "") -> str:
    import tkinter as tk
    from tkinter import filedialog

    with _dialog_lock:
        tkroot = tk.Tk()
        tkroot.withdraw()
        tkroot.attributes("-topmost", True)
        try:
            if kind == "folder":
                path = filedialog.askdirectory(parent=tkroot, title="Choose a folder", initialdir=initial or None)
            elif kind == "image":
                path = filedialog.askopenfilename(parent=tkroot, title="Choose the thumbnail",
                                                  filetypes=[("Image", "*.jpg *.jpeg *.png *.webp *.bmp")])
            elif kind == "audio":
                path = filedialog.askopenfilename(parent=tkroot, title="Choose the audio",
                                                  filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.aac *.ogg")])
            elif kind == "media":
                paths = filedialog.askopenfilenames(
                    parent=tkroot, title="Add media to this playlist",
                    filetypes=[("Media", "*.jpg *.jpeg *.png *.webp *.bmp *.wav *.mp3 *.m4a *.flac *.aac *.ogg "
                                         "*.mp4 *.mov *.mkv *.webm"), ("All files", "*.*")])
                return "\n".join(str(Path(x)) for x in paths)
            else:
                path = filedialog.askopenfilename(parent=tkroot, title="Choose a file")
        finally:
            tkroot.destroy()
    return str(Path(path)) if path else ""


def reveal(path: Path) -> None:
    if os.name != "nt":
        webbrowser.open(path.as_uri())
    elif path.is_file():
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        os.startfile(path)  # noqa: S606


# ---------------------------------------------------------------- HTTP

def _demo_script() -> str:
    path = os.environ.get("PLAYLISTKIT_DEMO_JS", "")
    return Path(path).read_text(encoding="utf-8") if path and Path(path).is_file() else ""


class Handler(BaseHTTPRequestHandler):
    server_version = "PlaylistKit"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        pass

    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _serve_file(self, path: Path) -> None:
        size = path.stat().st_size
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        url = urlparse(self.path)
        path, query = unquote(url.path), parse_qs(url.query)
        try:
            if path in ("/", "/index.html"):
                html = (WEBUI / "index.html").read_text(encoding="utf-8")
                if _demo_script():  # PLAYLISTKIT_DEMO_JS: a script that stages screens for the README demo
                    html = html.replace("</body>", '<script src="/__demo.js"></script></body>')
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if path in ("/icon-32.png", "/icon-192.png", "/icon-512.png", "/favicon.ico"):
                return self._serve_file(WEBUI / ("playlistkit.ico" if path == "/favicon.ico" else path[1:]))
            if path == "/editor.js":
                return self._send(200, (WEBUI / "editor.js").read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/edit":
                from playlistkit import editor

                p = get_project(query.get("id", [""])[0])
                e = editor.load_edit(p)
                return self._json({"edit": e, "media": editor.list_media(p),
                                   "titles": [[a, b, n] for a, b, n in editor.song_titles(p, e)],
                                   "mix": [f"out/{f.name}" for k, f in p.mix().items() if k in ("wav", "mp3")]})
            if path == "/api/media":
                from playlistkit import editor

                return self._json(editor.list_media(get_project(query.get("id", [""])[0])))
            if path == "/api/media/peaks":
                from playlistkit import editor

                p = get_project(query.get("id", [""])[0])
                return self._json(editor.peaks(p, query.get("ref", [""])[0]))
            if path == "/api/media/vthumb":
                from playlistkit import editor

                p = get_project(query.get("id", [""])[0])
                return self._serve_file(editor.video_thumb(p, query.get("ref", [""])[0]))
            if path == "/__demo.js" and _demo_script():
                return self._send(200, _demo_script().encode("utf-8"), "text/javascript; charset=utf-8")
            if path == "/api/ping":
                return self._json({"app": "playlistkit", "version": __version__})
            if path == "/api/state":
                STATE.touch()
                return self._json(STATE.snapshot())
            if path == "/api/settings":
                return self._json(load_settings())
            if path == "/api/update":
                return self._json(dict(updates.status(), enabled=load_settings()["check_updates"]))
            if path == "/api/genres":
                from playlistkit.sources import SOURCES

                return self._json({"genres": genres.as_list(), "groups": genres.GROUPS, "styles": list(STYLES),
                                   "sources": SOURCES, "resolutions": ["480p", "720p", "1080p"]})
            if path == "/api/projects":
                return self._json([p.summary() for p in projects.list_all(root())])
            if path == "/api/project":
                return self._json(project_detail(query.get("id", [""])[0]))
            if path == "/api/ai":
                from playlistkit import runtime

                search = query.get("search", ["0"])[0] == "1"
                return self._json(runtime.status(load_settings()["ai_python"], search=search))
            if path == "/api/backlog":
                return self._json(backlog().summary())
            if path.startswith("/files/"):  # /files/<pid>/<area>/<name>  area: song | out | thumb
                _, _, pid, area, name = path.split("/", 4)
                p = get_project(pid)
                base = {"song": p.songs, "out": p.out, "thumb": p.dir, "media": p.dir / "media",
                        "frame": p.work}.get(area)
                if base is None:
                    return self._send(404, b"Not found", "text/plain")
                target = (base / name).resolve()
                if target.parent != base.resolve() or target.suffix.lower() not in MEDIA_TYPES or not target.is_file():
                    return self._send(404, b"Not found", "text/plain")
                return self._serve_file(target)
            if path == "/local":  # an image or audio file the user picked (quick video preview)
                target = Path(query.get("path", [""])[0])
                if target.suffix.lower() not in MEDIA_TYPES or not target.is_file():
                    return self._send(404, b"Not found", "text/plain")
                return self._serve_file(target)
            self._send(404, b"Not found", "text/plain")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except (PlaylistKitError, ValueError, KeyError, FileNotFoundError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception:  # noqa: BLE001
            self._json({"error": traceback.format_exc()}, 500)

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._send(403, b"Forbidden", "text/plain")
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length") or 0)
        if path == "/api/media/upload":  # a file dragged in from Explorer: stream it to disk
            return self._upload(parse_qs(url.query), length)
        raw = self.rfile.read(length) if length else b""
        if path == "/api/bye":
            STATE.bye_at = time.monotonic()
            return self._json({"ok": True})
        if self.headers.get("X-PlaylistKit") != "1":  # other web pages cannot set this header without CORS
            return self._send(403, b"Forbidden", "text/plain")
        try:
            body = json.loads(raw or b"{}")
            self._json(self._post(path, body))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except (PlaylistKitError, ValueError, KeyError, FileNotFoundError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception:  # noqa: BLE001
            self._json({"error": traceback.format_exc()}, 500)

    def _upload(self, query: dict, length: int) -> None:
        from playlistkit import editor

        if self.headers.get("X-PlaylistKit") != "1":
            return self._send(403, b"Forbidden", "text/plain")
        try:
            p = get_project(query.get("id", [""])[0])
            target = editor.unique_media_path(p, unquote(query.get("name", ["file"])[0]))
            tmp = target.with_name(target.name + ".part")
            left = length
            with open(tmp, "wb") as f:
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            if left:
                tmp.unlink(missing_ok=True)
                raise PlaylistKitError("The upload was interrupted.")
            tmp.replace(target)
            self._json({"ref": f"media/{target.name}"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except (PlaylistKitError, ValueError, KeyError) as exc:
            self._json({"error": str(exc)}, 400)

    def _post(self, path: str, body: dict) -> dict:
        pid = str(body.get("id") or "")
        if path == "/api/settings":
            return save_settings(body)
        if path == "/api/project/create":
            p = projects.create(root(), body.get("genre") or "indie", str(body.get("name") or "").strip(),
                                str(body.get("songs_dir") or "").strip().strip('"'), str(body.get("pid") or ""))
            return p.summary()
        if path == "/api/project/update":
            p = get_project(pid)
            if body.get("genre") in GENRES:
                p.data["genre"] = body["genre"]
            if body.get("style") in STYLES:
                p.data["style"] = body["style"]
            if "name" in body:
                p.data["name"] = str(body["name"]).strip() or p.id
            p.save()
            return p.summary()
        if path == "/api/project/delete":
            p = get_project(pid)
            recycle(p.dir)
            return {"ok": True}
        if path == "/api/find":
            s = save_settings({"count": body.get("count", 30), "sources": ",".join(body.get("sources") or []),
                               "allow_used_artists": bool(body.get("allow_used_artists"))})
            sources = [x for x in s["sources"].split(",") if x]
            if not sources and not body.get("extra"):
                raise PlaylistKitError("Pick at least one source.")
            get_project(pid)
            start_job("finding", "Searching for songs", pid, job_find, pid, sources, s["count"],
                      str(body.get("extra") or ""), s["allow_used_artists"])
            return {"ok": True}
        if path == "/api/candidates":
            p = get_project(pid)
            sel = set(body.get("selected") or [])
            cands = read_json(p.file("candidates.json"), [])
            for c in cands:
                c["selected"] = f"{c['source']}:{c['sid']}" in sel
            write_json(p.file("candidates.json"), cands)
            return {"selected": len(sel)}
        if path == "/api/download":
            get_project(pid)
            start_job("downloading", "Downloading songs", pid, job_download, pid)
            return {"ok": True}
        if path == "/api/screen":
            get_project(pid)
            start_job("checking", "Checking songs", pid, job_screen, pid)
            return {"ok": True}
        if path == "/api/song/remove":
            return remove_song(pid, str(body.get("file") or ""), str(body.get("reason") or "not-fit"))
        if path == "/api/remix":
            style = body.get("style") or get_project(pid).style
            if style not in STYLES:
                raise PlaylistKitError("Unknown style.")
            opts = {k: body[k] for k in ("keyshift", "max_stretch", "reorder", "transition") if k in body}
            start_job("remixing", "Remixing", pid, job_remix, pid, style, opts)
            return {"ok": True}
        if path == "/api/meta":
            from playlistkit import meta

            p = get_project(pid)
            tracks = None
            if body.get("tracks"):
                from playlistkit.util import parse_ts

                tracks = [(parse_ts(t["ts"]), str(t["name"]).strip()) for t in body["tracks"] if str(t.get("name", "")).strip()]
            info = meta.make_for_project(p, str(body.get("name") or ""), tracks)
            return {"text": (p.out / "youtube_meta.txt").read_text(encoding="utf-8"), **info}
        if path == "/api/thumb":
            p = get_project(pid)
            src = Path(str(body.get("path") or ""))
            if src.suffix.lower() not in IMAGE_EXT or not src.is_file():
                raise PlaylistKitError("Choose a JPG, PNG or WebP image.")
            for old in p.dir.glob("thumb.*"):
                old.unlink(missing_ok=True)
            dest = p.dir / f"thumb{src.suffix.lower()}"
            shutil.copy2(src, dest)
            p.data["thumb"] = str(dest)
            p.save()
            return {"thumb": dest.name}
        if path == "/api/video":
            res = [r for r in body.get("resolutions") or [] if r in ("480p", "720p", "1080p")]
            if not res:
                raise PlaylistKitError("Pick at least one resolution.")
            image, audio = str(body.get("image") or ""), str(body.get("audio") or "")
            if not pid and not (image and audio):
                raise PlaylistKitError("Choose an image and an audio file.")
            if pid and not get_project(pid).data.get("thumb") and not image:
                raise PlaylistKitError("Choose a thumbnail first.")
            save_settings({"video_res": res[0]})
            start_job("video", "Making the video", pid, job_video, pid, image, audio, res, str(body.get("out_dir") or ""))
            return {"ok": True}
        if path == "/api/cut/preview":
            from playlistkit import cut

            p = get_project(pid)
            tracks, duration = cut.current_tracks(p)
            return cut.plan_cut(tracks, duration, cut.parse_claims(str(body.get("text") or ""))).to_dict()
        if path == "/api/cut/apply":
            get_project(pid)
            start_job("cutting", "Cutting claimed songs", pid, job_cut, pid, str(body.get("text") or ""))
            return {"ok": True}
        if path == "/api/ai/install":
            start_job("installing", "Installing the AI runtime", "", job_install_ai)
            return {"ok": True}
        if path == "/api/ai/check":
            from playlistkit import runtime

            return runtime.status(str(body.get("python") or load_settings()["ai_python"]), search=bool(body.get("search")))
        if path == "/api/ai/use":  # point the AI Python setting at a working install
            from playlistkit import runtime

            py = str(body.get("python") or "").strip().strip('"')
            res = runtime.check_python(py) if py else {"ok": False, "error": "no python given"}
            if not res["ok"]:
                raise PlaylistKitError(f"That Python cannot run the remix: {res['error']}")
            save_settings({"ai_python": py})
            return runtime.status(py)
        if path == "/api/stop":
            request_cancel()
            with STATE.lock:
                if STATE.busy:
                    STATE.status = "Stopping..."
            return {"ok": True}
        if path == "/api/update/check":
            updates.check(force=True)
            return dict(updates.status(), enabled=load_settings()["check_updates"])
        if path == "/api/update/seen":
            updates.mark_seen()
            return {"ok": True}
        if path == "/api/update/install":
            if STATE.busy:
                raise PlaylistKitError("Wait until PlaylistKit has finished its current job, then update.")
            if updates.PROGRESS["phase"] not in ("downloading", "verifying", "restarting"):
                threading.Thread(target=_install_update, daemon=True).start()
            return {"ok": True}
        if path == "/api/pick":
            return {"path": pick(str(body.get("kind") or "file"), str(root()))}
        if path == "/api/open":
            if pid:
                p = get_project(pid)
                area = {"song": p.songs, "out": p.out}.get(str(body.get("area") or ""), p.dir)
                target = area / str(body["file"]) if body.get("file") else area
                if not target.exists():
                    target = area if area.exists() else p.dir
            elif body.get("path"):
                target = Path(str(body["path"]))
            else:
                target = root()
            reveal(target)
            return {"ok": True}
        if path == "/api/edit/save":
            from playlistkit import editor

            return {"edit": editor.save_edit(get_project(pid), body.get("edit") or {})}
        if path == "/api/edit/reset":
            from playlistkit import editor

            p = get_project(pid)
            p.file("edit.json").unlink(missing_ok=True)
            return {"edit": editor.load_edit(p)}
        if path == "/api/edit/frame":
            from playlistkit import editor

            p = get_project(pid)
            editor.preview_frame(p, editor.clean_edit(p, body.get("edit") or {}), float(body.get("at") or 0))
            return {"url": f"/files/{p.id}/frame/frame-preview.png?t={time.time():.0f}"}
        if path == "/api/edit/export":
            from playlistkit import editor

            p = get_project(pid)
            e = editor.save_edit(p, body.get("edit") or {})
            start_job("video", "Exporting the video", pid, job_export, pid, e)
            return {"ok": True}
        if path == "/api/media/import":
            from playlistkit import editor

            p = get_project(pid)
            picked = [x for x in pick("media").split("\n") if x]
            return {"refs": [editor.import_file(p, Path(x)) for x in picked]}
        if path == "/api/media/delete":
            from playlistkit import editor

            p = get_project(pid)
            ref = str(body.get("ref") or "")
            if not ref.startswith("media/"):
                raise PlaylistKitError("Only files you added yourself can be removed here.")
            recycle(editor.resolve(p, ref))
            return {"ok": True}
        if path == "/api/link":
            url = str(body.get("url") or "")
            if url.startswith("https://"):
                webbrowser.open(url)
            return {"ok": True}
        raise PlaylistKitError("Unknown action.")


# ---------------------------------------------------------------- window and lifecycle

def _install_update() -> None:
    def quit_soon() -> None:
        if SERVER:
            threading.Timer(2.5, SERVER.shutdown).start()

    try:
        updates.download_and_install(quit_soon)
    except PlaylistKitError:
        pass  # the error is in updates.PROGRESS for the page to show


def _browser() -> str | None:
    candidates = []
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                           Path(base) / "Google/Chrome/Application/chrome.exe"]
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("google-chrome")


def open_window(url: str) -> None:
    exe = _browser()
    if exe:
        extra = os.environ.get("PLAYLISTKIT_BROWSER_ARGS", "").split()
        subprocess.Popen([exe, f"--app={url}", "--window-size=1300,920", *extra])
        from playlistkit.winapp import tag_window_later

        tag_window_later()  # own taskbar button instead of being grouped with other Edge app windows
    else:
        webbrowser.open(url)


def _running_instance() -> str | None:
    try:
        port = int(read_json(app_home() / SERVER_FILE)["port"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as resp:
            if json.loads(resp.read()).get("app") == "playlistkit":
                return f"http://127.0.0.1:{port}/"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _watchdog(server: ThreadingHTTPServer) -> None:
    while True:
        time.sleep(1)
        if STATE.busy or not STATE.seen:
            continue
        now = time.monotonic()
        closed = STATE.bye_at and STATE.bye_at > STATE.last_seen and now - STATE.bye_at > 5
        if closed or now - STATE.last_seen > IDLE_EXIT:
            server.shutdown()
            return


def _ensure_streams() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    stream = open(app_home() / "playlistkit-app.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream


def main() -> int:
    global SERVER
    _ensure_streams()
    existing = _running_instance()
    if existing:
        open_window(existing)
        return 0
    port = int(os.environ.get("PLAYLISTKIT_GUI_PORT") or 0)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    SERVER = server
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        write_json(app_home() / SERVER_FILE, {"port": server.server_address[1], "pid": os.getpid()})
    except OSError:
        pass
    add_log_sink(STATE.on_log)
    threading.Thread(target=_watchdog, args=(server,), daemon=True).start()
    if load_settings()["check_updates"]:
        updates.start_background_check()
    if not os.environ.get("PLAYLISTKIT_GUI_NO_WINDOW"):
        open_window(url)
    print(f"PlaylistKit is running at {url}  (close the app window to quit)", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        request_cancel()
        server.server_close()
        try:
            (app_home() / SERVER_FILE).unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
