"""DJ presets for the Remix tab: a style plus every DJ setting, made for a kind of music.

Picking one on the Remix tab sets the style and all the sliders; ▶ Demo then plays it.
Each preset lists the genres it suits; the first preset that lists a genre is the one
suggested for it. The values stay inside gui.DJ_KEYS and the sliders' steps (tests check it).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    style: str
    about: str
    genres: tuple[str, ...]
    dj: dict = field(default_factory=dict)


def _dj(**kw) -> dict:
    base = {"order": "smart", "transition_type": "auto", "transition": 14, "max_stretch": 0.08, "keyshift": True,
            "speed": 1.0, "reverb": 0.0, "lofi": False, "duck": 0.0, "lufs": -14,
            "gain_drums": 0, "gain_bass": 0, "gain_other": 0, "gain_vocals": 0}
    return {**base, **kw}


PRESETS: tuple[Preset, ...] = (
    Preset("rap-beat", "Rap beat mix", "dj",
           "Beat-matched 16-beat swaps, punchy drums and bass, vocals up front, loud.",
           ("rap", "hiphop"),
           _dj(transition_type="beat", transition=16, duck=0.1, lufs=-12, gain_drums=1, gain_bass=1, gain_vocals=1)),
    Preset("vinahouse", "Vinahouse club", "club",
           "Long beat-matched blends, heavy kick pump, big drums and bass, club loud.",
           ("vinahouse", "remix", "tiktok"),
           _dj(transition_type="beat", transition=24, max_stretch=0.12, duck=0.4, lufs=-10, gain_drums=2, gain_bass=2)),
    Preset("edm-festival", "EDM festival", "club",
           "Long blends over the drops, strong sidechain pump, a touch of space.",
           ("edm", "gaming"),
           _dj(transition_type="beat", transition=28, max_stretch=0.12, duck=0.45, reverb=0.06, lufs=-10,
               gain_drums=1, gain_bass=2)),
    Preset("phonk", "Phonk drift", "club",
           "Hard 808 bass and cowbells forward, pumping, loud.",
           ("phonk",),
           _dj(transition_type="beat", transition=16, max_stretch=0.12, duck=0.4, lufs=-10, gain_bass=3, gain_other=1)),
    Preset("deep-house", "Deep house smooth", "club",
           "Very long, smooth blends with a gentle pump and a little room.",
           ("deephouse",),
           _dj(transition_type="beat", transition=32, duck=0.25, reverb=0.1, lufs=-12, gain_vocals=-1)),
    Preset("synthwave", "Synthwave drive", "dj",
           "Beat-matched night-drive blends, synths forward, roomy.",
           ("synthwave",),
           _dj(transition_type="beat", transition=24, duck=0.2, reverb=0.16, lufs=-12, gain_other=1)),
    Preset("pop-radio", "Pop radio", "dj",
           "Quick, clean blends like a radio mix; vocals a little louder.",
           ("vpop", "kpop", "cpop", "jpop", "thai", "usuk", "latin", "tet", "christmas", "anime"),
           _dj(transition=12, lufs=-12, gain_vocals=1)),
    Preset("rock", "Rock / band", "dj",
           "Songs end on their last line, then the next band comes in; no tempo games.",
           ("rock", "country"),
           _dj(transition_type="fade", transition=10, max_stretch=0.04, keyshift=False, lufs=-12, gain_drums=1)),
    Preset("nightcore", "Nightcore", "nightcore",
           "20% faster and higher, pumping, loud.",
           ("nightcore",),
           _dj(transition_type="beat", transition=16, speed=1.2, duck=0.3, lufs=-10)),
    Preset("slowed-reverb", "Slowed + reverb", "slowed",
           "15% slower and lower with a big reverb; soft vocal fades.",
           ("slowed", "douyin", "rnb"),
           _dj(transition_type="fade", transition=16, max_stretch=0.04, keyshift=False, speed=0.85, reverb=0.32)),
    Preset("lofi-chill", "Lo-fi chill", "lofi",
           "8% slower, warm lo-fi filter, soft drums and bass, gentle blends.",
           ("lofi", "chill", "study"),
           _dj(transition=16, max_stretch=0.04, keyshift=False, speed=0.92, reverb=0.14, lofi=True,
               gain_drums=-2, gain_bass=-1)),
    Preset("indie-night", "Indie night", "indie",
           "Soft drums, vocals close, slightly slower, a little room.",
           ("indie", "ballad"),
           _dj(max_stretch=0.04, keyshift=False, speed=0.96, reverb=0.1, gain_drums=-2, gain_vocals=1)),
    Preset("acoustic", "Acoustic gentle", "indie",
           "Original speed, songs hand over after the last line, quiet and natural.",
           ("acoustic", "bolero", "trinh", "thieunhi", "indiefolk", "jazz", "bossa", "piano", "classical"),
           _dj(transition_type="fade", transition=10, max_stretch=0.04, keyshift=False, reverb=0.08, lufs=-16,
               gain_drums=-3, gain_vocals=1)),
    Preset("sleep", "Sleep & meditation", "lofi",
           "Slow, warm and far away: long fades, big reverb, almost no drums, very quiet.",
           ("sleep", "meditation"),
           _dj(transition_type="fade", transition=24, max_stretch=0.04, keyshift=False, speed=0.9, reverb=0.3,
               lofi=True, lufs=-18, gain_drums=-6, gain_bass=-2)),
)


def as_list() -> list[dict]:
    return [{"id": p.id, "name": p.name, "style": p.style, "about": p.about, "genres": list(p.genres), "dj": p.dj}
            for p in PRESETS]


def for_genre(genre: str) -> Preset | None:
    return next((p for p in PRESETS if genre in p.genres), None)
