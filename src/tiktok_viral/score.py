"""Viral score for TikTok posts: outperformance of the channel, corrected for age, weighted by shares.

Calibrated on 21,530 posts from 411 Vietnamese channels (2026-11-10): a post has about 20% of its views after
one day, 49% after two, 62% at 2-7 days and 90% at 7-14 days. Posts that beat their channel 3x had a share rate
1.56x the channel's usual; the save rate barely moved, so saves are reported but not scored.
The baseline is local: the nearest posts in time of the same format that are 7+ days old (90%+ of their views),
age-adjusted. A fixed channel-wide median made every recent post of a fast-growing channel look viral
(@kinhtegithe: recent median 12.5x its old one). Posts under 2 days are not scored: projecting them inflated
a 2-hour-old news post 5x.
"""

import re
import statistics
from dataclasses import dataclass

DAY = 86_400.0
AGE_CURVE = ((1, 0.2), (2, 0.49), (4, 0.61), (7, 0.64), (14, 0.9))
BASELINE_MAX_AGE = 180
LOCAL_POSTS = 20
PEER_MIN_AGE = 7
MIN_AGE = 2
MIN_BASELINE = 5
SHORT_MAX_SECONDS = 180
RISING_DAYS = 7
SHARE_LIFT_RANGE = (0.25, 4.0)
SPONSORED = re.compile(r"sponsor|tàitrợ|tai_?tro|taitro|hoptaccung|#ad\b|#quangcao|partner", re.IGNORECASE)


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


def is_sponsored(caption: str) -> bool:
    return bool(SPONSORED.search((caption or "").replace(" ", "")))


def _is_short(p: PostStat) -> bool:
    return p.duration_s <= SHORT_MAX_SECONDS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_posts(posts: list[PostStat], now: float, max_age_days: float) -> list[Scored]:
    out = []
    for fmt_short in (True, False):
        same = [p for p in posts if _is_short(p) == fmt_short and p.views > 0
                and (now - p.timestamp) / DAY <= BASELINE_MAX_AGE]
        for p in same:
            age = (now - p.timestamp) / DAY
            if age > max_age_days or age < MIN_AGE:
                continue
            others = [q for q in same if q.video_id != p.video_id and (now - q.timestamp) / DAY >= PEER_MIN_AGE]
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
