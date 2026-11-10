import json

import pytest

from tiktok_viral.topic import Topic, init_topic

NOW = 1_800_000_000.0
DAY = 86_400.0


def raw(vid: str, author: str, plays: int, followers: int = 1000) -> dict:
    return {
        "id": vid,
        "desc": f"video {vid}\nline two",
        "createTime": 1762000000,
        "author": {"uniqueId": author, "nickname": author.title(), "secUid": f"sec-{author}"},
        "stats": {"playCount": plays, "diggCount": 10, "commentCount": 2, "shareCount": 3, "collectCount": 4},
        "authorStats": {"followerCount": followers},
        "video": {"duration": 61},
    }


def entry(vid: int, views: int, age_days: float, shares: int = 10, caption: str = "Vì sao giá vàng tăng?",
          duration: int = 90) -> dict:
    return {"id": str(vid), "view_count": views, "timestamp": NOW - age_days * DAY, "duration": duration,
            "description": caption, "like_count": views // 20, "comment_count": 5, "repost_count": shares,
            "save_count": 3}


def channel_entries(base_views: int = 10_000, hit_views: int = 200_000, hit_age: float = 5) -> list[dict]:
    """30 ordinary posts spread over 60 days plus one fresh hit with a high share count."""
    posts = [entry(i, base_views + i * 10, 8 + i * 2) for i in range(30)]
    return [entry(999, hit_views, hit_age, shares=400)] + posts


@pytest.fixture
def topic(tmp_path) -> Topic:
    return init_topic("demo", "demo topic", "vi", root=tmp_path)


def write_run(tmp_path, inputs: list[dict], screen: dict | None):
    run = tmp_path / "run"
    run.mkdir()
    (run / "screen_input.json").write_text(json.dumps(inputs))
    if screen is not None:
        (run / "screen.json").write_text(json.dumps(screen))
    return run
