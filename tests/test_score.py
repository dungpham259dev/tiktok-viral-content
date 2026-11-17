import pytest

from tiktok_viral.score import (
    PostStat,
    age_fraction,
    is_sponsored,
    score_posts,
)

DAY = 86_400.0
NOW = 1_000 * DAY


def post(vid: str, views: int, age_days: float, shares: int = 0, dur: int = 60, caption: str = "") -> PostStat:
    return PostStat(vid, f"https://www.tiktok.com/@c/video/{vid}", caption, NOW - age_days * DAY, dur, views,
                    likes=0, comments=0, shares=shares, saves=0)


def baseline(n: int = 10, views: int = 1_000, shares: int = 10) -> list[PostStat]:
    return [post(f"b{i}", views, 20 + i, shares=shares) for i in range(n)]


def test_age_fraction_follows_the_measured_curve() -> None:
    assert age_fraction(0.5) == 0.2
    assert age_fraction(1.5) == 0.49
    assert age_fraction(5) == 0.64
    assert age_fraction(10) == 0.9
    assert age_fraction(40) == 1.0


def test_old_post_x_is_views_over_mature_baseline_median() -> None:
    scored = score_posts([post("hit", 10_000, 20, shares=100), *baseline()], NOW, max_age_days=30)
    hit = next(s for s in scored if s.post.video_id == "hit")
    assert hit.x == pytest.approx(10.0)
    assert hit.x_adj == pytest.approx(10.0)
    assert hit.share_lift == pytest.approx(1.0)
    assert hit.score == pytest.approx(10.0)
    assert not hit.rising


def test_young_post_is_projected_and_flagged_rising() -> None:
    scored = score_posts([post("new", 1_000, 3), *baseline()], NOW, max_age_days=30)
    new = next(s for s in scored if s.post.video_id == "new")
    assert new.x == pytest.approx(1.0)
    assert new.x_adj == pytest.approx(1 / 0.61)
    assert new.rising


def test_posts_under_two_days_are_too_early_to_score() -> None:
    scored = score_posts([post("hours", 50_000, 0.1), post("day", 50_000, 1.5), *baseline()], NOW, max_age_days=30)
    assert {s.post.video_id for s in scored} & {"hours", "day"} == set()


def test_share_lift_scales_score_by_square_root_and_is_clamped() -> None:
    posts = [post("shared", 1_000, 20, shares=40), post("silent", 1_000, 20, shares=0), *baseline()]
    by_id = {s.post.video_id: s for s in score_posts(posts, NOW, max_age_days=30)}
    assert by_id["shared"].share_lift == pytest.approx(4.0)
    assert by_id["shared"].score == pytest.approx(2.0)
    assert by_id["silent"].share_lift == pytest.approx(0.25)


def test_baseline_uses_same_format_and_excludes_old_and_too_young_posts() -> None:
    longs = [post(f"l{i}", 100_000, 30 + i, dur=600) for i in range(6)]
    scored = score_posts([post("short", 3_000, 20), *baseline(), *longs, post("ancient", 5, 400)], NOW,
                         max_age_days=30)
    short = next(s for s in scored if s.post.video_id == "short")
    assert short.baseline == 1_000


def test_only_recent_posts_are_returned_and_thin_channels_give_nothing() -> None:
    scored = score_posts([post("recent", 5_000, 3), *baseline()], NOW, max_age_days=7)
    assert [s.post.video_id for s in scored] == ["recent"]
    assert score_posts([post("x", 5_000, 3), *baseline(n=3)], NOW, max_age_days=30) == []


