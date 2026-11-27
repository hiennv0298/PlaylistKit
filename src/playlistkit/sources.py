"""Find songs: SoundCloud, YouTube, Audius, Jamendo, Internet Archive, ccMixter, or a local folder.

Every source returns Candidate objects. `safety` says how likely a song is to
draw a Content ID claim on YouTube:
  cc           Creative Commons licence (Jamendo, ccMixter, Internet Archive)
  artist       uploaded by the artist on a platform without distribution metadata
  unknown      a re-upload or a page we cannot judge
  distributed  has an ISRC / label line / "Official" channel: almost surely in Content ID
"""
from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from playlistkit import __version__
from playlistkit.backlog import Backlog, key
from playlistkit.genres import Genre
from playlistkit.util import AUDIO_EXT, PlaylistKitError, check_cancel, log

UA = f"PlaylistKit/{__version__} (+https://github.com/hiennv0298/PlaylistKit)"
SAFETY_SCORE = {"cc": 3.0, "artist": 2.0, "unknown": 1.0, "distributed": 0.0}
NO_LICENCE = ("youtube", "audius")  # their songs carry no licence: never safe to monetize
SOURCES = {
    "soundcloud": "SoundCloud",
    "youtube": "YouTube",
    "audius": "Audius",
    "jamendo": "Jamendo (Creative Commons)",
    "archive": "Internet Archive (netlabels)",
    "ccmixter": "ccMixter (Creative Commons)",
}
JUNK = re.compile(r"\b(karaoke|8d|beat|instrumental|type beat|1 hour|1 gio|playlist|tuyen tap|lien khuc|"
                  r"nonstop|full album|mashup|reaction|tutorial|hop am|tab)\b")
SOFT_JUNK = re.compile(r"\b(remix|edm|house|vinahouse|nightcore|sped up|speed up|tiktok|bass boosted|phonk|"
                       r"lofi|lo fi|cover)\b")


@dataclass(frozen=True)
class Licence:
    label: str      # "CC BY 4.0", "CC BY-NC-SA 3.0", "CC0", "all rights reserved"
    url: str        # the licence's deed, for the credits
    ok: bool        # allowed in a monetized remix: commercial use and changes are both allowed
    why: str = ""   # why not, when ok is False
    cc: bool = False


_CC_URL = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z+\-]+)(?:/([\d.]+))?", re.I)
_SC_LICENCE = {"cc-by": "by", "cc-by-sa": "by-sa", "cc-by-nc": "by-nc", "cc-by-nd": "by-nd", "cc-by-nc-sa": "by-nc-sa",
               "cc-by-nc-nd": "by-nc-nd", "no-rights-reserved": "zero"}


def licence(text: str) -> Licence:
    """Read a licence from a Creative Commons URL, a SoundCloud licence code or a licence name.
    Safe for a monetized channel: CC0, public domain, CC BY and CC BY-SA. Not safe: NC (no commercial
    use), ND (no changes, and a remix changes the song), Sampling+, and anything else."""
    t = (text or "").strip()
    low = t.lower()
    code, ver = None, ""
    m = _CC_URL.search(low)
    if m:
        kind, code, ver = m.group(1), m.group(2).strip("-"), m.group(3) or ""
        if kind == "publicdomain":
            code = "zero" if code == "zero" else "pdm"
    elif low in _SC_LICENCE:
        code = _SC_LICENCE[low]
    elif low in ("cc0", "cc0 1.0", "public domain"):
        code = "zero" if low.startswith("cc0") else "pdm"
    elif low.startswith("attribution") or low.startswith("creative commons attribution"):
        parts = ["by"] + [p for p, words in (("nc", ("noncommercial", "non-commercial")), ("nd", ("noderiv", "no deriv")),
                                             ("sa", ("share-alike", "sharealike", "share alike")))
                          if any(w in low for w in words)]
        code = "-".join(parts)
    if code is None:
        return Licence(t or "unknown", "", False, "no Creative Commons licence")
    if code == "zero":
        return Licence("CC0", "https://creativecommons.org/publicdomain/zero/1.0/", True, cc=True)
    if code == "pdm":
        return Licence("Public Domain", "https://creativecommons.org/publicdomain/mark/1.0/", True, cc=True)
    if code == "publicdomain":  # the old CC Public Domain Dedication (licenses/publicdomain/), before CC0
        return Licence("Public Domain", "https://creativecommons.org/licenses/publicdomain/", True, cc=True)
    if "sampling" in code:
        return Licence(f"CC {code.title()}", f"https://creativecommons.org/licenses/{code}/{ver or '1.0'}/", False,
                       "Sampling+: only for sampling, not the whole song", cc=True)
    parts = code.split("-")
    label = "CC " + code.upper() + (f" {ver}" if ver else "")
    url = f"https://creativecommons.org/licenses/{code}/{ver or '4.0'}/"
    if "nc" in parts:
        return Licence(label, url, False, "NC: no commercial use", cc=True)
    if "nd" in parts:
        return Licence(label, url, False, "ND: no changes (a remix changes it)", cc=True)
    return Licence(label, url, parts[0] == "by", "" if parts[0] == "by" else "unknown licence", cc=True)


