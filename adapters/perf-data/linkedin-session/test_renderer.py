"""renderer.render_report 的单元测试（合成数据，纯函数，不碰 playwright）。

只 import render_report / 纯 helper——crawler 在 renderer.main() 里才延迟 import，
所以本测试在没装 playwright 的环境也能跑。

跑：python test_renderer.py
"""
from renderer import _fmt_num, _ratio, render_report

# 合成样本：复刻 fetch_post_summary 的返回形状，数字是假的（对齐 test_extract 的英文样本）
SAMPLE = {
    "activity_id": "7341234567890123456",
    "metrics": {
        "impressions": 50000,
        "reach": 30000,
        "profile_views_from_post": 400,
        "followers_from_post": 180,
        "social_engagement": 300,
        "reactions": 100,
        "comments": 25,
        "reposts": 8,
        "saves": 100,
        "sends": 67,
    },
}


def test_fmt_num():
    assert _fmt_num(None) == "-"
    assert _fmt_num(152) == "152"
    assert _fmt_num(50000) == "5.0w"
    assert _fmt_num("n/a") == "n/a"


def test_ratio():
    assert _ratio(100, 50000) == "0.20%"
    assert _ratio(5, 0) == "-"
    assert _ratio(None, 100) == "-"


def test_render_has_activity_id_and_link():
    md = render_report(SAMPLE)
    assert "7341234567890123456" in md, md
    assert "urn:li:activity:7341234567890123456" in md, md


def test_render_metrics_and_ratios():
    md = render_report(SAMPLE, "我的稿子")
    assert "5.0w" in md, md          # impressions
    assert "3.0w" in md, md          # reach
    assert "0.60%" in md, md         # 互动率 300/50000
    assert "0.20%" in md, md         # 赞曝比 100/50000
    assert "我的稿子" in md, md       # 稿子原样进 report


def test_render_comments_text_unavailable():
    """LinkedIn 只给评论数、不给正文——report.md 必须标注 + 提示手动粘。"""
    md = render_report(SAMPLE)
    assert "只给评论数" in md, md
    assert "手动粘" in md, md


def test_render_missing_metrics_render_dash():
    # 某些指标抽不到（日/英切换）→ 渲染成 '-'，不炸
    md = render_report({"activity_id": "123", "metrics": {}})
    assert "# LinkedIn" in md, md
    assert "-" in md, md


def test_render_empty_result_no_crash():
    # fetch 返回 {} 时（理论上 run.sh 已拦截）render 也不该炸
    md = render_report({})
    assert "# LinkedIn" in md, md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n{len(fns)} passed")
