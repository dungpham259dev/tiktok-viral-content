import pytest
from conftest import write_run

from tiktok_viral.screen import apply_screen
from tiktok_viral.topic import TopicError

INPUTS = [{"handle": h, "sec_uid": f"sec-{h}", "median": 50_000} for h in ("good", "meh", "shop")]
SCREEN = {"good": {"keep": "yes", "category": "economics", "format": "narrated explainer", "reason": "why-questions"},
          "meh": {"keep": "maybe", "category": "finance", "format": "talking head", "reason": "advice"},
          "shop": {"keep": "no", "category": "seller", "format": "", "reason": "sells courses"}}


def test_apply_screen_records_all_and_follows_yes_and_maybe(topic, tmp_path) -> None:
    counts = apply_screen(topic, write_run(tmp_path, INPUTS, SCREEN), follow=True)
    assert counts == {"yes": 1, "maybe": 1, "no": 1, "followed": 2}
    assert [r["handle"] for r in topic.channels()] == ["good"]
    assert [r["handle"] for r in topic.channels(("maybe",))] == ["meh"]
    assert topic.channels()[0]["why"] == "narrated explainer; why-questions"
    assert topic.rejected_refs() == {"sec-shop"}


def test_apply_screen_without_follow_only_records(topic, tmp_path) -> None:
    counts = apply_screen(topic, write_run(tmp_path, INPUTS, SCREEN), follow=False)
    assert counts["followed"] == 0 and topic.channels(("watch", "maybe")) == []
    assert len(topic.screened()) == 3


@pytest.mark.parametrize("screen, message", [
    (None, "missing"),
    ({"good": {"keep": "sure"}}, "keep must be"),
    ({"stranger": {"keep": "yes"}}, "not in screen_input"),
])
def test_apply_screen_rejects_bad_screens(topic, tmp_path, screen, message) -> None:
    with pytest.raises(TopicError, match=message):
        apply_screen(topic, write_run(tmp_path, INPUTS, screen), follow=True)
    assert topic.screened() == {}