@dataclass
class Candidate:
    source: str
    sid: str
    url: str                 # page URL (yt-dlp can download it)
    artist: str
    title: str
    duration: float = 0.0
    plays: int = 0
    download: str = ""       # direct audio URL when the source gives one
    license: str = ""
    safety: str = "unknown"
    flags: list[str] = field(default_factory=list)
    genre: str = ""
    selected: bool = False
    skip: str = ""           # why it was filtered out
    score: float = 0.0
    lic: str = ""            # the licence as people read it: "CC BY 4.0"
    money: bool = False      # the licence allows a monetized remix (see licence())
    warn: str = ""           # what the backlog knows: used before, claimed by Content ID... (still allowed)
    hold: bool = False       # allowed but not ticked for you (claimed by Content ID before)
    fans: int = 0            # the uploader's followers (SoundCloud)
    verified: bool = False   # the uploader has a verified badge

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        names = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in names})


def http_json(url: str, timeout: float = 25) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https APIs
        return json.loads(resp.read().decode("utf-8", "replace"))


def _q(params: dict) -> str:
    return urllib.parse.urlencode(params, doseq=True)


# ---------------------------------------------------------------- SoundCloud

class _SoundCloud:
    API = "https://api-v2.soundcloud.com"

    def __init__(self) -> None:
        import yt_dlp
        from yt_dlp.extractor.soundcloud import SoundcloudSearchIE

        self.ie = SoundcloudSearchIE(yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}))
        if hasattr(self.ie, "_initialize_pre_login"):
            self.ie._initialize_pre_login()
        self.ie._real_initialize()

    def api(self, path: str, **query) -> dict:
        return self.ie._call_api(f"{self.API}{path}", None, query=query)

    @staticmethod
    def candidate(t: dict) -> Candidate | None:
        if not t.get("title") or not t.get("permalink_url"):
            return None
        pm = t.get("publisher_metadata") or {}
        flags = []
        if pm.get("isrc"):
            flags.append("ISRC")
        if pm.get("p_line") or pm.get("c_line") or pm.get("release_title") and pm.get("album_title"):
            flags.append("label line")
        policy = t.get("policy")
        if policy and policy not in ("ALLOW",):
            flags.append(f"policy {policy}")
        model = t.get("monetization_model")
        if model and model not in ("NOT_APPLICABLE",):
            flags.append(model.lower())
        uploader = (t.get("user") or {}).get("username") or ""
        title = t["title"]
        artist = pm.get("artist") or uploader
        # a self-upload names its uploader in the title or has just the song name;
        # "Other Artist - Song" from someone else is a re-upload (Content ID risk)
        up = key(uploader)
        generic = re.search(r"\b(music|hub|lyrics?|nhac|chill|official|records|playlist|tiktok|remix|vn|channel)\b", up)
        named = any(w in key(title).split() for w in up.split() if len(w) > 2) or (up and up.replace(" ", "") in key(title).replace(" ", ""))
        self_upload = bool(up) and not generic and (named or (" - " not in title and int(t.get("playback_count") or 0) < 2_000_000))
        if pm.get("artist") and key(pm["artist"]) not in (up, "") and up not in key(pm["artist"]):
            self_upload = False
        if flags:
            safety = "distributed"
        elif self_upload:
            safety = "artist"
        else:
            safety = "unknown"
            flags.append("re-upload?")
            if " - " in title and not pm.get("artist"):
                artist, title = [x.strip() for x in title.split(" - ", 1)]
        return Candidate("soundcloud", str(t["id"]), t["permalink_url"], artist, title,
                         (t.get("duration") or 0) / 1000, int(t.get("playback_count") or 0),
                         license=t.get("license") or "", safety=safety, flags=flags, genre=t.get("genre") or "",
                         fans=int((t.get("user") or {}).get("followers_count") or 0),
                         verified=bool((t.get("user") or {}).get("verified")))

    def search(self, query: str, limit: int, money_only: bool = False) -> list[Candidate]:
        out: list[Candidate] = []
        extra = {"filter.license": "to_modify_commercially"} if money_only else {}
        data = self.api("/search/tracks", q=query, limit=min(limit, 100), offset=0, linked_partitioning=1, **extra)
        for t in data.get("collection", []):
            c = self.candidate(t)
            if c:
                out.append(c)
        if money_only:  # user sets mix every licence: not worth the time here
            return out
        # popular user-made sets give more variety than plain track search
        sets = self.api("/search/playlists_without_albums", q=query, limit=6, offset=0, linked_partitioning=1)
        for s in sorted(sets.get("collection", []), key=lambda s: -(s.get("likes_count") or 0))[:3]:
            check_cancel()
            out += self.resolve_set(s.get("permalink_url", ""), limit=80)
        return out

    def resolve_set(self, url: str, limit: int = 200) -> list[Candidate]:
        if not url:
            return []
        pl = self.api("/resolve", url=url)
        tracks = pl.get("tracks", [])[:limit] if pl.get("kind") == "playlist" else [pl]
        full = {t["id"]: t for t in tracks if t.get("title")}
        missing = [t["id"] for t in tracks if t["id"] not in full]
        for i in range(0, len(missing), 50):
            for t in self.ie._call_api(f"{self.API}/tracks", None, query={"ids": ",".join(map(str, missing[i:i + 50]))}):
                full[t["id"]] = t
        out = []
        for t in tracks:
            c = self.candidate(full.get(t["id"]) or {})
            if c:
                out.append(c)
        return out


