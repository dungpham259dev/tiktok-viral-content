# Agent guide

This repo is a CLI plus an agent skill for finding viral TikTok content in any niche.

- Read `skills/tiktok-viral-content/SKILL.md` first; it is the workflow (answer from bundled data, discover, screen,
  viral list, transcripts, analysis). `references/` holds the screening rubric and the analysis guide.
- Run commands from the repo root with `uv run tiktok-viral ...`. Browser commands need `--extra discover`;
  transcripts need `--extra transcribe-mac` (Apple Silicon) or `--extra transcribe`.
- Topic data lives in `topics/<name>/`; `topics/vn-economics/` is a ready dataset. `cache/` and `runs/` are gitignored.
- Ask the user before `--stealth` (it breaks TikTok's terms). Never solve captchas yourself. Never print secrets
  from `.env`.
- Tests: `uv run pytest` (offline) and `uv run pytest -m live` (network). Lint: `uv run ruff check`.
