# Adapter: linkedin-session（领英分析抓取 → Supabase）

抓本人 LinkedIn 分析数据，**写入你 Supabase 现有的表**（不建新表）。独立运行，不挂在打分/预测循环上。

| 数据面 | 命令 | 落库表 | 状态 |
|---|---|---|---|
| 创作者面板（曝光/粉丝/主页访问/搜索出现） | `pull` | `profile_stats` | ✅ |
| 单帖互动（impressions/reactions/comments/reposts…） | `posts` | `engagement_snapshots` | ✅ |
| 受众画像（职位/地区/资历/行业/公司/规模） | `audience` | `audience_snapshots` | ✅ |
| 公司主页分析 | — | — | ⬜ 跳过（个人号无公司页） |

> `engagement_snapshots.impressions` 正是 Cowork 老流程留空的列——本 adapter 补上。

---

## 怎么抓的（和其它 adapter 的关键区别）

LinkedIn 把分析数据 **SSR/inline 进页面 DOM**，没有可拦的 voyager/XHR 接口（实测 27 个 voyager 响应里没有分析数据）。所以这里不走 douyin 那种 **XHR 拦截**，而是 **Playwright 持久化登录态 + 读渲染后 DOM 文本**，按标签锚点解析。

两个现实坑，已在代码里处理：
- **headless 可用** → 能挂 cron 无人值守。
- **LinkedIn 在 日/英 间随机切换语言**（同 session 都会变，`?lang=`/locale 强制无效）→ parser **双语**（`extract.py` 每个指标存 JP+EN 别名）。抽不到时**跳过、不写空行**（fail-safe）。

---

## 安装（一次性）

```bash
mkdir -p ~/linkedin-tracker && cd ~/linkedin-tracker
python3.11 -m venv .venv && source .venv/bin/activate   # 3.11+，别用系统 3.9
ADAPTER="<本 repo>/adapters/perf-data/linkedin-session"
pip install -r "$ADAPTER/requirements.txt"
playwright install chromium                              # ~500MB
```

凭据放 `~/linkedin-tracker/.cheat-secrets.json`（gitignore；该目录非 git repo）：
```json
{ "supabase_url": "https://xxxx.supabase.co", "supabase_service_key": "sb_secret_... 或 service_role JWT" }
```
> Supabase MCP 当前连不上，所以走 supabase-py 直连——更适合无人值守 routine。

`profile_stats` / `engagement_snapshots` 用账号**已有**的表。受众面的新表 `audience_snapshots` 建表语句见 `schema.sql`（在 SQL Editor 跑一次）。

---

## 用法

```bash
cd ~/linkedin-tracker && source .venv/bin/activate
ADAPTER="<本 repo>/adapters/perf-data/linkedin-session"

python "$ADAPTER/review.py" login                 # 首次：弹窗登录 LinkedIn，存 cookie
python "$ADAPTER/review.py" pull                   # 面板 → profile_stats（append 一行）
python "$ADAPTER/review.py" pull --dry-run         # 只打印不写
python "$ADAPTER/review.py" posts --limit=10       # 最新 10 帖 → engagement_snapshots
python "$ADAPTER/review.py" posts --limit=5 --dry-run
python "$ADAPTER/review.py" resolve <permalink>    # 永久链接/share urn → 规范 activity id（登记前归一）
python "$ADAPTER/review.py" post <activity_id|permalink>  # 单帖，只打印（接受 URL/urn）
python "$ADAPTER/review.py" audience [--dry-run]   # 受众画像 → audience_snapshots
python "$ADAPTER/review.py" discover [seconds]     # XHR 发现器
```

## 复盘（被 cheat-retro 调用）

`/cheat-retro` 在 `state.data_collection=adapter` + `platform=linkedin` 时自动调 `run.sh`，你一般不用手动跑。手动测试：

```bash
ADAPTER="<本 repo>/adapters/perf-data/linkedin-session"
bash "$ADAPTER/run.sh" <activity_id|帖子URL> <video_folder> [script.txt]
# 输出在 <video_folder>/report.md
```

第一个参数原样交给 crawler 归一（裸 activity id / `urn:li:activity` / `urn:li:share` / 永久链接都行，share→activity 会联网解析）。`renderer.py` 再把单帖分析渲染成 NotebookLM 友好的 `report.md`，直接写进 `<video_folder>`（不像 douyin/xhs 按标题自动命名——单帖分析页拿不到帖子标题）。

> **评论限制**：LinkedIn 单帖分析页**只给评论数、不给评论正文**，`report.md` 只能标注评论数，由 cheat-retro 降级要求你手动粘 top 评论。和 douyin/xhs 不同（那两个能抓到评论正文）。

## 每日 cron

`daily.sh` 跑 `pull` + `posts`。crontab 每天 9:00：
```cron
0 9 * * * CHEAT_PROJECT_ROOT=$HOME/linkedin-tracker bash <本 repo>/adapters/perf-data/linkedin-session/daily.sh >> $HOME/linkedin-tracker/cron.log 2>&1
```
帖数用 `LINKEDIN_POSTS_LIMIT` 环境变量覆盖（默认 10）。

---

## 风险 / 注意

- **LinkedIn 强反自动化**：用真实登录态 + 人类节奏（`posts` 帖间停 4s），别高频。比抖音敏感。
- **TOS**：仅抓你自己账号数据、个人用途，风险自负。
- **cookie 会过期**：`li_at` 失效后重跑 `login`。
- **结构会变**：LinkedIn 改版后 parser 可能失效，重跑 `discover` 或看 `.cheat-cache/linkedin-session-debug/*.txt` 对照更新 `extract.py`。
- **别提交 git**：`.auth-linkedin/`（cookie）、`.cheat-secrets.json`（key）——已忽略。

## 文件清单

```
adapters/perf-data/linkedin-session/
├── README.md          # 本文件
├── requirements.txt   # playwright + supabase
├── paths.py           # .auth-linkedin / debug / secrets 路径
├── crawler.py         # 登录 + 面板/单帖 DOM 抓取 + XHR 发现器
├── extract.py         # DOM 文本 → 指标（双语 parser，纯函数）
├── sink_supabase.py   # → profile_stats / engagement_snapshots（supabase-py）
├── review.py          # CLI：login / pull / resolve / post / posts / discover
├── renderer.py        # 单帖分析 → report.md（纯渲染 + run.sh 的抓取/渲染入口）
├── run.sh             # cheat-retro Path B 调用的 wrapper（fetch → render → report.md）
├── test_extract.py    # parser 单测（合成数据，含 JP+EN）
├── test_sink.py       # 行映射单测
├── test_crawler.py    # share→activity 归一单测（含假 page 异步集成测）
├── test_renderer.py   # render_report 单测（合成数据，纯函数）
├── schema.sql         # audience_snapshots 建表（其余表用账号已有的）
└── daily.sh           # cron wrapper
```
