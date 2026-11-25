# Changelog

Each release's section becomes its notes on the GitHub Releases page and in the app's "What's new" window.
Add a `## <version>` section here before pushing a `v<version>` tag.

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
