"""The video editor: a media library, a simple timeline and the FFmpeg export.

A project's edit lives in <project>/edit.json:

    {"res": "720p",
     "video":   [{"id", "media": "<area>/<name>", "start", "in", "dur", "fit": "blur|fill|fit", "zoom": false}],
     "overlay": [{"id", "kind": "text|nowplaying|wave|progress", "start", "dur",
                  "text", "pos": "bottom-left|...", "size": 4.0, "color": "#ffffff", "box": true}],
     "audio":   [{"id", "media", "start", "in", "dur", "volume": 1.0, "fade_in": 0, "fade_out": 0}]}

Times are seconds. "media" is "<area>/<file name>": area out (the mixes and videos),
thumb (the project's thumbnail) or media (files you imported or dragged in).
The page previews the edit with HTML and audio elements; export builds one
FFmpeg filter graph that draws exactly these layers.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from playlistkit.deps import find_ffmpeg, nvenc_available
from playlistkit.project import Project
from playlistkit.util import (AUDIO_EXT, IMAGE_EXT, NO_WINDOW, Cancelled, PlaylistKitError, cancelled, fmt_ts, log,
                              read_json, safe_filename, write_json)

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
RESOLUTIONS = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080)}
POSITIONS = ("top-left", "top", "top-right", "center", "bottom-left", "bottom", "bottom-right")
OVERLAYS = ("text", "nowplaying", "wave", "progress")
FONT_DIRS = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"),
             Path("/Library/Fonts")]
FONT_NAMES = ["segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "Arial.ttf"]


# ---------------------------------------------------------------- media library

def media_dir(p: Project) -> Path:
    return p.dir / "media"


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    return "audio" if ext in AUDIO_EXT else "image" if ext in IMAGE_EXT else "video" if ext in VIDEO_EXT else ""


def area_dir(p: Project, area: str) -> Path:
    try:
        return {"out": p.out, "thumb": p.dir, "media": media_dir(p)}[area]
    except KeyError:
        raise PlaylistKitError("Unknown media area.") from None


def resolve(p: Project, ref: str) -> Path:
    """'media/song.wav' -> the file, refusing anything outside the project's media areas."""
    area, _, name = str(ref).partition("/")
    base = area_dir(p, area).resolve()
    target = (base / name).resolve()
    if target.parent != base or not target.is_file() or not kind_of(target):
        raise PlaylistKitError(f"Media not found: {ref}")
    if area == "thumb" and not target.name.startswith("thumb."):
        raise PlaylistKitError(f"Media not found: {ref}")
    return target


