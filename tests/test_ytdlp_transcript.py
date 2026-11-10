import json

import pytest

from tiktok_viral import ytdlp
from tiktok_viral.transcript import NO_NARRATION, clean_text


def test_to_post_builds_url_and_skips_incomplete_entries() -> None:
    p = ytdlp.to_post({"id": 7, "view_count": 10, "timestamp": 1.0, "description": "a\nb", "repost_count": 3}, "h")
    assert p.url == "https://www.tiktok.com/@h/video/7" and p.caption == "a b" and p.shares == 3
    assert ytdlp.to_post({"id": 7, "timestamp": 1.0}, "h") is None
    assert ytdlp.to_post({"view_count": 1, "timestamp": 1.0}, "h") is None


def test_cached_channel_reads_fresh_cache_and_refetches_stale(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(ytdlp, "fetch_channel", lambda sec, n: calls.append(sec) or [{"id": "new"}])
    (tmp_path / "h.json").write_text(json.dumps({"entries": [{"id": "old"}, None]}))
    assert ytdlp.cached_channel("h", "sec", 10, tmp_path, 1) == ([{"id": "old"}], True)
    assert ytdlp.cached_channel("h", "sec", 10, tmp_path, 0) == ([{"id": "new"}], False)
    assert calls == ["sec"]
    assert json.loads((tmp_path / "h.json").read_text())["entries"] == [{"id": "new"}]


def test_run_ytdlp_raises_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(ytdlp, "YTDLP", ["false"])
    with pytest.raises(ytdlp.FetchError):
        ytdlp.run_ytdlp([])


def test_clean_text_drops_hallucinations_and_marks_music_only_videos() -> None:
    hallucinated = "Hãy subscribe cho kênh Ghiền Mì Gõ để không bỏ lỡ những video hấp dẫn\n\nThanks for watching"
    assert clean_text(hallucinated) == NO_NARRATION
    narration = " ".join(["Vì sao quán cà phê vắng khách vẫn sống được?"] * 3)
    assert clean_text(narration + "\nĐăng ký kênh nhé") == narration
