"""Find new channels for a topic: browser search, then a yt-dlp profile of every candidate, then a screen file.

Measured on Vietnamese economics (2026-11-10): account search (`keywords`) was the most precise source; tags mined
from known channels reached 6 of 13 known channels; profiling every candidate (not just the top 45) found three
strong channels the cut had skipped. Numbers do not tell whether a channel makes the right kind of video, so the
run ends with screen_input.json for an agent or a person to judge (see the skill).
"""

import csv
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from tiktok_viral.browser import collect, page_urls
from tiktok_viral.profile import Profile, build_profile, is_strong, post_samples, rank_profiles
from tiktok_viral.topic import Topic
from tiktok_viral.web import Author, coverage, language_authors, merge_accounts, mine_tags, rank_authors, source_yield
from tiktok_viral.ytdlp import FetchError, cached_channel

MIN_TAG_CHANNELS = 2
LANGUAGE_SHARE = 0.5
SCREEN_TOP = 12
SCREEN_RECENT = 5
PAUSE_S = 3
CANDIDATE_FIELDS = ["handle", "sec_uid", "followers", "found_by", "median", "posts_30d", "hits_30d", "viral_share",
                    "question_share", "duration_s", "best_video_views", "best_video_url"]


@dataclass(frozen=True)
class DiscoverOptions:
    scrolls: int = 6
    min_plays: int = 50_000
    check: int = 300
    check_accounts: int = 400
    good_median: int = 20_000
    min_posts_30d: int = 2
    posts: int = 60
    cache_days: float = 3
    any_language: bool = False
    stealth: bool = False
    headless: bool = False
    captcha_wait: int = 120


def mined_tags(topic: Topic, top: int, posts: int, cache_days: float) -> list[str]:
    captions: dict[str, list[str]] = {}
    for ch in topic.channels():
        try:
            entries, _ = cached_channel(ch["handle"], ch["sec_uid"], posts, topic.cache_dir, cache_days)
        except (FetchError, subprocess.TimeoutExpired) as exc:
            print(f"@{ch['handle']}: {exc}", file=sys.stderr)
            continue
        captions[ch["handle"]] = [e.get("description") or "" for e in entries]
    own = {"".join(c for c in ch["handle"].lower() if c.isalnum()) for ch in topic.channels(("watch", "maybe"))}
    uses = mine_tags(captions, MIN_TAG_CHANNELS, topic.generic_tags | own)
    return [u.tag for u in uses[:top]]


def profile_authors(authors: list[Author], topic: Topic, opts: DiscoverOptions) -> tuple[dict[str, Profile],
                                                                                       dict[str, list], list[str]]:
    stats: dict[str, Profile] = {}
    entries_of: dict[str, list] = {}
    errors: list[str] = []
    for a in authors:
        try:
            entries, cached = cached_channel(a.handle, a.sec_uid, opts.posts, topic.cache_dir, opts.cache_days)
        except (FetchError, subprocess.TimeoutExpired, ValueError) as exc:
            errors.append(f"@{a.handle}: {str(exc)[:160]}")
            continue
        stats[a.handle] = build_profile(entries, a.handle)
        entries_of[a.handle] = entries
        print(f"@{a.handle}: median {stats[a.handle].median:,}{' (cached)' if cached else ''}", file=sys.stderr)
        if not cached:
            time.sleep(PAUSE_S)
    return stats, entries_of, errors


def _candidate(a: Author, p: Profile | None) -> dict:
    row = {"handle": a.handle, "sec_uid": a.sec_uid, "followers": a.followers, "found_by": "; ".join(a.sources),
           "best_video_views": a.best_plays, "best_video_url": a.best_url}
    return row | ({k: v for k, v in asdict(p).items() if k in CANDIDATE_FIELDS} if p else {})


