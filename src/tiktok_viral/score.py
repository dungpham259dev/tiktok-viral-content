"""Viral score for TikTok posts: outperformance of the channel, corrected for age, weighted by shares.

Calibrated on 21,530 posts from 411 Vietnamese channels (2026-11-10): a post has about 20% of its views after
one day, 49% after two, 62% at 2-7 days and 90% at 7-14 days. Posts that beat their channel 3x had a share rate
1.56x the channel's usual; the save rate barely moved, so saves are reported but not scored.
The baseline is local: the nearest posts in time of the same format that are 7+ days old (90%+ of their views),
age-adjusted. A fixed channel-wide median made every recent post of a fast-growing channel look viral
(@kinhtegithe: recent median 12.5x its old one). Posts under 2 days are not scored: projecting them inflated
a 2-hour-old news post 5x.
When a format has fewer than 10 mature posts, the baseline uses mature posts of both formats: @lichsu360 had 7
mature long posts, 4 of them under 2.4K views, so its 357K-view long post scored x 150 on a 92K-median channel.
"""

import re
import statistics
import unicodedata
from dataclasses import dataclass

DAY = 86_400.0
AGE_CURVE = ((1, 0.2), (2, 0.49), (4, 0.61), (7, 0.64), (14, 0.9))
BASELINE_MAX_AGE = 180
LOCAL_POSTS = 20
PEER_MIN_AGE = 7
MIN_AGE = 2
MIN_BASELINE = 5
MIN_FORMAT_PEERS = 10
SHORT_MAX_SECONDS = 180
RISING_DAYS = 7
SHARE_LIFT_RANGE = (0.25, 4.0)
# Words are matched with their diacritics: stripped, "tai tro" would also be "tải trò chơi" or "tại trọ". The unaccented
# form counts only in a caption written without diacritics. "hợp tác cùng" alone is ordinary wording, so only its
# hashtag form (#hoptaccung...) counts. Hashtags are judged one by one, with diacritics stripped.
SPONSORED_WORDS = re.compile(r"(?<!non)(?<!un)(?<!not )sponsor|\btài trợ\b|\bpaid partner|\bbrand partner")
SPONSORED_WORDS_PLAIN = re.compile(r"\btai tro\b")
# "#ad" and "#ads" may be followed by "_x" ("#ads_tiktok") but not by letters or digits ("#adidas", "#ad1").
SPONSORED_TAGS = re.compile(r"^#(ads?(?![a-z0-9])|taitro$|partner$)|(?<!non)(?<!un)sponsor|duoctaitro|nhataitro|"
                            r"taitroboi|hoptaccung|quangcao|paidpartner|brandpartner|partnership")


@dataclass(frozen=True)
class PostStat:
    video_id: str
    url: str
    caption: str
    timestamp: float
    duration_s: int
    views: int
    likes: int
    comments: int
    shares: int
    saves: int


@dataclass(frozen=True)
class Scored:
    post: PostStat
    age_days: float
    baseline: int
    x: float
    x_adj: float
    share_lift: float
    save_rate: float
    score: float
    rising: bool
    sponsored: bool


def age_fraction(age_days: float) -> float:
    for limit, fraction in AGE_CURVE:
        if age_days < limit:
            return fraction
    return 1.0


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def is_sponsored(caption: str) -> bool:
    text = unicodedata.normalize("NFC", caption or "").lower()
    words = re.sub(r"[_\s]+", " ", re.sub(r"#\S+", " ", text))
    plain = _plain(text)
    unaccented = plain == text
    tags = re.findall(r"#[^\s#]+", plain)
    # "#quảng_cáo" is one tag written with a joiner: judge it with and without the "_".
    return bool(SPONSORED_WORDS.search(words) or (unaccented and SPONSORED_WORDS_PLAIN.search(words))
                or any(SPONSORED_TAGS.search(t) or SPONSORED_TAGS.search(t.replace("_", "")) for t in tags))


def _is_short(p: PostStat) -> bool:
    return p.duration_s <= SHORT_MAX_SECONDS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_posts(posts: list[PostStat], now: float, max_age_days: float) -> list[Scored]:
    out = []
    usable = [p for p in posts if p.views > 0 and (now - p.timestamp) / DAY <= BASELINE_MAX_AGE]
    mature = [p for p in usable if (now - p.timestamp) / DAY >= PEER_MIN_AGE]
    for fmt_short in (True, False):
        same = [p for p in usable if _is_short(p) == fmt_short]
        same_mature = [q for q in mature if _is_short(q) == fmt_short]
        for p in same:
            age = (now - p.timestamp) / DAY
            if age > max_age_days or age < MIN_AGE:
                continue
            own = [q for q in same_mature if q.video_id != p.video_id]
            # A thin format gives a median of a handful of posts, which a few flops can drag to near zero.
            others = own if len(own) >= MIN_FORMAT_PEERS else [q for q in mature if q.video_id != p.video_id]
            peers = sorted(others, key=lambda q: abs(q.timestamp - p.timestamp))[:LOCAL_POSTS]
            if len(peers) < MIN_BASELINE:
                continue
            base_views = statistics.median(q.views / age_fraction((now - q.timestamp) / DAY) for q in peers)
            base_share = statistics.median(q.shares / q.views for q in peers)
            x = p.views / base_views
            x_adj = x / age_fraction(age)
            lift = _clamp((p.shares / p.views) / base_share, *SHARE_LIFT_RANGE) if base_share else 1.0
            out.append(Scored(p, round(age, 1), int(base_views), x, x_adj, lift, p.saves / p.views,
                              x_adj * lift ** 0.5, age < RISING_DAYS, is_sponsored(p.caption)))
    return sorted(out, key=lambda s: -s.score)
