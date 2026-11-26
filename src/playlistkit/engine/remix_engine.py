#!/usr/bin/env python
"""
remix_playlist.py - Ghep nhieu bai thanh mot playlist remix lien mach.

Chuoi xu ly:
  1. Giai ma moi file nhac trong thu muc playlist ve WAV 44.1 kHz.
  2. Phan tich BPM, tong (key / Camelot), do to cua tung bai.
  3. Sap thu tu bai de chuyen nhip / chuyen tong muot nhat.
  4. Tach stem bang Demucs (GPU neu co): drums, bass, other, vocals.
  5. Time-stretch / pitch-shift (FFmpeg rubberband) de khop nhip, khop tong.
  6. Chuyen bai bang stem (vocal rut truoc, bass swap, drums ra sau), hoac
     echo-out khi hai bai lech nhip qua xa.
  7. Ap style (dj, club, lofi, slowed, nightcore), master ve -14 LUFS (chuan YouTube).
  8. Xuat WAV 48 kHz + MP3 320k + tracklist co moc thoi gian cho mo ta YouTube.

PlaylistKit runs this file with its AI Python (torch + demucs):
  python remix_engine.py <songs dir> --styles indie --work <work dir> --out <out dir> --slug <name>

Doi thu tu bai: sua "order" trong <work>/plan.json roi chay lai.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, oaconvolve, resample_poly, sosfilt, sosfiltfilt

ROOT = Path(__file__).resolve().parent.parent
SR = 44100          # sample rate xu ly
ASR = 22050         # sample rate phan tich
HOP = 256
STEMS = ("drums", "bass", "other", "vocals")
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".webm",
             ".wma", ".aiff", ".aif", ".mp4", ".mkv"}
PREMIX_LUFS = -18.0
TARGET_LUFS = -14.0

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
CAM_MAJOR = {"B": 1, "F#": 2, "C#": 3, "G#": 4, "D#": 5, "A#": 6, "F": 7, "C": 8,
             "G": 9, "D": 10, "A": 11, "E": 12}
CAM_MINOR = {"G#": 1, "D#": 2, "A#": 3, "F": 4, "C": 5, "G": 6, "D": 7, "A": 8,
             "E": 9, "B": 10, "F#": 11, "C#": 12}

# style -> (cach xu ly stem, hieu ung tren ban mix cuoi)
STYLES = {
    "dj": ("dj", None),
    "club": ("club", None),
    "lofi": ("dj", "lofi"),
    "slowed": ("dj", "slowed"),
    "nightcore": ("club", "nightcore"),
    "indie": ("indie", "indie"),      # lofi cho indie: trong/bass xu ly theo stem, giong len truoc
}
SPEED = {None: 1.0, "lofi": 0.92, "slowed": 0.85, "nightcore": 1.2, "indie": 0.96}
REVERB = {"lofi": (0.14, 1.8), "slowed": (0.32, 2.8)}   # fx -> (wet, decay)
TRANSITION_TYPES = ("auto", "beat", "fade", "echo")


# ----------------------------------------------------------------------------- utils
_T0 = time.time()


def log(msg: str) -> None:
    el = int(time.time() - _T0)
    print(f"[{el // 60:02d}:{el % 60:02d}] {msg}", flush=True)


def run(cmd: list) -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"Lenh that bai ({r.returncode}): {' '.join(cmd)[:400]}\n{r.stderr[-3000:]}")
    return r


def db2lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def read_wav(p: Path) -> np.ndarray:
    x, sr = sf.read(str(p), dtype="float32", always_2d=True)
    if sr != SR:
        raise RuntimeError(f"{p} co sample rate {sr}, can {SR}")
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return np.ascontiguousarray(x[:, :2])


def write_wav(p: Path, x: np.ndarray, subtype: str = "FLOAT") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(p), x, SR, subtype=subtype)


def fmt_time(sec: float) -> str:
    sec = int(round(max(0.0, sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def mono22(x: np.ndarray) -> np.ndarray:
    import librosa
    return librosa.resample(x.mean(axis=1), orig_sr=SR, target_sr=ASR)


# ----------------------------------------------------------------------------- input
def find_inputs(pdir: Path) -> list[Path]:
    return sorted(p for p in pdir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT)


def track_id(p: Path) -> str:
    h = hashlib.sha1(f"{p.name}|{p.stat().st_size}".encode("utf-8")).hexdigest()[:10]
    return "t_" + h


def tidy(s: str) -> str:
    """Chuan hoa ky tu: yt-dlp doi ? | " / thanh ban full-width, NFKC doi lai; gop dau tieng Viet."""
    s = unicodedata.normalize("NFKC", s.replace("⧸", "/"))
    s = re.sub(r"\s*\((official|lyrics?|mv|audio)[^)]*\)\s*", " ", s, flags=re.I)
    s = re.sub(r"\s*\|\s*(audio\s+)?official(\s+audio)?\s*$", "", s, flags=re.I)
    return re.sub(r"\s{2,}", " ", s).strip()


def clean_name(stem: str) -> str:
    s = re.sub(r"\s*-\s*SoundCloudMate\.com\s*$", "", stem, flags=re.I)
    s = re.sub(r"\s*\[[A-Za-z0-9_-]{6,}\]\s*$", "", s)          # [videoid] cua yt-dlp
    s = re.sub(r"^\d{1,3}\s*-\s+", "", s)                         # so thu tu "06 - " cua file tai ve
    return tidy(s)


def display_name(p: Path) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=title,artist",
                        "-of", "json", str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        tags = {k.lower(): v for k, v in (json.loads(r.stdout).get("format", {}).get("tags") or {}).items()}
    except Exception:
        tags = {}
    title, artist = tags.get("title"), tags.get("artist")
    if title:
        return tidy(f"{artist} - {title}" if artist else title)
    return clean_name(p.stem)


def decode(src: Path, dst: Path) -> None:
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "2",
         "-ar", SR, "-c:a", "pcm_f32le", dst])


# ----------------------------------------------------------------------------- analysis
def fit_ibi(bt: np.ndarray, ibi0: float) -> float:
    """Khoang cach phach (giay) chinh xac duoi muc frame, bang hoi quy tuyen tinh."""
    steps = np.maximum(1, np.round(np.diff(bt) / ibi0))
    n = np.concatenate([[0.0], np.cumsum(steps)])
    keep = np.ones(len(bt), bool)
    ibi = ibi0
    for _ in range(3):
        a = np.vstack([n[keep], np.ones(keep.sum())]).T
        ibi, c = np.linalg.lstsq(a, bt[keep], rcond=None)[0]
        res = bt - (n * ibi + c)
        mad = np.median(np.abs(res[keep] - np.median(res[keep]))) + 1e-6
        keep = np.abs(res - np.median(res[keep])) < max(4 * mad, 0.06)
        if keep.sum() < 8:
            break
    return float(ibi)


