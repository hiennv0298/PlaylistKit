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


def test_parts():
    assert editor._parts(600, 15) == [(0, 300), (300, 600)]
    assert editor._parts(4527, 2)[-1] == (4500, 4527)
    assert editor._parts(600.4, 15) == [(0, 300), (300, 600.4)]  # no part of a few frames at the end
    assert editor._parts(120, 2) == [(0, 120)]


def test_a_part_starts_where_the_timeline_is(proj, tmp_path):
    e = editor.default_edit(proj)
    e["overlay"] += [{"kind": "wave", "start": 0, "dur": 300, "pos": "bottom", "size": 4},
                     {"kind": "progress", "start": 0, "dur": 300, "pos": "bottom", "size": 4}]
    e = editor.clean_edit(proj, e)
    cmd, total, fps = editor.build_export(proj, e, tmp_path / "p.ts", tmp_path / "t", 120, 180, mode="video")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert cmd[-3:] == ["-f", "mpegts", str(tmp_path / "p.ts")] and "-map" in cmd and "[aout]" not in graph
    assert "-t" in cmd and cmd[cmd.index("-t", len(cmd) - 6) + 1] == "60.000"
    assert "(t+120.000)" in graph  # the progress bar carries on from 2:00
    assert "trim=start=1.000000" in graph  # the wave starts a second early, then drops those pictures
    assert "-ss" in cmd and "119.000" in cmd  # its sound from 1:59
    audio, _, _ = editor.build_export(proj, e, tmp_path / "a.m4a", tmp_path / "t2", mode="audio")
    assert "[amix]" in audio and "showwaves" not in audio[audio.index("-filter_complex") + 1]


def test_fingerprint_follows_what_is_drawn(proj, tmp_path):
    e = editor.clean_edit(proj, editor.default_edit(proj))
    texts = tmp_path / "t"
    texts.mkdir()
    cmd, _, _ = editor.build_export(proj, e, tmp_path / "x.ts", texts, 0, 300, mode="video")
    a = editor._fingerprint(cmd, texts, "m")
    assert a == editor._fingerprint(cmd[:-1] + ["elsewhere.ts"], texts, "m")  # where it is written does not count
    assert a != editor._fingerprint(cmd, texts, "m2")  # a replaced picture or song does
    (texts / "text0.txt").write_text("new title", encoding="utf-8")
    assert a != editor._fingerprint(cmd, texts, "m")


def test_empty_timeline(proj, tmp_path):
    with pytest.raises(PlaylistKitError):
        editor.build_export(proj, editor.clean_edit(proj, {}), tmp_path / "o.mp4", tmp_path / "t")


def test_positions():
    assert editor._xy("bottom-left") == ("h*0.05", "h-text_h-h*0.05")
    assert editor._xy("top") == ("(w-text_w)/2", "h*0.05")
    assert editor._xy("center") == ("(w-text_w)/2", "(h-text_h)/2")
