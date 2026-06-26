"""把 LinkedIn 单帖分析渲染成 NotebookLM 友好的 Markdown（与 douyin-session 同格式）。

cheat-retro 的 Path B 走这里：run.sh 调 crawler 抓单帖分析 → 本模块渲染 →
写 <video_folder>/report.md，cheat-retro 再读这个文件解析关键数据。

和 douyin-session/renderer.py 的两点差异（都是 LinkedIn 自身限制决定的）：
- 没有 output_dir_for/slugify：单帖分析页拿不到帖子标题，文件夹名由 cheat-retro 给定，
  run.sh 直接把 report.md 写进这个文件夹，不像抖音那样按标题自动命名。
- 渲染不出评论列表：单帖分析页**只给评论数、不给评论正文**（见下方「评论」段），
  report.md 标注后由 cheat-retro 降级要求用户手动粘 top 评论。
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path

POST_URL = "https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"


def _fmt_num(n) -> str:
    if n is None:
        return "-"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if n >= 10000:
        return f"{n / 10000:.1f}w"
    return str(n)


def _ratio(num, den) -> str:
    """派生比率（如赞曝比）。任一缺失 / 分母为 0 → '-'。"""
    try:
        num, den = int(num), int(den)
    except (ValueError, TypeError):
        return "-"
    if den <= 0:
        return "-"
    return f"{num / den * 100:.2f}%"


def render_report(result: dict, script: str = "") -> str:
    """{'metrics': {...}, 'activity_id': ...} → report.md 文本。

    指标 key 见 extract.POST_METRICS：impressions / reach / profile_views_from_post /
    followers_from_post / social_engagement / reactions / comments / reposts / saves / sends。
    缺失指标渲染成 '-'（LinkedIn 日/英随机切换，偶有某项抽不到——看 debug txt 补别名）。
    """
    metrics = result.get("metrics") or {}
    activity_id = result.get("activity_id") or "-"
    impressions = metrics.get("impressions")
    comments = metrics.get("comments")

    lines: list[str] = []
    lines.append(f"# LinkedIn 帖子 {activity_id}")
    lines.append("")
    lines.append(f"- 帖子 activity id：`{activity_id}`")
    lines.append(f"- 链接：{POST_URL.format(activity_id=activity_id)}")
    lines.append(f"- 抓取时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## 单帖分析")
    lines.append("")
    lines.append(f"- 曝光（impressions）：{_fmt_num(impressions)}")
    lines.append(f"- 触达（reach，去重人数）：{_fmt_num(metrics.get('reach'))}")
    lines.append(
        f"- 社交互动（social engagements）：{_fmt_num(metrics.get('social_engagement'))}"
        f"（互动率 {_ratio(metrics.get('social_engagement'), impressions)}）"
    )
    lines.append(f"- 点赞（reactions）：{_fmt_num(metrics.get('reactions'))}（赞曝比 {_ratio(metrics.get('reactions'), impressions)}）")
    lines.append(f"- 评论数（comments）：{_fmt_num(comments)}（评曝比 {_ratio(comments, impressions)}）")
    lines.append(f"- 转发（reposts）：{_fmt_num(metrics.get('reposts'))}")
    lines.append(f"- 收藏（saves）：{_fmt_num(metrics.get('saves'))}")
    lines.append(f"- 私信转发（sends）：{_fmt_num(metrics.get('sends'))}")
    lines.append(f"- 本帖带来主页访问（profile views）：{_fmt_num(metrics.get('profile_views_from_post'))}")
    lines.append(f"- 本帖涨粉（followers gained）：{_fmt_num(metrics.get('followers_from_post'))}")
    lines.append("")
    lines.append("> 曝光看不出的信号在比率：互动率 / 赞曝比 / 评曝比；reach 远小于 impressions 说明重复触达多。")
    lines.append("")

    lines.append("## 原始稿子")
    lines.append("")
    lines.append(script.strip() if script.strip() else "（未提供）")
    lines.append("")

    lines.append("## 评论")
    lines.append("")
    lines.append(f"⚠️ LinkedIn 单帖分析页**只给评论数（{_fmt_num(comments)}），不给评论正文**（分析页限制，抓不到）。")
    lines.append("评论才是真信号——请打开帖子评论区，手动粘 top 评论（每条带赞数）到对话里，cheat-retro 据此做评论聚类。")
    lines.append("")

    return "\n".join(lines)


def _read_script(script_path: str | None) -> str:
    if not script_path:
        return ""
    p = Path(script_path).expanduser()
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="ignore")
    print(f"[警告] 找不到稿子 {p}，稿子留空。")
    return ""


def main() -> None:
    """run.sh 入口：抓单帖分析（crawler 归一 ref → activity id）+ 渲染 + 写 report.md。

    用法：python renderer.py <activity_id|permalink> <video_folder> [script.txt]
    """
    if len(sys.argv) < 3:
        print("用法：python renderer.py <activity_id|permalink> <video_folder> [script.txt]")
        sys.exit(3)
    ref = sys.argv[1]
    video_folder = Path(sys.argv[2]).expanduser()
    script = _read_script(sys.argv[3] if len(sys.argv) > 3 else None)

    # 延迟导入：render_report 是纯函数，单测不该被 crawler 顶层的 playwright import 拖下水。
    import crawler

    print(f"[抓取] LinkedIn 单帖 {ref}")
    result = asyncio.run(crawler.fetch_post_summary(ref, headless=True))
    if not result.get("metrics"):
        print("❌ 没抓到单帖分析（未登录 / 无法解析 activity id / 非本人帖子）", file=sys.stderr)
        sys.exit(3)

    video_folder.mkdir(parents=True, exist_ok=True)
    if script:
        (video_folder / "script.txt").write_text(script, encoding="utf-8")
    report = video_folder / "report.md"
    report.write_text(render_report(result, script), encoding="utf-8")
    print(f"✓ {report}")


if __name__ == "__main__":
    main()
