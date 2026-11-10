"""TikTok channel and video access through yt-dlp: no browser, no login, no captcha.

yt-dlp reads a channel by its secUid (`tiktokuser:<secUid>`). It cannot search; finding channels needs the browser
(see browser.py). TikTok can break yt-dlp for a few days at a time; errors are raised, never swallowed.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from tiktok_viral.score import PostStat

YTDLP = [sys.executable, "-m", "yt_dlp"]
TIMEOUT_S = 300
# The default TikTok format pairs video with the post's attached music track; the muxed h264 file keeps the voice.
VOICE_FORMAT = "b[vcodec^=h264][acodec!=none]/b"


class FetchError(RuntimeError):
    pass


def run_ytdlp(args: list[str], timeout: int = TIMEOUT_S) -> str:
    proc = subprocess.run(YTDLP + args, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise FetchError(f"yt-dlp failed: {proc.stderr.strip()[-240:]}")
    return proc.stdout


def fetch_channel(sec_uid: str, posts: int) -> list[dict]:
    out = run_ytdlp(["--flat-playlist", "-J", "--playlist-end", str(posts), f"tiktokuser:{sec_uid}"])
    if not out.strip():
        raise FetchError("yt-dlp returned nothing")
    return [e for e in json.loads(out).get("entries") or [] if e]


def cached_channel(handle: str, sec_uid: str, posts: int, cache_dir: Path,
                   max_age_days: float) -> tuple[list[dict], bool]:
    """Channel entries from a fresh cache file when there is one, else from TikTok (and cached)."""
    path = cache_dir / f"{handle}.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < max_age_days * 86_400
    if fresh:
        data = json.loads(path.read_text())
        entries = [e for e in data.get("entries") or [] if e]
        # A 60-post fetch from discover must not stand in for a 200-post viral fetch.
        if entries and data.get("requested", len(entries)) >= posts:
            return entries[:posts], True
    entries = fetch_channel(sec_uid, posts)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"handle": handle, "sec_uid": sec_uid, "requested": posts, "entries": entries},
                               ensure_ascii=False))
    return entries, False


def to_post(entry: dict, handle: str) -> PostStat | None:
    if entry.get("view_count") is None or not entry.get("timestamp") or not entry.get("id"):
        return None
    return PostStat(str(entry["id"]), f"https://www.tiktok.com/@{handle}/video/{entry['id']}",
                    " ".join((entry.get("description") or "").split()), float(entry["timestamp"]),
                    int(entry.get("duration") or 0), int(entry["view_count"]), int(entry.get("like_count") or 0),
                    int(entry.get("comment_count") or 0), int(entry.get("repost_count") or 0),
                    int(entry.get("save_count") or 0))


def video_info(url: str) -> dict:
    return json.loads(run_ytdlp(["-J", "--no-playlist", url]))


def download_video(url: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    run_ytdlp(["-f", VOICE_FORMAT, "-o", str(dest / "video.%(ext)s"), url], timeout=900)
    files = sorted(dest.glob("video.*"))
    if not files:
        raise FetchError("download produced no file")
    return files[0]
