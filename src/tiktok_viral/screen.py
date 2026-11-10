"""Apply a content screen to a discovery run: record every verdict and follow the channels that passed.

screen.json (written by an agent or a person after reading screen_input.json):
  {"<handle>": {"keep": "yes|maybe|no", "category": "...", "format": "...", "reason": "..."}}
yes -> channels.csv tier watch; maybe -> tier maybe; every verdict -> screened.csv, so later runs skip "no".
"""

import json
from datetime import date
from pathlib import Path

from tiktok_viral.topic import VERDICTS, Topic, TopicError


def load_screen(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "screen.json"
    if not path.exists():
        raise TopicError(f"missing {path}: screen screen_input.json first")
    screen = json.loads(path.read_text())
    bad = [h for h, v in screen.items() if not isinstance(v, dict) or v.get("keep") not in VERDICTS]
    if bad:
        raise TopicError(f"screen.json: keep must be one of {VERDICTS} for {', '.join(bad)}")
    return screen


def apply_screen(topic: Topic, run_dir: Path, follow: bool) -> dict[str, int]:
    screen = load_screen(run_dir)
    inputs = {c["handle"]: c for c in json.loads((run_dir / "screen_input.json").read_text())}
    unknown = sorted(set(screen) - set(inputs))
    if unknown:
        raise TopicError(f"screen.json names channels not in screen_input.json: {', '.join(unknown)}")
    today = date.today().isoformat()
    verdicts, follows = [], []
    for handle, v in screen.items():
        ch = inputs[handle]
        verdicts.append({"handle": handle, "sec_uid": ch["sec_uid"], "verdict": v["keep"],
                         "category": v.get("category", ""), "format": v.get("format", ""),
                         "reason": v.get("reason", ""), "screened_on": today})
        if v["keep"] != "no":
            follows.append({"handle": handle, "sec_uid": ch["sec_uid"], "genre": v.get("category", ""),
                            "tier": "watch" if v["keep"] == "yes" else "maybe", "median": ch.get("median", ""),
                            "why": f"{v.get('format', '')}; {v.get('reason', '')}".strip("; "), "found_on": today})
    topic.record_screen(verdicts)
    added = topic.add_channels(follows) if follow else 0
    counts = {k: sum(v["keep"] == k for v in screen.values()) for k in VERDICTS}
    return counts | {"followed": added}
