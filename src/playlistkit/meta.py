"""Tracklist clean-up and the YouTube title, description and tags (youtube_meta.txt)."""
from __future__ import annotations

import re
from pathlib import Path

from playlistkit.genres import GENRES, Genre
from playlistkit.project import Project
from playlistkit.util import fmt_ts, human_duration, parse_ts, read_json

TAG_LIMIT = 480
_JUNK = [
    r"\((?:\s*official[^)]*|\s*lyrics?[^)]*|\s*mv[^)]*|\s*audio[^)]*|\s*mp3[^)]*|\s*\d+\s*kbps[^)]*|\s*hd\s*|"
    r"\s*original(?: song| version)?\s*|\s*bản gốc\s*|\s*free download\s*|\s*prod[^)]*)\)",
    r"\[(?:\s*official[^\]]*|\s*lyrics?[^\]]*|\s*mv[^\]]*|\s*audio[^\]]*|\s*original[^\]]*|\s*mp3[^\]]*)\]",
    r"\b(official (?:music )?(?:video|audio|mv)|official)\b",
    r"[♫♪★☆✪✔❤♥]+", r"꒰[^꒱]*꒱", r"[\U0001F300-\U0001FAFF]",
    r"\.(mp3|m4a|wav)\b", r"\(MP3_?\d+K\)", r"\s[-–]\s*(?:an\s)?original(?: song)? by .*$", r"\(\s*original by [^)]*\)",
]


def clean_track_name(name: str) -> str:
    """'Hali - Con Chim Phiêu Diêu - Hali' -> 'Hali - Con Chim Phiêu Diêu' and similar fixes."""
    s = name.replace("⧸", "/").replace("\\\\", "\\")
    s = re.sub(r"\[\s*demo\s*\]", "(Demo)", s, flags=re.I)
    s = re.sub(r"\[\s*live[^\]]*\]\s*", "", s, flags=re.I)
    for pat in _JUNK:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"\(\s*\)", " ", s)
    s = re.sub(r"\s*[\\|]+\s*original\b.*$", "", s, flags=re.I)
    parts = [p.strip(" -–/") for p in re.split(r"\s+[-–]\s+", s) if p.strip(" -–/")]
    if len(parts) >= 2:
        artist = parts[0]
        rest: list[str] = []
        for p in parts[1:]:
            m = re.fullmatch(rf"{re.escape(artist)}\s*(\(.*\))?", p, flags=re.I)
            if m:  # 'Title - Artist (Demo)' -> keep '(Demo)' on the title
                if m.group(1) and rest:
                    rest[-1] += " " + m.group(1)
                continue
            rest.append(p)
        # 'Artist - Title / Artist'
        rest = [re.sub(rf"\s*/\s*{re.escape(artist)}\s*$", "", p, flags=re.I) for p in rest]
        rest = [re.sub(rf"\s*-\s*{re.escape(artist)}\s*$", "", p, flags=re.I) for p in rest]
        s = " - ".join([artist] + rest) if rest else artist
    s = re.sub(r"\s{2,}", " ", s).strip(" -–/|")
    return s or name.strip()


