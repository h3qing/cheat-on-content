"""extract.parse_dashboard 的单元测试。用合成样本（不提交真实指标）。

跑：python test_extract.py
"""
from extract import _to_int, parse_audience, parse_dashboard, parse_post_summary

# 合成样本：复刻真实 /dashboard/ 的 inner_text 版式，但数字是假的
SAMPLE = """0 notifications total
Home
Me
Analytics & tools
Wednesday, January 1
Analytics
12,345
Post impressions
10.0% past 7 days
999
Followers
1.0% past 7 days
500
Profile viewers
Past 90 days
42
Search appearances
Previous week
Weekly sharing tracker
"""


def test_to_int():
    assert _to_int("34,057") == 34057
    assert _to_int("152") == 152
    assert _to_int("1.2K") == 1200
    assert _to_int("3M") == 3_000_000
    assert _to_int("n/a") is None


def test_parse_dashboard_values():
    r = parse_dashboard(SAMPLE)
    m = r["metrics"]
    assert m["post_impressions"] == 12345, m
    assert m["followers"] == 999, m
    assert m["profile_viewers"] == 500, m
    assert m["search_appearances"] == 42, m


def test_parse_dashboard_context():
    r = parse_dashboard(SAMPLE)
    assert r["context"]["profile_viewers"] == "Past 90 days"
    assert r["context"]["search_appearances"] == "Previous week"
    assert r["as_of_label"] == "Wednesday, January 1"


def test_parse_dashboard_missing_is_none():
    r = parse_dashboard("nothing useful here\njust text")
    assert all(v is None for v in r["metrics"].values())


# 2026-06 版式漂移：标签带后缀（"Post impressions in 7 days"）、"Total followers"，
# 且没有 "Analytics & tools" 锚（页面改成 Overview / Track performance）
SAMPLE_2026_06 = """Overview
Track performance
4,842
Post impressions in 7 days
75%
vs. prior 7 days
6,788
Total followers
13%
vs. prior 7 days
2,286
Profile viewers in 90 days
105%
vs. prior 7 days
105
Search appearances Jun 16–22
0%
vs. Jun 9–15
Weekly progress
"""


def test_parse_dashboard_2026_06_layout():
    r = parse_dashboard(SAMPLE_2026_06)
    m = r["metrics"]
    assert m["post_impressions"] == 4842, m
    assert m["followers"] == 6788, m
    assert m["profile_viewers"] == 2286, m
    assert m["search_appearances"] == 105, m


POST_SAMPLE = """Heqing Huangさんが投稿しました • 4日
post body with a stray number 123 inside
調査
9,999
インプレッション数
800
リーチしたメンバー
プロフィールアクティビティ
5
この投稿からのプロフィール閲覧ユーザー
2
この投稿で獲得したフォロワー
エンゲージメント
30
ソーシャルエンゲージメント
リアクション
20
コメント
6
再投稿
3
保存数
1
LinkedInでの送信数
0
上位統計データ
"""


def test_parse_post_summary():
    m = parse_post_summary(POST_SAMPLE)["metrics"]
    assert m["impressions"] == 9999, m
    assert m["reach"] == 800, m
    assert m["profile_views_from_post"] == 5, m
    assert m["followers_from_post"] == 2, m
    assert m["social_engagement"] == 30, m
    assert m["reactions"] == 20, m
    assert m["comments"] == 6, m
    assert m["reposts"] == 3, m
    assert m["saves"] == 1, m
    assert m["sends"] == 0, m


def test_parse_post_summary_missing():
    assert parse_post_summary("no metrics here")["metrics"]["impressions"] is None


POST_SAMPLE_EN = """Heqing Huang posted this • 6d
post body text with stray number 999
Discovery
50,000
Impressions
30,000
Members reached
Profile activity
400
Profile viewers from this post
180
Followers gained from this post
Engagement
300
Social engagements
Reactions
100
Comments
25
Reposts
8
Saves
100
Sends on LinkedIn
67
Top demographics
"""


def test_parse_post_summary_english():
    m = parse_post_summary(POST_SAMPLE_EN)["metrics"]
    assert m["impressions"] == 50000, m
    assert m["reach"] == 30000, m
    assert m["profile_views_from_post"] == 400, m
    assert m["followers_from_post"] == 180, m
    assert m["social_engagement"] == 300, m
    assert m["reactions"] == 100, m
    assert m["comments"] == 25, m
    assert m["reposts"] == 8, m
    assert m["saves"] == 100, m
    assert m["sends"] == 67, m


AUDIENCE_SAMPLE = """フォロワー数の増加
1,234
フォロワー合計
6%
直近7日間との比較
上位統計データ
すべて
役職
場所
職務レベル
会社
業種
会社規模
職務レベル
シニアレベル
35%
会社規模
従業員10,001人以上
26%
場所
サンフランシスコ ベイエリア
24%
業種
技術・情報・インターネット
18%
役職
ソフトウェアエンジニア
5%
会社
Scale AI
4%
会社概要
"""


def test_parse_audience():
    r = parse_audience(AUDIENCE_SAMPLE)
    assert r["total_followers"] == 1234, r
    d = r["top_demographics"]
    assert d["seniority"] == {"bucket": "シニアレベル", "pct": 35.0}, d
    assert d["company_size"] == {"bucket": "従業員10,001人以上", "pct": 26.0}, d
    assert d["location"]["bucket"] == "サンフランシスコ ベイエリア", d
    assert d["industry"]["pct"] == 18.0, d
    assert d["job_title"]["bucket"] == "ソフトウェアエンジニア", d
    assert d["company"] == {"bucket": "Scale AI", "pct": 4.0}, d


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n{len(fns)} passed")
