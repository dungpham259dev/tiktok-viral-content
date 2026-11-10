# tiktok-viral-content

Find TikTok channels in any niche, list their recent viral videos with links and view counts, and pull transcripts
so an AI agent (Claude Code, Codex) can work out why they went viral.

Ships with a ready dataset for **Vietnamese economics, finance and investing** (`topics/vn-economics/`): 32 followed
channels (23 core, 9 maybe), 117 screening verdicts, the search terms that worked, and the 74 viral videos of the last
30 days as of 2026-11-10. Ask your agent "what's viral in Vietnamese finance TikTok?" and it answers from that data, then refreshes it.

## How it works

| Step | Command | Needs a browser? | What it does |
|---|---|---|---|
| Find channels | `tiktok-viral discover` | yes (search is signed by TikTok's JavaScript) | hashtag pages, video search and account search; every candidate profiled |
| Screen channels | your agent reads `screen_input.json` | no | keeps channels that make the kind of video you want |
| Follow | `tiktok-viral screen-apply` | no | records every verdict, follows yes (and maybe) channels |
| Viral list | `tiktok-viral viral` | no (yt-dlp) | scores every recent post of followed channels |
| Transcripts | `tiktok-viral transcript` | no (yt-dlp + Whisper) | meta.json and transcript.txt per video |

Discovery is occasional (about monthly per niche). The viral list runs as often as you like: it only calls TikTok's
public endpoints through yt-dlp, with no browser, login or captcha.

### Viral score

`score = x_adj * sqrt(share_lift)`

- **x**: the post's views over the median of the 20 nearest same-format posts (short <= 180 s, or long) that are at
  least 7 days old. Using nearby posts, not a channel-wide median, keeps a fast-growing channel from making every new
  post look viral.
- **x_adj**: x divided by how much of its views a post that age usually has: 20% at day 1, 49% at day 2, 62% at days
  2-7, 90% at days 7-14. Measured on 21,530 posts from 411 Vietnamese channels. Posts under 2 days are not scored;
  2-7 days are flagged RISING.
- **share_lift**: the post's share rate over the channel's usual (clamped 0.25-4). Posts that beat their channel 3x
  had 1.56x the usual share rate; saves barely moved, so they are reported but not scored.
- Captions with sponsorship markers are flagged AD.

## Install

```bash
git clone <this repo> && cd tiktok-viral-content
uv sync                                   # viral list only (yt-dlp)
uv sync --extra discover && uv run playwright install chromium   # + channel discovery
uv sync --extra transcribe-mac            # + transcripts on Apple Silicon (or --extra transcribe elsewhere)
```

ffmpeg must be on PATH for transcripts.

### As an agent skill

- **Claude Code**: `ln -s "$PWD/skills/tiktok-viral-content" ~/.claude/skills/tiktok-viral-content`
- **Codex**: `ln -s "$PWD/skills/tiktok-viral-content" ~/.codex/skills/tiktok-viral-content` (Codex also reads `AGENTS.md`
  when started in this folder)

Then ask in plain words: "find viral finance videos on TikTok", "find channels about home cooking", "why did these go viral?".

### Updating

Say "update the skill" to your agent, or run `uv run tiktok-viral update`: it pulls the latest code, skill and bundled
data (`git pull --ff-only --autostash`), syncs dependencies and lists what changed. Your own topics are kept; if you
edited a bundled file that also changed upstream, it names the file and keeps your version in `git stash`.

## Usage

```bash
uv run tiktok-viral topics
uv run tiktok-viral channels vn-economics --all
uv run tiktok-viral viral vn-economics --days 30           # -> topics/vn-economics/runs/<stamp>-viral/viral.md
uv run tiktok-viral transcript --from-csv topics/vn-economics/runs/<stamp>-viral/viral.csv --top 10 --language vi

uv run tiktok-viral init home-cooking --language vi --description "Vietnamese home cooking"
# put account-search keywords in topics/home-cooking/keywords.txt, then:
uv run tiktok-viral discover home-cooking --topic-terms --stealth
uv run tiktok-viral screen-apply home-cooking topics/home-cooking/runs/<stamp>-discover
```

Commands that touch the browser need the `discover` extra; run them as
`uv run --extra discover tiktok-viral discover ...`.

## Captcha, stealth and TikTok's terms

- A fresh browser profile gets a slider captcha. Set `SADCAPTCHA_API_KEY` in `.env` (SadCaptcha, paid per solve, 25
  free credits; a run used 0-3) or solve it yourself in the window when notified. The tool never solves captchas itself.
- **Account search** (the most precise discovery source) refuses automated browsers. `--stealth` hides the automation
  flag so it works. That is against TikTok's terms of service, so it is off by default; turn it on knowingly.
- Scraping TikTok breaks its terms whatever the method. Use a home connection (datacenter IPs get blocked), keep
  runs small, never use a logged-in profile, and never reuse other creators' footage, narration or music: take the
  topic and angle, write your own script.

## What the bundled dataset holds

`topics/vn-economics/`: `channels.csv` (followed channels with why), `screened.csv` (every verdict, so discovery
skips rejected channels), `keywords.txt` and `tags.txt` (terms ranked by measured yield), `viral/2026-11-10.csv` (the
74 recent viral videos with topic tags) and `viral/2026-11-10-top20.csv` (20 with distinct subjects). Transcripts are
not included: they are other creators' words. Rebuild them with `tiktok-viral transcript`.

## Development

```bash
uv run pytest            # offline tests
uv run pytest -m live    # hits TikTok (yt-dlp only)
uv run ruff check
```

License: MIT.