def beat_grid(y: np.ndarray):
    import librosa
    oenv = librosa.onset.onset_strength(y=y, sr=ASR, hop_length=HOP)
    _, frames = librosa.beat.beat_track(onset_envelope=oenv, sr=ASR, hop_length=HOP, tightness=100)
    bt = librosa.frames_to_time(np.asarray(frames), sr=ASR, hop_length=HOP)
    if len(bt) < 16:
        return None
    ibi0 = float(np.median(np.diff(bt)))
    return bt.astype(float), fit_ibi(bt, ibi0)


def detect_key(y: np.ndarray):
    import librosa
    yh = librosa.effects.harmonic(y, margin=4)
    chroma = librosa.feature.chroma_cqt(y=yh, sr=ASR, hop_length=1024)
    prof = chroma.mean(axis=1)
    best = (-2.0, 0, "major")
    for pc in range(12):
        for mode, tmpl in (("major", KS_MAJOR), ("minor", KS_MINOR)):
            r = float(np.corrcoef(prof, np.roll(tmpl, pc))[0, 1])
            if r > best[0]:
                best = (r, pc, mode)
    return best[1], best[2], best[0]


def camelot(pc: int, mode: str) -> tuple[int, str]:
    name = NOTES[pc % 12]
    return (CAM_MAJOR[name], "B") if mode == "major" else (CAM_MINOR[name], "A")


def cam_str(pc: int, mode: str) -> str:
    n, l = camelot(pc, mode)
    return f"{n}{l}"


def key_str(pc: int, mode: str) -> str:
    return NOTES[pc % 12] + ("m" if mode == "minor" else "")


def cam_dist(a: tuple[int, str], b: tuple[int, str]) -> int:
    dn = min((a[0] - b[0]) % 12, (b[0] - a[0]) % 12)
    return dn if a[1] == b[1] else dn + 1


def loudness(x: np.ndarray) -> float:
    import pyloudnorm as pyln
    v = pyln.Meter(SR).integrated_loudness(x.astype(np.float64))
    return float(v) if np.isfinite(v) else -40.0


def analyze(files: list[Path], work: Path) -> dict:
    cache_p = work / "analysis.json"
    cache = json.loads(cache_p.read_text("utf-8")) if cache_p.exists() else {}
    out = {}
    for f in files:
        tid = track_id(f)
        wav = work / "decoded" / f"{tid}.wav"
        decode(f, wav)
        if tid in cache and cache[tid].get("src") == str(f):
            out[tid] = cache[tid]
            continue
        log(f"  phan tich: {f.name}")
        x = read_wav(wav)
        y = mono22(x)
        grid = beat_grid(y)
        pc, mode, conf = detect_key(y)
        import librosa
        energy = float(np.mean(librosa.onset.onset_strength(y=y, sr=ASR, hop_length=HOP)))
        out[tid] = {
            "src": str(f), "name": display_name(f), "duration": len(x) / SR,
            "ibi": grid[1] if grid else None,
            "bpm": round(60.0 / grid[1], 2) if grid else None,
            "pc": pc, "mode": mode, "key": key_str(pc, mode), "camelot": cam_str(pc, mode),
            "key_conf": round(conf, 3), "lufs": round(loudness(x), 2), "energy": round(energy, 4),
        }
    cache.update(out)
    work.mkdir(parents=True, exist_ok=True)
    cache_p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), "utf-8")
    return out


# ----------------------------------------------------------------------------- planning
def tempo_fit(ibi_prev: float, ibi_native: float, max_stretch: float):
    """rubberband tempo=s cho bai sau, cho phep quan he nhip doi / nhip nua."""
    best = None
    for m in (1.0, 0.5, 2.0):
        s = ibi_native / (ibi_prev * m)
        if best is None or abs(math.log(s)) < abs(math.log(best[0])):
            best = (s, m)
    ok = abs(math.log(best[0])) <= math.log(1 + max_stretch)
    return best[0], best[1], ok


def decide(prev: dict, b: dict, opts) -> dict:
    """prev: {'ibi','pc','mode'} cua bai truoc (sau xu ly); b: ban phan tich bai sau."""
    beat_ok = False
    s = 1.0
    if prev.get("ibi") and b.get("ibi"):
        s, _, beat_ok = tempo_fit(prev["ibi"], b["ibi"], opts.max_stretch)
    if not beat_ok:
        s = 1.0
    prev_cam = camelot(prev["pc"], prev["mode"])
    best_k, best_cost = 0, cam_dist(prev_cam, camelot(b["pc"], b["mode"])) * 3.0
    if beat_ok and not opts.no_keyshift:
        for k in (-1, 1):
            c = cam_dist(prev_cam, camelot(b["pc"] + k, b["mode"])) * 3.0 + 2.5
            if c < best_cost:
                best_k, best_cost = k, c
    tcost = abs(math.log(s)) * 100 if beat_ok else 25.0
    if not beat_ok:
        best_cost *= 0.5
    return {"mode": "beat" if beat_ok else "echo", "stretch": s, "semis": best_k,
            "cost": tcost + best_cost}


def simulate(order: list[str], an: dict, opts):
    total, decisions = 0.0, []
    first = an[order[0]]
    state = {"ibi": first["ibi"], "pc": first["pc"], "mode": first["mode"]}
    for tid in order[1:]:
        b = an[tid]
        d = decide(state, b, opts)
        if an[order[0]]["energy"] > b["energy"] and len(decisions) == 0:
            d["cost"] += 1.0          # uu tien mo dau nhe nhang hon
        total += d["cost"]
        decisions.append(d)
        ibi = (state["ibi"] if d["mode"] == "beat" else b["ibi"])
        state = {"ibi": ibi, "pc": b["pc"] + d["semis"], "mode": b["mode"]}
    return total, decisions


def best_order(an: dict, opts) -> list[str]:
    ids = list(an)
    if len(ids) <= 7:
        return list(min(itertools.permutations(ids), key=lambda o: simulate(list(o), an, opts)[0]))
    # nhieu bai: tham lam tu bai cham nhat, roi thu doi cho tung cap
    start = min(ids, key=lambda t: (an[t]["bpm"] or 999, an[t]["energy"]))
    order, rest = [start], set(ids) - {start}
    while rest:
        nxt = min(rest, key=lambda t: simulate(order + [t], an, opts)[0])
        order.append(nxt)
        rest.remove(nxt)
    improved = True
    while improved:
        improved = False
        base = simulate(order, an, opts)[0]
        for i, j in itertools.combinations(range(len(order)), 2):
            cand = order[:]
            cand[i], cand[j] = cand[j], cand[i]
            if simulate(cand, an, opts)[0] < base - 1e-6:
                order, improved = cand, True
                break
    return order


