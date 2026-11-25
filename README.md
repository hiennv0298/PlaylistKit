# PlaylistKit

Make long music playlists for YouTube: pick a genre, PlaylistKit finds songs, checks them, **remixes them into one seamless mix**, writes the **title, description, tracklist and tags**, and turns your thumbnail + the mix into an **MP4 (480p / 720p / 1080p)**. When YouTube's Content ID claims a song, paste the timestamps and PlaylistKit cuts it out without re-rendering.

Everything runs on your computer. No account, no API key (Jamendo needs a free client ID if you want that source).

## What it does

| Step | |
| :--- | :--- |
| **1 · Songs** | Search **SoundCloud, YouTube, Audius, Jamendo, Internet Archive netlabels and ccMixter** with words made for each of **42 genres**, or paste a SoundCloud set / YouTube playlist link, or use your own folder. Songs you used, removed or got claimed before are filtered out by the **backlog**, one song per artist. Each song shows its rights: Creative Commons, artist upload, unknown, or *Content ID likely* (SoundCloud releases with an ISRC or label line, official channels). Untick what you don't want, then **Download**. |
| **Check** | Every song is checked for heavy 808 sub-bass (in soft genres), low-quality uploads and duplicates. Remove a song with one click: it goes to the Recycle Bin and into the backlog so it never comes back. |
| **2 · Remix** | The remix engine separates each song into stems with Demucs, orders the songs by tempo and key, beat-matches them and blends them with stem transitions (vocals out first, bass swap, drums last), applies the genre's style and masters to −14 LUFS. Output: 48 kHz WAV, MP3 320k and a tracklist with timestamps. |
| **3 · YouTube** | Title like `chuyện mưa và những câu xin chào 🌧️ \| 1 giờ 44 phút`, a description with the tracklist, credits for Creative Commons songs, 3 hashtags, and up to 500 characters of tags. Copy each with one click; edit song names in the tracklist. |
| **Video** | Choose a thumbnail and make the MP4: still image, 2 fps H.264 + AAC 384 kHz, so a 1h40 playlist encodes in a couple of minutes. Images that aren't 16:9 sit on a blurred copy of themselves. **Quick video** on the home screen does the same for any image + WAV/MP3. |
| **4 · Content ID** | Paste the claim times from YouTube Studio (`47:48 — 51:52` …). PlaylistKit shows which songs they hit and the new length, then cuts them out with 3 s crossfades, re-limits the audio, and updates the tracklist, description and backlog. |

### Genres

| Group | Genres (remix style) |
| :--- | :--- |
| Việt Nam | Indie Việt, Acoustic, Ballad (indie) · Nhạc trẻ / V-Pop, Rap Việt, Tết (dj) · Remix Việt, Vinahouse, Nhạc TikTok (club) · Bolero / Nhạc vàng, Nhạc Trịnh / Nhạc xưa, Thiếu nhi (indie) |
| Châu Á | K-Pop, C-Pop / Nhạc Hoa, J-Pop, Anime / OST, T-Pop (dj) · Douyin (slowed) |
| Quốc tế | US-UK Pop, Hip-hop, R&B / Soul, Rock (dj) · Indie Folk, Jazz, Bossa Nova, Country (indie) · Latin / Reggaeton (club) |
| Điện tử & DJ | EDM / DJ, Deep House, Phonk, Gaming (club) · Synthwave (dj) · Slowed + Reverb (slowed) · Nightcore |
| Thư giãn | Chill, Lo-fi, Học tập, Ngủ / Ambient, Thiền (lofi) · Piano, Cổ điển (indie) |
| Khác | Giáng sinh |

Remix styles: **indie** soft drums, low sub-bass, vocals forward, 4 % slower · **lofi** beat-matched, lo-fi filter, 8 % slower · **dj** beat-matched stem transitions · **club** harder drums and bass · **slowed** 15 % slower with reverb · **nightcore** 20 % faster.

## Install

