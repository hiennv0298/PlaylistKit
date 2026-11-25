"""Quick quality check of every song before the remix.

Flags songs that usually sound wrong in a playlist: heavy sub-bass (808s) in a
soft genre, band-limited low-quality uploads, songs that are far too short or
long, and duplicates (same title twice).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from playlistkit.backlog import key
from playlistkit.deps import find_ffmpeg
from playlistkit.genres import GENRES
from playlistkit.project import Project
from playlistkit.util import NO_WINDOW, check_cancel, log, read_json, write_json

SR = 44100


def probe(path: Path) -> dict:
    ff = find_ffmpeg()
    out = subprocess.run([str(ff.ffprobe), "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
                         capture_output=True, text=True, encoding="utf-8", creationflags=NO_WINDOW).stdout
    fmt = (json.loads(out or "{}").get("format") or {})
    return {"duration": float(fmt.get("duration") or 0), "bitrate": int(fmt.get("bit_rate") or 0) // 1000}


def decode_mono(path: Path, sr: int = SR, seconds: float | None = None) -> np.ndarray:
    ff = find_ffmpeg()
    cmd = [str(ff.ffmpeg), "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", str(sr)]
    if seconds:
        cmd += ["-t", str(seconds)]
    raw = subprocess.run(cmd + ["-f", "f32le", "-"], capture_output=True, creationflags=NO_WINDOW).stdout
    return np.frombuffer(raw, np.float32)


def spectrum_stats(y: np.ndarray, sr: int = SR) -> dict:
    """Sub-bass and low share (dB of total energy) and the frequency where the spectrum ends."""
    n = 4096
    frames = len(y) // n
    if frames < 4:
        return {"sub_db": -99.0, "low_db": -99.0, "cutoff_khz": 0.0}
    x = y[: frames * n].reshape(frames, n) * np.hanning(n).astype(np.float32)
    spec = (np.abs(np.fft.rfft(x, axis=1)) ** 2).mean(axis=0)
    fr = np.fft.rfftfreq(n, 1 / sr)
    total = spec.sum() + 1e-20
    sub = spec[(fr >= 20) & (fr < 60)].sum() / total
    low = spec[(fr >= 60) & (fr < 150)].sum() / total
    db = 10 * np.log10(spec + 1e-20)
    ref = db[(fr > 1000) & (fr < 3000)].mean()
    above = np.where(db > ref - 50)[0]
    cutoff = fr[above.max()] if above.size else 0.0
    return {"sub_db": round(float(10 * np.log10(sub + 1e-12)), 1), "low_db": round(float(10 * np.log10(low + 1e-12)), 1),
            "cutoff_khz": round(float(cutoff) / 1000, 1)}


def check_song(path: Path, genre_id: str) -> dict:
    g = GENRES.get(genre_id, GENRES["indie"])
    info = probe(path)
    st = spectrum_stats(decode_mono(path, seconds=420))
    flags = []
    if info["duration"] <= 0 or st["sub_db"] <= -98:
        return {**info, **st, "flags": [{"level": "bad", "text": "cannot read this file (no audio)"}]}
    soft = g.style in ("indie", "lofi")
    if soft and st["sub_db"] > -5:
        flags.append(("bad", f"very heavy sub-bass ({st['sub_db']} dB)"))
    elif soft and st["sub_db"] > -8:
        flags.append(("warn", f"heavy sub-bass ({st['sub_db']} dB), listen first"))
    if 0 < st["cutoff_khz"] < 11:
        flags.append(("bad", f"low quality: nothing above {st['cutoff_khz']} kHz"))
    elif 0 < st["cutoff_khz"] < 13:
        flags.append(("warn", f"lossy upload (cuts at {st['cutoff_khz']} kHz)"))
    if info["duration"] and info["duration"] < max(60, g.min_sec - 30):
        flags.append(("warn", f"short ({info['duration'] / 60:.1f} min)"))
    if info["duration"] > g.max_sec + 120:
        flags.append(("warn", f"long ({info['duration'] / 60:.1f} min)"))
    return {**info, **st, "flags": [{"level": lv, "text": t} for lv, t in flags]}


def screen_project(project: Project, progress=None) -> dict:
    files = project.song_files()
    cache_path = project.file("screen.json")
    cache: dict = read_json(cache_path, {})
    out: dict = {}
    for i, f in enumerate(files):
        check_cancel()
        if progress:
            progress(i, len(files))
        sig = f"{f.stat().st_size}:{int(f.stat().st_mtime)}"
        if cache.get(f.name, {}).get("sig") == sig:
            out[f.name] = cache[f.name]
            continue
        try:
            res = check_song(f, project.genre)
        except Exception as exc:  # noqa: BLE001
            res = {"duration": 0, "flags": [{"level": "bad", "text": f"cannot read: {exc}"}]}
        res["sig"] = sig
        out[f.name] = res
        worst = next((fl["text"] for fl in res["flags"] if fl["level"] == "bad"), "")
        log(f"   {f.name[:60]:60s} {res.get('duration', 0) / 60:5.2f} min  sub {res.get('sub_db', 0):6.1f} dB"
            + (f"  <- {worst}" if worst else ""))
    # duplicates: same title twice
    seen: dict[str, str] = {}
    for name in out:
        stem = Path(name).stem.split(" - ", 1)[-1]
        k = key(stem.split(" - ")[-1])
        if k and k in seen:
            out[name]["flags"].append({"level": "bad", "text": f"duplicate of {seen[k]}"})
        else:
            seen[k] = name
    write_json(cache_path, out)
    if progress:
        progress(len(files), len(files))
    return out