# ---------------------------------------------------------------- YouTube

_OFFICIAL = re.compile(r"(vevo|official|- topic|records|entertainment|music group|media)$", re.I)


def _yt_entries(target: str) -> list[dict]:
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False) or {}
    return [e for e in info.get("entries") or [info] if e]


def _yt_candidate(e: dict) -> Candidate | None:
    vid = e.get("id")
    if not vid or not e.get("title"):
        return None
    channel = e.get("channel") or e.get("uploader") or ""
    title = e["title"]
    artist, _, rest = title.partition(" - ")
    if not rest:
        artist, rest = channel, title
    flags = ["official channel"] if _OFFICIAL.search(channel.strip()) else []
    if re.search(r"official (mv|music video|audio|video)", title, re.I):
        flags.append("official release")
    url = e.get("url") if str(e.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={vid}"
    return Candidate("youtube", vid, url, artist.strip(), rest.strip(), float(e.get("duration") or 0),
                     int(e.get("view_count") or 0), safety="distributed" if flags else "unknown", flags=flags)


def youtube_search(query: str, limit: int) -> list[Candidate]:
    out = []
    for e in _yt_entries(f"ytsearch{min(limit, 60)}:{query}"):
        c = _yt_candidate(e)
        if c:
            out.append(c)
    return out


def youtube_playlist(url: str) -> list[Candidate]:
    return [c for c in (_yt_candidate(e) for e in _yt_entries(url)) if c]


# ---------------------------------------------------------------- Audius

_audius_host = ""


def audius_host() -> str:
    global _audius_host
    if not _audius_host:
        try:
            hosts = http_json("https://api.audius.co").get("data") or []  # type: ignore[union-attr]
            _audius_host = hosts[0] if hosts else "https://discoveryprovider.audius.co"
        except (OSError, ValueError, IndexError):
            _audius_host = "https://discoveryprovider.audius.co"
    return _audius_host


def audius_search(query: str, limit: int) -> list[Candidate]:
    host = audius_host()
    data = http_json(f"{host}/v1/tracks/search?" + _q({"query": query, "app_name": "PlaylistKit",
                                                        "limit": min(limit, 50)}))
    out = []
    for t in data.get("data") or []:  # type: ignore[union-attr]
        if not t.get("id") or t.get("is_streamable") is False:
            continue
        user = t.get("user") or {}
        out.append(Candidate("audius", t["id"], f"https://audius.co{t.get('permalink', '')}", user.get("name") or "",
                             t.get("title") or "", float(t.get("duration") or 0), int(t.get("play_count") or 0),
                             download=f"{host}/v1/tracks/{t['id']}/stream?app_name=PlaylistKit",
                             license="artist upload (Audius)", safety="artist", genre=t.get("genre") or ""))
    return out


# ---------------------------------------------------------------- Jamendo

def jamendo_search(tags: list[str], query: str, limit: int, client_id: str) -> list[Candidate]:
    if not client_id:
        log("   Jamendo skipped: add your free Jamendo client ID in Settings (devportal.jamendo.com).")
        return []
    params = {"client_id": client_id, "format": "json", "limit": min(limit, 200), "include": "musicinfo licenses",
              "audioformat": "mp32", "order": "popularity_total", "audiodlformat": "mp32"}
    if tags:
        params["fuzzytags"] = " ".join(tags[:3])
    elif query:
        params["search"] = query
    data = http_json("https://api.jamendo.com/v3.0/tracks/?" + _q(params))
    out = []
    for t in data.get("results") or []:  # type: ignore[union-attr]
        dl = t.get("audiodownload") if t.get("audiodownload_allowed") else ""
        out.append(Candidate("jamendo", str(t.get("id")), t.get("shareurl") or "", t.get("artist_name") or "",
                             t.get("name") or "", float(t.get("duration") or 0),
                             int((t.get("stats") or {}).get("listened") or 0), download=dl or t.get("audio") or "",
                             license=t.get("license_ccurl") or "Creative Commons", safety="cc"))
    return out


# ---------------------------------------------------------------- Internet Archive

def archive_search(tags: list[str], limit: int, money_only: bool = False) -> list[Candidate]:
    subj = " OR ".join(f'subject:"{t}"' for t in tags[:3]) or "subject:music"
    # opensource_audio is open to any uploader, who sets the licence (commercial mixtapes marked CC turn up there);
    # for monetizing only the netlabels collection counts: releases by labels that chose the licence
    coll = "collection:netlabels" if money_only else "(collection:netlabels OR collection:opensource_audio)"
    q = f"mediatype:audio AND {coll} AND ({subj}) AND licenseurl:*creativecommons*"
    data = http_json("https://archive.org/advancedsearch.php?" + _q({
        "q": q, "fl[]": ["identifier", "title", "creator", "licenseurl", "downloads"], "rows": 60 if money_only else 12,
        "sort[]": "downloads desc", "output": "json"}))
    out: list[Candidate] = []
    docs = (data.get("response") or {}).get("docs") or []  # type: ignore[union-attr]
    if money_only:  # the licence is on the album: skip NC / ND albums before reading their files
        docs = [d for d in docs if licence(str(d.get("licenseurl") or "")).ok][:12]
    for doc in docs:
        check_cancel()
        ident = doc.get("identifier")
        if not ident:
            continue
        try:
            meta = http_json(f"https://archive.org/metadata/{ident}")
        except (OSError, ValueError):
            continue
        creator = doc.get("creator") or ""
        creator = creator[0] if isinstance(creator, list) else creator
        files = [f for f in meta.get("files") or [] if "MP3" in str(f.get("format", ""))]  # type: ignore[union-attr]
        files.sort(key=lambda f: (str(f.get("format")) != "VBR MP3", f.get("name", "")))
        seen = set()
        for f in files:
            name = f.get("name", "")
            stem = Path(name).stem
            if stem in seen:
                continue
            seen.add(stem)
            length = f.get("length") or 0
            try:
                secs = float(length) if ":" not in str(length) else sum(
                    float(x) * 60 ** i for i, x in enumerate(reversed(str(length).split(":"))))
            except ValueError:
                secs = 0.0
            out.append(Candidate("archive", f"{ident}/{name}", f"https://archive.org/details/{ident}",
                                 f.get("artist") or f.get("creator") or creator, f.get("title") or stem, secs,
                                 int(doc.get("downloads") or 0) // max(1, len(files)),
                                 download=f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}",
                                 license=doc.get("licenseurl") or "", safety="cc"))
            if len(out) >= limit:
                return out
    return out


