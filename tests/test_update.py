import subprocess

from tiktok_viral import cli

GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


def _run(cwd, *args) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


def _setup(tmp_path):
    dev, friend = tmp_path / "dev", tmp_path / "friend"
    dev.mkdir()
    _run(dev, "init", "-q", "-b", "main")
    (dev / "notes.txt").write_text("v1\n")
    _run(dev, "add", "-A")
    _run(dev, "commit", "-qm", "v1")
    _run(tmp_path, "clone", "-q", str(dev), str(friend))
    return dev, friend


def _push(dev, text: str, message: str) -> None:
    (dev / "notes.txt").write_text(text)
    _run(dev, "commit", "-qam", message)


def test_update_pulls_new_commits_and_reports_them(tmp_path, monkeypatch, capsys) -> None:
    dev, friend = _setup(tmp_path)
    monkeypatch.setattr(cli, "REPO", friend)
    assert cli.main(["update"]) == 0
    assert "already up to date" in capsys.readouterr().out
    _push(dev, "v2\n", "feat: new data")
    assert cli.main(["update"]) == 0
    assert "feat: new data" in capsys.readouterr().out
    assert (friend / "notes.txt").read_text() == "v2\n"


def test_update_reports_conflicts_with_local_edits(tmp_path, monkeypatch, capsys) -> None:
    dev, friend = _setup(tmp_path)
    monkeypatch.setattr(cli, "REPO", friend)
    _push(dev, "upstream\n", "v2")
    (friend / "notes.txt").write_text("mine\n")
    assert cli.main(["update"]) == 1
    assert "conflict with it in: notes.txt" in capsys.readouterr().err


def test_update_outside_a_git_clone_fails_clearly(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "REPO", tmp_path)
    assert cli.main(["update"]) == 2
    assert "not a git clone" in capsys.readouterr().err
