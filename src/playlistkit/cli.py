"""Command line: `playlistkit` opens the app; the sub-commands script the same steps."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playlistkit import __version__
from playlistkit.util import PlaylistKitError, log, setup_console


def cmd_doctor(_args) -> int:
    from playlistkit import runtime
    from playlistkit.deps import find_ffmpeg, has_rubberband, nvenc_available, nvidia_gpu

    ff = find_ffmpeg()
    log(f"PlaylistKit {__version__}")
    log(f"FFmpeg: {ff.ffmpeg}  rubberband: {'yes' if has_rubberband(ff.ffmpeg) else 'NO (the remix needs it)'}  "
        f"NVENC: {'yes' if nvenc_available(ff.ffmpeg) else 'no'}")
    log(f"NVIDIA GPU: {nvidia_gpu() or 'none'}")
    from playlistkit.gui import load_settings

    st = runtime.status(load_settings()["ai_python"])
    log(f"AI runtime: {'ready' if st.get('ok') else 'not installed'}  {st.get('python', '')}  "
        f"torch {st.get('torch', '-')}  CUDA {st.get('cuda', False)}")
    return 0


def cmd_video(args) -> int:
    from playlistkit.video import make_video

    out = Path(args.out) if args.out else Path(args.audio).with_name(f"{Path(args.audio).stem}_{args.res}.mp4")
    make_video(Path(args.image), Path(args.audio), out, args.res)
    return 0


def cmd_cut(args) -> int:
    from playlistkit import cut, meta
    from playlistkit import project as projects
    from playlistkit.gui import backlog, root

    p = projects.load(root(), args.project)
    tracks, duration = cut.current_tracks(p)
    plan = cut.plan_cut(tracks, duration, cut.parse_claims(" ".join(args.ranges)))
    for i in plan.claimed:
        log(f"  remove {plan.tracks[i][1]}")
    if args.dry_run:
        return 0
    cut.apply_cut(p, plan, backlog())
    meta.make_for_project(p, name=p.data.get("title_name", ""))
    return 0


def cmd_install_ai(_args) -> int:
    from playlistkit import runtime

    runtime.install()
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(prog="playlistkit", description="Find songs, remix them into a playlist, make the video.")
    ap.add_argument("--version", action="version", version=f"PlaylistKit {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="open the app window (default)")
    sub.add_parser("doctor", help="check FFmpeg, the GPU and the AI runtime")
    sub.add_parser("install-ai", help="install PyTorch + Demucs for the remix engine")
    v = sub.add_parser("video", help="make an MP4 from an image and an audio file")
    v.add_argument("--image", required=True)
    v.add_argument("--audio", required=True)
    v.add_argument("--res", default="720p", choices=["480p", "720p", "1080p"])
    v.add_argument("-o", "--out")
    c = sub.add_parser("cut", help="cut Content ID claimed songs out of a project's mix")
    c.add_argument("project")
    c.add_argument("ranges", nargs="+", help='e.g. "47:48-51:52" "1:06:09-1:09:29"')
    c.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd in (None, "gui"):
            from playlistkit.gui import main as gui_main

            return gui_main()
        return {"doctor": cmd_doctor, "video": cmd_video, "cut": cmd_cut, "install-ai": cmd_install_ai}[args.cmd](args)
    except PlaylistKitError as exc:
        log(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