# ---------------------------------------------------------------- ccMixter

def ccmixter_search(tags: list[str], limit: int) -> list[Candidate]:
    out: list[Candidate] = []
    for tag in (tags[:3] or ["chill"]):  # ccMixter ANDs tags, so ask one tag at a time
        # f=js, not f=json: json also repeats the whole answer in an X-JSON header, and past ~18 songs that
        # header is longer than Python accepts (64 KB), so every ccMixter search failed
        data = http_json("https://ccmixter.org/api/query?" + _q({"f": "js", "tags": tag, "limit": min(limit, 60),
                                                                  "sort": "rank"}))
        for u in data if isinstance(data, list) else []:
            files = [f for f in u.get("files") or [] if str(f.get("download_url", "")).lower().endswith(".mp3")]
            if not files:
                continue
            ps = (files[0].get("file_format_info") or {}).get("ps") or "0"
            try:
                secs = sum(float(x) * 60 ** i for i, x in enumerate(reversed(str(ps).split(":"))))
            except ValueError:
                secs = 0.0
            out.append(Candidate("ccmixter", str(u.get("upload_id")), u.get("file_page_url") or "",
                                 u.get("user_real_name") or u.get("user_name") or "", u.get("upload_name") or "", secs,
                                 int(u.get("upload_num_scores") or 0), download=files[0]["download_url"],
                                 license=u.get("license_url") or u.get("license_name") or "Creative Commons",
                                 safety="cc"))
    return out


