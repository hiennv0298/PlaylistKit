"""The song backlog: every song ever downloaded, used, removed or claimed.

A tab-separated file (it opens in Excel) with the columns
    status  playlist  artist  title  note  date
Statuses: downloaded, used, claimed (Content ID), not-fit, bad-quality, duplicate,
banned-artist (artist '*' rows block an artist everywhere).
New downloads are filtered against it so a song is never used twice and a
removed or claimed song never comes back.
"""
from __future__ import annotations

import datetime as dt
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from playlistkit.util import fold

HEADER = ["status", "playlist", "artist", "title", "note", "date"]
BLOCKING = {"used", "downloaded", "claimed", "not-fit", "bad-quality", "duplicate"}
AVOID_ARTIST = {"claimed", "not-fit", "bad-quality", "banned-artist"}
_lock = threading.Lock()
_NOISE = re.compile(r"\((official|lyrics?|mv|audio|video|demo|live|acoustic|prod[^)]*|ft[^)]*|feat[^)]*)[^)]*\)|"
                    r"\[(official|lyrics?|mv|audio|video|demo|live)[^\]]*\]")


def key(text: str) -> str:
    """Comparable form of a title or artist."""
    return fold(_NOISE.sub(" ", text.lower()))


@dataclass
class Row:
    status: str
    playlist: str
    artist: str
    title: str
    note: str = ""
    date: str = ""

    def cells(self) -> list[str]:
        return [self.status, self.playlist, self.artist, self.title, self.note, self.date]


