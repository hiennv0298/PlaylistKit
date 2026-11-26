# Changelog

Each release's section becomes its notes on the GitHub Releases page and in the app's "What's new" window.
Add a `## <version>` section here before pushing a `v<version>` tag.

## 0.2.3

- **Fixed: Remix stopped with "Demucs that bai"** (`--clip-mode: invalid choice: 'none'`). The AI runtime installs Demucs 4.0.1, whose command line has no `none` option. The engine now starts Demucs so that it accepts it. Stems are still saved without clipping, so they add up exactly to the original song.
- **No more double clicks.** A button turns off while its work runs and comes back when it is done. While a job runs (find, download, check, remix, MP4, cut, Install AI, export), every button that starts a job is off, because PlaylistKit runs one job at a time.

## 0.2.2

- **Check for updates** button in the header and in Settings, which shows the current version, the latest one and when it last checked.
- **New versions show up right away.** PlaylistKit checks when it opens and every few hours while it stays open. An answer saved by an older version is no longer trusted, so 0.2.0 could miss 0.2.1 for up to a day; this no longer happens.
- **Update now closes the old version and opens the new one in the same window.** The window reloads into the new version by itself, with no leftover "PlaylistKit is not running" window and no second window.

## 0.2.1

- **AI runtime check on the Remix tab and in Settings** now tells apart: installed and set, installed but not set, a broken AI Python path, and not installed.
- **Finds an existing install by itself:** PlaylistKit's own AI folder, then Pythons on this PC (PATH, the `py` launcher, python.org installs, conda/miniforge, the active venv) that already have torch + demucs.
- **Use it** button sets the AI Python to the install it found, in one click. A working path typed in Settings can be saved the same way.
- **Install AI sets the AI Python for you** when it finishes, and **Remix** sets it by itself when the runtime is installed but not set yet.

## 0.2.0

- **Video editor** (🎬 Video editor on a playlist): a media library, a preview and a timeline, like a small Clipchamp.
  - **Media:** the playlist's mixes, thumbnail and videos are already there. Add more with **Import** or by dragging files from Explorer into the window.
  - **Timeline** with three tracks (video & images, text & effects, audio): drag media onto a track, move clips, drag their edges to trim, **Split** (S), **Delete**, **Undo/Redo** (Ctrl+Z / Ctrl+Y), zoom. Audio clips show their waveform.
  - **Text & effects:** your own titles, **Now playing** (the current song's name, taken from the tracklist), a **sound wave** and a **progress bar**. Position, size, colour and a dark box are adjustable.
  - **Pictures:** fit on a blurred copy, fill or fit with black bars, optional slow zoom. **Audio:** volume, fade in and out.
  - **Preview** plays the timeline with sound; **Check frame** shows exactly what the exported video looks like at the playhead.
  - **Export** 480p, 720p or 1080p MP4 for YouTube (NVIDIA GPU encoding when available). Still pictures export at 2 fps (fast); a sound wave uses 15 fps, video clips and slow zoom 25 fps.
- The edit is saved by itself in the playlist folder (`edit.json`).

## 0.1.3

- **Own taskbar button.** PlaylistKit's window is no longer grouped with ClipKit or other Edge app windows; it gets its own taskbar button and icon, and *Pin to taskbar* pins PlaylistKit itself.
- New demo video in the README: one playlist from start to finish (pick a genre, find 3 songs, check, remix, YouTube text, MP4, Content ID cut).

## 0.1.2

- **New app icon**, drawn separately for every size so it stays sharp in the taskbar, title bar, Start menu and desktop.
- The app window's taskbar icon is no longer blurry (the window now uses 32/192/512 px icons).
- When the window loses PlaylistKit (after **Update now**, or after PlaylistKit was closed), it says so and tells you what to do, instead of buttons silently doing nothing.

## 0.1.1

- First public build (0.1.0 was tagged but its installer could not be built).
- Content ID preview shows clean song names.
- The song check warns about lossy uploads only when they are really band-limited (below 13 kHz), so normal SoundCloud downloads are no longer flagged.
- A demo and screenshots in the README.

## 0.1.0

- First release.
- **42 genres** in 6 groups: Việt Nam (indie, acoustic, ballad, V-Pop, rap, remix, vinahouse, TikTok, bolero, nhạc Trịnh, thiếu nhi, Tết), Asia (K-Pop, C-Pop, Douyin, J-Pop, anime, T-Pop), international (US-UK, hip-hop, R&B, rock, indie folk, jazz, bossa nova, latin, country), electronic (EDM, deep house, phonk, synthwave, gaming, slowed + reverb, nightcore), relaxing (chill, lo-fi, study, piano, classical, sleep, meditation) and Christmas. Each has its own search words, remix style and YouTube text.
- **Six song sources:** SoundCloud, YouTube, Audius, Jamendo, Internet Archive netlabels and ccMixter, plus your own folder, a SoundCloud set or a YouTube playlist link. Creative Commons sources are marked, and SoundCloud releases with an ISRC or label line are flagged as likely Content ID matches.
- **Song backlog:** every downloaded, used, removed or claimed song is kept in a spreadsheet file so it never comes back; ban artists you never want.
- **Song check:** flags heavy 808 sub-bass in soft genres, low-quality uploads and duplicates; remove a song with one click (it goes to the Recycle Bin).
- **Remix** with the playlist engine (Demucs stems, beat-matched transitions, six styles, -14 LUFS). The AI part (PyTorch + Demucs, about 2.5 GB) installs on first use, and runs at low priority so other apps go first.
- **YouTube text:** title "name 🌙 | 1 giờ 22 phút", description with tracklist, credits for Creative Commons songs, hashtags and tags.
- **MP4 video** from your thumbnail and the mix at 480p, 720p or 1080p, fast (2 fps still image). Also works with any image + WAV/MP3 (Quick video).
- **Content ID:** paste the claim times from YouTube Studio, preview which songs they hit, and cut them out of the mix without re-rendering.
- **Updates inside the app:** a daily check on GitHub Releases, What's new notes, and one-click Update now for the installer version.