def _probe(path: Path) -> dict:
    ff = find_ffmpeg()
    out = subprocess.run([str(ff.ffprobe), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams",
                          str(path)], capture_output=True, text=True, encoding="utf-8", creationflags=NO_WINDOW).stdout
    data = json.loads(out or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    dur = float((data.get("format") or {}).get("duration") or 0)
    return {"dur": dur, "w": int(v.get("width") or 0), "h": int(v.get("height") or 0), "audio": bool(a)}


def list_media(p: Project) -> list[dict]:
    cache_path = p.work / "media-info.json"
    cache = read_json(cache_path, {})
    items = []
    sources = [("out", f) for f in sorted(p.out.glob("*")) if p.out.is_dir()]
    sources += [("thumb", f) for f in sorted(p.dir.glob("thumb.*"))]
    sources += [("media", f) for f in sorted(media_dir(p).glob("*")) if media_dir(p).is_dir()]
    changed = False
    for area, f in sources:
        k = kind_of(f)
        if not f.is_file() or not k or f.name.startswith(("_", ".")) or ".part" in f.name:
            continue
        ref = f"{area}/{f.name}"
        sig = f"{f.stat().st_size}:{int(f.stat().st_mtime)}"
        info = cache.get(ref)
        if not info or info.get("sig") != sig:
            try:
                info = {**_probe(f), "sig": sig}
            except Exception:  # noqa: BLE001
                info = {"dur": 0, "w": 0, "h": 0, "audio": False, "sig": sig}
            cache[ref] = info
            changed = True
        items.append({"ref": ref, "area": area, "name": f.name, "kind": k, "dur": round(info["dur"], 3),
                      "w": info["w"], "h": info["h"], "size": f.stat().st_size})
    if changed:
        write_json(cache_path, cache)
    order = {"thumb": 0, "out": 1, "media": 2}
    items.sort(key=lambda m: (order[m["area"]], {"image": 0, "audio": 1, "video": 2}[m["kind"]], m["name"].lower()))
    return items


def unique_media_path(p: Project, name: str) -> Path:
    folder = media_dir(p)
    folder.mkdir(parents=True, exist_ok=True)
    clean = safe_filename(Path(name).name)
    if not kind_of(Path(clean)):
        raise PlaylistKitError("Only images, audio and video files can be added.")
    target = folder / clean
    n = 2
    while target.exists():
        target = folder / f"{Path(clean).stem} ({n}){Path(clean).suffix}"
        n += 1
    return target


def import_file(p: Project, src: Path) -> str:
    target = unique_media_path(p, src.name)
    shutil.copy2(src, target)
    return f"media/{target.name}"


def video_thumb(p: Project, ref: str) -> Path:
    src = resolve(p, ref)
    folder = p.work / "media-thumbs"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / (re.sub(r"[^\w.-]+", "_", ref) + ".jpg")
    if not out.is_file() or out.stat().st_mtime < src.stat().st_mtime:
        ff = find_ffmpeg()
        dur = _probe(src)["dur"]
        subprocess.run([str(ff.ffmpeg), "-v", "error", "-y", "-ss", f"{min(1.0, dur / 3):.2f}", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=320:-2", str(out)], capture_output=True, creationflags=NO_WINDOW)
    if not out.is_file():
        raise PlaylistKitError("Could not make a thumbnail.")
    return out


def peaks(p: Project, ref: str, per_sec: int = 10) -> list[float]:
    """Waveform peaks (0-1), per_sec values per second, cached in work/."""
    src = resolve(p, ref)
    folder = p.work / "peaks"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / (re.sub(r"[^\w.-]+", "_", ref) + f".{per_sec}.json")
    sig = f"{src.stat().st_size}:{int(src.stat().st_mtime)}"
    cached = read_json(out, {})
    if cached.get("sig") == sig:
        return cached["peaks"]
    import numpy as np

    sr = 4000
    ff = find_ffmpeg()
    raw = subprocess.run([str(ff.ffmpeg), "-v", "quiet", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True, creationflags=NO_WINDOW).stdout
    y = np.abs(np.frombuffer(raw, np.int16).astype(np.float32)) / 32768.0
    step = sr // per_sec
    n = len(y) // step
    vals = y[: n * step].reshape(n, step).max(axis=1) if n else np.zeros(0)
    top = float(np.percentile(vals, 99)) if n else 1.0
    result = [round(float(min(1.0, v / (top or 1.0))), 3) for v in vals]
    write_json(out, {"sig": sig, "peaks": result})
    return result


# ---------------------------------------------------------------- the edit

def _id() -> str:
    return uuid.uuid4().hex[:8]


def default_edit(p: Project) -> dict:
    """Thumbnail over the whole mix, the mix as audio, and 'now playing' titles."""
    mix = p.mix()
    audio_file = mix.get("wav") or mix.get("mp3")
    thumb = next(iter(sorted(p.dir.glob("thumb.*"))), None)
    edit: dict = {"res": "720p", "video": [], "overlay": [], "audio": []}
    dur = _probe(audio_file)["dur"] if audio_file else 0.0
    if audio_file:
        edit["audio"].append({"id": _id(), "media": f"out/{audio_file.name}", "start": 0.0, "in": 0.0, "dur": dur,
                              "volume": 1.0, "fade_in": 0.0, "fade_out": 3.0})
    if thumb:
        edit["video"].append({"id": _id(), "media": f"thumb/{thumb.name}", "start": 0.0, "in": 0.0,
                              "dur": dur or 10.0, "fit": "blur", "zoom": False})
    if audio_file and mix.get("tracklist"):
        edit["overlay"].append({"id": _id(), "kind": "nowplaying", "start": 0.0, "dur": dur, "text": "",
                                "pos": "bottom-left", "size": 3.6, "color": "#ffffff", "box": True})
    return edit


def _num(v, default: float, lo: float = 0.0, hi: float = 1e7) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x)) if x == x else default


def clean_edit(p: Project, raw: dict) -> dict:
    edit = {"res": raw.get("res") if raw.get("res") in RESOLUTIONS else "720p", "video": [], "overlay": [], "audio": []}
    for c in raw.get("video") or []:
        resolve(p, c.get("media", ""))
        edit["video"].append({"id": str(c.get("id") or _id())[:16], "media": c["media"],
                              "start": _num(c.get("start"), 0), "in": _num(c.get("in"), 0),
                              "dur": _num(c.get("dur"), 5, 0.1), "fit": c.get("fit") if c.get("fit") in ("blur", "fill", "fit") else "blur",
                              "zoom": bool(c.get("zoom"))})
    for c in raw.get("audio") or []:
        resolve(p, c.get("media", ""))
        edit["audio"].append({"id": str(c.get("id") or _id())[:16], "media": c["media"],
                              "start": _num(c.get("start"), 0), "in": _num(c.get("in"), 0),
                              "dur": _num(c.get("dur"), 5, 0.1), "volume": _num(c.get("volume"), 1, 0, 3),
                              "fade_in": _num(c.get("fade_in"), 0, 0, 60), "fade_out": _num(c.get("fade_out"), 0, 0, 60)})
    for c in raw.get("overlay") or []:
        if c.get("kind") not in OVERLAYS:
            continue
        color = c.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(c.get("color", ""))) else "#ffffff"
        edit["overlay"].append({"id": str(c.get("id") or _id())[:16], "kind": c["kind"],
                                "start": _num(c.get("start"), 0), "dur": _num(c.get("dur"), 5, 0.1),
                                "text": str(c.get("text") or "")[:300],
                                "pos": c.get("pos") if c.get("pos") in POSITIONS else "bottom-left",
                                "size": _num(c.get("size"), 4, 1, 20), "color": color, "box": bool(c.get("box", True))})
    return edit


def load_edit(p: Project) -> dict:
    raw = read_json(p.file("edit.json"), {})
    if not raw:
        return default_edit(p)
    try:
        return clean_edit(p, raw)
    except PlaylistKitError:
        # a file was deleted: drop the clips that used it
        for track in ("video", "audio"):
            ok = []
            for c in raw.get(track) or []:
                try:
                    resolve(p, c.get("media", ""))
                    ok.append(c)
                except PlaylistKitError:
                    pass
            raw[track] = ok
        return clean_edit(p, raw)


def save_edit(p: Project, raw: dict) -> dict:
    edit = clean_edit(p, raw)
    write_json(p.file("edit.json"), edit)
    return edit


def duration(edit: dict) -> float:
    ends = [c["start"] + c["dur"] for t in ("video", "overlay", "audio") for c in edit[t]]
    return max(ends, default=0.0)


def song_titles(p: Project, edit: dict) -> list[tuple[float, float, str]]:
    """(start, end, name) on the edit's timeline for 'now playing', from the mix's tracklist."""
    from playlistkit.meta import clean_track_name, read_tracklist

    mix = p.mix()
    if "tracklist" not in mix:
        return []
    mix_names = {f"out/{f.name}" for k, f in mix.items() if k in ("wav", "mp3")}
    tracks = read_tracklist(mix["tracklist"])
    out = []
    for clip in (c for c in edit["audio"] if c["media"] in mix_names):  # the mix may be split into pieces
        for i, (t, name) in enumerate(tracks):
            end = tracks[i + 1][0] if i + 1 < len(tracks) else 1e9
            a = max(clip["start"] + (t - clip["in"]), clip["start"])
            b = min(clip["start"] + (end - clip["in"]), clip["start"] + clip["dur"])
            if b - a > 0.5:
                out.append((a, b, clean_track_name(name)))
    return sorted(out)


# ---------------------------------------------------------------- export

_EMOJI = re.compile("[🀀-🫿☀-➿️‍⬀-⯿]")


def strip_emoji(text: str) -> str:
    """The video font has no emoji; the page strips them too so the preview matches."""
    return " ".join(_EMOJI.sub("", text).split())

def _font() -> Path | None:
    for d in FONT_DIRS:
        for n in FONT_NAMES:
            if (d / n).is_file():
                return d / n
    return None


def _ff_path(path: Path) -> str:
    """A path inside a filter argument: forward slashes, escaped colon and quote."""
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _xy(pos: str, margin: str = "h*0.05") -> tuple[str, str]:
    """drawtext x/y for a position like 'bottom-left' (the page uses the same 5 % margin)."""
    vert, _, horiz = pos.partition("-")
    if vert in ("left", "right"):
        vert, horiz = "center", vert
    x = {"left": margin, "right": f"w-text_w-{margin}"}.get(horiz, "(w-text_w)/2")
    y = {"top": margin, "bottom": f"h-text_h-{margin}"}.get(vert, "(h-text_h)/2")
    return x, y


def build_export(p: Project, edit: dict, out: Path, tmp: Path) -> tuple[list[str], float, int]:
    """FFmpeg command for the edit. Returns (cmd, duration, fps)."""
    ff = find_ffmpeg()
    w, h = RESOLUTIONS[edit["res"]]
    total = duration(edit)
    if total <= 0:
        raise PlaylistKitError("The timeline is empty: drag media from the left onto the tracks.")
    # 25 fps for video clips and slow zoom, 15 fps is smooth enough for a sound wave, 2 fps for still pictures
    if any(kind_of(resolve(p, c["media"])) == "video" or c["zoom"] for c in edit["video"]):
        fps = 25
    elif any(o["kind"] == "wave" for o in edit["overlay"]):
        fps = 15
    else:
        fps = 2
    inputs: list[str] = []
    graph: list[str] = [f"color=c=black:s={w}x{h}:r={fps}:d={total:.3f}[base0]"]
    n_in = 0

    def add_input(args: list[str]) -> int:
        nonlocal n_in
        inputs.extend(args)
        n_in += 1
        return n_in - 1

    last = "base0"
    for i, c in enumerate(edit["video"]):
        src = resolve(p, c["media"])
        kind = kind_of(src)
        if kind == "image":
            idx = add_input(["-loop", "1", "-framerate", str(fps), "-t", f"{c['dur']:.3f}", "-i", str(src)])
        else:
            idx = add_input(["-ss", f"{c['in']:.3f}", "-t", f"{c['dur']:.3f}", "-i", str(src)])
        v = f"[{idx}:v]fps={fps},format=rgba"
        if c["zoom"] and kind == "image":
            frames = max(1, int(c["dur"] * fps))
            v += (f",scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                  f"zoompan=z='1+0.12*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}")
            graph.append(f"{v}[v{i}a]")
        elif c["fit"] == "fill":
            graph.append(f"{v},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[v{i}a]")
        elif c["fit"] == "fit":
            graph.append(f"{v},scale={w}:{h}:force_original_aspect_ratio=decrease,"
                         f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black[v{i}a]")
        else:  # blur: the picture fitted over a blurred, darker copy of itself
            graph.append(f"{v},split=2[bg{i}][fg{i}]")
            graph.append(f"[bg{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                         f"boxblur=20:2,eq=brightness=-0.08[b{i}]")
            graph.append(f"[fg{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[f{i}]")
            graph.append(f"[b{i}][f{i}]overlay=(W-w)/2:(H-h)/2[v{i}a]")
        graph.append(f"[v{i}a]setpts=PTS-STARTPTS+{c['start']:.3f}/TB[v{i}]")
        end = c["start"] + c["dur"]
        graph.append(f"[{last}][v{i}]overlay=eof_action=pass:enable='between(t,{c['start']:.3f},{end:.3f})'[base{i + 1}]")
        last = f"base{i + 1}"

    # audio first: the wave overlay needs the mixed audio
    a_labels = []
    for i, c in enumerate(edit["audio"]):
        src = resolve(p, c["media"])
        idx = add_input(["-ss", f"{c['in']:.3f}", "-t", f"{c['dur']:.3f}", "-i", str(src)])
        chain = f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={c['volume']:.3f}"
        if c["fade_in"] > 0:
            chain += f",afade=t=in:st=0:d={c['fade_in']:.2f}"
        if c["fade_out"] > 0:
            chain += f",afade=t=out:st={max(0.0, c['dur'] - c['fade_out']):.3f}:d={c['fade_out']:.2f}"
        delay = int(round(c["start"] * 1000))
        chain += f",adelay={delay}|{delay}[a{i}]"
        graph.append(chain)
        a_labels.append(f"[a{i}]")
    if a_labels:
        graph.append("".join(a_labels) + f"amix=inputs={len(a_labels)}:normalize=0:duration=longest,"
                     f"apad,atrim=0:{total:.3f}[amix]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{total:.3f}[amix]")
    waves = [o for o in edit["overlay"] if o["kind"] == "wave"]
    if waves:
        graph.append(f"[amix]asplit={len(waves) + 1}[aout]" + "".join(f"[aw{i}]" for i in range(len(waves))))
    else:
        graph.append("[amix]anull[aout]")

    font = _font()
    tmp.mkdir(parents=True, exist_ok=True)
    text_n = 0
    for j, o in enumerate(edit["overlay"]):
        a, b = o["start"], o["start"] + o["dur"]
        fs = max(8, int(h * o["size"] / 100))
        color = o["color"].lstrip("#")
        if o["kind"] in ("text", "nowplaying"):
            if not font:
                log("   no font found for titles; skipped")
                continue
            if o["kind"] == "text":
                items = [(a, b, o["text"])]
            else:
                items = [(max(a, s), min(b, e), (o["text"] + " " if o["text"] else "") + name)
                         for s, e, name in song_titles(p, edit) if min(b, e) - max(a, s) > 0.5]
            x, y = _xy(o["pos"])
            for s, e, text in items:
                if not text.strip():
                    continue
                tf = tmp / f"text{text_n}.txt"
                tf.write_text(strip_emoji(text), encoding="utf-8")
                text_n += 1
                box = f":box=1:boxcolor=black@0.45:boxborderw={max(4, fs // 3)}" if o["box"] else \
                    ":shadowcolor=black@0.7:shadowx=2:shadowy=2"
                graph.append(f"[{last}]drawtext=fontfile='{_ff_path(font)}':textfile='{_ff_path(tf)}':fontsize={fs}:"
                             f"fontcolor=0x{color}:x={x}:y={y}{box}:enable='between(t,{s:.3f},{e:.3f})'[t{text_n}]")
                last = f"t{text_n}"
        elif o["kind"] == "progress":
            bar_h = max(3, int(h * o["size"] / 100 / 4))
            y = "0" if o["pos"].startswith("top") else f"{h - bar_h}"
            graph.append(f"color=c=0x{color}:s={w}x{bar_h}:r={fps}:d={total:.3f},format=rgba,colorchannelmixer=aa=0.85[pb{j}]")
            graph.append(f"[{last}][pb{j}]overlay=x='-{w}+{w}*(t-{a:.3f})/{o['dur']:.3f}':y={y}:eof_action=pass:"
                         f"enable='between(t,{a:.3f},{b:.3f})'[p{j}]")
            last = f"p{j}"
        elif o["kind"] == "wave":
            k = waves.index(o)
            wh = max(20, int(h * o["size"] / 100 * 2.5))
            ww = int(w * 0.9)
            graph.append(f"[aw{k}]showwaves=s={ww}x{wh}:mode=cline:rate={fps}:colors=0x{color}@0.85,format=rgba[wv{j}]")
            # 'bottom' sits above the bottom titles (now playing), like the page shows it
            y = "H*0.06" if o["pos"].startswith("top") else "(H-h)/2" if o["pos"] == "center" else "H-h-H*0.15"
            graph.append(f"[{last}][wv{j}]overlay=x=(W-w)/2:y={y}:eof_action=pass:"
                         f"enable='between(t,{a:.3f},{b:.3f})'[w{j}]")
            last = f"w{j}"
    graph.append(f"[{last}]format=yuv420p,setsar=1[vout]")

    # a mostly still picture needs little bitrate; the cap keeps an hour-long video around 0.5-2 GB at most
    rate = {"480p": 1200, "720p": 2500, "1080p": 5000}[edit["res"]]
    cap = ["-maxrate", f"{rate * 2}k", "-bufsize", f"{rate * 4}k"]
    if fps > 2 and nvenc_available(ff.ffmpeg):
        venc = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "26", "-b:v", f"{rate}k", *cap, "-g", str(fps * 2)]
    elif fps > 2:
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", *cap, "-g", str(fps * 2)]
    else:
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "22", "-g", str(fps * 10)]
    cmd = [str(ff.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-progress", "pipe:1", "-nostats", *inputs,
           "-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]", *venc,
           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "384k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    return cmd, total, fps


def export(p: Project, edit: dict, progress=None) -> Path:
    out = p.out / f"{p.id}_edit_{edit['res']}.mp4"
    tmp_out = out.with_name(out.stem + ".part.mp4")
    tmp = p.work / "export-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    cmd, total, fps = build_export(p, edit, tmp_out, tmp)
    log(f"Exporting {edit['res']} at {fps} fps, {fmt_ts(total)} long -> {out.name}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=NO_WINDOW)
    assert proc.stdout is not None
    for line in proc.stdout:
        if cancelled():
            proc.kill()
            proc.wait()
            tmp_out.unlink(missing_ok=True)
            raise Cancelled()
        m = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
        if m and progress:
            progress(min(1.0, int(m.group(1)) / 1e6 / total))
    err = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        tmp_out.unlink(missing_ok=True)
        raise PlaylistKitError("FFmpeg could not export the video:\n" + "\n".join(err.strip().splitlines()[-12:]))
    tmp_out.replace(out)
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"Video ready: {out}  ({out.stat().st_size / 1e6:.0f} MB)")
    return out


def preview_frame(p: Project, edit: dict, at: float) -> Path:
    """One exported frame at time `at` (to check titles and layout exactly as FFmpeg draws them)."""
    tmp = p.work / "frame-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    png = p.work / "frame-preview.png"
    cmd, total, fps = build_export(p, edit, png, tmp)
    # replace the encoder/output part with a single frame grab
    i = cmd.index("-map")
    graph_part = cmd[:i]
    one = graph_part + ["-map", "[vout]", "-ss", f"{max(0.0, min(at, total - 0.1)):.3f}", "-frames:v", "1",
                        "-update", "1", str(png)]
    one = [a for a in one if a not in ("-progress", "pipe:1", "-nostats")]
    k = one.index("-filter_complex") + 1
    one[k] += ";[aout]anullsink"  # no audio in a still frame
    proc = subprocess.run(one, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if proc.returncode != 0 or not png.is_file():
        raise PlaylistKitError("Could not draw the frame:\n" + "\n".join(proc.stderr.strip().splitlines()[-8:]))
    return png