1. Download `PlaylistKit-Setup-<version>.exe` from [**Releases**](https://github.com/hiennv0298/PlaylistKit/releases/latest) (or the portable zip) and run it. No admin rights needed; FFmpeg is included.
2. Open **PlaylistKit**. The first time you press **Remix**, install the AI runtime from **Settings → Install AI**: it downloads PyTorch + Demucs (about 2.5 GB, CUDA build when you have an NVIDIA GPU) into `%LOCALAPPDATA%\PlaylistKit\ai`. Already have a Python with torch and demucs? Point **Settings → AI Python** at it instead.

> The installer is not code-signed yet, so Windows SmartScreen may warn you: click **More info → Run anyway**.

Run from source instead: `run.cmd` (creates `.venv` on first run), or `pip install -e .` then `playlistkit`.

### Updates

PlaylistKit checks GitHub Releases once a day (nothing about you is sent) and shows a notice with the release notes. With the installer version, **Update now** downloads the new installer, checks it against the release's `SHA256SUMS.txt`, installs it and reopens the app; your playlists, settings and the AI runtime stay. A *What's new* window shows the notes once after each update. Click the version in the header to check right away; turn the daily check off in Settings.

## Copyright, honestly

- Most commercial songs (V-Pop, K-Pop, C-Pop, Douyin, US-UK…) are registered with **Content ID**. A mix of them will be claimed: the owners may monetize or block the video. The genre screen says how risky each genre is.
- Safer: songs the artists upload themselves without distribution, and **Creative Commons** music from Jamendo, ccMixter and Internet Archive netlabels (CC BY needs credit: PlaylistKit writes it into the description; NC licences forbid monetized use).
- Upload as **Private** first, open *Copyright → See details*, and paste the claim times into tab 4.

## Command line

```bash
playlistkit                         # open the app
playlistkit doctor                  # FFmpeg (needs rubberband), NVENC, GPU, AI runtime
playlistkit install-ai              # install PyTorch + Demucs
playlistkit video --image thumb.png --audio mix.wav --res 720p
playlistkit cut indie-3 "47:48-51:52" "1:06:09-1:09:29" --dry-run
```

## Files

```
<Music>\PlaylistKit\
  backlog.tsv                 every song: downloaded / used / claimed / not-fit / bad-quality / duplicate / banned-artist
  indie-1\
    project.json  candidates.json  downloads.json  screen.json  thumb.jpg
    songs\                    the downloaded songs (or your own folder)
    work\                     engine caches (decoded audio, stems): safe to delete
    out\  indie-1_indie.wav/.mp3  tracklist_indie.txt  youtube_meta.txt  indie-1_720p.mp4
```

## Development

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Build the Windows release (the installer needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -DownloadFfmpeg
```

### Releasing a new version

1. Set the version in `pyproject.toml`, `src/playlistkit/__init__.py` and `installer/playlistkit.iss`.
2. Add a `## <version>` section at the top of [`CHANGELOG.md`](CHANGELOG.md), written for users: it becomes the GitHub release text and the in-app *What's new*.
3. Commit, then `git tag -a v<version> -m "PlaylistKit <version>"` and `git push origin v<version>`.

The **Release** workflow checks the tag against the version and the changelog, builds the installer and the portable zip, writes `SHA256SUMS.txt` and publishes them. Installed copies see the update within a day.

```
src/playlistkit/
  gui.py         the app: local web server, JSON API, app window, jobs
  webui/         the page (one HTML file, no dependencies)
  genres.py      42 genre presets: queries, remix style, Content ID risk, YouTube text
  sources.py     SoundCloud, YouTube, Audius, Jamendo, Internet Archive, ccMixter, local folders
  backlog.py     the song backlog (TSV)
  download.py    yt-dlp and direct downloads
  screen.py      sub-bass, bandwidth, duplicates
  runtime.py     installs the AI runtime (uv + PyTorch + Demucs) and runs the engine
  engine/        remix_engine.py: Demucs stems, beat-matching, transitions, styles, mastering
  meta.py        tracklist clean-up, title, description, tags
  video.py       still image + audio -> MP4
  cut.py         Content ID cuts
  updates.py     GitHub Releases check, verified one-click install
```

MIT License.
