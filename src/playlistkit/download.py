"""Download the selected songs into the project's songs folder."""
from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path

from playlistkit.backlog import Backlog
from playlistkit.deps import find_ffmpeg
from playlistkit.project import Project
from playlistkit.sources import UA, Candidate
from playlistkit.util import AUDIO_EXT, Cancelled, PlaylistKitError, check_cancel, log, read_json, safe_filename, write_json

_CT_EXT = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
           "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/wav": ".wav", "audio/x-wav": ".wav",
           "audio/aac": ".aac", "audio/webm": ".webm", "audio/opus": ".opus"}


def _next_index(folder: Path) -> int:
    nums = [int(m.group(1)) for p in folder.glob("*") if (m := re.match(r"(\d+)\s*-", p.name))]
    return max(nums, default=0) + 1


def _fetch(url: str, dest_stem: Path, page: str = "") -> Path:
    headers = {"User-Agent": UA}
    if page.startswith("http"):  # ccMixter refuses files asked for without the song's page as Referer (403)
        headers["Referer"] = page
    req = urllib.request.Request(url, headers=headers)
    tmp = dest_stem.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:  # noqa: S310
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        while chunk := resp.read(1 << 18):
            check_cancel()
            out.write(chunk)
        final_url = resp.geturl()
    ext = _CT_EXT.get(ctype) or next((e for e in AUDIO_EXT if final_url.lower().split("?")[0].endswith(e)), ".mp3")
    dest = dest_stem.with_name(dest_stem.name + ext)
    tmp.replace(dest)
    return dest


def _ytdlp(url: str, dest_stem: Path) -> Path:
    import yt_dlp

    opts = {"format": "bestaudio/best", "outtmpl": str(dest_stem) + ".%(ext)s", "noplaylist": True,
            "quiet": True, "no_warnings": True, "noprogress": True, "retries": 3,
            "ffmpeg_location": str(find_ffmpeg().folder),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "best"},
                               {"key": "FFmpegMetadata"}]}

    def hook(_d: dict) -> None:
        check_cancel()

    opts["progress_hooks"] = [hook]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in dest_stem.parent.glob(dest_stem.name + ".*") if p.suffix.lower() in AUDIO_EXT]
    if not files:
        raise PlaylistKitError("yt-dlp finished but no audio file was written.")
    return files[0]


def download_selected(project: Project, cands: list[Candidate], backlog: Backlog,
                      progress=None) -> list[str]:
    """Download every selected candidate that is not downloaded yet. Returns the new file names."""
    songs = project.songs
    songs.mkdir(parents=True, exist_ok=True)
    record_path = project.file("downloads.json")
    record: dict = read_json(record_path, {})
    done_ids = {v.get("uid") for v in record.values()}
    todo = [c for c in cands if c.selected and f"{c.source}:{c.sid}" not in done_ids]
    new: list[str] = []
    for i, c in enumerate(todo, 1):
        check_cancel()
        if progress:
            progress(i - 1, len(todo))
        label = f"{c.artist} - {c.title}" if c.artist else c.title
        log(f"[{i}/{len(todo)}] {label}  ({c.source})")
        stem = songs / safe_filename(f"{_next_index(songs):02d} - {label}")
        try:
            if c.source == "local":
                src = Path(c.download)
                if src.parent.resolve() == songs.resolve():
                    path = src
                else:
                    path = stem.with_name(stem.name + src.suffix.lower())
                    shutil.copy2(src, path)
            elif c.download:
                path = _fetch(c.download, stem, c.url)
            else:
                path = _ytdlp(c.url, stem)
        except Cancelled:
            for leftover in songs.glob(stem.name + ".*"):
                leftover.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001 - skip one broken download, keep going
            log(f"   failed: {str(exc)[:300]}")
            continue
        record[path.name] = {"uid": f"{c.source}:{c.sid}", "source": c.source, "url": c.url, "artist": c.artist,
                             "title": c.title, "license": c.license, "safety": c.safety}
        write_json(record_path, record)
        backlog.mark(project.id, c.artist or "?", c.title, "downloaded", c.source if c.source != "soundcloud" else "")
        new.append(path.name)
    if progress:
        progress(len(todo), len(todo))
    log(f"Downloaded {len(new)} of {len(todo)} songs into {songs}")
    return new


def song_info(project: Project, path: Path) -> dict:
    """Artist/title of a song file: from downloads.json, else from the file name."""
    rec = read_json(project.file("downloads.json"), {}).get(path.name)
    if rec:
        return {"artist": rec.get("artist", ""), "title": rec.get("title", ""), "source": rec.get("source", ""),
                "url": rec.get("url", ""), "license": rec.get("license", ""), "safety": rec.get("safety", "")}
    stem = re.sub(r"^\d+\s*-\s*", "", path.stem)
    artist, _, title = stem.partition(" - ")
    if not title:
        artist, title = "", stem
    return {"artist": artist.strip(), "title": title.strip(), "source": "local", "url": "", "license": "",
            "safety": "unknown"}