class Backlog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.rows: list[Row] = []
        self.load()

    def load(self) -> None:
        self.rows = []
        if not self.path.is_file():
            return
        for i, line in enumerate(self.path.read_text(encoding="utf-8-sig").splitlines()):
            cells = line.split("\t")
            if i == 0 and cells[:1] == ["status"] or not line.strip():
                continue
            cells += [""] * (6 - len(cells))
            self.rows.append(Row(*[c.strip() for c in cells[:6]]))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["\t".join(HEADER)] + ["\t".join(c.replace("\t", " ") for c in r.cells()) for r in self.rows]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    # ------------------------------------------------------------ queries
    def banned_artists(self, extra: list[str] | None = None) -> set[str]:
        names = {key(r.artist).rstrip(".") for r in self.rows if r.status == "banned-artist"}
        return {n for n in names | {key(a) for a in (extra or [])} if n}

    def avoid_artists(self) -> set[str]:
        out = set()
        for r in self.rows:
            if r.status in AVOID_ARTIST and r.artist != "*":
                for part in re.split(r",|&| x | ft\.? | feat\.? |\(|\+", r.artist):
                    k = key(part)
                    if len(k) > 1:
                        out.add(k)
        return out

    def used_artists(self) -> set[str]:
        out = set()
        for r in self.rows:
            if r.status in ("used", "downloaded"):
                for part in re.split(r",|&| x | ft\.? | feat\.? |\(|\+", r.artist):
                    k = key(part)
                    if len(k) > 1:
                        out.add(k)
        return out

    def known_titles(self) -> set[str]:
        return {key(r.title) for r in self.rows if r.title not in ("", "*") and r.status in BLOCKING}

    def check(self, artist: str, title: str, allow_used_artists: bool = False,
              banned: set[str] | None = None) -> str:
        """Why this song should be skipped ('' if it is fine)."""
        who, t = key(artist), key(title)
        banned = self.banned_artists() if banned is None else banned
        for b in banned:  # artist names only: "Vũ" must not block a title like "Vũ trụ"
            if b and (b in who.split() if " " not in b else f" {b} " in f" {who} "):
                return "banned artist"
        if any(a == who or (len(a) > 3 and f" {a} " in f" {who} ") or (len(a) > 5 and f" {a} " in f" {t} ")
               for a in self.avoid_artists()):
            return "artist was claimed or removed before"
        titles = self.known_titles()
        if t and (t in titles or any(len(k) > 6 and (k in t or t in k) for k in titles)):
            return "already in the backlog"
        if not allow_used_artists and any(a == who or (len(a) > 3 and f" {a} " in f" {who} ")
                                          for a in self.used_artists()):
            return "artist already used"
        return ""

    def _row_for(self, title: str, statuses: set[str]) -> Row | None:
        t = key(title)
        if not t:
            return None
        for r in self.rows:
            if r.status in statuses and r.title not in ("", "*"):
                k = key(r.title)
                if k == t or (len(k) > 6 and (k in t or t in k)):
                    return r
        return None

    def review(self, artist: str, title: str, allow_used_artists: bool = False,
               banned: set[str] | None = None) -> tuple[str, str, bool]:
        """(skip, warning, hold) for a found song. Only a banned artist and songs you removed as not fitting or
        bad quality are skipped. Everything else the backlog knows is shown with a warning: a song or artist
        claimed by Content ID (hold: not ticked for you, it cannot be monetized), and songs or artists used before."""
        who = key(artist)
        banned = self.banned_artists() if banned is None else banned
        for b in banned:  # artist names only: "Vũ" must not block a title like "Vũ trụ"
            if b and (b in who.split() if " " not in b else f" {b} " in f" {who} "):
                return "banned artist", "", False
        removed = self._row_for(title, {"not-fit", "bad-quality"})
        if removed:
            return f"removed before ({removed.status}, {removed.playlist})", "", False
        claimed = self._row_for(title, {"claimed"})
        if claimed:
            return "", f"Content ID claimed it in {claimed.playlist}: cannot be monetized", True
        t = key(title)

        def artist_in(names: set[str]) -> bool:
            return any(a == who or (len(a) > 3 and f" {a} " in f" {who} ") or (len(a) > 5 and f" {a} " in f" {t} ")
                       for a in names)
        claimed_artists = {k for r in self.rows if r.status == "claimed" and r.artist != "*"
                           for k in self._artist_keys(r.artist)}
        if artist_in(claimed_artists):
            return "", "this artist was claimed by Content ID before: likely to be claimed again", True
        used = self._row_for(title, {"used", "downloaded", "duplicate"})
        if used:
            return "", f"already used in {used.playlist}", False
        if not allow_used_artists and artist_in(self.used_artists()):
            return "", "artist used before", False
        return "", "", False

    @staticmethod
    def _artist_keys(artist: str) -> set[str]:
        return {k for part in re.split(r",|&| x | ft\.? | feat\.? |\(|\+", artist) if len(k := key(part)) > 1}

    def claimed_titles(self) -> dict[str, str]:
        """key(title) -> playlist, for songs Content ID claimed."""
        return {key(r.title): r.playlist for r in self.rows if r.status == "claimed" and r.title not in ("", "*")}

    def find(self, playlist: str, artist: str, title: str) -> Row | None:
        ka, kt = key(artist), key(title)
        for r in self.rows:
            if r.playlist == playlist and key(r.artist) == ka and key(r.title) == kt:
                return r
        return None

    # ------------------------------------------------------------ changes
    def mark(self, playlist: str, artist: str, title: str, status: str, note: str = "") -> None:
        with _lock:
            today = dt.date.today().isoformat()
            row = self.find(playlist, artist, title)
            if row:
                row.status, row.date = status, today
                if note:
                    row.note = note
            else:
                self.rows.append(Row(status, playlist, artist, title, note, today))
            self.save()

    def mark_many(self, playlist: str, songs: list[tuple[str, str]], status: str, note: str = "",
                  only_from: set[str] | None = None) -> int:
        """Set the status of several songs at once; only_from limits which current statuses change."""
        with _lock:
            today = dt.date.today().isoformat()
            n = 0
            for artist, title in songs:
                row = self.find(playlist, artist, title)
                if row:
                    if only_from is not None and row.status not in only_from:
                        continue
                    row.status, row.date = status, today
                    if note:
                        row.note = note
                else:
                    self.rows.append(Row(status, playlist, artist, title, note, today))
                n += 1
            self.save()
            return n

    def ban_artist(self, artist: str, note: str = "") -> None:
        with _lock:
            self.rows.insert(0, Row("banned-artist", "*", artist, "*", note, dt.date.today().isoformat()))
            self.save()

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for r in self.rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        return {"path": str(self.path), "total": len(self.rows), "counts": counts,
                "banned": sorted({r.artist for r in self.rows if r.status == "banned-artist"})}
