"""A topic workspace: the channels we follow for one niche, every screen verdict, search terms, cache and runs.

topics/<name>/
  topic.json      {"name", "description", "language", "generic_tags": [...]}
  channels.csv    handle, sec_uid, genre, tier (watch | maybe), median, why, found_on
  screened.csv    handle, sec_uid, verdict (yes | maybe | no), category, format, reason, screened_on
  keywords.txt    account-search keywords, one per line (# comments allowed)
  tags.txt        hashtags without #
  queries.txt     video-search phrases
  cache/          yt-dlp channel files (gitignored)
  runs/           discover and viral outputs (gitignored)
"""

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path

CHANNEL_FIELDS = ["handle", "sec_uid", "genre", "tier", "median", "why", "found_on"]
SCREEN_FIELDS = ["handle", "sec_uid", "verdict", "category", "format", "reason", "screened_on"]
TIERS = ("watch", "maybe")
VERDICTS = ("yes", "maybe", "no")
REPO_TOPICS = Path(__file__).resolve().parents[2] / "topics"


class TopicError(ValueError):
    pass


def topics_root() -> Path:
    env = os.environ.get("TIKTOK_VIRAL_TOPICS")
    if env:
        return Path(env).expanduser()
    local = Path.cwd() / "topics"
    return local if local.is_dir() else REPO_TOPICS


def list_topics(root: Path | None = None) -> list[str]:
    root = root or topics_root()
    return sorted(p.name for p in root.iterdir() if (p / "topic.json").exists()) if root.is_dir() else []


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = (line.strip() for line in path.read_text().splitlines())
    # "# note" is a comment; "#kinhte" is a hashtag in tags.txt.
    return [line for line in lines if line and line != "#" and not line.startswith("# ")]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@dataclass(frozen=True)
class Topic:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def config(self) -> dict:
        return json.loads((self.path / "topic.json").read_text())

    @property
    def language(self) -> str:
        return self.config.get("language", "")

    @property
    def generic_tags(self) -> set[str]:
        return {t.lower() for t in self.config.get("generic_tags", [])}

    @property
    def cache_dir(self) -> Path:
        return self.path / "cache"

    def run_dir(self, kind: str, stamp: str) -> Path:
        out = self.path / "runs" / f"{stamp}-{kind}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def keywords(self) -> list[str]:
        return _read_lines(self.path / "keywords.txt")

    def tags(self) -> list[str]:
        return [t.lstrip("#") for t in _read_lines(self.path / "tags.txt")]

    def queries(self) -> list[str]:
        return _read_lines(self.path / "queries.txt")

    def channels(self, tiers: tuple[str, ...] = ("watch",)) -> list[dict]:
        return [r for r in _read_csv(self.path / "channels.csv") if r["tier"] in tiers]

    def known_refs(self) -> set[str]:
        return {r["sec_uid"] for r in _read_csv(self.path / "channels.csv")}

    def screened(self) -> dict[str, dict]:
        return {r["sec_uid"]: r for r in _read_csv(self.path / "screened.csv")}

    def rejected_refs(self) -> set[str]:
        return {sec for sec, r in self.screened().items() if r["verdict"] == "no"}

    def add_channels(self, rows: list[dict]) -> int:
        bad = [r for r in rows if r.get("tier") not in TIERS or not r.get("sec_uid")]
        if bad:
            raise TopicError(f"channel rows need sec_uid and tier in {TIERS}: {[r.get('handle') for r in bad]}")
        current = _read_csv(self.path / "channels.csv")
        by_ref = {r["sec_uid"]: r for r in current}
        added = 0
        for row in rows:
            old = by_ref.get(row["sec_uid"])
            if old is None:
                added += 1
            elif old["tier"] == "watch":
                continue
            by_ref[row["sec_uid"]] = {**(old or {}), **row}
        _write_csv(self.path / "channels.csv", CHANNEL_FIELDS, list(by_ref.values()))
        return added

    def record_screen(self, rows: list[dict]) -> None:
        bad = [r for r in rows if r.get("verdict") not in VERDICTS]
        if bad:
            raise TopicError(f"verdict must be one of {VERDICTS}: {[r.get('handle') for r in bad]}")
        merged = {r["sec_uid"]: r for r in _read_csv(self.path / "screened.csv")}
        merged.update({r["sec_uid"]: r for r in rows})
        _write_csv(self.path / "screened.csv", SCREEN_FIELDS, sorted(merged.values(), key=lambda r: r["handle"]))


def load_topic(name_or_path: str, root: Path | None = None) -> Topic:
    candidate = Path(name_or_path).expanduser()
    path = candidate if (candidate / "topic.json").exists() else (root or topics_root()) / name_or_path
    if not (path / "topic.json").exists():
        raise TopicError(f"no topic '{name_or_path}' (looked for {path / 'topic.json'}); "
                         "create it with `tiktok-viral init`")
    return Topic(path)


def init_topic(name: str, description: str, language: str, root: Path | None = None) -> Topic:
    path = (root or topics_root()) / name
    if (path / "topic.json").exists():
        raise TopicError(f"topic '{name}' already exists at {path}")
    path.mkdir(parents=True, exist_ok=True)
    (path / "topic.json").write_text(json.dumps({"name": name, "description": description, "language": language,
                                                 "generic_tags": ["fyp", "foryou", "foryoupage", "viral", "trending",
                                                                  "xuhuong", "learnontiktok", "capcut"]},
                                                ensure_ascii=False, indent=1) + "\n")
    _write_csv(path / "channels.csv", CHANNEL_FIELDS, [])
    _write_csv(path / "screened.csv", SCREEN_FIELDS, [])
    for name_ in ("keywords.txt", "tags.txt", "queries.txt"):
        (path / name_).write_text(f"# {name_[:-4]}, one per line\n")
    return Topic(path)
