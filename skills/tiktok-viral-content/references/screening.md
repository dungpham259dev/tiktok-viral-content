# Screening channels

`screen_input.json` gives, per channel: handle, bio (from account search), what found it, median views, posts in the
last 30 days, hits in 30 days (posts scoring 3+), share of posts over 100K, share of question captions, median
duration, its 12 biggest posts and 5 newest other posts (views, duration, caption).

Write `screen.json`:

```json
{"<handle>": {"keep": "yes|maybe|no", "category": "economics", "format": "narrated explainer 2-3 min", "reason": "one line"}}
```

## Verdicts

- **yes**: the substance is the topic (most of the top and recent captions are about it), the channel explains or
  answers something, it is active, and the median is solid. Narrated or faceless explainers rank above talking heads
  because their structure is easy to learn from.
- **maybe**: the topic fits but the format or numbers are off: news recaps, talking-head advice, tutorials,
  biographies, a small channel with very high multiples, or a channel posting 20 times a day.
- **no**: sellers, shops and affiliate posts; banks and brands advertising; courses and lead magnets; news outlets
  and gossip; politics and war; quotes and motivation; vlogs, comedy, games; foreign-language channels for a local
  topic; inactive channels.

Judge only what the captions show. If they are not enough (empty captions, hashtags only), choose maybe and say what to
check. Never guess a format you did not see.

## Signals that held up (Vietnamese economics, 2026-11-10)

- 30%+ of captions phrased as questions ("vì sao", "tại sao", "bao nhiêu", "?") kept 21 of 24 known good channels
  and dropped 74% of off-topic ones. Short tech channels can fall under it; use it to order, not to reject.
- A high median beats one huge video: a channel with 1.7K median and one 29M video is a lottery ticket.
- Channels whose name or bio holds the niche words (found by account search) were the most often "yes".