def load_plan(an: dict, work: Path, opts) -> list[str]:
    plan_p = work / "plan.json"
    if getattr(opts, "order", None) == "files":       # A -> Z by file name, as the songs folder shows them
        return list(an)
    if plan_p.exists() and not opts.reorder:
        plan = json.loads(plan_p.read_text("utf-8"))
        order = [t for t in plan.get("order", []) if t in an]
        if set(order) == set(an):
            return order
    order = best_order(an, opts)
    plan = {"order": order,
            "_huong_dan": "Doi thu tu cac id trong 'order' roi chay lai script de render theo thu tu moi.",
            "tracks": {t: f'{an[t]["name"]} | {an[t]["bpm"]} BPM | {an[t]["key"]} ({an[t]["camelot"]})'
                       for t in order}}
    plan_p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
    return order


# ----------------------------------------------------------------------------- stems
# The stems must not be clipped or rescaled (add_residual makes them sum exactly to the original).
# Demucs 4.0.1's save_audio supports clip="none", but its command line only offers rescale/clamp,
# so Demucs is started through this launcher, which adds "none" to the accepted choices when missing.
DEMUCS_LAUNCHER = """
import sys
import demucs.separate as sep

_get_parser = sep.get_parser


def get_parser():
    parser = _get_parser()
    for action in parser._actions:
        if "--clip-mode" in action.option_strings and action.choices and "none" not in action.choices:
            action.choices = [*action.choices, "none"]
    return parser


sep.get_parser = get_parser
sep.main(sys.argv[1:])
"""


def separate(ids: list[str], work: Path, device: str) -> None:
    todo = [t for t in ids if not all((work / "stems" / "htdemucs" / t / f"{s}.wav").exists() for s in STEMS)]
    if not todo:
        return
    log(f"  tach stem {len(todo)} bai bang Demucs ({device})...")
    base = [sys.executable, "-c", DEMUCS_LAUNCHER, "-n", "htdemucs", "--float32", "--clip-mode", "none",
            "-o", str(work / "stems")]
    files = [str(work / "decoded" / f"{t}.wav") for t in todo]
    r = subprocess.run(base + ["-d", device] + files)
    if r.returncode != 0 and device != "cpu":
        log("  GPU loi (co the het VRAM), chay lai bang CPU...")
        r = subprocess.run(base + ["-d", "cpu"] + files)
    if r.returncode != 0:
        raise RuntimeError("Demucs that bai")


def add_residual(work: Path, ids: list[str]) -> None:
    """Cong phan du (ban goc - tong stem) vao stem 'other' de tong 4 stem dung bang ban goc,
    giu nguyen chat luong o nhung doan khong chuyen bai."""
    for tid in ids:
        d = work / "stems" / "htdemucs" / tid
        mark = d / ".residual_ok"
        if mark.exists():
            continue
        x = read_wav(work / "decoded" / f"{tid}.wav")
        st = load_stems(d)
        n = min(len(x), len(st["other"]))
        s = sum(v[:n] for v in st.values())
        other = st["other"].copy()
        other[:n] += x[:n] - s
        write_wav(d / "other.wav", other)
        for old in (work / "proc").glob(f"{tid}_*"):            # ban keo nhip cu dua tren stem cu
            for f in old.iterdir():
                f.unlink()
            old.rmdir()
        mark.write_text("ok", "utf-8")


def stems_dir(work: Path, tid: str, stretch: float, semis: int) -> Path:
    src = work / "stems" / "htdemucs" / tid
    if abs(stretch - 1.0) < 1e-4 and semis == 0:
        return src
    dst = work / "proc" / f"{tid}_s{stretch:.5f}_k{semis:+d}"
    if all((dst / f"{s}.wav").exists() for s in STEMS):
        return dst
    dst.mkdir(parents=True, exist_ok=True)
    filt = f"rubberband=tempo={stretch:.6f}:pitch={2 ** (semis / 12):.6f}:pitchq=quality"
    for s in STEMS:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src / f"{s}.wav",
             "-af", filt, "-c:a", "pcm_f32le", dst / f"{s}.wav"])
    return dst


def load_stems(d: Path) -> dict[str, np.ndarray]:
    st = {s: read_wav(d / f"{s}.wav") for s in STEMS}
    n = max(len(v) for v in st.values())
    return {s: (np.pad(v, ((0, n - len(v)), (0, 0))) if len(v) < n else v) for s, v in st.items()}


# ----------------------------------------------------------------------------- measurement
def loud_edges(mix: np.ndarray):
    blk = SR // 10
    n = len(mix) // blk
    p = (mix[: n * blk] ** 2).mean(axis=1).reshape(n, blk).mean(axis=1)
    db = 10 * np.log10(p + 1e-12)
    ref = float(np.percentile(db, 75))
    sm = np.convolve(db, np.ones(10) / 10, mode="same")
    a = np.where(db > ref - 30)[0]
    l = np.where(sm > ref - 9)[0]
    e = np.where(db > ref - 45)[0]
    start = a[0] * 0.1 if len(a) else 0.0
    end_audio = (e[-1] + 1) * 0.1 if len(e) else len(mix) / SR
    end_music = min((l[-1] + 1) * 0.1, end_audio) if len(l) else end_audio
    return start, end_music, end_audio


def onset22(x: np.ndarray, lowpass: float | None = None) -> np.ndarray:
    import librosa
    m = x.mean(axis=1)
    if lowpass:
        m = sosfilt(butter(4, lowpass, "lowpass", fs=SR, output="sos"), m)
    y = librosa.resample(m.astype(np.float32), orig_sr=SR, target_sr=ASR)
    return librosa.onset.onset_strength(y=y, sr=ASR, hop_length=HOP)


def downbeats_of(bt: np.ndarray, kick: np.ndarray, bass: np.ndarray, full: np.ndarray) -> np.ndarray:
    idx = np.clip(np.round(bt * ASR / HOP).astype(int), 0, len(full) - 1)

    def nz(v):
        return v[idx] / (np.percentile(v, 99) + 1e-9)
    score = nz(kick) + nz(bass) + 0.5 * nz(full)
    phase = int(np.argmax([score[p::4].mean() if len(score[p::4]) else -1 for p in range(4)]))
    return bt[phase::4]


def vocal_activity(v: np.ndarray, mix: np.ndarray) -> dict:
    """Moi 0.1 s: co dang hat khong. Tra ve tong tich luy de dem nhanh so giay co vocal."""
    blk = SR // 10
    n = len(v) // blk

    def db(x):
        return 10 * np.log10((x[: n * blk] ** 2).mean(axis=1).reshape(n, blk).mean(axis=1) + 1e-12)
    vdb, mdb = db(v), db(mix)
    ref = float(np.percentile(vdb, 90))
    if ref < float(np.percentile(mdb, 90)) - 20:        # bai khong loi
        act = np.zeros(n, bool)
    else:
        act = (vdb > ref - 18) & (vdb > -50)
        act = np.convolve(act.astype(float), np.ones(5) / 5, mode="same") > 0.5
    idx = np.where(act)[0]
    return {"vact_cs": np.concatenate([[0], np.cumsum(act)]),
            "v_first": idx[0] * 0.1 if len(idx) else None,
            "v_last": (idx[-1] + 1) * 0.1 if len(idx) else None}


