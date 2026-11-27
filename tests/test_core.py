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


def test_backlog_warns_instead_of_hiding(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    bl.ban_artist("Vũ.")
    bl.mark("lofi-1", "Lamp", "Hatachi No Koi", "claimed", "Content ID: cannot be monetized")
    bl.mark("lofi-1", "Thỏ", "Em đi đâu", "used")
    bl.mark("lofi-1", "Ai Đó", "Bài dở", "bad-quality")
    assert bl.review("Vũ.", "Lạ Lùng")[0] == "banned artist"
    assert bl.review("Someone", "Bài dở")[0].startswith("removed before")
    skip, warn, hold = bl.review("Lamp", "Hatachi No Koi (Official Audio)")
    assert not skip and hold and "cannot be monetized" in warn and "lofi-1" in warn
    skip, warn, hold = bl.review("Lamp", "Another Song")  # the artist was claimed
    assert not skip and hold and "claimed" in warn
    assert bl.review("Someone", "Em đi đâu") == ("", "already used in lofi-1", False)
    assert bl.review("Thỏ", "Bài mới") == ("", "artist used before", False)
    assert bl.review("Thỏ", "Bài mới", allow_used_artists=True) == ("", "", False)
    assert bl.claimed_titles() == {"hatachi no koi": "lofi-1"}


def test_pick_warns_and_never_ticks_claimed_songs(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    bl.mark("lofi-1", "Lamp", "Hatachi No Koi", "claimed")
    bl.mark("lofi-1", "Thỏ", "Em đi đâu", "used")
    c = [Candidate("jamendo", "1", "u", "Lamp", "Hatachi No Koi", 200, 9999, license="cc-by", safety="cc"),
         Candidate("jamendo", "2", "u", "Thỏ", "Em đi đâu", 200, 9999, license="cc-by", safety="cc"),
         Candidate("jamendo", "3", "u", "New", "Fresh", 200, 10, license="cc-by", safety="cc")]
    out = {x.sid: x for x in pick(c, genres.GENRES["chill"], 5, bl, [])}
    assert not out["1"].skip and out["1"].hold and not out["1"].selected  # shown, warned, not ticked
    assert not out["2"].skip and out["2"].warn and out["2"].selected     # used before: a warning only
    assert out["3"].selected and not out["3"].warn
    money = {x.sid: x for x in pick(c, genres.GENRES["chill"], 5, bl, [], money_only=True)}
    assert money["1"].skip == "claimed by Content ID before"


def test_pick_holds_well_known_artists_and_covers(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    g = genres.get("indie")
    c = [Candidate("soundcloud", "1", "u", "Ngọt", "Vé đi thiên đường", 200, 266_000, safety="artist", fans=120_000),
         Candidate("soundcloud", "2", "u", "TRANG", "Nắng", 200, 900, safety="artist", verified=True),
         Candidate("soundcloud", "3", "u", "ACENS", "Tình thôi", 200, 52_000, safety="artist", fans=8_000),
         Candidate("soundcloud", "4", "u", "th.", "Thế Thôi (cover)", 200, 300, safety="artist"),
         Candidate("soundcloud", "5", "u", "TRANG", "Nắng | Sáng tác: TRANG x Ca sĩ: PKL", 200, 900, safety="artist"),
         Candidate("soundcloud", "6", "u", "zux", "cho. ai?", 200, 122, safety="artist", fans=3)]
    out = {x.sid: x for x in pick(c, genres.GENRES["vpop"], 6, bl, [])}  # indie and lofi skip covers outright
    assert out["1"].hold and "120,000 followers" in out["1"].warn and not out["1"].selected
    assert out["2"].hold and "verified" in out["2"].warn
    assert not out["3"].hold and "fairly known" in out["3"].warn and out["3"].selected  # a warning only
    assert out["4"].hold and "cover" in out["4"].warn
    assert out["5"].hold
    assert out["6"].selected and not out["6"].warn
    reup = Candidate("soundcloud", "9", "u", "Madihu", "Có Khi", 200, 4_000, safety="unknown")
    assert pick([reup], g, 1, bl, [])[0].hold
    # a small artist ranks above a big one with many more plays
    small = Candidate("soundcloud", "7", "u", "Small", "Bài nhỏ", 200, 20_000, safety="artist")
    big = Candidate("soundcloud", "8", "u", "Big", "Bài to", 200, 5_000_000, safety="artist")
    ranked = [x.sid for x in pick([big, small], g, 1, bl, []) if x.selected]
    assert ranked == ["7"]


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


STUDIO_CLAIMS = """Video: indie 1 edit 720p
Tổng quan về thông báo xác nhận quyền sở hữu
1:17:16
Video của bạn
indie 1 edit 720p
Thông báo xác nhận quyền sở hữu
Loại
Nghe Em
Bản quyền
Giai điệu hoặc lời bài hát
Không ảnh hưởng đến video.
Xem chi tiết
Chọn cách giải quyết
dear life
festo
Bản quyền
Âm thanh
Không ảnh hưởng đến video.
Xem chi tiết
Chọn cách giải quyết
EMVN - Tôi Và Em
Bản quyền
Giai điệu hoặc lời bài hát
Nội dung bị xác nhận quyền sở hữu: Cuối Chiều
8:10 — 9:19
"""


def test_claim_list_names_the_songs():
    assert cut.parse_claim_songs(STUDIO_CLAIMS) == [("", "Nghe Em"), ("festo", "dear life"), ("EMVN", "Tôi Và Em"),
                                                    ("", "Cuối Chiều")]
    assert cut.parse_claims(STUDIO_CLAIMS) == [(490.0, 559.0)]


def test_claimed_songs_warn_about_any_upload_of_them(tmp_path):
    bl = Backlog(tmp_path / "b.tsv")
    saved = cut.remember_claim_songs("indie-1", STUDIO_CLAIMS, bl)
    assert len(saved) == 4
    assert cut.remember_claim_songs("indie-1", STUDIO_CLAIMS, bl) == []  # saved once
    # a cover by someone else, under the claimed song's name, is held
    skip, warn, hold = bl.review("Someone", "Cuối Chiều (acoustic)")
    assert not skip and hold and "Content ID" in warn
    # the artist Content ID named is held too
    assert bl.review("festo", "new song")[2]
    assert not bl.review("Someone", "Bài mới")[2]
