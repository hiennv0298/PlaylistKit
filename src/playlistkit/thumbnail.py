"""The playlist's YouTube thumbnail made inside PlaylistKit.

The page draws it (webui/thumb.js: a 1280x720 canvas with the playlist name, the length and
a background made for the genre) and sends the picture here. It is saved as thumb.jpg in the
project folder, like a thumbnail you choose yourself, so Make MP4 and the video editor use it.
The design is kept in project.json so the window opens with the same choices next time.
"""
from __future__ import annotations

import base64
import re

from playlistkit.project import Project
from playlistkit.util import PlaylistKitError

MAX_BYTES = 12 * 1024 * 1024
_KINDS = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}


def save(p: Project, data_url: str, design: dict | None = None, auto: bool = False) -> str:
    """Save a data:image/jpeg|png;base64 picture as the thumbnail. Returns the file name."""
    m = re.fullmatch(r"data:image/(?:jpeg|png);base64,([A-Za-z0-9+/=\s]+)", data_url or "")
    if not m:
        raise PlaylistKitError("The thumbnail picture is missing.")
    raw = base64.b64decode(m.group(1))
    if not raw or len(raw) > MAX_BYTES:
        raise PlaylistKitError("The thumbnail picture is too large.")
    ext = next((e for magic, e in _KINDS.items() if raw.startswith(magic)), None)
    if not ext:
        raise PlaylistKitError("The thumbnail must be a JPG or PNG picture.")
    for old in p.dir.glob("thumb.*"):
        old.unlink(missing_ok=True)
    dest = p.dir / f"thumb{ext}"
    dest.write_bytes(raw)
    p.data["thumb"] = str(dest)
    p.data["thumb_auto"] = bool(auto)  # made by itself: it follows the playlist name until you edit it
    if isinstance(design, dict):
        p.data["thumb_design"] = design
    p.save()
    return dest.name


def chosen(p: Project) -> None:
    """A picture you chose yourself replaced the made one: stop updating it."""
    p.data["thumb_auto"] = False
    p.save()