def vsec(m: dict, t0: float, t1: float) -> float:
    """So giay co vocal trong [t0, t1] (giay trong bai)."""
    cs = m["vact_cs"]
    i0 = int(np.clip(round(t0 * 10), 0, len(cs) - 1))
    i1 = int(np.clip(round(t1 * 10), 0, len(cs) - 1))
    return 0.1 * float(cs[i1] - cs[i0]) if i1 > i0 else 0.0


def measure(stems: dict[str, np.ndarray]) -> dict:
    mix = sum(stems.values())
    start, end_music, end_audio = loud_edges(mix)
    grid = beat_grid(mono22(mix))
    m = {"start": start, "end_music": end_music, "end_audio": end_audio,
         "length": len(mix) / SR, "beats": None, "ibi": None, "downbeats": None}
    m.update(vocal_activity(stems["vocals"], mix))
    if grid:
        bt, ibi = grid
        kick = onset22(stems["drums"], 150)
        bass = onset22(stems["bass"])
        full = onset22(mix)
        m.update(beats=bt, ibi=ibi, downbeats=downbeats_of(bt, kick, bass, full),
                 _onsets=(kick, bass, full))
    return m


def canonicalize(m: dict, target_ibi: float) -> None:
    """Dua luoi phach cua bai sau ve cung don vi phach voi bai truoc (nhip doi / nhip nua)."""
    r = m["ibi"] / target_ibi
    kick, bass, full = m["_onsets"]
    if 0.4 < r < 0.62:                                   # bai sau dem nhanh gap doi
        db0 = m["downbeats"][0]
        par = int(np.argmin(np.abs(m["beats"] - db0))) % 2
        bt = m["beats"][par::2]
        m.update(beats=bt, ibi=m["ibi"] * 2, downbeats=downbeats_of(bt, kick, bass, full))
    elif 1.6 < r < 2.5:                                  # bai sau dem cham mot nua
        bt = m["beats"]
        mids = (bt[:-1] + bt[1:]) / 2
        m.update(beats=np.sort(np.concatenate([bt, mids])), ibi=m["ibi"] / 2)


# ----------------------------------------------------------------------------- transitions
def refine_offset(a_drums, b_drums, a0, b0, length, maxlag):
    """Tinh chinh do lech (giay) bang tuong quan cheo onset trong vung chuyen bai."""
    import librosa
    hop = 64

    def env(x, t0, t1):
        i0, i1 = max(0, int(t0 * SR)), max(0, int(t1 * SR))
        seg = x[i0:i1].mean(axis=1)
        if len(seg) < SR:
            return None
        y = librosa.resample(seg.astype(np.float32), orig_sr=SR, target_sr=ASR)
        return librosa.onset.onset_strength(y=y, sr=ASR, hop_length=hop)
    ea = env(a_drums, a0, a0 + length)
    eb = env(b_drums, b0 - maxlag, b0 + length + maxlag)
    if ea is None or eb is None or b0 - maxlag < 0:
        return 0.0
    dt = hop / ASR
    J = int(maxlag / dt)
    n = min(len(ea), len(eb) - 2 * J)
    if n <= 0 or ea[:n].std() < 1e-6 or eb.std() < 1e-6:
        return 0.0
    ea = ea[:n] - ea[:n].mean()
    corr = [float(np.dot(ea, eb[J - j: J - j + n])) for j in range(-J, J + 1)]
    j = int(np.argmax(corr)) - J
    return j * dt


def beat_transition(A: dict, B: dict, a_dir: Path, b_dir: Path, opts):
    """Chuyen bai khop phach, thu nhieu vi tri / do dai, chon cai mat it vocal nhat.
    Thoi diem toan cuc: off_B = off_A + rel."""
    ibi = A["ibi"]
    a_lim = min(A["end_music"], A["beats"][-1] + ibi)     # vung chuyen phai con phach
    b_lim = min(B["end_music"], B["beats"][-1])
    minplay = min(30.0, 0.3 * (a_lim - A["entry"]))
    b_entries = [d for d in B["downbeats"] if d >= B["start"] - 0.5 * ibi][:6]
    best = None
    for nb in (8, 16, 24, 32):
        L = nb * ibi
        if L > max(8 * ibi, opts.transition * 1.6):
            continue
        for dA in A["downbeats"]:
            if dA < A["entry"] + minplay or dA < a_lim - 90 or dA + L > a_lim + 1e-3:
                continue
            ab = A["beats"][A["beats"] >= dA - 1e-3][:nb]
            if len(ab) < nb * 0.9:
                continue
            for dB in b_entries:
                if dB + L + 20 > b_lim:
                    continue
                bb = B["beats"][B["beats"] >= dB - 1e-3][:nb]
                k = min(len(ab), len(bb))
                if k < nb * 0.9:
                    continue
                rel = float(np.mean(ab[:k] - bb[:k]))
                eB = dA - rel
                hs = [(vsec(A, dA + h * ibi, dA + L) + vsec(B, eB, eB + h * ibi)
                       + 1e-3 * abs(h - nb / 2), h) for h in range(1, nb)]
                vcost, vh = min(hs)
                lost_a = vsec(A, dA + L, A["end_audio"])
                lost_b = vsec(B, B["start"], eB)
                instr_cut = max(0.0, (A["end_audio"] - (dA + L)) - lost_a) + max(0.0, (eB - B["start"]) - lost_b)
                cost = vcost + lost_a + lost_b + 0.03 * instr_cut - 0.04 * L
                if best is None or cost < best["cost"]:
                    best = {"type": "beat", "a_start": dA, "length": L, "beats": nb, "rel": rel,
                            "b_entry": eB, "vh": vh, "ibi": ibi, "cost": cost}
    if best is None:
        return None
    fine = refine_offset(read_wav(a_dir / "drums.wav"), read_wav(b_dir / "drums.wav"),
                         best["a_start"], best["b_entry"], best["length"], min(0.06, 0.15 * ibi))
    best["rel"] += fine
    best["b_entry"] -= fine
    best["fine"] = fine
    return best


def fade_transition(A: dict, B: dict):
    """Chuyen theo cau hat: bai A hat xong cau cuoi, outro cua A tan dan duoi intro cua B,
    B bat dau hat khi A da tat. Khong can khop phach."""
    va_end = A["v_last"] if A["v_last"] else A["end_music"]
    vb_start = B["v_first"] if B["v_first"] is not None else B["start"] + 4.0
    outro = max(0.0, A["end_audio"] - va_end)
    intro = max(0.0, vb_start - B["start"])
    ov = float(np.clip(min(outro, intro), 1.0, 10.0))
    hand = va_end + ov                                  # giay trong A luc B bat dau hat
    eB = max(B["start"], vb_start - ov - 0.5)
    cut = min(hand, A["end_audio"])
    fade0 = min(va_end + 0.3, cut - 0.5)
    rel = hand - vb_start
    cost = vsec(A, cut, A["end_audio"]) + vsec(B, B["start"], eB) + 2.0
    if outro < 1.5 and intro < 1.5:
        cost += 2.0                                     # gan nhu cat cung
    return {"type": "fade", "cut": cut, "fade0": fade0, "b_entry": eB, "b_fade": float(min(2.0, ov)),
            "rel": rel, "cost": cost}


