---
name: tiktok-viral-content
description: Use when someone wants viral TikTok videos or source channels for a niche ("what's viral in finance TikTok", "tìm kênh/video viral về kinh tế", "find channels like X", "list videos to remake"), wants transcripts of TikTok videos, or wants to know why a set of TikTok videos went viral. Works for any topic; ships with Vietnamese data for economics/finance/investing and for fun facts/science/history explainers.
---

# tiktok-viral-content

Finds channels in a niche, ranks their recent videos by a viral score, and pulls transcripts for analysis.
The repo is the folder two levels above this file's real path (`skills/tiktok-viral-content/` is a symlink target);
run every command from the repo root with `uv run tiktok-viral ...`.

**Update**: when the user asks to update the skill or tool, run `uv run tiktok-viral update` (git pull + uv sync) and
report the new commits. The skill file itself updates with the pull (it is a symlink into the clone). If the pull
fails on local edits, show `git status` and ask before stashing or discarding anything.

## 0. Answer from data first

Run `uv run tiktok-viral topics`. If a topic covers the request (e.g. `vn-economics` for Vietnamese economics,
business, personal finance or investing; `vn-fun-knowledge` for fun facts, science curiosities, mysteries, history), answer from it before fetching anything:

- recent viral videos: the newest `topics/<t>/viral/*.csv`, or the newest `topics/<t>/runs/*-viral/viral.csv`
- channels: `topics/<t>/channels.csv` (tier `watch` = core, `maybe` = borderline), with the reason for each

Say the date of the data. Then offer, or just run when the user wants fresh numbers, `uv run tiktok-viral viral <t>`
(no browser, about 5 s per channel).

## 1. New topic

```bash
uv run tiktok-viral init <name> --language vi --description "..."   # language: caption filter, '' = any
```

Fill `keywords.txt` with nouns a channel in the niche puts in its name or bio ("kiến thức kinh tế", "home cooking").
Generic words ("why", "business") return sellers and junk. Add a few hashtags to `tags.txt`. Keep `queries.txt` short:
phrase searches found little.

## 2. Discover (browser, occasional)

```bash
uv run --extra discover tiktok-viral discover <t> --topic-terms [--mine-tags 10] [--stealth]
```

- Takes 30-90 minutes; run it in the background. It writes `topics/<t>/runs/<stamp>-discover/`.
- **Ask the user before adding `--stealth`.** Account search (the most precise source) only works with it, and it
  breaks TikTok's terms. Without it, account pages report "refused" and tags and queries still work.
- A captcha needs `SADCAPTCHA_API_KEY` in `.env` (paid) or a person at the window; never solve captchas yourself.
- Read `digest.md`: coverage of channels already followed, and the yield of each keyword/tag. Move the terms that
  found nothing to the bottom of their file for next time.

## 3. Screen (you judge the content)

Read `screen_input.json` (strong channels only: median >= 20K views, active; question-led ones first) and write
`screen.json` next to it, following `references/screening.md`. Then:

```bash
uv run tiktok-viral screen-apply <t> topics/<t>/runs/<stamp>-discover
```

Show the user what you kept and why before or right after applying; `screened.csv` keeps every verdict.

## 4. Viral list

```bash
uv run tiktok-viral viral <t> [--days 30] [--include-maybe]
```

Read `viral.md`. Tag each row by sub-topic yourself and drop rows off the brief (news, politics, gossip, ads; check the
AD flag). When asked for N videos "not overlapping", keep one video per subject and at most 2 per channel. Always give
link, views, x (times the channel's usual) and age; explain x when the user has not seen it before.

## 5. Transcripts and analysis

```bash
uv run --extra transcribe-mac tiktok-viral transcript --from-csv <viral.csv> --top 10 --language vi --out transcripts
```

Each video gets `meta.json` and `transcript.txt`. "no narration" means music and on-screen text only: say so, do not
analyse words that are not there. Then follow `references/analysis.md`.

## Rules

- Never reuse other creators' narration, footage or music; the output is topic, angle and structure.
- Numbers in the dataset are snapshots; quote their date.
- Errors are shown, not hidden: a channel yt-dlp cannot read ("account that has access") is listed under Problems.