@pytest.mark.parametrize("caption,expected", [
    ("Trả góp #HomeCredit #hoptaccungHomeCredit", True),
    ("Đi chợ #ĐượctàitrợbởiGrab", True),
    ("#Shopee #Sponsoredcontent #noidungduoctaitro", True),
    ("Vì sao buffet không lỗ? #kinhte", False),
    ("#ad mua ngay", True),
    ("#HợpTácCùngShopee giảm giá", True),
    ("Hợp tác cùng nhau phát triển", False),
    ("Video có tài trợ, cảm ơn Grab", True),
    ("noi dung duoc tai tro boi Grab", True),
    ("Tải trò chơi miễn phí, ở tại trọ sinh viên", False),
    ("Not sponsored, just my opinion #nonsponsored", False),
    ("#adidas #admin #advice", False),
    ("Nội dung được tài trợ bởi VPBank", True),
    ("Paid partnership with Grab", True),
    ("Business partner là gì? #kinhte", False),
    ("#adidas giảm giá", False),
    ("Quảng cáo trên TV tốn bao nhiêu tiền?", False),
    ("Tải trọng 10 tấn, tại trong nhà #khoahoc", False),
    ("Đặt ai trợ giúp? #tảitrọng", False),
    ("Mua sắm #partnership #brandpartner", True),
    ("Review #quảng_cáo", True),
    ("Đồ uống #ads_tiktok", True),
    ("#ad1 giảm giá", False),
])
def test_sponsored_captions_are_flagged(caption: str, expected: bool) -> None:
    assert is_sponsored(caption) is expected


def test_a_mature_post_is_left_out_of_its_own_baseline() -> None:
    peers = [post(f"p{i}", v, 20 + i) for i, v in enumerate([100, 200, 300, 400, 500])]
    scored = score_posts([post("hit", 9_000, 20), *peers], NOW, max_age_days=30)
    hit = next(s for s in scored if s.post.video_id == "hit")
    assert hit.baseline == 300
    assert hit.x == pytest.approx(30.0)


def test_a_growing_channel_does_not_make_every_recent_post_viral() -> None:
    old = [post(f"o{i}", 100, 60 + i) for i in range(20)]
    recent = [post(f"r{i}", 1_000, 15 + i) for i in range(20)]
    scored = {s.post.video_id: s for s in score_posts([post("now", 1_000, 16), *recent, *old], NOW, max_age_days=30)}
    assert scored["now"].x == pytest.approx(1.0)


def test_baseline_takes_only_posts_old_enough_to_have_their_views() -> None:
    fresh = [post(f"f{i}", 50, 3) for i in range(10)]
    week = [post(f"w{i}", 900, 9 + i * 0.1) for i in range(6)]
    scored = {s.post.video_id: s for s in score_posts([post("hit", 5_000, 3), *fresh, *week], NOW, max_age_days=30)}
    assert scored["hit"].baseline == 1_000


def test_channel_without_mature_posts_is_skipped() -> None:
    burst = [post(f"b{i}", 1_000, 2 + i * 0.2) for i in range(20)]
    assert score_posts(burst, NOW, max_age_days=30) == []


def test_a_thin_format_borrows_the_baseline_of_the_whole_channel() -> None:
    # 4 long flops among 6 mature long posts used to give a 2K baseline on a channel whose posts get 90K.
    longs = [post(f"l{i}", v, 20 + i, dur=600) for i, v in enumerate([500, 1_500, 1_800, 2_400, 107_000, 128_000])]
    shorts = [post(f"s{i}", 90_000, 20 + i) for i in range(20)]
    scored = score_posts([post("hit", 360_000, 13, dur=600), *longs, *shorts], NOW, max_age_days=30)
    hit = next(s for s in scored if s.post.video_id == "hit")
    assert hit.baseline == 90_000
    assert hit.x == pytest.approx(4.0)


def test_a_format_with_enough_mature_posts_keeps_its_own_baseline() -> None:
    longs = [post(f"l{i}", 5_000, 20 + i, dur=600) for i in range(10)]
    shorts = [post(f"s{i}", 90_000, 20 + i) for i in range(20)]
    scored = score_posts([post("hit", 50_000, 13, dur=600), *longs, *shorts], NOW, max_age_days=30)
    hit = next(s for s in scored if s.post.video_id == "hit")
    assert hit.baseline == 5_000


@pytest.mark.parametrize("longs,expected", [(10, 5_000), (9, 90_000)])
def test_the_format_fallback_counts_peers_without_the_post_itself(longs: int, expected: int) -> None:
    mature_longs = [post(f"l{i}", 5_000, 20 + i, dur=600) for i in range(longs)]
    shorts = [post(f"s{i}", 90_000, 20 + i) for i in range(20)]
    scored = score_posts([post("hit", 50_000, 20.5, dur=600), *mature_longs, *shorts], NOW, max_age_days=30)
    assert next(s for s in scored if s.post.video_id == "hit").baseline == expected
