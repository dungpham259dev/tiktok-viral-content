from conftest import raw

from tiktok_viral.web import (
    Account,
    Item,
    coverage,
    hashtags,
    language_authors,
    merge_accounts,
    mine_tags,
    parse_items,
    parse_users,
    rank_authors,
    source_yield,
)


def test_parse_items_reads_both_payload_keys_and_flattens_text() -> None:
    from_tag = parse_items({"itemList": [raw("1", "a", 500)]}, "tag:kinhte")
    from_search = parse_items({"item_list": [raw("2", "b", 900)]}, "q:buffet")
    assert from_tag[0].url == "https://www.tiktok.com/@a/video/1"
    assert from_tag[0].title == "video 1 line two"
    assert from_tag[0].date == "2025-11-01"
    assert from_tag[0].saves == 4
    assert from_search[0].source == "q:buffet"


def test_parse_items_skips_rows_without_author_or_stats() -> None:
    broken = [{"id": "1"}, {"id": "2", "author": {"uniqueId": "a"}}, None]
    assert parse_items({"itemList": broken}, "tag:x") == []
    assert parse_items({"status_code": 0}, "tag:x") == []


def test_rank_authors_dedupes_videos_and_drops_known_channels() -> None:
    items = [
        *parse_items({"itemList": [raw("1", "a", 500), raw("2", "a", 90_000), raw("3", "b", 70_000)]}, "tag:x"),
        *parse_items({"itemList": [raw("2", "a", 90_000), raw("4", "known", 1_000_000)]}, "tag:y"),
    ]
    ranked = rank_authors(items, known={"sec-known"}, min_plays=50_000)
    assert [a.handle for a in ranked] == ["a", "b"]
    assert ranked[0].hits == 2
    assert ranked[0].best_plays == 90_000
    assert ranked[0].sources == ("tag:x", "tag:y")


def test_rank_authors_requires_one_video_over_the_floor() -> None:
    items = parse_items({"itemList": [raw("1", "small", 4_000)]}, "tag:x")
    assert rank_authors(items, known=set(), min_plays=50_000) == []
    assert isinstance(items[0], Item)


def test_hashtags_are_lowercased_and_deduped_per_caption() -> None:
    assert hashtags("Vay mua xe? #KinhTe #kinhte #tài_chính #fyp,#x") == ["kinhte", "tài_chính", "fyp", "x"]
    assert hashtags("") == []


def test_mine_tags_needs_several_channels_and_drops_generic_tags() -> None:
    captions = {
        "a": ["one #kinhte #fyp #kenh_a", "two #kinhte #taichinh"],
        "b": ["three #kinhte #taichinh #xuhuong"],
        "c": ["four #kinhte #kenh_c"],
    }
    mined = mine_tags(captions, min_channels=2, stop={"fyp", "xuhuong"})
    assert [(t.tag, t.channels, t.posts) for t in mined] == [("kinhte", 3, 4), ("taichinh", 2, 2)]


def test_coverage_counts_known_channels_seen_in_items() -> None:
    items = parse_items({"itemList": [raw("1", "a", 500), raw("2", "a", 600), raw("3", "zz", 700)]}, "t")
    assert coverage({i.sec_uid for i in items}, {"sec-a": "a", "sec-b": "b"}) == (["a"], ["b"])


def _captioned(vid: str, author: str, text: str) -> dict:
    return {**raw(vid, author, 100), "desc": text}


def test_language_authors_need_most_captions_in_the_language() -> None:
    items = parse_items({"itemList": [
        _captioned("1", "vi", "Vì sao quán buffet vẫn lời?"), _captioned("2", "vi", "#kinhte"),
        _captioned("3", "en", "Leg day #gym"), _captioned("4", "en", "Push day"),
        _captioned("5", "mix", "Giá vàng hôm nay"), _captioned("6", "mix", "gold price"),
    ]}, "t")
    assert language_authors(items, "vi", min_share=0.5) == {"sec-vi", "sec-mix"}


def test_language_without_marker_keeps_every_author() -> None:
    items = parse_items({"itemList": [_captioned("1", "en", "Leg day"), _captioned("2", "vi", "Vì sao")]}, "t")
    assert language_authors(items, "", min_share=0.5) == {"sec-en", "sec-vi"}
    assert language_authors(items, "ja", min_share=0.5) == {"sec-en", "sec-vi"}


def test_source_yield_counts_videos_and_accounts_per_source() -> None:
    items = [*parse_items({"itemList": [raw("1", "a", 500), raw("2", "b", 600)]}, "tag:x"),
             *parse_items({"itemList": [raw("3", "a", 700), raw("4", "known", 1)]}, "q:y")]
    accounts = [Account("c", "C", "sec-c", 1, "", 1, "user:k"), Account("a", "A", "sec-a", 1, "", 1, "user:k")]
    got = source_yield(items, accounts, known={"sec-known"}, good={"sec-a", "sec-c"})
    assert got == {"tag:x": (2, 2, 1), "q:y": (2, 1, 1), "user:k": (2, 2, 2)}


def test_parse_users_reads_account_search_results() -> None:
    payload = {"user_list": [
        {"user_info": {"unique_id": "kt", "nickname": "Kinh Tế", "sec_uid": "sec-kt", "follower_count": 900,
                       "signature": "Giải thích\nkinh tế", "aweme_count": 40}},
        {"user_info": {"unique_id": "nosec"}}, {"other": 1}, None,
    ]}
    accounts = parse_users(payload, "user:kinh tế")
    assert accounts == [Account("kt", "Kinh Tế", "sec-kt", 900, "Giải thích kinh tế", 40, "user:kinh tế")]
    assert parse_users({}, "user:x") == []


def test_merge_accounts_joins_sources_and_skips_known() -> None:
    video_authors = rank_authors(parse_items({"itemList": [raw("1", "a", 90_000)]}, "tag:x"), set(), 50_000)
    accounts = [Account("a", "A", "sec-a", 5, "", 1, "user:k1"), Account("n", "N", "sec-n", 7, "bio", 2, "user:k1"),
                Account("n", "N", "sec-n", 7, "bio", 2, "user:k2"), Account("z", "Z", "sec-z", 1, "", 1, "user:k1")]
    merged = merge_accounts(video_authors, accounts, known={"sec-z"})
    assert [(m.handle, m.sources) for m in merged] == [("n", ("user:k1", "user:k2")), ("a", ("tag:x", "user:k1"))]
