"""Genre presets: where to look for songs, how to remix them and how to describe the playlist.

Each genre has search queries per source, a remix style for the engine, a
Content ID risk note, and YouTube text (emoji, tagline, hashtags, tags).

Remix styles (see engine/remix_engine.py):
  indie     soft drums, low sub-bass, vocals forward, slowed 4%      (acoustic, indie, ballad...)
  lofi      beat-matched, then a lo-fi filter and 8% slower         (chill, study)
  dj        beat-matched, stem transitions, no effect                (pop, rap, K-pop...)
  club      like dj with harder drums and bass                       (remix, EDM, vinahouse)
  slowed    dj, 15% slower with reverb                               (slowed + reverb, Douyin)
  nightcore club, 20% faster and higher                              (nightcore)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Genre:
    id: str
    name: str
    group: str
    style: str
    emoji: str
    queries: tuple[str, ...]                   # SoundCloud / YouTube / Audius text search
    tags: tuple[str, ...] = ()                 # Jamendo, ccMixter, Internet Archive tags (English)
    risk: str = "medium"                       # Content ID risk when using SoundCloud/YouTube uploads
    min_sec: int = 120
    max_sec: int = 360
    hashtags: tuple[str, ...] = ()
    yt_tags: tuple[str, ...] = ()
    tagline: str = ""
    blurb: str = ""
    engine: dict = field(default_factory=dict)  # extra engine options


SOFT = {"keyshift": False, "max_stretch": 0.04}
DANCE = {"keyshift": True, "max_stretch": 0.08}

_G = [
    # ---- Việt Nam
    Genre("indie", "Indie Việt", "Việt Nam", "indie", "🌙",
          ("indie việt", "indie viet demo", "nhạc indie việt acoustic", "indie vietnam original"),
          ("indie", "acoustic", "singer-songwriter"), "medium",
          hashtags=("#indieviet", "#nhacchill", "#playlist"),
          yt_tags=("indie việt", "indie viet", "nhạc indie", "nhạc chill", "playlist indie", "nhạc indie nhẹ nhàng",
                   "acoustic việt", "nhạc mộc", "demo indie", "vietnamese indie"),
          tagline="a playlist of small songs — indie • acoustic • chill",
          blurb="{n} bài indie Việt, phần lớn là demo và bản mộc do chính các bạn nghệ sĩ tự đăng, được mix lại nhẹ hơn, "
                "chậm hơn một chút, giọng hát gần hơn. {dur_text} cho những buổi tối pha cà phê, làm việc muộn, "
                "hay chỉ ngồi nghe ai đó kể chuyện.", engine=SOFT),
    Genre("acoustic", "Acoustic Việt", "Việt Nam", "indie", "🎸",
          ("acoustic việt", "acoustic cover việt", "guitar acoustic việt original", "mộc acoustic"),
          ("acoustic", "folk", "guitar"), "medium",
          hashtags=("#acoustic", "#nhacmoc", "#playlist"),
          yt_tags=("acoustic việt", "nhạc acoustic", "nhạc mộc", "guitar acoustic", "acoustic nhẹ nhàng", "playlist acoustic"),
          tagline="just a guitar and a voice — acoustic • mộc • chill",
          blurb="{n} bài acoustic, chỉ guitar và giọng hát. {dur_text} nhẹ nhàng để làm việc, đọc sách hay thư giãn.",
          engine=SOFT),
    Genre("ballad", "Ballad Việt", "Việt Nam", "indie", "💧",
          ("ballad việt", "nhạc ballad buồn", "ballad việt original", "nhạc buồn tâm trạng"),
          ("ballad", "pop", "piano"), "high",
          hashtags=("#ballad", "#nhacbuon", "#playlist"),
          yt_tags=("ballad việt", "nhạc ballad", "nhạc buồn", "nhạc tâm trạng", "playlist ballad", "nhạc trẻ buồn"),
          tagline="for the quiet hours — ballad • tâm trạng",
          blurb="{n} bản ballad cho những lúc chậm lại. {dur_text} để nghe một mình.", engine=SOFT),
    Genre("vpop", "Nhạc trẻ / V-Pop", "Việt Nam", "dj", "✨",
          ("vpop", "nhạc trẻ", "v-pop hits", "nhạc trẻ hay nhất"),
          ("pop",), "high",
          hashtags=("#vpop", "#nhactre", "#playlist"),
          yt_tags=("vpop", "v-pop", "nhạc trẻ", "nhạc trẻ hay nhất", "nhạc hot", "playlist vpop", "nhạc việt"),
          tagline="V-Pop mix — nhạc trẻ • hits",
          blurb="{n} bài V-Pop được nối liền mạch thành một bản mix {dur_text}.", engine=DANCE),
    Genre("rap", "Rap Việt", "Việt Nam", "dj", "🎤",
          ("rap việt", "rap việt underground", "rap việt chill", "rap love việt"),
          ("hiphop", "rap"), "high",
          hashtags=("#rapviet", "#hiphop", "#playlist"),
          yt_tags=("rap việt", "rap viet", "hiphop việt", "underground", "rap chill", "playlist rap việt"),
          tagline="Rap Việt mix — underground • chill rap • love rap",
          blurb="{n} bài rap Việt nối liền mạch, beat khớp nhịp. {dur_text} để lái xe, tập gym hay làm việc.",
          min_sec=100, engine=DANCE),
    Genre("remix", "Remix Việt", "Việt Nam", "club", "🔥",
          ("nhạc remix việt", "remix tiktok việt", "nhạc trẻ remix", "remix hot"),
          ("remix", "dance"), "high",
          hashtags=("#remix", "#nhacremix", "#playlist"),
          yt_tags=("nhạc remix", "remix việt", "nhạc trẻ remix", "remix tiktok", "nonstop", "playlist remix"),
          tagline="Remix Việt nonstop — bass • tiktok • hot",
          blurb="{n} bản remix nối liền nhịp, nonstop {dur_text}.", min_sec=90, engine=DANCE),
    Genre("vinahouse", "Vinahouse", "Việt Nam", "club", "💥",
          ("vinahouse", "nonstop vinahouse", "việt mix vinahouse", "vinahouse remix 2026"),
          ("house", "dance"), "high",
          hashtags=("#vinahouse", "#nonstop", "#vietmix"),
          yt_tags=("vinahouse", "nonstop", "việt mix", "nhạc bay", "vinahouse remix", "nhạc dj"),
          tagline="Vinahouse nonstop — việt mix • bass căng",
          blurb="{n} track vinahouse nối nhịp liên tục, {dur_text} không nghỉ.", min_sec=90, engine=DANCE),
    Genre("tiktok", "Nhạc TikTok", "Việt Nam", "club", "📱",
          ("nhạc tiktok", "nhạc hot tiktok", "tiktok trend việt", "nhạc tiktok remix"),
          ("pop", "dance"), "high",
          hashtags=("#nhactiktok", "#tiktok", "#playlist"),
          yt_tags=("nhạc tiktok", "nhạc hot tiktok", "trend tiktok", "tiktok remix", "nhạc xu hướng", "playlist tiktok"),
          tagline="TikTok hits mix — trend • viral",
          blurb="{n} bài đang hot trên TikTok, nối liền mạch {dur_text}.", min_sec=60, engine=DANCE),
    Genre("bolero", "Bolero / Nhạc vàng", "Việt Nam", "indie", "🌾",
          ("bolero", "nhạc vàng", "bolero trữ tình", "nhạc trữ tình quê hương"),
          ("bolero", "latin"), "high",
          hashtags=("#bolero", "#nhacvang", "#trutinh"),
          yt_tags=("bolero", "nhạc vàng", "trữ tình", "nhạc quê hương", "bolero hay nhất", "nhạc xưa"),
          tagline="bolero • nhạc vàng • trữ tình",
          blurb="{n} bài bolero trữ tình, {dur_text} nghe cùng gia đình.", engine=SOFT),
    Genre("trinh", "Nhạc Trịnh / Nhạc xưa", "Việt Nam", "indie", "🍂",
          ("nhạc trịnh", "nhạc trịnh công sơn", "nhạc xưa", "tình khúc xưa"),
          ("vintage", "folk"), "high",
          hashtags=("#nhactrinh", "#nhacxua", "#playlist"),
          yt_tags=("nhạc trịnh", "trịnh công sơn", "nhạc xưa", "tình khúc", "nhạc phòng trà", "acoustic nhạc trịnh"),
          tagline="nhạc Trịnh • tình khúc xưa • phòng trà",
          blurb="{n} tình khúc xưa, {dur_text} cho buổi chiều chậm.", engine=SOFT),
    Genre("thieunhi", "Thiếu nhi", "Việt Nam", "indie", "🧸",
          ("nhạc thiếu nhi", "bài hát thiếu nhi", "nhạc cho bé"),
          ("children", "kids"), "medium",
          hashtags=("#thieunhi", "#nhacchobe", "#playlist"),
          yt_tags=("nhạc thiếu nhi", "bài hát thiếu nhi", "nhạc cho bé", "nhạc mầm non", "ca nhạc thiếu nhi"),
          tagline="nhạc thiếu nhi vui nhộn",
          blurb="{n} bài hát thiếu nhi, {dur_text} cho bé vui chơi.", min_sec=60, engine=SOFT),
    Genre("tet", "Nhạc Tết / Xuân", "Việt Nam", "dj", "🧧",
          ("nhạc tết", "nhạc xuân", "nhạc tết remix", "xuân 2027"),
          ("happy", "festive"), "high",
          hashtags=("#nhactet", "#nhacxuan", "#tet"),
          yt_tags=("nhạc tết", "nhạc xuân", "tết 2027", "nhạc tết remix", "playlist tết"),
          tagline="nhạc Tết • xuân về", blurb="{n} bài nhạc xuân, {dur_text} cho ngày Tết.", engine=DANCE),
    # ---- Châu Á
    Genre("kpop", "K-Pop", "Châu Á", "dj", "💜",
          ("kpop", "k-pop hits", "kpop playlist", "kpop chill"),
          ("kpop", "pop"), "high",
          hashtags=("#kpop", "#kpopplaylist", "#playlist"),
          yt_tags=("kpop", "k-pop", "kpop playlist", "kpop mix", "korean pop", "kpop hits"),
          tagline="K-Pop mix — hits • chill", blurb="{n} K-Pop tracks mixed together, {dur_en}.", engine=DANCE),
    Genre("cpop", "C-Pop / Nhạc Hoa", "Châu Á", "dj", "🏮",
          ("c-pop", "nhạc hoa", "chinese pop", "华语流行"),
          ("chinese", "pop"), "high",
          hashtags=("#cpop", "#nhachoa", "#playlist"),
          yt_tags=("cpop", "c-pop", "nhạc hoa", "nhạc trung", "chinese song", "华语", "playlist nhạc hoa"),
          tagline="C-Pop • nhạc Hoa • 华语", blurb="{n} bài nhạc Hoa, nối liền mạch {dur_text}.", engine=DANCE),
    Genre("douyin", "Douyin / 抖音", "Châu Á", "slowed", "🌸",
          ("douyin", "抖音", "nhạc douyin", "douyin remix", "douyin slowed"),
          ("chinese", "remix"), "high",
          hashtags=("#douyin", "#nhactrung", "#抖音"),
          yt_tags=("douyin", "抖音", "nhạc douyin", "nhạc trung tiktok", "douyin remix", "nhạc trung hot"),
          tagline="Douyin hits — 抖音 • slowed", blurb="{n} bài hot trên Douyin, slowed nhẹ, {dur_text}.",
          min_sec=60, engine=DANCE),
    Genre("jpop", "J-Pop", "Châu Á", "dj", "🗻",
          ("jpop", "j-pop", "japanese pop", "city pop"),
          ("jpop", "japanese"), "high",
          hashtags=("#jpop", "#citypop", "#playlist"),
          yt_tags=("jpop", "j-pop", "japanese music", "city pop", "jpop playlist"),
          tagline="J-Pop • city pop", blurb="{n} J-Pop tracks, {dur_en}.", engine=DANCE),
    Genre("anime", "Anime / OST", "Châu Á", "dj", "🎌",
          ("anime ost", "anime opening", "anime song", "ost phim"),
          ("soundtrack", "anime"), "high",
          hashtags=("#anime", "#ost", "#playlist"),
          yt_tags=("anime", "anime ost", "anime opening", "soundtrack", "ost", "anime playlist"),
          tagline="anime • OST • soundtrack", blurb="{n} anime songs and OSTs, {dur_en}.", engine=DANCE),
    Genre("thai", "T-Pop (Thái)", "Châu Á", "dj", "🐘",
          ("thai pop", "t-pop", "เพลงไทย"), ("thai", "pop"), "high",
          hashtags=("#tpop", "#thaisong", "#playlist"),
          yt_tags=("tpop", "t-pop", "thai song", "nhạc thái", "เพลงไทย"),
          tagline="T-Pop • nhạc Thái", blurb="{n} bài T-Pop, {dur_text}.", engine=DANCE),
    # ---- Quốc tế
    Genre("usuk", "US-UK Pop", "Quốc tế", "dj", "🌎",
          ("us uk pop", "pop hits", "english songs", "top hits"),
          ("pop",), "high",
          hashtags=("#usuk", "#pophits", "#playlist"),
          yt_tags=("us uk", "nhạc us uk", "pop hits", "english songs", "top hits", "playlist us uk"),
          tagline="US-UK pop mix", blurb="{n} US-UK pop songs mixed together, {dur_en}.", engine=DANCE),
    Genre("hiphop", "Hip-hop / US Rap", "Quốc tế", "dj", "🧢",
          ("hip hop", "us rap", "boom bap", "chill hip hop"),
          ("hiphop", "rap"), "high",
          hashtags=("#hiphop", "#rap", "#playlist"),
          yt_tags=("hip hop", "rap", "us rap", "boom bap", "hip hop playlist", "rap mix"),
          tagline="hip-hop mix", blurb="{n} hip-hop tracks, beat-matched, {dur_en}.", min_sec=100, engine=DANCE),
    Genre("rnb", "R&B / Soul", "Quốc tế", "dj", "🍷",
          ("r&b", "rnb chill", "soul", "neo soul"),
          ("rnb", "soul"), "medium",
          hashtags=("#rnb", "#soul", "#playlist"),
          yt_tags=("r&b", "rnb", "soul", "neo soul", "chill rnb", "rnb playlist"),
          tagline="R&B • soul • late night", blurb="{n} R&B and soul tracks, {dur_en}.", engine=DANCE),
    Genre("rock", "Rock", "Quốc tế", "dj", "🤘",
          ("rock", "alternative rock", "rock việt", "indie rock"),
          ("rock", "alternative"), "medium",
          hashtags=("#rock", "#alternative", "#playlist"),
          yt_tags=("rock", "alternative rock", "indie rock", "rock việt", "rock playlist"),
          tagline="rock • alternative", blurb="{n} rock tracks, {dur_en}.", engine=DANCE),
    Genre("indiefolk", "Indie Folk (EN)", "Quốc tế", "indie", "🌲",
          ("indie folk", "bedroom pop", "indie acoustic", "soft indie"),
          ("indie", "folk", "acoustic"), "medium",
          hashtags=("#indiefolk", "#bedroompop", "#playlist"),
          yt_tags=("indie folk", "bedroom pop", "indie acoustic", "soft indie", "indie playlist", "chill indie"),
          tagline="indie folk • bedroom pop • soft", blurb="{n} soft indie songs, {dur_en}.", engine=SOFT),
    Genre("jazz", "Jazz", "Quốc tế", "indie", "🎷",
          ("jazz", "jazz cafe", "smooth jazz", "jazz việt"),
          ("jazz",), "low",
          hashtags=("#jazz", "#cafemusic", "#playlist"),
          yt_tags=("jazz", "smooth jazz", "jazz cafe", "coffee jazz", "jazz playlist", "relaxing jazz"),
          tagline="jazz • cafe • smooth", blurb="{n} jazz tracks for a slow cafe afternoon, {dur_en}.", engine=SOFT),
    Genre("bossa", "Bossa Nova", "Quốc tế", "indie", "☕",
          ("bossa nova", "bossa nova cafe", "bossa nova cover"),
          ("bossanova", "latin", "jazz"), "low",
          hashtags=("#bossanova", "#cafemusic", "#playlist"),
          yt_tags=("bossa nova", "bossa nova cafe", "cafe music", "bossa playlist", "relaxing bossa"),
          tagline="bossa nova • cafe", blurb="{n} bossa nova songs, {dur_en}.", engine=SOFT),
    Genre("latin", "Latin / Reggaeton", "Quốc tế", "club", "💃",
          ("reggaeton", "latin pop", "latin hits"), ("latin", "reggaeton"), "high",
          hashtags=("#latin", "#reggaeton", "#playlist"),
          yt_tags=("latin", "reggaeton", "latin pop", "latin hits", "latin playlist"),
          tagline="latin • reggaeton", blurb="{n} latin tracks, {dur_en}.", engine=DANCE),
    Genre("country", "Country / Folk", "Quốc tế", "indie", "🤠",
          ("country", "folk", "americana"), ("country", "folk"), "medium",
          hashtags=("#country", "#folk", "#playlist"),
          yt_tags=("country", "folk", "americana", "country playlist"),
          tagline="country • folk", blurb="{n} country and folk songs, {dur_en}.", engine=SOFT),
    # ---- Điện tử & DJ
    Genre("edm", "EDM / DJ", "Điện tử & DJ", "club", "🎧",
          ("edm", "dj mix", "electro house", "progressive house"),
          ("electronic", "edm", "house"), "medium",
          hashtags=("#edm", "#djmix", "#playlist"),
          yt_tags=("edm", "dj mix", "electronic", "house", "edm mix", "edm playlist"),
          tagline="EDM • DJ mix", blurb="{n} EDM tracks beat-matched into one DJ mix, {dur_en}.", min_sec=90,
          engine=DANCE),
    Genre("deephouse", "Deep House", "Điện tử & DJ", "club", "🌊",
          ("deep house", "chill house", "tropical house", "deep house việt"),
          ("deephouse", "house", "chillout"), "medium",
          hashtags=("#deephouse", "#chillhouse", "#playlist"),
          yt_tags=("deep house", "chill house", "tropical house", "deep house mix", "house music"),
          tagline="deep house • chill house", blurb="{n} deep house tracks, {dur_en}.", min_sec=120, engine=DANCE),
    Genre("phonk", "Phonk", "Điện tử & DJ", "club", "🏎️",
          ("phonk", "drift phonk", "brazilian phonk"), ("phonk", "trap"), "medium",
          hashtags=("#phonk", "#driftphonk", "#playlist"),
          yt_tags=("phonk", "drift phonk", "brazilian phonk", "phonk mix", "gym phonk"),
          tagline="phonk • drift", blurb="{n} phonk tracks, {dur_en}.", min_sec=90, engine=DANCE),
    Genre("synthwave", "Synthwave / Retro", "Điện tử & DJ", "dj", "🌆",
          ("synthwave", "retrowave", "80s synth"), ("synthwave", "electronic", "retro"), "low",
          hashtags=("#synthwave", "#retrowave", "#playlist"),
          yt_tags=("synthwave", "retrowave", "80s", "outrun", "synthwave mix"),
          tagline="synthwave • retrowave", blurb="{n} synthwave tracks, {dur_en}.", engine=DANCE),
    Genre("gaming", "Gaming", "Điện tử & DJ", "club", "🎮",
          ("gaming music", "ncs", "no copyright gaming music", "dubstep"),
          ("electronic", "dubstep", "gaming"), "low",
          hashtags=("#gamingmusic", "#ncs", "#playlist"),
          yt_tags=("gaming music", "music for gaming", "ncs", "edm gaming", "dubstep", "gaming mix"),
          tagline="music for gaming", blurb="{n} high-energy tracks for gaming, {dur_en}.", min_sec=90, engine=DANCE),
    Genre("slowed", "Slowed + Reverb", "Điện tử & DJ", "slowed", "🌫️",
          ("slowed reverb", "slowed and reverb", "nhạc slowed"), ("chill", "ambient"), "high",
          hashtags=("#slowedreverb", "#slowed", "#playlist"),
          yt_tags=("slowed reverb", "slowed", "slowed and reverb", "nhạc slowed", "sad slowed"),
          tagline="slowed + reverb", blurb="{n} songs, slowed with reverb, {dur_en}.", engine=DANCE),
    Genre("nightcore", "Nightcore", "Điện tử & DJ", "nightcore", "⚡",
          ("nightcore", "sped up", "nightcore mix"), ("electronic", "pop"), "high",
          hashtags=("#nightcore", "#spedup", "#playlist"),
          yt_tags=("nightcore", "sped up", "nightcore mix", "nightcore playlist"),
          tagline="nightcore • sped up", blurb="{n} songs, sped up, {dur_en}.", engine=DANCE),
    # ---- Thư giãn
    Genre("chill", "Chill", "Thư giãn", "lofi", "☁️",
          ("nhạc chill", "chill việt", "chill vibes", "chill pop"),
          ("chill", "chillout", "lounge"), "medium",
          hashtags=("#nhacchill", "#chill", "#playlist"),
          yt_tags=("nhạc chill", "chill", "chill vibes", "nhạc thư giãn", "playlist chill", "nhạc nhẹ nhàng"),
          tagline="chill • vibes • thư giãn", blurb="{n} bài chill, {dur_text} để thư giãn.", engine=SOFT),
    Genre("lofi", "Lo-fi", "Thư giãn", "lofi", "📻",
          ("lofi", "lofi việt", "lofi hip hop", "lofi chill"),
          ("lofi", "chillhop", "hiphop"), "medium",
          hashtags=("#lofi", "#lofichill", "#playlist"),
          yt_tags=("lofi", "lofi chill", "lofi việt", "lofi hip hop", "nhạc lofi", "lofi playlist", "chill beats"),
          tagline="lo-fi • chill beats", blurb="{n} bài lo-fi, {dur_text} để học, làm việc hay ngủ.", engine=SOFT),
    Genre("study", "Học tập / Tập trung", "Thư giãn", "lofi", "📚",
          ("study music", "focus music", "music for studying", "nhạc học bài"),
          ("ambient", "instrumental", "piano", "lofi"), "low",
          hashtags=("#studymusic", "#focus", "#playlist"),
          yt_tags=("study music", "focus music", "nhạc học bài", "nhạc tập trung", "music for studying", "deep focus"),
          tagline="study • focus", blurb="{n} tracks to help you focus, {dur_en}.", engine=SOFT),
    Genre("piano", "Piano / Không lời", "Thư giãn", "indie", "🎹",
          ("piano", "piano cover", "nhạc không lời", "instrumental"),
          ("piano", "instrumental", "classical"), "low",
          hashtags=("#piano", "#nhackhongloi", "#playlist"),
          yt_tags=("piano", "piano cover", "nhạc không lời", "instrumental", "relaxing piano", "piano playlist"),
          tagline="piano • không lời", blurb="{n} bản piano không lời, {dur_text}.", engine=SOFT),
    Genre("classical", "Cổ điển", "Thư giãn", "indie", "🎻",
          ("classical music", "nhạc cổ điển", "mozart", "chopin"),
          ("classical", "orchestral"), "low", min_sec=120, max_sec=600,
          hashtags=("#classicalmusic", "#nhaccodien", "#playlist"),
          yt_tags=("classical music", "nhạc cổ điển", "mozart", "chopin", "bach", "classical playlist"),
          tagline="classical", blurb="{n} classical pieces, {dur_en}.", engine=SOFT),
    Genre("sleep", "Ngủ / Ambient", "Thư giãn", "lofi", "🌌",
          ("sleep music", "ambient", "nhạc ngủ ngon", "relaxing music"),
          ("ambient", "relaxation", "newage"), "low", min_sec=120, max_sec=900,
          hashtags=("#sleepmusic", "#ambient", "#playlist"),
          yt_tags=("sleep music", "ambient", "nhạc ngủ", "relaxing music", "nhạc thư giãn", "deep sleep"),
          tagline="sleep • ambient", blurb="{n} ambient tracks for sleep, {dur_en}.", engine=SOFT),
    Genre("meditation", "Thiền / Phật giáo", "Thư giãn", "lofi", "🪷",
          ("nhạc thiền", "meditation music", "nhạc phật giáo không lời"),
          ("meditation", "ambient", "relaxation"), "low", min_sec=120, max_sec=900,
          hashtags=("#nhacthien", "#meditation", "#playlist"),
          yt_tags=("nhạc thiền", "meditation music", "nhạc phật giáo", "nhạc tĩnh tâm", "relaxing"),
          tagline="thiền • tĩnh tâm", blurb="{n} bản nhạc thiền, {dur_text} để tĩnh tâm.", engine=SOFT),
    Genre("christmas", "Giáng sinh", "Khác", "dj", "🎄",
          ("christmas songs", "nhạc giáng sinh", "noel"), ("christmas",), "high",
          hashtags=("#christmas", "#giangsinh", "#noel"),
          yt_tags=("christmas songs", "nhạc giáng sinh", "noel", "christmas playlist", "nhạc noel"),
          tagline="Christmas • Noel", blurb="{n} Christmas songs, {dur_en}.", engine=DANCE),
]

GENRES: dict[str, Genre] = {g.id: g for g in _G}
GROUPS = list(dict.fromkeys(g.group for g in _G))
STYLES = ("indie", "lofi", "dj", "club", "slowed", "nightcore")
RISK_TEXT = {
    "low": "Low Content ID risk: instrumental and Creative Commons music is easy to find.",
    "medium": "Medium Content ID risk: prefer self-uploaded originals and Creative Commons sources.",
    "high": "High Content ID risk: most songs in this genre are commercial releases registered with Content ID. "
            "Expect claims on SoundCloud/YouTube re-uploads; Jamendo, Audius and Internet Archive are safer.",
}


def get(genre_id: str) -> Genre:
    try:
        return GENRES[genre_id]
    except KeyError:
        raise KeyError(f"unknown genre '{genre_id}'") from None


# Creative Commons catalogues are mostly Western and instrumental: worth searching for these genres only
CC_FRIENDLY = {"indiefolk", "jazz", "bossa", "country", "rock", "edm", "deephouse", "phonk", "synthwave", "gaming",
               "chill", "lofi", "study", "piano", "classical", "sleep", "meditation", "hiphop", "rnb", "latin"}


def default_sources(g: Genre) -> list[str]:
    if g.id in CC_FRIENDLY:
        return ["soundcloud", "audius", "jamendo", "archive", "ccmixter"]
    return ["soundcloud", "youtube"]


def as_list() -> list[dict]:
    return [{"id": g.id, "name": g.name, "group": g.group, "style": g.style, "emoji": g.emoji, "risk": g.risk,
             "risk_text": RISK_TEXT[g.risk], "queries": list(g.queries), "sources": default_sources(g)} for g in _G]
