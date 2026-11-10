import pytest

from tiktok_viral.topic import TopicError, init_topic, list_topics, load_topic, topics_root


def test_init_creates_an_empty_workspace(topic, tmp_path) -> None:
    assert list_topics(tmp_path) == ["demo"]
    assert topic.language == "vi"
    assert "fyp" in topic.generic_tags
    assert topic.channels() == [] and topic.screened() == {}
    assert topic.keywords() == [] and topic.tags() == [] and topic.queries() == []
    with pytest.raises(TopicError, match="already exists"):
        init_topic("demo", "", "", root=tmp_path)


def test_load_topic_by_name_or_path_and_clear_error(topic, tmp_path) -> None:
    assert load_topic("demo", tmp_path).path == topic.path
    assert load_topic(str(topic.path)).path == topic.path
    with pytest.raises(TopicError, match="tiktok-viral init"):
        load_topic("missing", tmp_path)


def test_topics_root_prefers_env_then_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_VIRAL_TOPICS", str(tmp_path / "x"))
    assert topics_root() == tmp_path / "x"
    monkeypatch.delenv("TIKTOK_VIRAL_TOPICS")
    (tmp_path / "topics").mkdir()
    monkeypatch.chdir(tmp_path)
    assert topics_root() == tmp_path / "topics"


def test_term_files_skip_comments_and_hash_signs(topic) -> None:
    (topic.path / "tags.txt").write_text("# tags\n#kinhte\n\ntaichinh\n")
    (topic.path / "keywords.txt").write_text("kiến thức kinh tế\n# old\n")
    assert topic.tags() == ["kinhte", "taichinh"]
    assert topic.keywords() == ["kiến thức kinh tế"]


def _row(handle: str, tier: str, why: str = "") -> dict:
    return {"handle": handle, "sec_uid": f"sec-{handle}", "genre": "economics", "tier": tier, "median": "1000",
            "why": why, "found_on": "2026-11-10"}


def test_add_channels_counts_new_and_never_downgrades_watch(topic) -> None:
    assert topic.add_channels([_row("a", "watch", "first"), _row("b", "maybe")]) == 2
    assert topic.add_channels([_row("a", "maybe", "second"), _row("b", "watch"), _row("c", "maybe")]) == 1
    tiers = {r["handle"]: (r["tier"], r["why"]) for r in topic.channels(("watch", "maybe"))}
    assert tiers == {"a": ("watch", "first"), "b": ("watch", ""), "c": ("maybe", "")}
    assert topic.known_refs() == {"sec-a", "sec-b", "sec-c"}


def test_add_channels_rejects_bad_rows(topic) -> None:
    with pytest.raises(TopicError):
        topic.add_channels([_row("a", "core")])
    with pytest.raises(TopicError):
        topic.add_channels([{**_row("a", "watch"), "sec_uid": ""}])


def test_record_screen_overwrites_by_channel_and_tracks_rejects(topic) -> None:
    def verdict(handle: str, v: str) -> dict:
        return {"handle": handle, "sec_uid": f"sec-{handle}", "verdict": v, "category": "", "format": "",
                "reason": "", "screened_on": "2026-11-10"}
    topic.record_screen([verdict("b", "no"), verdict("a", "maybe")])
    topic.record_screen([verdict("a", "no")])
    assert topic.rejected_refs() == {"sec-a", "sec-b"}
    assert list(topic.screened()) == ["sec-a", "sec-b"]
    with pytest.raises(TopicError):
        topic.record_screen([verdict("c", "keep")])