# ---------------------------------------------------------------- local

def local_folder(folder: Path) -> list[Candidate]:
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in AUDIO_EXT:
            stem = re.sub(r"^\d+\s*-\s*", "", p.stem)
            artist, _, title = stem.partition(" - ")
            if not title:
                artist, title = "", stem
            out.append(Candidate("local", str(p), str(p), artist.strip(), title.strip(), download=str(p),
                                 safety="unknown", license="your file"))
    return out


# ---------------------------------------------------------------- search + pick

def search(genre: Genre, sources: list[str], want: int, settings: dict, extra: str = "",
           progress: Callable[[str], None] = log, money_only: bool = False) -> list[Candidate]:
    """Collect candidates from the chosen sources. `extra` is a custom query, a set/playlist URL or a folder.
    money_only: look only where licences allow a monetized remix (pick() then drops the rest)."""
    found: list[Candidate] = []
    per = max(30, want * 3) * (3 if money_only else 1)  # many Creative Commons songs are NC or ND
    extra = extra.strip().strip('"')
    if extra:
        if Path(extra).is_dir():
            progress(f"Reading songs from {extra}")
            return local_folder(Path(extra))
        if "soundcloud.com/" in extra:
            progress(f"SoundCloud: {extra}")
            return _SoundCloud().resolve_set(extra, limit=500)
        if "youtube.com/" in extra or "youtu.be/" in extra:
            progress(f"YouTube: {extra}")
            return youtube_playlist(extra)
    queries = [extra] if extra else list(genre.queries)
    sc = None
    if money_only:
        skipped = [SOURCES[s] for s in sources if s in NO_LICENCE]
        if skipped:
            progress(f"   Skipping {', '.join(skipped)}: songs there have no licence that allows monetizing")
        sources = [s for s in sources if s not in NO_LICENCE]
    for src in sources:
        check_cancel()
        try:
            if src == "soundcloud":
                sc = sc or _SoundCloud()
                for q in queries[:3]:
                    progress(f"SoundCloud: searching '{q}'" + (" (licence allows commercial changes)" if money_only else ""))
                    found += sc.search(q, min(per, 100), money_only)
            elif src == "youtube":
                for q in queries[:3]:
                    progress(f"YouTube: searching '{q}'")
                    found += youtube_search(q, per // 2)
            elif src == "audius":
                for q in queries[:2]:
                    progress(f"Audius: searching '{q}'")
                    found += audius_search(q, per)
            elif src == "jamendo":
                progress(f"Jamendo: tags {', '.join(genre.tags[:3])}")
                found += jamendo_search(list(genre.tags) if not extra else [], extra, per,
                                        settings.get("jamendo_client_id", ""))
            elif src == "archive":
                progress(f"Internet Archive: {', '.join(genre.tags[:3])}")
                found += archive_search(list(genre.tags), per, money_only)
            elif src == "ccmixter":
                progress(f"ccMixter: {', '.join(genre.tags[:2])}")
                found += ccmixter_search(list(genre.tags), per)
        except PlaylistKitError:
            raise
        except Exception as exc:  # noqa: BLE001 - one broken source should not stop the others
            progress(f"   {SOURCES.get(src, src)} failed: {str(exc)[:200]}")
        progress(f"   {len(found)} songs so far")
    return found


# on SoundCloud, a CC licence on a remix / cover covers only the remixer's part, never the original song
# (ccMixter remixes are different: they are built from Creative Commons stems)
_NOT_THEIRS = re.compile(r"\b(remix|rmx|cover|bootleg|flip|mashup|edit|rework|vip mix|nightcore|sped up|slowed)\b", re.I)


# songs Content ID knows: a well-known artist is almost always registered with a label or distributor,
# and a cover is claimed by whoever wrote the song (melody / lyrics claims)
BIG_FANS, BIG_PLAYS = 50_000, 200_000
KNOWN_FANS, KNOWN_PLAYS = 5_000, 50_000
_COVER = re.compile(r"\b(cover|covered by|written by|original by|ost)\b|\b(ca sĩ|sáng tác|st|composer)\s*:", re.I)


def fame(c: Candidate) -> tuple[int, str]:
    """(2 well-known / 1 fairly known / 0 small, why). Small artists are the ones Content ID rarely knows."""
    if c.source == "local":
        return 0, ""
    if c.verified or c.fans >= BIG_FANS or c.plays >= BIG_PLAYS:
        why = "verified artist" if c.verified else (f"{c.fans:,} followers" if c.fans >= BIG_FANS else f"{c.plays:,} plays")
        return 2, f"well-known ({why}): Content ID likely"
    if c.fans >= KNOWN_FANS or c.plays >= KNOWN_PLAYS:
        why = f"{c.fans:,} followers" if c.fans >= KNOWN_FANS else f"{c.plays:,} plays"
        return 1, f"fairly known ({why}): may be claimed"
    return 0, ""


def money_skip(c: Candidate) -> str:
    """Why a song cannot go into a monetized remix ('' when it can). Your own files are your call."""
    if c.source == "local":
        return ""
    lic = licence(c.license)
    if not lic.ok:
        return f"licence: {lic.why}"
    if c.source == "soundcloud" and (c.safety != "artist" or c.flags):
        return "licence set by someone who may not own the song"
    if c.source == "soundcloud" and _NOT_THEIRS.search(f"{c.artist} {c.title}"):
        return "remix or cover: the original song is not theirs to license"
    return ""


def song_rights(info: dict) -> dict:
    """{'lic', 'money'} for a downloaded song (download.song_info). Your own files: money is None (your call)."""
    if (info.get("source") or "local") == "local":
        return {"lic": "your file", "money": None}
    c = Candidate(info["source"], "", info.get("url", ""), info.get("artist", ""), info.get("title", ""),
                  license=info.get("license", ""), safety=info.get("safety", "unknown"))
    lic = licence(c.license)
    return {"lic": lic.label if lic.cc else "no licence", "money": not money_skip(c)}


def pick(cands: list[Candidate], genre: Genre, want: int, backlog: Backlog, banned: list[str],
         allow_used_artists: bool = False, allow_distributed: bool = False, money_only: bool = False) -> list[Candidate]:
    """Filter and rank; the best `want` songs are pre-selected, one per artist.
    money_only: only songs whose licence allows a monetized remix (CC BY, CC BY-SA, CC0, public domain)."""
    soft = genre.style in ("indie", "lofi")
    banned_set = backlog.banned_artists(banned)
    seen_ids: set[str] = set()
    best_by_title: dict[str, Candidate] = {}
    for c in cands:
        lic = licence(c.license)
        c.lic = "your file" if c.source == "local" else (lic.label if lic.cc else "")
        c.money = not money_skip(c) and c.source != "local"
        uid = f"{c.source}:{c.sid}"
        if uid in seen_ids:
            c.skip = "duplicate"
            continue
        seen_ids.add(uid)
        t = key(f"{c.title}")
        claimed_before = False
        text = key(f"{c.artist} {c.title} {c.genre}")
        if c.source != "local" and c.duration and not genre.min_sec <= c.duration <= genre.max_sec:
            c.skip = f"length {int(c.duration // 60)}:{int(c.duration % 60):02d}"
        elif c.source == "youtube" and c.plays < 5000:
            c.skip = "few views"
        elif c.source != "local" and JUNK.search(text):
            c.skip = "not a single song"
        elif soft and c.source != "local" and SOFT_JUNK.search(text):
            c.skip = f"not {genre.name}"
        else:  # the backlog warns about songs and artists used or claimed before; only removed songs are skipped
            c.skip, c.warn, c.hold = backlog.review(c.artist, c.title, allow_used_artists, banned_set)
            claimed_before = c.hold
            level, why = fame(c)
            if c.source == "soundcloud" and c.safety == "unknown" and not level:
                level, why = 2, "uploaded by someone else (re-upload?): its owner can claim it"
            if c.source != "local" and _COVER.search(f"{c.artist} {c.title}"):
                level, why = 2, "someone else wrote this song (cover): its writer can claim it"
            if level:
                c.warn = "; ".join(w for w in (c.warn, why) if w)
                c.hold = c.hold or level == 2
        if not c.skip and c.safety == "distributed" and not allow_distributed and genre.risk != "high":
            c.skip = "distributed release (Content ID likely)"
        if not c.skip and money_only:
            c.skip = money_skip(c) or ("claimed by Content ID before" if claimed_before else "")
        # some plays show people like it; past ~20k more plays only means Content ID is more likely to know it
        c.score = SAFETY_SCORE.get(c.safety, 1.0) + min(math.log10(c.plays + 10), 4.3) / 2
        if c.warn:  # new songs come first; a song with a warning fills the playlist only when needed
            c.score -= 4.0 if c.hold else 1.5
        prev = best_by_title.get(t)
        if not c.skip and prev and not prev.skip:
            if c.score > prev.score:
                prev.skip = "duplicate"
            else:
                c.skip = "duplicate"
                continue
        if not c.skip:
            best_by_title[t] = c
    ok = sorted((c for c in cands if not c.skip), key=lambda c: -c.score)
    artists: set[str] = set()
    by_source: dict[str, list[Candidate]] = {}
    for c in ok:
        a = key(c.artist) or c.sid
        if a in artists:
            c.skip = "same artist"
            continue
        artists.add(a)
        by_source.setdefault(c.source, []).append(c)
    # share the playlist between sources in proportion to how many good songs each one found,
    # so one big catalogue does not fill it alone; the rest goes by score
    total = sum(len(q) for q in by_source.values())
    n = 0
    for q in by_source.values():
        for c in q[: round(want * len(q) / total) if total else 0]:
            if n < want and not c.hold:
                c.selected = True
                n += 1
    for c in ok:
        if n >= want:
            break
        if not c.skip and not c.selected and not c.hold:  # claimed songs are never ticked for you
            c.selected = True
            n += 1
    unique_cands, uids = [], set()
    for c in cands:
        uid = f"{c.source}:{c.sid}"
        if uid not in uids:
            uids.add(uid)
            unique_cands.append(c)
    return sorted(unique_cands, key=lambda c: (not c.selected, bool(c.skip), -c.score))
