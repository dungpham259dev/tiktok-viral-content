"""tiktok-viral: find channels in a niche, list their recent viral videos, pull transcripts."""

import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

from tiktok_viral.discover import DiscoverOptions, mined_tags, run_discover
from tiktok_viral.screen import apply_screen
from tiktok_viral.topic import TopicError, init_topic, list_topics, load_topic, topics_root
from tiktok_viral.transcript import TranscriptError, fetch_transcript
from tiktok_viral.viral import run_viral
from tiktok_viral.ytdlp import FetchError

REPO = Path(__file__).resolve().parents[2]
URL = re.compile(r"https://www\.tiktok\.com/@([\w.\-]+)/video/(\d+)")


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _split(text: str) -> list[str]:
    return [t.strip().lstrip("#") for t in (text or "").split(",") if t.strip()]


def cmd_topics(_: argparse.Namespace) -> int:
    root = topics_root()
    names = list_topics(root)
    print(f"topics in {root}:" if names else f"no topics in {root}; create one with `tiktok-viral init`")
    for name in names:
        t = load_topic(name, root)
        print(f"  {name}: {len(t.channels())} watched, {len(t.channels(('maybe',)))} maybe, "
              f"{len(t.screened())} screened - {t.config.get('description', '')}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    t = init_topic(args.name, args.description, args.language)
    print(f"created {t.path}: add account keywords to keywords.txt, then run discover")
    return 0


def cmd_channels(args: argparse.Namespace) -> int:
    t = load_topic(args.topic)
    tiers = ("watch", "maybe") if args.all else ("watch",)
    for row in sorted(t.channels(tiers), key=lambda r: -int(r["median"] or 0)):
        print(f"{row['tier']:5} @{row['handle']:28} median {int(row['median'] or 0):>9,}  {row['why'][:70]}")
    return 0


def cmd_mine_tags(args: argparse.Namespace) -> int:
    print(", ".join(mined_tags(load_topic(args.topic), args.top, args.posts, args.cache_days)))
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    t = load_topic(args.topic)
    keywords = _split(args.keywords) + (t.keywords() if args.topic_terms else [])
    tags = _split(args.tags) + (t.tags() if args.topic_terms else [])
    queries = _split(args.queries) + (t.queries() if args.topic_terms else [])
    if args.mine_tags:
        tags += mined_tags(t, args.mine_tags, args.posts, args.cache_days)
    opts = DiscoverOptions(scrolls=args.scrolls, check=args.check, check_accounts=args.check_accounts,
                           good_median=args.good_median, posts=args.posts, cache_days=args.cache_days,
                           any_language=args.any_language, stealth=args.stealth, headless=args.headless,
                           captcha_wait=args.captcha_wait)
    out = run_discover(t, list(dict.fromkeys(tags)), list(dict.fromkeys(queries)), list(dict.fromkeys(keywords)), opts)
    print(f"-> {out}\nNext: screen {out / 'screen_input.json'} into screen.json, then "
          f"`tiktok-viral screen-apply {args.topic} {out}`")
    return 0


def cmd_screen_apply(args: argparse.Namespace) -> int:
    counts = apply_screen(load_topic(args.topic), Path(args.run_dir), follow=not args.no_follow)
    print(", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


def cmd_viral(args: argparse.Namespace) -> int:
    tiers = ("watch", "maybe") if args.include_maybe else ("watch",)
    out = run_viral(load_topic(args.topic), args.days, args.min_views, args.min_score, args.posts, tiers,
                    args.cache_days)
    print(f"-> {out / 'viral.md'}")
    return 0


def _urls_from(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.from_csv:
        with open(args.from_csv, newline="") as fh:
            urls += [r["url"] for r in csv.DictReader(fh)][: args.top]
    bad = [u for u in urls if not URL.fullmatch(u)]
    if bad:
        raise SystemExit(f"not TikTok video URLs: {bad}")
    return urls


def cmd_transcript(args: argparse.Namespace) -> int:
    out_root = Path(args.out)
    failures = 0
    for url in _urls_from(args):
        handle, vid = URL.fullmatch(url).groups()
        slug = f"{handle}-{vid}"
        try:
            res = fetch_transcript(url, out_root / slug, out_root / ".media" / slug, args.language)
            print(f"OK  {slug}: {res['words']} words ({res['source']}), {res['views']} views")
        except (FetchError, TranscriptError) as exc:
            failures += 1
            print(f"ERR {slug}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def cmd_update(_: argparse.Namespace) -> int:
    if _git("rev-parse", "--verify", "HEAD").returncode != 0:
        print(f"error: {REPO} is not a git clone with commits; reinstall with git clone", file=sys.stderr)
        return 2
    before = _git("rev-parse", "HEAD").stdout.strip()
    pull = _git("pull", "--ff-only", "--autostash")
    if pull.returncode != 0:
        print(f"error: git pull failed (local edits to tracked files?):\n{pull.stderr.strip()}\n"
              f"see `git -C {REPO} status`", file=sys.stderr)
        return 1
    after = _git("rev-parse", "HEAD").stdout.strip()
    conflicts = _git("diff", "--name-only", "--diff-filter=U").stdout.split()
    if conflicts:
        print(f"updated to {after[:7]}, but your local edits conflict with it in: {', '.join(conflicts)}\n"
              "the files hold conflict markers; your edits are also kept in `git stash list`. "
              f"Fix them, then `git -C {REPO} add <file>` and `git -C {REPO} stash drop`", file=sys.stderr)
        return 1
    if before == after:
        print("already up to date")
        return 0
    print(_git("log", "--oneline", f"{before}..{after}").stdout.strip())
    sync = subprocess.run(["uv", "sync", "--inexact"], cwd=REPO, capture_output=True, text=True)
    print("dependencies synced" if sync.returncode == 0 else f"warning: uv sync failed: {sync.stderr[-200:]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tiktok-viral", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("topics", help="list topic workspaces").set_defaults(func=cmd_topics)
    sub.add_parser("update", help="pull the latest tool, skill and bundled data").set_defaults(func=cmd_update)

    p = sub.add_parser("init", help="create a topic workspace")
    p.add_argument("name")
    p.add_argument("--description", default="")
    p.add_argument("--language", default="", help="caption language filter, e.g. vi; empty keeps every language")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("channels", help="list the channels a topic follows")
    p.add_argument("topic")
    p.add_argument("--all", action="store_true", help="include tier maybe")
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("mine-tags", help="hashtags that 2+ followed channels use")
    p.add_argument("topic")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--posts", type=int, default=60)
    p.add_argument("--cache-days", type=float, default=3)
    p.set_defaults(func=cmd_mine_tags)

    p = sub.add_parser("discover", help="find new channels (browser) and write screen_input.json")
    p.add_argument("topic")
    p.add_argument("--keywords", default="", help="account-search keywords, comma-separated")
    p.add_argument("--tags", default="", help="hashtags, comma-separated")
    p.add_argument("--queries", default="", help="video-search phrases, comma-separated")
    p.add_argument("--topic-terms", action="store_true", help="add keywords.txt, tags.txt and queries.txt")
    p.add_argument("--mine-tags", type=int, default=0, help="add the N tags followed channels use most")
    p.add_argument("--stealth", action="store_true",
                   help="hide the automation flag so account search works (against TikTok's terms; your call)")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--captcha-wait", type=int, default=120)
    p.add_argument("--scrolls", type=int, default=6)
    p.add_argument("--check", type=int, default=300, help="video-found channels to profile")
    p.add_argument("--check-accounts", type=int, default=400, help="account-search channels to profile")
    p.add_argument("--good-median", type=int, default=20_000)
    p.add_argument("--posts", type=int, default=60, help="posts fetched per candidate channel")
    p.add_argument("--cache-days", type=float, default=3)
    p.add_argument("--any-language", action="store_true")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("screen-apply", help="record screen.json verdicts and follow the channels that passed")
    p.add_argument("topic")
    p.add_argument("run_dir")
    p.add_argument("--no-follow", action="store_true", help="record verdicts only")
    p.set_defaults(func=cmd_screen_apply)

    p = sub.add_parser("viral", help="score the recent videos of followed channels (no browser)")
    p.add_argument("topic")
    p.add_argument("--days", type=float, default=30)
    p.add_argument("--min-views", type=int, default=20_000)
    p.add_argument("--min-score", type=float, default=3.0)
    p.add_argument("--posts", type=int, default=200)
    p.add_argument("--cache-days", type=float, default=0.5)
    p.add_argument("--include-maybe", action="store_true")
    p.set_defaults(func=cmd_viral)

    p = sub.add_parser("transcript", help="download videos and transcribe their narration")
    p.add_argument("urls", nargs="*")
    p.add_argument("--from-csv", help="a viral.csv; takes its first --top rows")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--out", default="transcripts")
    p.add_argument("--language", default="", help="whisper language code, e.g. vi")
    p.set_defaults(func=cmd_transcript)
    return ap


def main(argv: list[str] | None = None) -> int:
    load_env(Path.cwd() / ".env")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (TopicError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