def _digest(topic: Topic, ranked: list[Author], stats: dict[str, Profile], seen: tuple[list[str], list[str]],
            yields: dict[str, tuple[int, int, int]], problems: list[str], opts: DiscoverOptions) -> str:
    found, missed = seen
    lines = [f"# Discovery: {topic.name} ({datetime.now():%Y-%m-%d})", "",
             f"{len(ranked)} new channels, {len(stats)} profiled. Coverage of channels already followed: "
             f"{len(found)}/{len(found) + len(missed)}.", "", "## Strong channels (to screen)", "",
             "| channel | median | posts 30d | hits 30d | questions | duration |", "|---|---:|---:|---:|---:|---:|"]
    for a in ranked:
        p = stats.get(a.handle)
        if p and is_strong(p, opts.good_median, opts.min_posts_30d):
            lines.append(f"| [@{a.handle}](https://www.tiktok.com/@{a.handle}) | {p.median:,} | {p.posts_30d} | "
                         f"{p.hits_30d} | {p.question_share:.0%} | {p.duration_s}s |")
    lines += ["", f"## Yield per source (good = median >= {opts.good_median:,} and active)", "",
              "| source | results | new channels | good |", "|---|---:|---:|---:|"]
    for src, (res, new, good) in sorted(yields.items(), key=lambda kv: (-kv[1][2], -kv[1][1])):
        lines.append(f"| {src} | {res} | {new} | {good} |")
    if problems:
        lines += ["", "## Problems", ""] + [f"- {p}" for p in problems]
    return "\n".join(lines) + "\n"


def run_discover(topic: Topic, tags: list[str], queries: list[str], keywords: list[str],
                 opts: DiscoverOptions) -> Path:
    if not (tags or queries or keywords):
        raise ValueError("nothing to search: give tags, queries or keywords")
    out = topic.run_dir("discover", datetime.now().strftime("%Y%m%d-%H%M"))
    got = collect(page_urls(tags, queries, keywords), opts.scrolls, opts.headless, opts.captcha_wait, opts.stealth)
    known, rejected = topic.known_refs(), topic.rejected_refs()
    keep = None if opts.any_language else language_authors(got.items, topic.language, LANGUAGE_SHARE)
    pool = [i for i in got.items if keep is None or i.sec_uid in keep]
    authors = merge_accounts(rank_authors(pool, known | rejected, opts.min_plays), got.accounts, known | rejected)
    by_account = [a for a in authors if any(s.startswith("user:") for s in a.sources)]
    by_video = [a for a in authors if a not in by_account]
    stats, entries_of, errors = profile_authors(by_account[: opts.check_accounts] + by_video[: opts.check], topic, opts)
    order = {h: i for i, h in enumerate(rank_profiles(stats, opts.good_median, opts.min_posts_30d))}
    ranked = sorted(authors, key=lambda a: order.get(a.handle, len(order)))
    good = {a.sec_uid for a in ranked if a.handle in stats and is_strong(stats[a.handle], opts.good_median,
                                                                         opts.min_posts_30d)}
    bios = {acc.sec_uid: acc.bio for acc in got.accounts}
    screen_input = []
    for a in ranked:
        if a.sec_uid in good:
            top, recent = post_samples(entries_of[a.handle], SCREEN_TOP, SCREEN_RECENT)
            screen_input.append({"handle": a.handle, "sec_uid": a.sec_uid, "url": f"https://www.tiktok.com/@{a.handle}",
                                 "bio": bios.get(a.sec_uid, ""), "found_by": list(a.sources),
                                 **asdict(stats[a.handle]), "top_posts": top, "recent_posts": recent})
    (out / "screen_input.json").write_text(json.dumps(screen_input, ensure_ascii=False, indent=1))
    with (out / "candidates.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CANDIDATE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(_candidate(a, stats.get(a.handle)) for a in ranked)
    seen = coverage({i.sec_uid for i in got.items} | {a.sec_uid for a in got.accounts},
                    {r["sec_uid"]: r["handle"] for r in topic.channels()})
    yields = source_yield(pool, got.accounts, known | rejected, good)
    (out / "digest.md").write_text(_digest(topic, ranked, stats, seen, yields, got.problems + errors, opts))
    return out
