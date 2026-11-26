import base64

import pytest

from playlistkit import project, thumbnail
from playlistkit.util import PlaylistKitError

JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def url(raw: bytes, kind: str = "jpeg") -> str:
    return f"data:image/{kind};base64," + base64.b64encode(raw).decode()


@pytest.fixture
def proj(tmp_path):
    return project.create(tmp_path, "indie", "demo")


def test_saves_made_thumbnail_and_design(proj):
    (proj.dir / "thumb.png").write_bytes(PNG)
    name = thumbnail.save(proj, url(JPG), {"look": "night", "title": "mưa"}, auto=True)
    assert name == "thumb.jpg" and (proj.dir / "thumb.jpg").read_bytes() == JPG
    assert not (proj.dir / "thumb.png").exists()  # one thumbnail at a time
    again = project.load(proj.dir.parent, proj.id)
    assert again.data["thumb_auto"] is True and again.data["thumb_design"]["title"] == "mưa"
    assert again.data["thumb"].endswith("thumb.jpg")


def test_png_and_manual_save(proj):
    assert thumbnail.save(proj, url(PNG, "png"), None, auto=False) == "thumb.png"
    assert proj.data["thumb_auto"] is False and "thumb_design" not in proj.data


@pytest.mark.parametrize("bad", ["", "data:text/html;base64,PGI+", url(b"GIF89a....")])
def test_rejects_other_data(proj, bad):
    with pytest.raises(PlaylistKitError):
        thumbnail.save(proj, bad)
