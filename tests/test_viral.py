import csv

import pytest
from conftest import NOW, channel_entries

from tiktok_viral import viral
from tiktok_viral.ytdlp import FetchError


@pytest.fixture
def followed(topic):
    topic.add_channels([
        {"handle": "steady", "sec_uid": "sec-steady", "genre": "economics", "tier": "watch", "median": "10000"},
        {"handle": "broken", "sec_uid": "sec-broken", "genre": "finance", "tier": "watch", "median": "1"},
        {"handle": "edge", "sec_uid": "sec-edge", "genre": "finance", "tier": "maybe", "median": "1"},
    ])
    return topic


def fake_cache(handle, sec_uid, posts, cache_dir, max_age_days):
    if handle == "broken":
        raise FetchError("yt-dlp failed: This account requires an account that has access")
    return channel_entries(), True


def test_run_viral_scores_followed_channels_and_reports_problems(followed, monkeypatch) -> None:
    monkeypatch.setattr(viral, "cached_channel", fake_cache)
    out = viral.run_viral(followed, now=NOW)
    with (out / "viral.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["channel"], r["views"]) for r in rows] == [("steady", "200000")]
    assert rows[0]["url"] == "https://www.tiktok.com/@steady/video/999"
    assert rows[0]["rising"] == "True" and float(rows[0]["score"]) >= 3
    md = (out / "viral.md").read_text()
    assert "@steady" in md and "RISING" in md
    assert "## Problems" in md and "@broken: yt-dlp failed" in md


def test_run_viral_include_maybe_and_thresholds(followed, monkeypatch) -> None:
    monkeypatch.setattr(viral, "cached_channel", fake_cache)
    out = viral.run_viral(followed, tiers=("watch", "maybe"), now=NOW)
    with (out / "viral.csv").open() as fh:
        assert sorted(r["channel"] for r in csv.DictReader(fh)) == ["edge", "steady"]
    out = viral.run_viral(followed, min_views=500_000, now=NOW + 60)
    with (out / "viral.csv").open() as fh:
        assert list(csv.DictReader(fh)) == []


def test_run_viral_warns_when_a_channel_has_too_few_mature_posts(followed, monkeypatch) -> None:
    monkeypatch.setattr(viral, "cached_channel", lambda *a: (channel_entries()[:5], True))
    md = (viral.run_viral(followed, now=NOW) / "viral.md").read_text()
    assert "fewer than 10 posts older than 7 days" in md


def test_run_viral_needs_followed_channels(topic) -> None:
    with pytest.raises(ValueError, match="follows no channels"):
        viral.run_viral(topic, now=NOW)
