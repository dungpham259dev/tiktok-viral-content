"""Recent viral videos from the channels a topic follows, ranked by viral score (see score.py). No browser."""

import csv
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from tiktok_viral.score import Scored, score_posts
from tiktok_viral.topic import Topic
from tiktok_viral.ytdlp import FetchError, cached_channel, to_post

FIELDS = ["score", "x_adj", "x", "share_lift", "rising", "sponsored", "age_days", "date", "views", "shares", "saves",
          "comments", "duration_s", "channel", "genre", "channel_baseline", "title", "url"]
MIN_MATURE = 10
PAUSE_S = 2


def _row(s: Scored, channel: dict) -> dict:
    p = s.post
    return {"score": round(s.score, 1), "x_adj": round(s.x_adj, 1), "x": round(s.x, 1),
            "share_lift": round(s.share_lift, 2), "rising": s.rising, "sponsored": s.sponsored,
            "age_days": s.age_days, "date": datetime.fromtimestamp(p.timestamp, UTC).date().isoformat(),
            "views": p.views, "shares": p.shares, "saves": p.saves, "comments": p.comments,
            "duration_s": p.duration_s, "channel": channel["handle"], "genre": channel.get("genre", ""),
            "channel_baseline": s.baseline, "title": p.caption[:200], "url": p.url}


def _markdown(topic: Topic, rows: list[dict], days: float, errors: list[str]) -> str:
    lines = [f"# Recent viral TikTok videos: {topic.name} ({datetime.now():%Y-%m-%d})", "",
             f"Posts from the last {days:g} days. score = age-adjusted x (views over the channel's usual) times "
             "sqrt(share lift). RISING = 2-7 days old. AD = sponsored caption.", "",
             "| score | x | age | views | channel | title | link |", "|---:|---:|---:|---:|---|---|---|"]
    for r in rows:
        flags = " ".join(f for f, on in (("RISING", r["rising"]), ("AD", r["sponsored"])) if on)
        lines.append(f"| {r['score']} | {r['x_adj']} | {r['age_days']}d | {r['views']:,} | @{r['channel']} | "
                     f"{flags} {r['title'][:80]} | {r['url']} |")
    if errors:
        lines += ["", "## Problems", ""] + [f"- {e}" for e in errors]
    return "\n".join(lines) + "\n"


def run_viral(topic: Topic, days: float = 30, min_views: int = 20_000, min_score: float = 3.0, posts: int = 200,
              tiers: tuple[str, ...] = ("watch",), cache_days: float = 0.5, now: float | None = None) -> Path:
    channels = topic.channels(tiers)
    if not channels:
        raise ValueError(f"topic {topic.name} follows no channels in tiers {tiers}")
    now = now or time.time()
    rows, errors = [], []
    for ch in channels:
        try:
            entries, cached = cached_channel(ch["handle"], ch["sec_uid"], posts, topic.cache_dir, cache_days)
        except (FetchError, subprocess.TimeoutExpired, ValueError) as exc:
            errors.append(f"@{ch['handle']}: {str(exc)[:160]}")
            continue
        found = [p for p in (to_post(e, ch["handle"]) for e in entries) if p]
        if sum(1 for p in found if now - p.timestamp >= 7 * 86_400) < MIN_MATURE:
            errors.append(f"@{ch['handle']}: fewer than {MIN_MATURE} posts older than 7 days; raise --posts")
        scored = [s for s in score_posts(found, now, days) if s.post.views >= min_views and s.score >= min_score]
        rows += [_row(s, ch) for s in scored]
        print(f"@{ch['handle']}: {len(found)} posts, {len(scored)} viral", file=sys.stderr)
        if not cached:
            time.sleep(PAUSE_S)
    rows.sort(key=lambda r: -r["score"])
    out = topic.run_dir("viral", datetime.now().strftime("%Y%m%d-%H%M"))
    with (out / "viral.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "viral.md").write_text(_markdown(topic, rows, days, errors))
    return out
