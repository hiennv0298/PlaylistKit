from pathlib import Path

from playlistkit import gui, runtime


def test_dj_opts_keeps_known_keys_in_range():
    o = gui.dj_opts({"speed": 3, "reverb": -1, "gain_vocals": 2.5, "order": "files", "transition_type": "bogus",
                     "lofi": 1, "keyshift": 0, "evil": "x", "lufs": None})
    assert o == {"speed": 1.3, "reverb": 0.0, "gain_vocals": 2.5, "order": "files", "lofi": True, "keyshift": False}


def test_engine_cmd_passes_dj_settings():
    cmd = runtime.engine_cmd(Path("py"), Path("s"), Path("w"), Path("o"), "x", "dj",
                             {"order": "files", "transition_type": "fade", "speed": 0.9, "reverb": 0.2, "lofi": False,
                              "duck": 0.3, "gain_bass": -3, "lufs": -12, "demo": 2, "keyshift": False})
    s = " ".join(cmd)
    for part in ("--order files", "--transition-type fade", "--speed 0.9", "--reverb 0.2", "--lofi off", "--duck 0.3",
                 "--gain-bass -3.0", "--lufs -12.0", "--demo 2", "--no-keyshift"):
        assert part in s, part


def test_engine_cmd_without_dj_settings_is_unchanged():
    s = " ".join(runtime.engine_cmd(Path("py"), Path("s"), Path("w"), Path("o"), "x", "lofi", {}))
    for flag in ("--order", "--transition-type", "--speed", "--reverb", "--lofi", "--duck", "--gain-", "--lufs", "--demo"):
        assert flag not in s, flag
