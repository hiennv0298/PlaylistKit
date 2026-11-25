"""Cut Content ID claimed songs out of a finished mix, without re-rendering.

Paste the claim timestamps from YouTube Studio (any text with "47:48 — 51:52"
ranges works). Each range is matched to the songs it overlaps; those songs are
removed and the remaining parts are joined with 3 s equal-power crossfades,
then limited again. The tracklist, youtube_meta.txt and the backlog follow.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from playlistkit.backlog import Backlog, key
from playlistkit.deps import find_ffmpeg
from playlistkit.download import song_info
from playlistkit.meta import clean_track_name, read_tracklist, write_tracklist
from playlistkit.project import Project
from playlistkit.util import PlaylistKitError, fmt_ts, log, parse_ts, read_json, recycle, run, write_json

XF = 3.0
RANGE = re.compile(r"(\d{1,2}(?::\d{2}){1,2})\s*(?:—|–|-|to|→|~)\s*(\d{1,2}(?::\d{2}){1,2})")
LIMITER = ("aresample=192000,alimiter=limit=0.84:attack=3:release=80:level=false:latency=true,aresample=48000")


@dataclass
class Plan:
    claims: list[tuple[float, float]]
    claimed: list[int]                  # indexes into tracks
    remove: list[tuple[float, float]]   # time ranges taken out
    keep: list[tuple[float, float]]
    tracks: list[tuple[float, str]]
    new_tracks: list[tuple[float, str]]
    duration: float
    new_duration: float

    def to_dict(self) -> dict:
        return {"claims": [[fmt_ts(a), fmt_ts(b)] for a, b in self.claims],
                "claimed": [{"index": i, "ts": fmt_ts(self.tracks[i][0]), "name": clean_track_name(self.tracks[i][1])} for i in self.claimed],
                "remove": [[fmt_ts(a), fmt_ts(b)] for a, b in self.remove],
                "new_tracks": [{"ts": fmt_ts(t), "name": clean_track_name(n)} for t, n in self.new_tracks],
                "duration": fmt_ts(self.duration), "new_duration": fmt_ts(self.new_duration)}


def parse_claims(text: str) -> list[tuple[float, float]]:
    out = []
    for a, b in RANGE.findall(text or ""):
        s, e = parse_ts(a), parse_ts(b)
        if e > s:
            out.append((s, e))
    return sorted(out)


def plan_cut(tracks: list[tuple[float, str]], duration: float, claims: list[tuple[float, float]]) -> Plan:
    if not claims:
        raise PlaylistKitError("No time ranges found. Paste ranges like 47:48 — 51:52.")
    spans = [(t, tracks[i + 1][0] if i + 1 < len(tracks) else duration) for i, (t, _) in enumerate(tracks)]
    claimed: set[int] = set()
    for a, b in claims:
        for i, (s, e) in enumerate(spans):
            overlap = min(b, e) - max(a, s)
            if overlap >= min(10.0, (b - a) / 2):
                claimed.add(i)
    if not claimed:
        raise PlaylistKitError("The ranges do not match any song in this mix. Is this the right playlist?")
    regions = []
    for i in sorted(claimed):
        s, e = spans[i]
        for a, b in claims:
            if min(b, e) - max(a, s) > 0:
                s, e = min(s, a), max(e, b)
        regions.append((max(0.0, s), min(duration, e)))
    merged: list[list[float]] = []
    for s, e in sorted(regions):
        if merged and s <= merged[-1][1] + 1.0:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    keep, pos = [], 0.0
    for s, e in merged:
        if s - pos > 1.0:
            keep.append((pos, s))
        pos = e
    if duration - pos > 1.0:
        keep.append((pos, duration))
    if not keep:
        raise PlaylistKitError("Every song would be removed.")
    starts, length = [], 0.0
    for i, (a, b) in enumerate(keep):
        starts.append(0.0 if i == 0 else length - XF)
        length = (b - a) if i == 0 else length + (b - a) - XF
    new = []
    for i, (t, name) in enumerate(tracks):
        if i in claimed:
            continue
        end = spans[i][1]
        for (a, b), s0 in zip(keep, starts):
            if t < b and end > a + 10:
                new.append((s0 + max(0.0, t - a), name))
                break
    new.sort()
    if new:
        new[0] = (0.0, new[0][1])
    return Plan(claims, sorted(claimed), [(a, b) for a, b in merged], keep, tracks, new, duration, length)


def _ffmpeg_cut(wav: Path, keep: list[tuple[float, float]], duration: float, out_wav: Path) -> None:
    ff = find_ffmpeg()
    cmd = [str(ff.ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
    for a, b in keep:
        cmd += ["-ss", f"{a:.3f}"] + (["-to", f"{b:.3f}"] if b < duration - 0.05 else []) + ["-i", str(wav)]
    chain, last = [], "[0:a]"
    for i in range(1, len(keep)):
        chain.append(f"{last}[{i}:a]acrossfade=d={XF}:c1=qsin:c2=qsin[x{i}]")
        last = f"[x{i}]"
    post = []
    if keep[0][0] > 0.5:
        post.append("afade=t=in:d=2")
    tail = keep[-1][1] < duration - 0.5
    filt = ";".join(chain + [f"{last}{','.join(post + [LIMITER]) if post else LIMITER}[out]"])
    cmd += ["-filter_complex", filt, "-map", "[out]", "-c:a", "pcm_s24le", "-ar", "48000", str(out_wav)]
    run(cmd)
    if tail:  # fade the new ending (the old ending was cut)
        tmp = out_wav.with_name(out_wav.stem + "_f.wav")
        d = sum(b - a for a, b in keep) - XF * (len(keep) - 1)
        run([str(ff.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(out_wav), "-af",
             f"afade=t=out:st={max(0.0, d - 5):.3f}:d=5", "-c:a", "pcm_s24le", str(tmp)])
        tmp.replace(out_wav)


def _match_file(project: Project, name: str) -> Path | None:
    files = project.song_files()
    k = key(name)
    best, score = None, 0.0
    for f in files:
        info = song_info(project, f)
        for cand in (f"{info['artist']} {info['title']}", re.sub(r"^\d+\s*-\s*", "", f.stem)):
            r = difflib.SequenceMatcher(None, k, key(cand)).ratio()
            if r > score:
                best, score = f, r
    return best if score >= 0.5 else None


def apply_cut(project: Project, plan: Plan, backlog: Backlog, style: str | None = None) -> dict:
    style = style or project.style
    mix = project.mix(style)
    if "wav" not in mix:
        raise PlaylistKitError("The WAV of the mix is missing; it is needed to cut without re-rendering.")
    wav = mix["wav"]
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = project.work / f"before-cut-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    log(f"Cutting {len(plan.claimed)} songs: " + "; ".join(plan.tracks[i][1] for i in plan.claimed))
    tmp = project.out / "_cut_tmp.wav"
    _ffmpeg_cut(wav, plan.keep, plan.duration, tmp)
    wav.replace(backup / wav.name)
    if mix.get("tracklist"):
        mix["tracklist"].replace(backup / mix["tracklist"].name)
    tmp.replace(wav)
    ff = find_ffmpeg()
    mp3 = wav.with_suffix(".mp3")
    run([str(ff.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame",
         "-b:a", "320k", str(mp3)])
    write_tracklist(project.out / f"tracklist_{style}.txt", plan.new_tracks)
    # songs: backlog + recycle files and their caches
    an_path = project.work / "analysis.json"
    an = read_json(an_path, {})
    removed = []
    for i in plan.claimed:
        name = plan.tracks[i][1]
        f = _match_file(project, name)
        info = song_info(project, f) if f else {"artist": name.split(" - ")[0], "title": name.split(" - ", 1)[-1]}
        backlog.mark(project.id, info["artist"] or "?", info["title"], "claimed", "Content ID")
        if f:
            for tid, v in list(an.items()):
                if Path(str(v.get("src", ""))).name == f.name:
                    for p in [project.work / "decoded" / f"{tid}.wav", project.work / "stems" / "htdemucs" / tid,
                              *(project.work / "proc").glob(f"{tid}*")]:
                        recycle(p)
                    del an[tid]
            recycle(f)
        removed.append(name)
    if an:
        write_json(an_path, an)
    # drop the old backups but this one
    for old in project.work.glob("before-cut-*"):
        if old != backup:
            recycle(old)
    log(f"New length {fmt_ts(plan.new_duration)}, {len(plan.new_tracks)} songs. Backup of the old mix: {backup}")
    return {"removed": removed, "duration": plan.new_duration, "songs": len(plan.new_tracks), "backup": str(backup)}


def current_tracks(project: Project, style: str | None = None) -> tuple[list[tuple[float, str]], float]:
    from playlistkit.screen import probe

    mix = project.mix(style)
    if "tracklist" not in mix or not (mix.get("wav") or mix.get("mp3")):
        raise PlaylistKitError("Render the mix first.")
    return read_tracklist(mix["tracklist"]), probe(mix.get("wav") or mix["mp3"])["duration"]
