"""Make the YouTube video: one still image (the thumbnail) + the mix.

A still picture needs very few frames, so the video runs at 2 fps with a
10-second keyframe interval and x264's stillimage tuning: a 1h40 playlist
encodes in a minute or two instead of the 10+ minutes of a 30 fps encode.
Images that are not 16:9 are fitted over a blurred copy of themselves.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from playlistkit.deps import find_ffmpeg
from playlistkit.screen import probe
from playlistkit.util import NO_WINDOW, Cancelled, PlaylistKitError, cancelled, log

RESOLUTIONS = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080)}
FPS = 2


def build_cmd(ffmpeg: Path, image: Path, audio: Path, out: Path, res: str, duration: float,
              audio_copy: bool = False) -> list[str]:
    if res not in RESOLUTIONS:
        raise PlaylistKitError(f"Resolution must be one of {', '.join(RESOLUTIONS)}.")
    w, h = RESOLUTIONS[res]
    vf = (f"[0:v]split=2[bg][fg];"
          f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2,eq=brightness=-0.08[b];"
          f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[f];"
          f"[b][f]overlay=(W-w)/2:(H-h)/2,format=yuv420p,setsar=1[v]")
    crf = {"480p": "23", "720p": "22", "1080p": "21"}[res]
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-progress", "pipe:1", "-nostats",
           "-loop", "1", "-framerate", str(FPS), "-i", str(image), "-i", str(audio),
           "-filter_complex", vf, "-map", "[v]", "-map", "1:a:0",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", crf,
           "-r", str(FPS), "-g", str(FPS * 10), "-pix_fmt", "yuv420p",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    cmd += ["-c:a", "copy"] if audio_copy else ["-c:a", "aac", "-b:a", "384k", "-ar", "48000"]
    cmd += ["-t", f"{duration:.3f}", "-movflags", "+faststart", str(out)]
    return cmd


def make_video(image: Path, audio: Path, out: Path, res: str = "720p", progress=None) -> Path:
    image, audio, out = Path(image), Path(audio), Path(out)
    if not image.is_file():
        raise PlaylistKitError("Choose a thumbnail image first.")
    if not audio.is_file():
        raise PlaylistKitError("Choose the audio (WAV or MP3) first.")
    ff = find_ffmpeg()
    duration = probe(audio)["duration"]
    if duration <= 0:
        raise PlaylistKitError(f"Cannot read the length of {audio.name}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd = build_cmd(ff.ffmpeg, image, audio, tmp, res, duration, audio_copy=audio.suffix.lower() in (".m4a", ".aac"))
    log(f"Encoding {res} video ({duration / 60:.1f} min) -> {out.name}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=NO_WINDOW)
    assert proc.stdout is not None
    for line in proc.stdout:
        if cancelled():
            proc.kill()
            proc.wait()
            tmp.unlink(missing_ok=True)
            raise Cancelled()
        m = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
        if m and progress:
            progress(min(1.0, int(m.group(1)) / 1e6 / duration))
    err = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        tmp.unlink(missing_ok=True)
        raise PlaylistKitError("FFmpeg could not make the video:\n" + "\n".join(err.strip().splitlines()[-10:]))
    tmp.replace(out)
    if progress:
        progress(1.0)
    log(f"Video ready: {out}  ({out.stat().st_size / 1e6:.0f} MB)")
    return out
