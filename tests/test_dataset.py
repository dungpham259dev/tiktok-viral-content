"""Integrity of the bundled topic data and of what the repo would publish."""

import csv
import re
import subprocess
from pathlib import Path

import pytest

from tiktok_viral.topic import CHANNEL_FIELDS, SCREEN_FIELDS, TIERS, VERDICTS, list_topics, load_topic

REPO = Path(__file__).resolve().parents[1]
TOPICS = REPO / "topics"
SEC_UID = re.compile(r"MS4wLjABAAAA[\w-]{20,}")
VIDEO_URL = re.compile(r"https://www\.tiktok\.com/@[\w.\-]+/video/\d+")


def _csv(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _header(path: Path) -> list[str]:
    with path.open(newline="") as fh:
        return next(csv.reader(fh))


@pytest.mark.parametrize("name", list_topics(TOPICS))
def test_topic_files_are_consistent(name: str) -> None:
    topic = load_topic(name, TOPICS)
    channels = _csv(topic.path / "channels.csv")
    screened = _csv(topic.path / "screened.csv")
    assert _header(topic.path / "channels.csv") == CHANNEL_FIELDS
    assert _header(topic.path / "screened.csv") == SCREEN_FIELDS
    assert all(SEC_UID.fullmatch(r["sec_uid"]) for r in channels + screened)
    assert len({r["sec_uid"] for r in channels}) == len(channels)
    assert len({r["sec_uid"] for r in screened}) == len(screened)
    assert {r["tier"] for r in channels} <= set(TIERS)
    assert {r["verdict"] for r in screened} <= set(VERDICTS)
    assert not topic.known_refs() & topic.rejected_refs(), "a followed channel is also rejected"


def test_bundled_viral_lists_link_real_videos_of_known_channels() -> None:
    for path in TOPICS.glob("*/viral/*.csv"):
        rows = _csv(path)
        assert rows, path
        assert all(VIDEO_URL.fullmatch(r["url"]) for r in rows), path
        assert len({r["url"] for r in rows}) == len(rows), path


def _published_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    return [REPO / line for line in out.splitlines() if line]


def test_repo_ships_no_transcripts_media_or_secrets() -> None:
    files = _published_files()
    assert files
    assert not [f for f in files if f.name in {"transcript.txt", ".env"} or f.suffix in {".mp4", ".wav", ".m4a"}]
    secret = re.compile(r"(SADCAPTCHA_API_KEY|APIFY_TOKEN|YOUTUBE_API_KEY)\s*=\s*\S{8,}|\b[0-9a-f]{32}\b")
    leaks = [f for f in files
             if f.is_file() and f.suffix != ".lock" and secret.search(f.read_text(errors="ignore"))]
    assert not leaks, leaks


def test_csv_files_use_unix_line_endings(topic) -> None:
    topic.add_channels([{"handle": "a", "sec_uid": "sec-a", "tier": "watch"}])
    files = [topic.path / "channels.csv", *TOPICS.glob("*/*.csv"), *TOPICS.glob("*/viral/*.csv")]
    assert not [f for f in files if b"\r\n" in f.read_bytes()]
