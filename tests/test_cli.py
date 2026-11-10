from conftest import write_run

from tiktok_viral import cli


def test_topics_init_and_channels_commands(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("TIKTOK_VIRAL_TOPICS", str(tmp_path))
    assert cli.main(["topics"]) == 0
    assert "no topics" in capsys.readouterr().out
    assert cli.main(["init", "cooking", "--language", "vi", "--description", "home cooking"]) == 0
    assert cli.main(["init", "cooking"]) == 2
    assert "already exists" in capsys.readouterr().err
    assert cli.main(["topics"]) == 0
    assert "cooking: 0 watched, 0 maybe, 0 screened - home cooking" in capsys.readouterr().out
    assert cli.main(["channels", "nope"]) == 2


def test_screen_apply_command(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("TIKTOK_VIRAL_TOPICS", str(tmp_path / "topics"))
    (tmp_path / "topics").mkdir()
    cli.main(["init", "t"])
    run = write_run(tmp_path, [{"handle": "a", "sec_uid": "sec-a", "median": 9}], {"a": {"keep": "yes"}})
    capsys.readouterr()
    assert cli.main(["screen-apply", "t", str(run)]) == 0
    assert capsys.readouterr().out.strip() == "yes 1, maybe 0, no 0, followed 1"
    assert cli.main(["channels", "t"]) == 0
    assert "@a" in capsys.readouterr().out


def test_transcript_rejects_non_tiktok_urls(monkeypatch) -> None:
    import pytest
    with pytest.raises(SystemExit, match="not TikTok video URLs"):
        cli.main(["transcript", "https://example.com/video/1"])


def test_load_env_keeps_existing_values(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text('# c\nTV_A="one"\nTV_B=two\n')
    monkeypatch.setenv("TV_B", "kept")
    monkeypatch.delenv("TV_A", raising=False)
    cli.load_env(tmp_path / ".env")
    import os
    assert os.environ["TV_A"] == "one" and os.environ["TV_B"] == "kept"
    monkeypatch.delenv("TV_A")
