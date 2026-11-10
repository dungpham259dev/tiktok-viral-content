from conftest import NOW, channel_entries, entry

from tiktok_viral.profile import Profile, build_profile, is_strong, post_samples, rank_profiles


def test_build_profile_measures_median_activity_questions_and_hits() -> None:
    entries = channel_entries() + [None, {"view_count": None}]
    p = build_profile(entries, "demo", now=NOW)
    assert p.posts == 31
    assert p.posts_30d == 13
    assert 10_000 <= p.median <= 10_300
    assert p.viral_share == round(1 / 31, 2)
    assert p.hits_30d == 1
    assert p.question_share == 1.0
    assert p.duration_s == 90


def test_build_profile_of_an_empty_channel_is_zero() -> None:
    assert build_profile([], "x", now=NOW) == Profile(0, 0, 0, 0.0, 0, 0.0, 0)


def test_question_share_counts_vietnamese_and_english_questions() -> None:
    captions = ["Vì sao xăng tăng", "giá vàng hôm nay", "Ai lãi?", "Why is gold up", "Bài 1 rất hay", "Mua nhà"]
    p = build_profile([entry(i, 100, 10, caption=c) for i, c in enumerate(captions)], "x", now=NOW)
    assert p.question_share == 0.5


def _prof(median: int, posts_30d: int = 10, share: float = 0.0, q: float = 0.0) -> Profile:
    return Profile(60, posts_30d, median, share, 0, q, 90)


def test_rank_profiles_orders_active_channels_by_median() -> None:
    ranked = rank_profiles({"lottery": _prof(2_000, share=0.01), "steady": _prof(400_000),
                            "dead": _prof(900_000, posts_30d=0), "tie": _prof(400_000, share=0.5)},
                           good_median=20_000, min_posts_30d=2)
    assert ranked == ["tie", "steady", "lottery", "dead"]


def test_rank_profiles_puts_question_led_channels_first_among_strong_ones() -> None:
    ranked = rank_profiles({"news": _prof(500_000, q=0.05), "explainer": _prof(60_000, q=0.7),
                            "small": _prof(5_000, q=0.9)}, good_median=20_000, min_posts_30d=2)
    assert ranked == ["explainer", "news", "small"]


def test_is_strong_needs_median_and_activity() -> None:
    assert is_strong(_prof(30_000, posts_30d=3), 20_000, 2)
    assert not is_strong(_prof(30_000, posts_30d=1), 20_000, 2)
    assert not is_strong(_prof(10_000), 20_000, 2)


def test_post_samples_take_biggest_and_newest_posts_once() -> None:
    entries = [{"view_count": v, "timestamp": t, "duration": 30, "description": f"cap {v}\nx"}
               for v, t in [(10, 5), (900, 1), (500, 4), (50, 3), (70, 2)]] + [None, {"view_count": None}]
    top, recent = post_samples(entries, top=2, recent=2)
    assert [p["views"] for p in top] == [900, 500]
    assert [p["views"] for p in recent] == [10, 50]
    assert top[0]["caption"] == "cap 900 x"
