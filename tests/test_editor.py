from pathlib import Path

import pytest

from playlistkit import editor, project
from playlistkit.util import PlaylistKitError


@pytest.fixture
def proj(tmp_path, monkeypatch):
    p = project.create(tmp_path, "indie", "demo")
    p.out.mkdir()
    (p.out / f"{p.id}_indie.wav").write_bytes(b"x")
    (p.out / "tracklist_indie.txt").write_text("00:00 A - One\n02:00 B - Two - B\n04:00 C - Three\n", encoding="utf-8")
    (p.dir / "thumb.png").write_bytes(b"x")
    monkeypatch.setattr(editor, "_probe", lambda path: {"dur": 300.0, "w": 1280, "h": 720, "audio": True})

    class FF:
        ffmpeg = Path("ffmpeg")
        ffprobe = Path("ffprobe")

    monkeypatch.setattr(editor, "find_ffmpeg", lambda: FF)
    monkeypatch.setattr(editor, "nvenc_available", lambda _: False)
    return p


def test_default_edit_and_titles(proj):
    e = editor.default_edit(proj)
    assert [c["media"] for c in e["video"]] == ["thumb/thumb.png"]
    assert e["audio"][0]["dur"] == 300 and e["overlay"][0]["kind"] == "nowplaying"
    e["audio"][0].update(start=10, **{"in": 60})  # start the mix at 1:00, 10 s into the video
    titles = editor.song_titles(proj, e)
    assert titles[0][2] == "A - One" and titles[0][0] == 10 and titles[0][1] == 70
    assert titles[1][2] == "B - Two" and titles[1][0] == 70


def test_clean_edit_rejects_outside_files(proj):
    with pytest.raises(PlaylistKitError):
        editor.clean_edit(proj, {"video": [{"media": "out/../../secret.png"}]})
    with pytest.raises(PlaylistKitError):
        editor.clean_edit(proj, {"audio": [{"media": "thumb/project.json"}]})
    e = editor.clean_edit(proj, {"res": "4k", "overlay": [{"kind": "evil"}, {"kind": "text", "pos": "nowhere", "color": "red"}]})
    assert e["res"] == "720p" and len(e["overlay"]) == 1
    assert e["overlay"][0]["pos"] == "bottom-left" and e["overlay"][0]["color"] == "#ffffff"


def test_export_command(proj, tmp_path):
    e = editor.default_edit(proj)
    e["overlay"] += [{"kind": "wave", "start": 0, "dur": 300, "pos": "bottom", "size": 4},
                     {"kind": "progress", "start": 0, "dur": 300, "pos": "bottom", "size": 4},
                     {"kind": "text", "start": 0, "dur": 5, "text": "Hello 🌧️", "pos": "top", "size": 6}]
    e = editor.clean_edit(proj, e)
    cmd, total, fps = editor.build_export(proj, e, tmp_path / "o.mp4", tmp_path / "tmp")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert total == 300 and fps == 15
    assert "showwaves" in graph and "drawtext" in graph and "amix" in graph and "boxblur" in graph
    assert (tmp_path / "tmp").glob("text*.txt")
    texts = sorted((tmp_path / "tmp").glob("text*.txt"))
    assert any(t.read_text(encoding="utf-8") == "Hello" for t in texts)  # emoji stripped
    assert any("A - One" == t.read_text(encoding="utf-8") for t in texts)


def test_empty_timeline(proj, tmp_path):
    with pytest.raises(PlaylistKitError):
        editor.build_export(proj, editor.clean_edit(proj, {}), tmp_path / "o.mp4", tmp_path / "t")


def test_positions():
    assert editor._xy("bottom-left") == ("h*0.05", "h-text_h-h*0.05")
    assert editor._xy("top") == ("(w-text_w)/2", "h*0.05")
    assert editor._xy("center") == ("(w-text_w)/2", "(h-text_h)/2")
