# vn-fun-knowledge

Vietnamese entertaining explainers on TikTok: fun facts, how things work, science curiosities, mysteries and history
(the "Vui Vẻ" style). Built 2026-11-10 from two discovery runs (289 new channels profiled); 59 strong candidates were
screened by an AI agent.

- `channels.csv`: 17 followed channels (tier `watch`) and 12 `maybe`, including @vuivedongian, the official Vui Vẻ
  TikTok. `median` = median views of their latest posts.
- `screened.csv`: every verdict. Most `no` were news pages, comedy skits, vlogs, shops, patriotic/political reels.
- `keywords.txt`, `tags.txt`, `queries.txt`: search terms ranked by how many strong channels each found. Hashtags
  beat account search here (#cothebanchuabiet found 16, #lichsuvietnam 13).
- `viral/2026-11-10.csv`: 176 videos from the last 30 days that beat their channel (score >= 5), tagged fun-facts /
  how-things-work / science / mysteries / geography / history. Political and war-politics posts were dropped.
- `viral/2026-11-10-top20.csv`: 20 of them with distinct subjects, at most 2 per channel.

What wins (2026-10/11): "Vì sao ..." about a familiar object or job (ballet shoes, coffee tasters, mosquitoes), "what
really happened behind" a famous show or person, "người xưa ..." daily-life history, absurd what-ifs (8.2 billion
lasers), and craft series ("Chúc mừng bạn đã xây ..."). Long narrated explainers (4-6 min) do as well as 60 s ones.
Refresh with `tiktok-viral viral vn-fun-knowledge`; numbers here are a snapshot.