def echo_transition(A: dict, B: dict):
    minplay = min(30.0, 0.3 * (A["end_music"] - A["entry"]))
    D = float(np.clip(A["ibi"], 0.3, 0.9)) if A["ibi"] else 0.5
    grid = list(A["downbeats"]) if A["downbeats"] is not None else []
    va_end = A["v_last"] or 0.0
    after = [d for d in grid if va_end - 0.1 <= d <= A["end_audio"] and d >= A["entry"] + minplay]
    before = [d for d in grid if A["entry"] + minplay <= d <= A["end_music"]]
    cut = after[0] if after else (before[-1] if before else A["end_music"])
    cost = vsec(A, cut, A["end_audio"]) + 3.0
    return {"type": "echo", "cut": cut, "delay": D, "rel": cut + D - B["start"],
            "b_entry": B["start"], "cost": cost}


def kf_in(tr, stem):
    """Diem gain (giay trong bai vao, gain) khi bai vao."""
    e = tr["b_entry"]
    if tr["type"] == "beat":
        L, ibi, vh = tr["length"], tr["ibi"], tr["vh"]
        return {"drums": [(e, 0), (e + 0.5 * L, 1)],
                "other": [(e, 0), (e + 0.25 * L, 0), (e + 0.75 * L, 1)],
                "bass": [(e, 0), (e + 0.5 * L - 0.25 * ibi, 0), (e + 0.5 * L + 0.25 * ibi, 1)],
                "vocals": [(e, 0), (e + (vh - 0.5) * ibi, 0), (e + (vh + 0.5) * ibi, 1)]}[stem]
    if tr["type"] == "fade":
        return [(e, 0), (e + tr["b_fade"], 1)]
    return [(e, 0), (e + 1.5, 1)]


def kf_out(tr, stem):
    """Diem gain (giay trong bai ra, gain) khi bai ra."""
    if tr["type"] == "beat":
        s, L, ibi, vh = tr["a_start"], tr["length"], tr["ibi"], tr["vh"]
        return {"vocals": [(s + (vh - 0.5) * ibi, 1), (s + (vh + 0.5) * ibi, 0)],
                "other": [(s + 0.5 * L, 1), (s + 0.85 * L, 0)],
                "bass": [(s + 0.5 * L - 0.25 * ibi, 1), (s + 0.5 * L + 0.25 * ibi, 0)],
                "drums": [(s + 0.75 * L, 1), (s + L, 0)]}[stem]
    if tr["type"] == "fade":
        return [(tr["fade0"], 1), (tr["cut"], 0)]
    c = tr["cut"]
    return [(c - 0.02, 1), (c, 0)]


def envelope(points, t0: float, n: int) -> np.ndarray:
    pts = sorted(points)
    xs, ys = [], []
    for x, y in pts:
        if xs and x <= xs[-1]:
            x = xs[-1] + 1e-4
        xs.append(x)
        ys.append(y)
    t = t0 + np.arange(n, dtype=np.float64) / SR
    return np.interp(t, xs, ys, left=0.0, right=0.0).astype(np.float32)


# ----------------------------------------------------------------------------- styles / fx
def kick_env(drums: np.ndarray) -> np.ndarray:
    low = np.abs(sosfilt(butter(4, 140, "lowpass", fs=SR, output="sos"), drums.mean(axis=1)))
    blk = 220
    n = len(low) // blk
    if n < 10:
        return np.zeros(len(drums), np.float32)
    pk = low[: n * blk].reshape(n, blk).max(axis=1)
    a_att, a_rel = math.exp(-1 / (0.005 * SR / blk)), math.exp(-1 / (0.16 * SR / blk))
    env = np.empty(n)
    e = 0.0
    for i, v in enumerate(pk):
        c = a_att if v > e else a_rel
        e = c * e + (1 - c) * v
        env[i] = e
    env = np.clip(env / (np.percentile(env, 97) + 1e-9), 0, 1)
    return np.interp(np.arange(len(drums)), (np.arange(n) + 0.5) * blk, env).astype(np.float32)


def indie_stems(st: dict) -> dict:
    """Indie/bedroom pop: trong mem va lui ra sau, bass tron it sub, giong + guitar len truoc.
    Reverb chi tren vocals/other (IR da cat < 250 Hz) de low end khong bi duc."""
    sos = lambda o, f, t: butter(o, f, t, fs=SR, output="sos")
    env = kick_env(st["drums"])
    d = sosfiltfilt(sos(2, 55, "highpass"), st["drums"], axis=0)
    d = sosfilt(sos(1, 8000, "lowpass"), d, axis=0)                     # hi-hat bot chat
    d = reverb(d.astype(np.float32), wet=0.22, decay=0.6) * db2lin(-6.0)  # "phong" ngan cho mem
    b = sosfiltfilt(sos(2, 45, "highpass"), st["bass"], axis=0)
    b = sosfiltfilt(sos(2, 2000, "lowpass"), b, axis=0)
    b = b - 0.5 * sosfiltfilt(sos(2, 90, "lowpass"), b, axis=0)          # shelf ~ -6 dB duoi 90 Hz
    b = b.mean(axis=1, keepdims=True).repeat(2, axis=1)
    b = b * db2lin(-3.0) * (1 - 0.30 * env)[:, None]                     # nhuong cho kick
    o = sosfiltfilt(sos(2, 70, "highpass"), st["other"], axis=0) * db2lin(1.5)
    v = st["vocals"] * db2lin(2.0)
    return {"drums": d.astype(np.float32), "bass": b.astype(np.float32),
            "other": reverb(o.astype(np.float32), wet=0.18, decay=2.0),
            "vocals": reverb(v.astype(np.float32), wet=0.18, decay=2.0)}


def style_stems(st: dict, style: str, opts=None) -> dict:
    """The style's stem treatment, then the DJ settings: kick ducking (pump) and the level of each stem."""
    duck = getattr(opts, "duck", None)
    if style == "indie":
        st = indie_stems(st)
    elif style == "club":
        g = {"drums": 2.0, "bass": 2.5, "other": -1.0, "vocals": 0.5}
        st = {k: v * db2lin(g[k]) for k, v in st.items()}
        if duck is None:
            duck = 0.30
    if duck:
        env = kick_env(st["drums"])
        st["other"] = st["other"] * (1 - duck * env)[:, None]
        st["vocals"] = st["vocals"] * (1 - duck * (0.08 / 0.30) * env)[:, None]  # vocals duck much less
    gains = {k: getattr(opts, f"gain_{k}", 0.0) or 0.0 for k in STEMS}
    if any(gains.values()):
        st = {k: v * db2lin(gains[k]) for k, v in st.items()}
    return st


