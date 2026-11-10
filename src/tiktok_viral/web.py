"""Parsing and ranking of TikTok web payloads: hashtag pages, video search and account search."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime

TITLE_MAX = 160
HASHTAG = re.compile(r"#(\w+)", re.UNICODE)
LANGUAGE_MARKERS = {
    "vi": re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.IGNORECASE),
}


@dataclass(frozen=True)
class Item:
    url: str
    video_id: str
    handle: str
    name: str
    sec_uid: str
    followers: int
    title: str
    date: str
    plays: int
    likes: int
    comments: int
    shares: int
    saves: int
    duration_s: int
    source: str


@dataclass(frozen=True)
class Author:
    handle: str
    name: str
    sec_uid: str
    followers: int
    hits: int
    best_plays: int
    best_url: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Account:
    handle: str
    name: str
    sec_uid: str
    followers: int
    bio: str
    videos: int
    source: str


@dataclass(frozen=True)
class TagUse:
    tag: str
    channels: int
    posts: int


def _item(row: dict, source: str) -> Item | None:
    author = row.get("author") or {}
    stats = row.get("stats") or {}
    handle, video_id = author.get("uniqueId"), row.get("id")
    if not handle or not video_id or stats.get("playCount") is None:
        return None
    created = int(row.get("createTime") or 0)
    return Item(
        url=f"https://www.tiktok.com/@{handle}/video/{video_id}",
        video_id=str(video_id),
        handle=handle,
        name=author.get("nickname") or handle,
        sec_uid=author.get("secUid") or "",
        followers=int((row.get("authorStats") or {}).get("followerCount") or 0),
        title=" ".join((row.get("desc") or "").split())[:TITLE_MAX],
        date=datetime.fromtimestamp(created, UTC).date().isoformat() if created else "",
        plays=int(stats["playCount"]),
        likes=int(stats.get("diggCount") or 0),
        comments=int(stats.get("commentCount") or 0),
        shares=int(stats.get("shareCount") or 0),
        saves=int(stats.get("collectCount") or 0),
        duration_s=int((row.get("video") or {}).get("duration") or 0),
        source=source,
    )


def parse_items(payload: dict, source: str) -> list[Item]:
    rows = payload.get("itemList") or payload.get("item_list") or []
    parsed = (_item(row, source) for row in rows if isinstance(row, dict))
    return [item for item in parsed if item is not None]


def parse_users(payload: dict, source: str) -> list[Account]:
    accounts = []
    for row in payload.get("user_list") or []:
        info = (row or {}).get("user_info") or {}
        if not info.get("unique_id") or not info.get("sec_uid"):
            continue
        accounts.append(Account(info["unique_id"], info.get("nickname") or info["unique_id"], info["sec_uid"],
                                int(info.get("follower_count") or 0), " ".join((info.get("signature") or "").split()),
                                int(info.get("aweme_count") or 0), source))
    return accounts


def unique_videos(items: list[Item]) -> list[Item]:
    seen: dict[str, Item] = {}
    for item in items:
        seen.setdefault(item.video_id, item)
    return list(seen.values())


def rank_authors(items: list[Item], known: set[str], min_plays: int) -> list[Author]:
    by_author: dict[str, list[Item]] = {}
    for item in unique_videos(items):
        if item.sec_uid and item.sec_uid not in known:
            by_author.setdefault(item.sec_uid, []).append(item)
    sources_of: dict[str, set[str]] = {}
    for item in items:
        sources_of.setdefault(item.sec_uid, set()).add(item.source)
    authors = []
    for sec_uid, vids in by_author.items():
        best = max(vids, key=lambda v: v.plays)
        if best.plays < min_plays:
            continue
        authors.append(Author(best.handle, best.name, sec_uid, max(v.followers for v in vids), len(vids),
                              best.plays, best.url, tuple(sorted(sources_of[sec_uid]))))
    return sorted(authors, key=lambda a: (-a.best_plays, -a.hits))


def merge_accounts(authors: list[Author], accounts: list[Account], known: set[str]) -> list[Author]:
    """Account-search hits first (they matched on name or bio), then the remaining video authors."""
    by_sec = {a.sec_uid: a for a in authors}
    found: dict[str, list[Account]] = {}
    for acc in accounts:
        if acc.sec_uid not in known:
            found.setdefault(acc.sec_uid, []).append(acc)
    merged = []
    for sec, accs in found.items():
        base = by_sec.get(sec)
        sources = tuple(sorted({a.source for a in accs} | set(base.sources if base else ())))
        if base:
            merged.append(Author(base.handle, base.name, sec, max(base.followers, accs[0].followers),
                                 base.hits + len(accs), base.best_plays, base.best_url, sources))
        else:
            acc = accs[0]
            merged.append(Author(acc.handle, acc.name, sec, acc.followers, len(accs), 0, "", sources))
    merged.sort(key=lambda a: (a.best_plays > 0, -a.followers))
    return merged + [a for a in authors if a.sec_uid not in found]


def language_authors(items: list[Item], language: str, min_share: float) -> set[str]:
    """sec_uids whose captions are mostly in `language`; every author passes when the language has no marker."""
    marker = LANGUAGE_MARKERS.get(language)
    total: dict[str, int] = {}
    hits: dict[str, int] = {}
    for item in unique_videos(items):
        total[item.sec_uid] = total.get(item.sec_uid, 0) + 1
        hits[item.sec_uid] = hits.get(item.sec_uid, 0) + bool(marker is None or marker.search(item.title))
    return {sec for sec, n in total.items() if hits[sec] / n >= min_share}


def hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(t.lower() for t in HASHTAG.findall(text or "")))


def mine_tags(captions: dict[str, list[str]], min_channels: int, stop: set[str]) -> list[TagUse]:
    channels: dict[str, set[str]] = {}
    posts: dict[str, int] = {}
    for channel, texts in captions.items():
        for text in texts:
            for tag in hashtags(text):
                if tag in stop:
                    continue
                channels.setdefault(tag, set()).add(channel)
                posts[tag] = posts.get(tag, 0) + 1
    uses = [TagUse(t, len(chs), posts[t]) for t, chs in channels.items() if len(chs) >= min_channels]
    return sorted(uses, key=lambda u: (-u.channels, -u.posts, u.tag))


def coverage(seen: set[str], known: dict[str, str]) -> tuple[list[str], list[str]]:
    found = sorted(name for ref, name in known.items() if ref in seen)
    missed = sorted(name for ref, name in known.items() if ref not in seen)
    return found, missed


def source_yield(items: list[Item], accounts: list[Account], known: set[str],
                 good: set[str]) -> dict[str, tuple[int, int, int]]:
    """Per tag, query or account keyword: (results, new channels, good new channels)."""
    results: dict[str, set[str]] = {}
    channels: dict[str, set[str]] = {}
    for item in items:
        results.setdefault(item.source, set()).add(item.video_id)
        channels.setdefault(item.source, set()).add(item.sec_uid)
    for acc in accounts:
        results.setdefault(acc.source, set()).add(acc.sec_uid)
        channels.setdefault(acc.source, set()).add(acc.sec_uid)
    out = {}
    for src, found in results.items():
        new = channels[src] - known
        out[src] = (len(found), len(new), len(new & good))
    return out
