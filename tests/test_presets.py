import math

from playlistkit import gui, presets
from playlistkit.genres import GENRES, STYLES

# the Remix tab's sliders: (min, step) — a preset value must sit on a step or the slider moves it
STEPS = {"transition": (4, 1), "max_stretch": (0, 0.02), "speed": (0.7, 0.01), "reverb": (0, 0.02), "duck": (0, 0.05),
         "gain_drums": (-12, 1), "gain_bass": (-12, 1), "gain_other": (-12, 1), "gain_vocals": (-12, 1)}
LUFS_MENU = {-18, -16, -14, -12, -10}


def test_presets_are_valid():
    ids = [p.id for p in presets.PRESETS]
    assert len(ids) == len(set(ids))
    for p in presets.PRESETS:
        assert p.style in STYLES, p.id
        assert set(p.genres) <= set(GENRES), p.id
        assert gui.dj_opts(p.dj) == {k: v for k, v in p.dj.items()}, p.id  # every value inside the engine's limits
        assert p.dj["lufs"] in LUFS_MENU, p.id
        for k, (lo, step) in STEPS.items():
            n = (p.dj[k] - lo) / step
            assert math.isclose(n, round(n), abs_tol=1e-6), (p.id, k)


def test_every_genre_has_a_preset():
    missing = [g for g in GENRES if presets.for_genre(g) is None]
    assert not missing


def test_preset_id_is_kept_with_the_settings():
    assert gui.dj_opts({"preset": "lofi-chill"})["preset"] == "lofi-chill"
    assert "preset" not in gui.dj_opts({"preset": "<script>"})