def echo_tail(seg: np.ndarray, delay: float, repeats: int = 7) -> np.ndarray:
    D = int(delay * SR)
    seg = seg.copy()
    f = min(len(seg) // 4, int(0.005 * SR))
    if f > 0:
        ramp = np.linspace(0, 1, f, dtype=np.float32)[:, None]
        seg[:f] *= ramp
        seg[-f:] *= ramp[::-1]
    out = np.zeros((D * repeats + len(seg), 2), np.float32)
    for k in range(1, repeats + 1):
        lp = butter(2, max(700.0, 7000.0 / (1.35 ** k)), "lowpass", fs=SR, output="sos")
        hp = butter(2, min(600.0, 120.0 * k), "highpass", fs=SR, output="sos")
        rep = sosfilt(hp, sosfilt(lp, seg, axis=0), axis=0) * (0.62 * 0.6 ** (k - 1))
        i = (k - 1) * D
        out[i:i + len(rep)] += rep.astype(np.float32)
    return out


def change_speed(x: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1) < 1e-6:
        return x
    fr = Fraction(factor).limit_denominator(100)
    return resample_poly(x, fr.denominator, fr.numerator, axis=0).astype(np.float32)


def reverb(x: np.ndarray, wet: float, decay: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(decay * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9 * t / decay)[:, None]
    ir = sosfilt(butter(2, 5000, "lowpass", fs=SR, output="sos"), ir, axis=0)
    ir = sosfilt(butter(2, 250, "highpass", fs=SR, output="sos"), ir, axis=0)
    ir = np.concatenate([np.zeros((int(0.025 * SR), 2)), ir])
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))
    w = np.stack([oaconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return ((1 - 0.35 * wet) * x + wet * w).astype(np.float32)


def fx_speed(fx: str | None, opts=None) -> float:
    sp = getattr(opts, "speed", None)
    return float(sp) if sp else SPEED[fx]


def apply_fx(x: np.ndarray, fx: str | None, opts=None) -> np.ndarray:
    """The style's effect on the whole mix. DJ settings (speed, reverb, lo-fi) replace the style's own
    values; left unset, every style sounds exactly as before."""
    x = change_speed(x, fx_speed(fx, opts))
    if fx == "indie":
        x = sosfilt(butter(2, 35, "highpass", fs=SR, output="sos"), x, axis=0)
        x = sosfilt(butter(1, 12000, "lowpass", fs=SR, output="sos"), x, axis=0)
        t = np.arange(len(x)) / SR
        tw = t + 0.0007 * np.sin(2 * np.pi * 0.45 * t)                  # wow rat nhe
        x = np.stack([np.interp(tw, t, x[:, c]) for c in range(2)], axis=1).astype(np.float32)
    lo = getattr(opts, "lofi", None) or ("on" if fx == "lofi" else "off")
    wet, decay = REVERB.get(fx, (0.0, 1.8))
    if getattr(opts, "reverb", None) is not None:
        wet = float(opts.reverb)
        decay = 2.8 if wet >= 0.25 else 1.8
    if lo == "on":  # lo-fi sach: am hon, wow ~4 cent; khong re vinyl, hiss hay meo tieng (nghe nhu loa re)
        x = sosfilt(butter(2, 70, "highpass", fs=SR, output="sos"), x, axis=0)
        x = sosfilt(butter(1, 6500, "lowpass", fs=SR, output="sos"), x, axis=0)
        t = np.arange(len(x)) / SR
        tw = t + 0.0009 * np.sin(2 * np.pi * 0.45 * t)
        x = np.stack([np.interp(tw, t, x[:, c]) for c in range(2)], axis=1).astype(np.float32)
    if wet > 0:
        x = reverb(x.astype(np.float32), wet=wet, decay=decay)
    return np.asarray(x, dtype=np.float32)


# ----------------------------------------------------------------------------- build
def build_sequence(order: list[str], an: dict, work: Path, opts):
    """Xu ly tung bai theo thu tu, chon kieu chuyen bai va vi tri toan cuc.
    Thoi diem toan cuc cua giay t trong bai i = plans[i]['off'] + t."""
    seq, plans = [], []
    for i, tid in enumerate(order):
        a = an[tid]
        gain = db2lin(PREMIX_LUFS - a["lufs"])
        if not seq:
            d_ = stems_dir(work, tid, 1.0, 0)
            m = measure(load_stems(d_))
            m["entry"] = m["start"]
            seq.append({"id": tid, "name": a["name"], "dir": d_, "m": m, "stretch": 1.0, "semis": 0,
                        "pc": a["pc"], "mode": a["mode"], "gain": gain, "an": a})
            plans.append({"off": 0.3 - m["start"], "trans": {"type": "first", "b_entry": m["start"]},
                          "trans_out": None, "chapter": 0.0})
            log(f"  [1/{len(order)}] {a['name']}: {a['bpm']} BPM, {a['key']} ({a['camelot']})")
            continue
        P = seq[-1]
        A = P["m"]
        d = decide({"ibi": A["ibi"], "pc": P["pc"], "mode": P["mode"]}, a, opts)
        stretch, semis = d["stretch"], d["semis"]
        # ung vien 1: khop phach (bai B da keo nhip / doi tong)
        beat = None
        if d["mode"] == "beat":
            d_b = stems_dir(work, tid, stretch, semis)
            m_b = measure(load_stems(d_b))
            if m_b["ibi"]:
                canonicalize(m_b, A["ibi"])
                r = m_b["ibi"] / A["ibi"]
                if abs(r - 1) > 0.0025 and abs(math.log(stretch * r)) <= math.log(1 + opts.max_stretch):
                    stretch *= r
                    log(f"      tinh chinh stretch -> x{stretch:.4f} (sai so nhip {100 * (r - 1):+.2f}%)")
                    d_b = stems_dir(work, tid, stretch, semis)
                    m_b = measure(load_stems(d_b))
                    canonicalize(m_b, A["ibi"])
                beat = beat_transition(A, m_b, P["dir"], d_b, opts)
        # ung vien 2, 3: chuyen theo cau hat / echo-out, giu toc do va tong goc
        d_n = stems_dir(work, tid, 1.0, 0)
        m_n = m_b if (beat is not None and d_n == d_b) else measure(load_stems(d_n))
        cands = [(c["cost"], c["type"], c) for c in (beat, fade_transition(A, m_n), echo_transition(A, m_n))
                 if c is not None]
        log("      diem chuyen bai (thap = tot): " + ", ".join(f"{t} {c:.1f}" for c, t, _ in sorted(cands)))
        tr = min(cands, key=lambda c: c[0])[2]
        want = getattr(opts, "transition_type", "auto")
        if want != "auto":
            pick = [c[2] for c in cands if c[1] == want]
            if pick:
                tr = pick[0]
            else:
                log(f"      {want}: khong lam duoc o day (nhip lech qua xa), dung {tr['type']}")
        if tr["type"] == "beat":
            d_, m = d_b, m_b
        else:
            stretch, semis, d_, m = 1.0, 0, d_n, m_n
        m["entry"] = tr["b_entry"]
        off_b = plans[-1]["off"] + tr["rel"]
        chapter = (plans[-1]["off"] + tr["a_start"] + 0.5 * tr["length"]) if tr["type"] == "beat" \
            else off_b + tr["b_entry"]
        plans[-1]["trans_out"] = tr
        plans.append({"off": off_b, "trans": tr, "trans_out": None, "chapter": chapter})
        seq.append({"id": tid, "name": a["name"], "dir": d_, "m": m, "stretch": stretch, "semis": semis,
                    "pc": a["pc"] + semis, "mode": a["mode"], "gain": gain, "an": a})
        extra = (f"{tr['beats']} phach, giao vocal o phach {tr['vh']}, tinh chinh {1000 * tr['fine']:+.1f} ms"
                 if tr["type"] == "beat" else
                 f"bai truoc tat dan {tr['fade0']:.1f}-{tr['cut']:.1f}s, bai sau vao tu {tr['b_entry']:.1f}s"
                 if tr["type"] == "fade" else f"cat bai truoc o {tr['cut']:.1f}s + echo")
        log(f"  [{i + 1}/{len(order)}] {a['name']}: {a['bpm']} BPM, {a['key']} ({a['camelot']}) -> "
            f"stretch x{stretch:.4f}, {semis:+d} cung, chuyen bai {tr['type']} ({extra})")
    return seq, plans


def mix_base(seq: list[dict], plans: list[dict], stem_style: str, opts=None) -> np.ndarray:
    ends = []
    for tr, pl in zip(seq, plans):
        end = tr["m"]["end_audio"] if pl["trans_out"] is None else (
            pl["trans_out"]["a_start"] + pl["trans_out"]["length"] if pl["trans_out"]["type"] == "beat"
            else pl["trans_out"]["cut"] + pl["trans_out"].get("delay", 0.0) * 8)
        ends.append(pl["off"] + end)
    buf = np.zeros((int((max(ends) + 2) * SR), 2), np.float32)
    for i, (tr, pl) in enumerate(zip(seq, plans)):
        st = load_stems(tr["dir"])
        st = {k: v * tr["gain"] for k, v in st.items()}
        st = style_stems(st, stem_style, opts)
        m, tin, tout = tr["m"], pl["trans"], pl["trans_out"]
        t0 = tin["b_entry"]
        t1 = m["end_audio"] if tout is None else (
            tout["a_start"] + tout["length"] if tout["type"] == "beat" else tout["cut"])
        i0, i1 = int(max(0, t0) * SR), min(int(t1 * SR) + 1, len(st["drums"]))
        n = i1 - i0
        if n <= 0:
            continue
        contrib = np.zeros((n, 2), np.float32)
        for s in STEMS:
            pts = [(t0, 0.0), (t0 + 0.3, 1.0)] if tin["type"] == "first" else kf_in(tin, s)
            if tout is None:
                pts += [(m["end_audio"] - 2.5, 1.0), (m["end_audio"], 0.0)]
            else:
                pts += kf_out(tout, s)
            contrib += st[s][i0:i1] * envelope(pts, i0 / SR, n)[:, None]
        g0 = int(round((pl["off"] + i0 / SR) * SR))
        if g0 < 0:
            contrib, g0 = contrib[-g0:], 0
        buf[g0:g0 + len(contrib)] += contrib[: len(buf) - g0]
        if tout is not None and tout["type"] == "echo":
            c, D = tout["cut"], tout["delay"]
            a, b = int((c - D) * SR), int(c * SR)
            seg = sum(st[s][a:b] for s in STEMS)
            tail = echo_tail(seg, D)
            g = int(round((pl["off"] + c) * SR))
            buf[g:g + len(tail)] += tail[: len(buf) - g]
    nz = np.where(np.abs(buf).max(axis=1) > 1e-4)[0]
    return buf[: nz[-1] + int(0.5 * SR)] if len(nz) else buf


def master(x: np.ndarray, out_base: Path, work: Path, target: float = TARGET_LUFS) -> dict:
    g = db2lin(target - loudness(x))
    tmp = work / "tmp_master.wav"
    write_wav(tmp, x * g)
    wav, mp3 = out_base.with_suffix(".wav"), out_base.with_suffix(".mp3")
    wav.parent.mkdir(parents=True, exist_ok=True)
    # limiter chay o 192 kHz (oversample 4x) de chan ca dinh giua cac mau (true peak)
    chain = ("aresample=192000:resampler=soxr,alimiter=limit=0.84:attack=3:release=80:level=false:latency=true,"
             "aresample=48000:resampler=soxr")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", tmp, "-af", chain,
         "-c:a", "pcm_s24le", wav])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libmp3lame",
         "-b:a", "320k", mp3])
    tmp.unlink(missing_ok=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    summ = r.stderr[r.stderr.rfind("Summary:"):]
    I = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    P = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
    return {"wav": str(wav), "mp3": str(mp3), "lufs": float(I.group(1)) if I else None,
            "true_peak_dbfs": float(P.group(1)) if P else None}


def render_demo(order: list[str], an: dict, work: Path, out: Path, style: str, opts) -> None:
    """A short preview of one transition (song k -> k+1 in the playlist order) with the chosen style and
    DJ settings. Only these two songs are separated, so it is quick once the songs are analysed."""
    k = min(max(1, opts.demo), len(order) - 1)
    pair = order[k - 1:k + 1]
    log(f"3) Tach stem (demo: chuyen bai {k} -> {k + 1})")
    separate(pair, work, opts.device)
    add_residual(work, pair)
    log("4) Khop nhip / tong")
    seq, plans = build_sequence(pair, an, work, opts)
    log("5) Render demo")
    stem_style, fx = STYLES[style]
    base = mix_base(seq, plans, stem_style, opts)
    c = plans[1]["chapter"]
    a, b = max(0, int((c - opts.demo_before) * SR)), min(len(base), int((c + opts.demo_after) * SR))
    x = apply_fx(base[a:b], fx, opts)
    f = min(len(x) // 4, int(1.5 * SR))
    ramp = np.linspace(0, 1, f, dtype=np.float32)[:, None]
    x[:f] *= ramp
    x[len(x) - f:] *= ramp[::-1]
    res = master(x, out / "_demo", work, opts.lufs)
    sp = fx_speed(fx, opts)
    info = {"style": style, "transition": k, "of": len(order) - 1, "from": seq[0]["name"], "to": seq[1]["name"],
            "type": plans[1]["trans"]["type"], "at": round((c - a / SR) / sp, 2), "length": round(len(x) / SR, 2),
            "mp3": "_demo.mp3", "lufs": res["lufs"], "made": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "_demo.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), "utf-8")
    (out / "_demo.wav").unlink(missing_ok=True)
    log(f"Demo xong: {seq[0]['name']} -> {seq[1]['name']} ({info['type']}), {fmt_time(len(x) / SR)}")


def lower_priority() -> None:
    """Chay o muc uu tien thap (Below Normal) de nhuong CPU cho viec khac, vd render video. Tien trinh con ke thua."""
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        import os
        os.nice(10)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--normal-priority" not in sys.argv:
        lower_priority()
    ap = argparse.ArgumentParser(description="Remix nhieu bai thanh mot playlist lien mach")
    ap.add_argument("playlist", help="thu muc chua cac bai, vd songs\\indie\\playlist-1")
    ap.add_argument("--styles", default="dj,lofi,slowed", help=f"cac style, cach nhau dau phay: {','.join(STYLES)}")
    ap.add_argument("--reorder", action="store_true", help="bo qua plan.json, tu sap lai thu tu")
    ap.add_argument("--no-keyshift", action="store_true", help="khong doi tong bai nao")
    ap.add_argument("--max-stretch", type=float, default=0.08, help="muc keo/nen nhip toi da (0.08 = 8%%)")
    ap.add_argument("--transition", type=float, default=14.0, help="do dai chuyen bai mong muon (giay)")
    ap.add_argument("--device", default="cuda", help="cuda hoac cpu cho Demucs")
    ap.add_argument("--work", help="thu muc cache (mac dinh <ROOT>/work/<slug>)")
    ap.add_argument("--out", help="thu muc ket qua (mac dinh <ROOT>/output/<slug>)")
    ap.add_argument("--slug", help="ten file ket qua (mac dinh theo ten thu muc)")
    ap.add_argument("--normal-priority", action="store_true", help="khong ha muc uu tien CPU")
    # DJ settings: left unset, each style keeps its own sound
    ap.add_argument("--order", choices=("smart", "keep", "files"), help="smart: theo nhip/tong; keep: plan.json; files: A-Z")
    ap.add_argument("--transition-type", choices=TRANSITION_TYPES, default="auto", help="kieu chuyen bai uu tien")
    ap.add_argument("--speed", type=float, help="toc do ca ban mix (doi ca cao do), vd 0.85 slowed, 1.2 nightcore")
    ap.add_argument("--reverb", type=float, help="reverb 0-0.6")
    ap.add_argument("--lofi", choices=("on", "off"), help="loc lo-fi: am hon, wow nhe")
    ap.add_argument("--duck", type=float, help="kick nen nhac/giong (pump) 0-0.6")
    for s in STEMS:
        ap.add_argument(f"--gain-{s}", type=float, default=0.0, help=f"muc {s} (dB)")
    ap.add_argument("--lufs", type=float, default=TARGET_LUFS, help="do to ban mix (LUFS)")
    ap.add_argument("--demo", type=int, default=0, help="chi render demo chuyen bai thu N -> N+1 (_demo.mp3)")
    ap.add_argument("--demo-before", type=float, default=22.0, help="demo: so giay truoc diem chuyen")
    ap.add_argument("--demo-after", type=float, default=26.0, help="demo: so giay sau diem chuyen")
    opts = ap.parse_args()
    if opts.order:
        opts.reorder = opts.order == "smart"
    opts.speed = min(1.5, max(0.6, opts.speed)) if opts.speed else None
    opts.reverb = min(0.6, max(0.0, opts.reverb)) if opts.reverb is not None else None
    opts.duck = min(0.6, max(0.0, opts.duck)) if opts.duck is not None else None
    opts.lufs = min(-8.0, max(-24.0, opts.lufs))
    for s in STEMS:
        setattr(opts, f"gain_{s}", min(12.0, max(-24.0, getattr(opts, f"gain_{s}"))))

    pdir = Path(opts.playlist)
    pdir = pdir if pdir.is_absolute() else (ROOT / pdir)
    if not pdir.is_dir():
        sys.exit(f"Khong thay thu muc {pdir}")
    try:
        rel = pdir.resolve().relative_to(ROOT / "songs").parts
    except ValueError:
        rel = (pdir.name,)
    slug = opts.slug or "-".join(rel) or pdir.name
    work = Path(opts.work) if opts.work else ROOT / "work" / slug
    out = Path(opts.out) if opts.out else ROOT / "output" / slug
    styles = [s.strip() for s in opts.styles.split(",") if s.strip()]
    bad = [s for s in styles if s not in STYLES]
    if bad:
        sys.exit(f"Style khong co: {bad}. Chon trong: {list(STYLES)}")

    t_start = time.time()
    files = find_inputs(pdir)
    if len(files) < 2:
        sys.exit(f"Can it nhat 2 bai trong {pdir}, dang co {len(files)}")
    log(f"Playlist '{slug}': {len(files)} bai")
    log("1) Giai ma + phan tich")
    an = analyze(files, work)
    order = load_plan(an, work, opts)
    log("2) Thu tu: " + "  ->  ".join(an[t]["name"] for t in order))
    if opts.demo:
        return render_demo(order, an, work, out, styles[0], opts)
    log("3) Tach stem")
    separate(order, work, opts.device)
    add_residual(work, order)
    log("4) Khop nhip / tong")
    seq, plans = build_sequence(order, an, work, opts)

    old_report = out / "report.json"
    prev_renders = json.loads(old_report.read_text("utf-8")).get("renders", {}) if old_report.exists() else {}
    report = {"playlist": slug, "tracks": [], "renders": prev_renders}
    for tr, pl in zip(seq, plans):
        t = pl["trans"]
        report["tracks"].append({
            "name": tr["name"], "bpm_goc": tr["an"]["bpm"], "key_goc": tr["an"]["key"],
            "camelot_goc": tr["an"]["camelot"], "stretch": round(tr["stretch"], 4),
            "doi_tong": tr["semis"], "chuyen_vao": t["type"],
            "chuyen_vao_beats": t.get("beats"), "giao_vocal_o_phach": t.get("vh"),
            "lech_tinh_chinh_ms": round(1000 * t.get("fine", 0.0), 1)})

    log("5) Render")
    bases = {}
    for style in styles:
        stem_style, fx = STYLES[style]
        if stem_style not in bases:
            bases[stem_style] = mix_base(seq, plans, stem_style, opts)
        x = apply_fx(bases[stem_style], fx, opts)
        res = master(x, out / f"{slug}_{style}", work, opts.lufs)
        sp = fx_speed(fx, opts)
        lines = [f"{fmt_time(pl['chapter'] / sp)} {tr['name']}" for tr, pl in zip(seq, plans)]
        (out / f"tracklist_{style}.txt").write_text("\n".join(lines) + "\n", "utf-8")
        res["duration"] = fmt_time(len(x) / SR)
        report["renders"][style] = res
        log(f"   {style:<9} {res['duration']}  {res['lufs']} LUFS  peak {res['true_peak_dbfs']} dBFS  -> {res['mp3']}")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    log(f"Xong sau {time.time() - t_start:.0f}s. File o: {out}")


if __name__ == "__main__":
    main()
