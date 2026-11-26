import pytest

from playlistkit import meta, project
from playlistkit.backlog import Backlog
from playlistkit.genres import GENRES
from playlistkit.sources import Candidate, licence, money_skip, pick, song_rights
from playlistkit.util import write_json


@pytest.mark.parametrize("text, label, ok", [
    ("http://creativecommons.org/licenses/by/3.0/", "CC BY 3.0", True),
    ("https://creativecommons.org/licenses/by-sa/4.0/", "CC BY-SA 4.0", True),
    ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0", True),
    ("http://creativecommons.org/publicdomain/mark/1.0/", "Public Domain", True),
    ("http://creativecommons.org/licenses/by-nc-sa/3.0/", "CC BY-NC-SA 3.0", False),
    ("http://creativecommons.org/licenses/by-nd/4.0/", "CC BY-ND 4.0", False),
    ("http://creativecommons.org/licenses/sampling+/1.0/", None, False),
    ("cc-by", "CC BY", True),
    ("cc-by-nc", "CC BY-NC", False),
    ("no-rights-reserved", "CC0", True),
    ("all-rights-reserved", None, False),
    ("Attribution Noncommercial (3.0)", None, False),
    ("Attribution", "CC BY", True),
    ("artist upload (Audius)", None, False),
    ("", None, False),
])
def test_licence(text, label, ok):
    lic = licence(text)
    assert lic.ok is ok
    if label:
        assert lic.label == label
    if not ok:
        assert lic.why


def cand(source, sid, lic, safety="cc", artist=None):
    return Candidate(source, sid, f"https://x/{sid}", artist or f"Artist {sid}", f"Song {sid}", 200, 1000,
                     license=lic, safety=safety)


def test_money_only_keeps_licences_that_allow_monetizing(tmp_path):
    cands = [cand("jamendo", "1", "http://creativecommons.org/licenses/by/3.0/"),
             cand("jamendo", "2", "http://creativecommons.org/licenses/by-nc/3.0/"),
             cand("archive", "3", "http://creativecommons.org/licenses/by-nd/3.0/"),
             cand("youtube", "4", "", "unknown"),
             cand("soundcloud", "5", "cc-by", "artist"),
             cand("soundcloud", "6", "cc-by", "unknown"),
             cand("ccmixter", "7", "https://creativecommons.org/publicdomain/zero/1.0/"),
             Candidate("soundcloud", "8", "u", "Beatz", "Halsey - Colors (Chill Remix)", 200, 1000, license="cc-by",
                       safety="artist")]
    out = {c.sid: c for c in pick(cands, GENRES["chill"], 10, Backlog(tmp_path / "b.tsv"), [], money_only=True)}
    assert {s for s, c in out.items() if not c.skip} == {"1", "5", "7"}
    assert money_skip(out["8"]).startswith("remix or cover") and not out["8"].money
    assert out["2"].skip.startswith("licence: NC") and out["3"].skip.startswith("licence: ND")
    assert out["1"].money and out["1"].lic == "CC BY 3.0" and not out["2"].money


def test_without_money_only_nothing_new_is_skipped(tmp_path):
    cands = [cand("jamendo", "2", "http://creativecommons.org/licenses/by-nc/3.0/")]
    out = pick(cands, GENRES["chill"], 10, Backlog(tmp_path / "b.tsv"), [])
    assert not out[0].skip and out[0].selected and not out[0].money


def test_song_rights():
    assert song_rights({"source": "local"}) == {"lic": "your file", "money": None}
    assert song_rights({"source": "jamendo", "license": "http://creativecommons.org/licenses/by-sa/3.0/", "safety": "cc"}) \
        == {"lic": "CC BY-SA 3.0", "money": True}
    assert song_rights({"source": "youtube", "license": "", "safety": "unknown"})["money"] is False


def test_credits_name_title_author_source_and_licence(tmp_path):
    p = project.create(tmp_path, "chill", "demo")
    (p.songs / "a.mp3").write_bytes(b"x")
    write_json(p.file("downloads.json"), {
        "a.mp3": {"source": "jamendo", "url": "https://www.jamendo.com/track/1", "artist": "Lee", "title": "Rain",
                  "license": "http://creativecommons.org/licenses/by/3.0/", "safety": "cc"},
        "gone.mp3": {"source": "jamendo", "url": "u", "artist": "X", "title": "Y",
                     "license": "http://creativecommons.org/licenses/by/3.0/", "safety": "cc"}})
    assert meta.credits_for(p) == ['• "Rain" by Lee, CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/), '
                                   'https://www.jamendo.com/track/1']
