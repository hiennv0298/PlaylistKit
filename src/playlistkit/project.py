"""A playlist project: one folder with the songs, the engine's caches and the outputs.

    <projects folder>/<id>/
        project.json        name, genre, style, title...
        songs/              the audio files (or an existing folder you pointed it at)
        candidates.json     songs found by the last search
        downloads.json      where each downloaded file came from
        screen.json         the quality check of each song
        work/               engine caches (decoded audio, stems): safe to delete
        out/                <id>_<style>.wav/.mp3, tracklist_<style>.txt, youtube_meta.txt, *.mp4
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from playlistkit.genres import GENRES
from playlistkit.util import PlaylistKitError, audio_files, read_json, slugify, write_json


@dataclass
class Project:
    dir: Path
    data: dict

    @property
    def id(self) -> str:
        return self.dir.name

    @property
    def songs(self) -> Path:
        return Path(self.data["songs_dir"]) if self.data.get("songs_dir") else self.dir / "songs"

    @property
    def work(self) -> Path:
        return self.dir / "work"

    @property
    def out(self) -> Path:
        return self.dir / "out"

    @property
    def genre(self) -> str:
        return self.data.get("genre", "indie")

    @property
    def style(self) -> str:
        return self.data.get("style") or GENRES.get(self.genre, GENRES["indie"]).style

    def save(self) -> None:
        self.data["updated"] = dt.datetime.now().isoformat(timespec="seconds")
        write_json(self.dir / "project.json", self.data)

    def file(self, name: str) -> Path:
        return self.dir / name

    def song_files(self) -> list[Path]:
        return audio_files(self.songs)

    def mix(self, style: str | None = None) -> dict:
        """The rendered mix for a style: {'wav', 'mp3', 'tracklist'} paths that exist."""
        style = style or self.style
        base = self.out / f"{self.id}_{style}"
        found = {"wav": base.with_suffix(".wav"), "mp3": base.with_suffix(".mp3"),
                 "tracklist": self.out / f"tracklist_{style}.txt"}
        return {k: p for k, p in found.items() if p.is_file()}

    def summary(self) -> dict:
        mix = self.mix()
        videos = sorted(p.name for p in self.out.glob("*.mp4")) if self.out.is_dir() else []
        g = GENRES.get(self.genre)
        return {"id": self.id, "name": self.data.get("name") or self.id, "genre": self.genre,
                "genre_name": g.name if g else self.genre, "emoji": g.emoji if g else "🎵", "style": self.style,
                "songs": len(self.song_files()), "songs_dir": str(self.songs), "has_mix": "wav" in mix,
                "videos": videos, "title": self.data.get("title", ""), "updated": self.data.get("updated", ""),
                "created": self.data.get("created", "")}


def load(root: Path, pid: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", pid or ""):
        raise PlaylistKitError("Invalid project.")
    d = Path(root) / pid
    data = read_json(d / "project.json", {})
    if not data:
        raise PlaylistKitError(f"Project '{pid}' not found.")
    return Project(d, data)


def list_all(root: Path) -> list[Project]:
    root = Path(root)
    out = []
    if root.is_dir():
        for d in root.iterdir():
            data = read_json(d / "project.json", {}) if d.is_dir() else {}
            if data:
                out.append(Project(d, data))
    return sorted(out, key=lambda p: p.data.get("updated") or p.data.get("created") or "", reverse=True)


def next_id(root: Path, genre: str) -> str:
    root = Path(root)
    n = 1
    if root.is_dir():
        nums = [int(m.group(1)) for d in root.iterdir() if (m := re.fullmatch(rf"{re.escape(genre)}-(\d+)", d.name))]
        n = max(nums, default=0) + 1
    return f"{genre}-{n}"


def create(root: Path, genre: str, name: str = "", songs_dir: str = "", pid: str = "") -> Project:
    if genre not in GENRES:
        raise PlaylistKitError(f"Unknown genre '{genre}'.")
    root = Path(root)
    pid = slugify(pid) if pid else next_id(root, genre)
    d = root / pid
    if (d / "project.json").exists():
        raise PlaylistKitError(f"A project named '{pid}' already exists.")
    d.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().isoformat(timespec="seconds")
    data = {"name": name or pid, "genre": genre, "style": GENRES[genre].style, "created": now, "updated": now,
            "songs_dir": songs_dir, "title": ""}
    p = Project(d, data)
    p.save()
    if not songs_dir:
        p.songs.mkdir(exist_ok=True)
    return p
