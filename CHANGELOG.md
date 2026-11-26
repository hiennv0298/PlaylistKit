# Changelog

Each release's section becomes its notes on the GitHub Releases page and in the app's "What's new" window.
Add a `## <version>` section here before pushing a `v<version>` tag.

## 0.2.11

- **Fixed: the bar at the bottom stayed at "100%" with a Stop button after a job had finished.** This happened when the bar had been closed with ✕ before, or when the job was started from another window. A running job is now always shown and ends with "Done.".
- **The bar closes by itself** 8 seconds after a job finished well. Errors and Stopped stay until you close them.
- **Fixed: credits said "CC PUBLICDOMAIN"** with a dead link for songs under the old Creative Commons public domain dedication. They now say "Public Domain" with its real link.

## 0.2.10

- **Fixed: Export in the video editor seemed to do nothing.** While another job ran (Make MP4, for example), every button that starts a job ignored clicks without a word. Such a button now says which job is running and to wait for it or press Stop.
- **Export answers at once:** the bar at the bottom shows "Exporting the video · Starting…" the moment you press it.
- **Errors in the window are no longer silent.** They show in the bar at the bottom and are written to the app's log (`playlistkit-app.log`), so a button that fails says why.

## 0.2.9

- **Export carries on after Stop.** The video editor now makes a long video in 5-minute parts and keeps each finished part. Export after **Stop** starts where it stopped instead of from the beginning.
- **Export after a small edit only remakes what changed.** Each part is kept under a fingerprint of exactly what it shows. Moving a title at 30:00 remakes only the part around 30:00; the other parts and the sound are reused.
- The parts are joined without re-encoding, so the finished video is the same as before. They are kept in the playlist's `work` folder until the next export, and only for the last export.

## 0.2.8

- **Fixed: other apps were grouped under PlaylistKit's taskbar button** (CommentKit, ClipKit, anything else running on 127.0.0.1).
  - The cause: Edge replaced PlaylistKit's own taskbar ID with one named after the window's address, `MSEdge.127.0.0.1_/`, which every local app shares.
  - PlaylistKit now opens at its own address, `playlistkit.localhost`, and keeps putting its taskbar ID back while it runs. Pinning and the icon stay PlaylistKit's.
- **Fixed: two PlaylistKits could listen on the same port** (for example the old and the new one around an update). Requests then went to either one at random. The port is now PlaylistKit's alone; a second start uses another port.

## 0.2.7

- **Only music I can monetize** (Songs tab). Finds only songs whose licence allows a monetized remix: CC BY, CC BY-SA, CC0 and public domain.
  - Left out: **NC** (no commercial use), **ND** (no changes, and a remix changes the song), Sampling+, songs with no licence, and SoundCloud remixes and covers of other people's songs.
  - YouTube and Audius are skipped: their songs carry no such licence.
  - Internet Archive is searched only in its netlabels collection, because anyone can upload to the open collection and choose any licence. Commercial mixtapes marked CC turned up there.
- **Every song shows its licence** in the search results, with **$ ok** when it can be monetized. The Songs list says how many songs cannot be monetized.
- **Better credits in the YouTube description:** each Creative Commons song is credited with its title, artist, licence, a link to the licence and its page, as CC BY asks. Songs removed since are no longer credited.
- **Fixed: ccMixter search always failed** ("got more than 65536 bytes when reading header line").

## 0.2.6

- **Better thumbnails, without the length.**
  - The line under the title is now your choice: nothing (the new default), the artists in the playlist, the length, or your own text. Thumbnails PlaylistKit made by itself are redrawn without the length.
  - Bigger titles: a short name fills the picture.
  - Title effects made for each background: gradient with glow, glow, outline or shadow. A picture from the playlist gets an outline.
  - Three new backgrounds: **City night** (now the default for rap, hip-hop and phonk), **Vinyl record** (R&B, jazz, bossa nova) and **Aurora** (sleep, meditation). Synthwave has mountains on the horizon.
  - The genre emoji sits in the top line, with a short line on each side.

## 0.2.5

- **DJ settings on the Remix tab, for every genre.**
  - **Mixing:** song order (smart by tempo and key, A → Z, or the last mix's order), the kind of transition (auto, beat mix, vocal fade, echo out), its length, the max tempo change and key changes.
  - **Sound:** speed (slower and lower, or faster and higher), reverb, kick pump (sidechain), lo-fi warmth and loudness (−18 to −10 LUFS).
  - **Levels:** drums, bass, music and vocals, −12 to +6 dB.
  - The sliders start where the style is, so leaving them alone sounds the same as before. **↺ Reset** puts them back. The settings are kept with the playlist.
- **DJ presets:** 14 ready-made mixes that set the style and every DJ setting at once. They are Rap beat mix, Vinahouse club, EDM festival, Phonk drift, Deep house smooth, Synthwave drive, Pop radio, Rock / band, Nightcore, Slowed + reverb, Lo-fi chill, Indie night, Acoustic gentle, and Sleep & meditation. Every genre has one, and the presets for the playlist's genre come first in the menu. Moving any slider turns the menu to **Custom**.
- **▶ Demo:** hear one transition (1 → 2, 2 → 3, …) with your settings before making the whole mix. It renders about 45 seconds around the transition and plays it on the Remix tab. Only those two songs are separated, so a demo takes under a minute once the songs have been analysed.
- **Thumbnails made by PlaylistKit.** Once a playlist has a name, PlaylistKit makes its 1280×720 YouTube thumbnail by itself: the name, the length and the genre emoji on a background drawn for the genre (night sky, sunset, synthwave, ocean, rainy window, paper, forest, festive or bokeh). It follows the name and length while you change them. **✨ Make thumbnail** on the YouTube & video tab changes the background (or uses a picture from the playlist, darkened and blurred), the text, the font, the colour and where the text sits. **Choose your own…** still uses your own image. Make MP4 makes the thumbnail first if there is none.
- **The sound wave in the video editor's preview shows the mix's real loudness** around the playhead, without the made-up movement it had. The exported video already drew the wave from the audio itself.

## 0.2.4

- **Fixed: Update now did not install the new version.** The installer started while PlaylistKit was still running and could not close it, because PlaylistKit has no window of its own. A silent update then gave up and you stayed on the old version. The installer now waits for PlaylistKit to quit, closes it if it does not, and installs. Updating from 0.2.2 or 0.2.3 works with this release.
- **Fixed: Close this window** did nothing after you had opened a playlist. The window can now close itself. If Windows still refuses, it tells you to use the X or Alt+F4.

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
