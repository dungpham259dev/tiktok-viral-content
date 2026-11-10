"""Channel profile from its recent posts: how many views a normal video gets, how often it hits, what format."""

import re
import statistics
import time
from dataclasses import dataclass

from tiktok_viral.score import score_posts
from tiktok_viral.ytdlp import to_post

DAY = 86_400.0
RECENT_DAYS = 30
VIRAL_VIEWS = 100_000
HIT_SCORE = 3.0
HIT_MIN_VIEWS = 20_000
CAPTION_MAX = 200
# 30%+ question captions kept 21 of 24 known good explainer channels and dropped 74% of off-niche ones.
QUESTION = re.compile(r"(tại sao|vì sao|bao nhiêu|thế nào|ra sao|là gì|\bai\b|\bwhy\b|\bhow\b|\bwhat\b|\?)",
                      re.IGNORECASE)


@dataclass(frozen=True)
class Profile:
    posts: int
    posts_30d: int
    median: int
    viral_share: float
    hits_30d: int
    question_share: float
    duration_s: int


def build_profile(entries: list[dict], handle: str, now: float | None = None) -> Profile:
    now = now or time.time()
    valid = [e for e in entries if e and e.get("view_count") is not None]
    views = [int(e["view_count"]) for e in valid]
    if not views:
        return Profile(0, 0, 0, 0.0, 0, 0.0, 0)
    posts = [p for p in (to_post(e, handle) for e in valid) if p]
    hits = [s for s in score_posts(posts, now, RECENT_DAYS) if s.score >= HIT_SCORE and s.post.views >= HIT_MIN_VIEWS]
    recent = sum(1 for e in valid if e.get("timestamp") and now - e["timestamp"] <= RECENT_DAYS * DAY)
    captions = [e.get("description") or "" for e in valid]
    return Profile(
        posts=len(views),
        posts_30d=recent,
        median=int(statistics.median(views)),
        viral_share=round(sum(v >= VIRAL_VIEWS for v in views) / len(views), 2),
        hits_30d=len(hits),
        question_share=round(sum(bool(QUESTION.search(c)) for c in captions) / len(captions), 2),
        duration_s=int(statistics.median(int(e.get("duration") or 0) for e in valid)),
    )


def is_strong(p: Profile, good_median: int, min_posts_30d: int) -> bool:
    return p.median >= good_median and p.posts_30d >= min_posts_30d


def rank_profiles(profiles: dict[str, Profile], good_median: int, min_posts_30d: int,
                  min_questions: float = 0.3) -> list[str]:
    """Active strong channels first, question-led (explainer) ones ahead, then by median views."""
    def key(handle: str) -> tuple[bool, bool, bool, int, float]:
        p = profiles[handle]
        strong = p.median >= good_median
        return (p.posts_30d < min_posts_30d, not strong, not (strong and p.question_share >= min_questions),
                -p.median, -p.viral_share)
    return sorted(profiles, key=key)


def _sample(entry: dict) -> dict:
    return {"views": int(entry["view_count"]), "duration_s": int(entry.get("duration") or 0),
            "caption": " ".join((entry.get("description") or "").split())[:CAPTION_MAX]}


def post_samples(entries: list[dict], top: int, recent: int) -> tuple[list[dict], list[dict]]:
    """The channel's biggest posts and its newest other posts, for a content screen."""
    posts = [e for e in entries if e and e.get("view_count") is not None]
    biggest = sorted(posts, key=lambda e: -e["view_count"])[:top]
    taken = {id(e) for e in biggest}
    newest = [e for e in sorted(posts, key=lambda e: -(e.get("timestamp") or 0)) if id(e) not in taken][:recent]
    return [_sample(e) for e in biggest], [_sample(e) for e in newest]