def read_tracklist(path: Path) -> list[tuple[float, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+(?::\d+){1,2})\s+(.*\S)", line)
        if m:
            out.append((parse_ts(m.group(1)), m.group(2)))
    return out


def write_tracklist(path: Path, tracks: list[tuple[float, str]]) -> None:
    path.write_text("\n".join(f"{fmt_ts(t)} {n}" for t, n in tracks) + "\n", encoding="utf-8")


def dur_vi(seconds: float) -> str:
    m = seconds / 60
    if m < 50:
        return f"{int(m)} phút"
    if m < 70:
        return "Một tiếng"
    if m < 88:
        return "Hơn một tiếng"
    if m < 110:
        return "Hơn một tiếng rưỡi"
    if m < 130:
        return "Gần hai tiếng"
    return f"Hơn {int(m // 60)} tiếng"


def dur_en(seconds: float) -> str:
    h, m = divmod(int(seconds // 60), 60)
    return (f"{h} hour{'s' if h > 1 else ''} {m} min" if h else f"{m} minutes").replace(" 0 min", "")


def default_name(tracks: list[tuple[float, str]]) -> str:
    """A title suggestion: the closing song's title, lower case, like 'chuyện mưa và những câu xin chào'."""
    if not tracks:
        return "playlist"
    parts = clean_track_name(tracks[-1][1]).split(" - ")
    title = parts[1] if len(parts) > 1 else parts[0]
    title = re.sub(r"\(.*?\)", "", title).strip()
    return title.lower() or "playlist"


def build(genre: Genre, name: str, tracks: list[tuple[float, str]], duration: float,
          credits: list[str] | None = None) -> dict:
    title = f"{name} {genre.emoji} | {human_duration(duration)}"
    blurb = genre.blurb.format(n=len(tracks), dur_text=dur_vi(duration), dur_en=dur_en(duration))
    lines = [f"{name} {genre.emoji}", genre.tagline, "", blurb, "", "🎧 Tracklist"]
    lines += [f"{fmt_ts(t)} {n}" for t, n in tracks]
    lines += [""]
    if credits:
        lines += ["📜 Credits / licences"] + credits + [""]
    lines += ["🎵 Toàn bộ bài hát thuộc về các nghệ sĩ và chủ sở hữu bản quyền. Nếu bạn là tác giả và muốn gỡ bài, "
              "hãy liên hệ mình qua bình luận hoặc email trên kênh.", "",
              "Nếu playlist này hợp với bạn, nhấn đăng ký để nghe playlist tiếp theo nhé ☁️", "",
              " ".join(genre.hashtags[:3])]
    tags: list[str] = []
    for t in list(genre.yt_tags) + [name] + [n.split(" - ")[0] for _, n in tracks]:
        t = t.strip().replace(",", " ")
        if t and t.lower() not in {x.lower() for x in tags} and len(", ".join(tags + [t])) <= TAG_LIMIT:
            tags.append(t)
    return {"title": title, "description": "\n".join(lines), "tags": ", ".join(tags)}


def render_text(meta: dict) -> str:
    return (f"=== TITLE ===\n\n{meta['title']}\n\n=== DESCRIPTION ===\n\n{meta['description']}\n\n"
            f"=== TAGS (paste into the Tags box, max 500 characters) ===\n\n{meta['tags']}\n")


def credits_for(project: Project) -> list[str]:
    """Licence lines for Creative Commons songs (CC BY requires credit)."""
    rec = read_json(project.file("downloads.json"), {})
    out = []
    for info in rec.values():
        if info.get("safety") == "cc" or "creativecommons" in str(info.get("license", "")):
            who = f"{info.get('artist')} - {info.get('title')}".strip(" -")
            out.append(f"• {who} — {info.get('license') or 'Creative Commons'} — {info.get('url', '')}".rstrip(" —"))
    return out


def make_for_project(project: Project, name: str = "", tracks: list[tuple[float, str]] | None = None,
                     duration: float | None = None) -> dict:
    mix = project.mix()
    if "tracklist" not in mix:
        raise FileNotFoundError("Render the mix first: there is no tracklist yet.")
    if tracks is None:
        tracks = [(t, clean_track_name(n)) for t, n in read_tracklist(mix["tracklist"])]
    if duration is None:
        from playlistkit.screen import probe

        duration = probe(mix.get("wav") or mix["mp3"])["duration"]
    genre = GENRES.get(project.genre, GENRES["indie"])
    name = (name or project.data.get("title_name") or default_name(tracks)).strip()
    meta = build(genre, name, tracks, duration, credits_for(project))
    (project.out / "youtube_meta.txt").write_text(render_text(meta), encoding="utf-8")
    project.data["title_name"] = name
    project.data["title"] = meta["title"]
    project.save()
    return {**meta, "name": name, "tracks": [{"t": t, "ts": fmt_ts(t), "name": n} for t, n in tracks],
            "duration": duration}
