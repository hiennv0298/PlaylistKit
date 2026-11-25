from pathlib import Path

import pytest

from playlistkit import cut, genres, meta, video
from playlistkit.backlog import Backlog
from playlistkit.sources import Candidate, pick


def test_genres_complete():
    assert len(genres.GENRES) >= 35
    for g in genres.GENRES.values():
        assert g.style in genres.STYLES
        assert g.queries and g.hashtags and g.yt_tags and g.risk in genres.RISK_TEXT
        g.blurb.format(n=3, dur_text="x", dur_en="y")


def test_backlog_blocks_used_and_claimed(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    bl.ban_artist("Vũ.")
    bl.mark("indie-1", "Hali", "Con Chim Phiêu Diêu", "claimed", "Content ID")
    bl.mark("indie-1", "Thỏ", "Em đi đâu", "used")
    bl2 = Backlog(tmp_path / "b.tsv")
    assert bl2.check("Vũ.", "Lạ Lùng") == "banned artist"
    assert bl2.check("Someone", "Vũ Trụ Có Anh") == ""
    assert "claimed" in bl2.check("Hali", "Bài khác")
    assert bl2.check("Someone", "Em đi đâu (Official Audio)") == "already in the backlog"
    assert bl2.check("Thỏ", "Bài mới") == "artist already used"
    assert bl2.check("Thỏ", "Bài mới", allow_used_artists=True) == ""
    assert bl2.check("New Artist", "New Song") == ""


def test_pick_one_per_artist_and_filters(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    g = genres.get("indie")
    c = [Candidate("soundcloud", "1", "u1", "A", "Song One", 200, 1000, safety="artist"),
         Candidate("soundcloud", "2", "u2", "A", "Song Two", 200, 5000, safety="artist"),
         Candidate("soundcloud", "3", "u3", "B", "Song Three (Remix)", 200, 9000, safety="artist"),
         Candidate("soundcloud", "4", "u4", "C", "Song Four", 30, 9000, safety="artist"),
         Candidate("soundcloud", "5", "u5", "D", "Song Five", 200, 9, safety="distributed"),
         Candidate("jamendo", "6", "u6", "E", "Song Six", 200, 9, safety="cc"),
         Candidate("jamendo", "6", "u6", "E", "Song Six", 200, 9, safety="cc")]
    out = pick(c, g, 5, bl, [])
    sel = [x.sid for x in out if x.selected]
    assert sorted(sel) == ["2", "6"]
    skips = {x.sid: x.skip for x in out}
    assert skips["1"] == "same artist" and "not" in skips["3"] and "length" in skips["4"]
    assert "distributed" in skips["5"]
    assert len(out) == 6


def test_clean_track_name():
    assert meta.clean_track_name("Hali - Con Chim Phiêu Diêu - Hali") == "Hali - Con Chim Phiêu Diêu"
    assert meta.clean_track_name("Bluemato - Bluemato - Chuyến tàu xanh [EP version]") == "Bluemato - Chuyến tàu xanh [EP version]"
    assert meta.clean_track_name("Phạm Nguyên Ngọc - Lâu Không Cười ⧸ Phạm Nguyên Ngọc") == "Phạm Nguyên Ngọc - Lâu Không Cười"
    assert meta.clean_track_name("dím - ẩm ương (original)") == "dím - ẩm ương"
    assert meta.clean_track_name("Đồng Nart - Mỗi Khi - Đồng Nart [Demo]") == "Đồng Nart - Mỗi Khi (Demo)"
    assert meta.clean_track_name("chee - hà nội có phải là anh? - original by hnhngan") == "chee - hà nội có phải là anh?"
    assert meta.default_name([(0, "x"), (9, "chee - Hà Nội Có Phải Là Anh? - original by hnhngan")]) == "hà nội có phải là anh?"


def test_meta_build():
    g = genres.get("indie")
    m = meta.build(g, "chuyện mưa", [(0, "A - One"), (245, "B - Two")], 4935)
    assert m["title"] == "chuyện mưa 🌙 | 1 giờ 22 phút"
    assert "00:00 A - One" in m["description"] and "04:05 B - Two" in m["description"]
    assert m["description"].rstrip().endswith("#indieviet #nhacchill #playlist")
    assert len(m["tags"]) <= 500 and "indie việt" in m["tags"]


TRACKS = [(0, "a"), (120, "b"), (300, "c"), (480, "d"), (700, "e")]


def test_cut_plan_maps_claims_and_merges_neighbours():
    claims = cut.parse_claims("[2:00 — 4:58](https://x) 5:01 — 8:02\n11:50 - 11:55")
    plan = cut.plan_cut(TRACKS, 900, claims)
    # 4:58 and 8:02 reach 2 s into the next songs: those are not claimed; a short claim inside e is
    assert [TRACKS[i][1] for i in plan.claimed] == ["b", "c", "e"]
    assert plan.remove == [(120, 482), (700, 900)]
    assert plan.keep == [(0, 120), (482, 700)]
    assert [n for _, n in plan.new_tracks] == ["a", "d"]
    assert plan.new_tracks[1][0] == pytest.approx(117)  # 120 - 3 s crossfade
    assert plan.new_duration == pytest.approx(120 + 218 - 3)


def test_cut_rejects_unknown_ranges():
    with pytest.raises(Exception):
        cut.plan_cut(TRACKS, 900, cut.parse_claims("nothing here"))


def test_video_cmd():
    cmd = video.build_cmd(Path("ffmpeg"), Path("t.png"), Path("a.wav"), Path("o.mp4"), "480p", 100.0)
    s = " ".join(cmd)
    assert "scale=854:480" in s and "-tune stillimage" in s and "-t 100.000" in s and "aac" in s
    with pytest.raises(Exception):
        video.build_cmd(Path("ffmpeg"), Path("t.png"), Path("a.wav"), Path("o.mp4"), "4k", 1)
