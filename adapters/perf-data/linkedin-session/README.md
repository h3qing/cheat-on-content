# Adapter: linkedin-session（领英分析抓取 → Supabase）

抓本人 LinkedIn 分析数据，**写入你 Supabase 现有的表**（不建新表）。独立运行，不挂在打分/预测循环上。

| 数据面 | 命令 | 落库表 | 状态 |
|---|---|---|---|
| 创作者面板（曝光/粉丝/主页访问/搜索出现） | `pull` | `profile_stats` | ✅ |
| 单帖互动（impressions/reactions/comments/reposts…） | `posts` | `engagement_snapshots` | ✅ |
| 受众画像（职位/地区/资历/行业/公司/规模） | `audience` | `audience_snapshots` | ✅ |
| 逐人受众分类（学生/专业人士/创始人…） | `import-connections` / `followers` / `classify` | `audience_members` | ✅ |
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
python "$ADAPTER/review.py" audience [--dry-run]   # 受众画像（aggregate）→ audience_snapshots
python "$ADAPTER/review.py" discover [seconds]     # XHR 发现器
```

### 逐人受众分类（audience_members）

把每个连接/关注者归到 8 类（student / early_career / professional / leadership /
recruiter_hr / educator / creator_media / other），存进 `audience_members`，**一人一行、
profile_key 唯一**，所以爬一次就够，之后只增量补新人、不重爬。建表见 `schema.sql`。

数据来源分两路：**连接**用 LinkedIn 官方导出（最稳，不爬）；**纯关注者**才爬列表页。

```bash
# ① 连接：Settings → Data privacy → Get a copy of your data → "Connections" → Connections.csv
python "$ADAPTER/review.py" import-connections ~/Downloads/Connections.csv [--dry-run]

# ② 纯关注者（CSV 看不到的人）：爬关注者列表
python "$ADAPTER/review.py" followers [--max=5000] [--dry-run]

# ③ 分类：确定性关键词规则先判，模糊的写成 worklist 交给 LLM
python "$ADAPTER/review.py" classify [--dry-run]
#    → 命中的直接写回 category；模糊行落到 .cheat-cache/.../classify_tail.json

# ④ LLM tail：让 Claude 读 classify_tail.json，按 8 类打标成 [{profile_key,category},…]，写回
python "$ADAPTER/review.py" set-categories labeled.json
```

> **hybrid 分类**：规则（`classify.py`，纯函数、可测）覆盖绝大多数 headline，零成本；
> 只有规则判不了的模糊尾巴才交给 LLM（Claude 读 worklist 打标）——成本只花在尾巴上。
> `import` / `followers` 只 upsert 身份列，**永不覆盖**已分类的 category（幂等、可反复重导）。

受众构成查询：
```sql
select category, count(*) from audience_members group by category order by 2 desc;
select relationship, count(*) from audience_members group by relationship;
```

### 测量循环（接受请求后看年轻人占比有没有涨）

`audience_members` 是当下快照（一人一行），看不出趋势。`snapshot` 把当下构成定格成
一行 `audience_composition`，多次跑就有时间序列。每接受一批连接请求后跑一轮：

```bash
python "$ADAPTER/review.py" followers          # 新粉丝（已接受的连接会自动关注你）
python "$ADAPTER/review.py" classify           # 给新人分类
python "$ADAPTER/review.py" snapshot           # 定格当下构成 → 趋势
```

趋势查询（年轻人 = student + early_career 占比随时间）：
```sql
select captured_at, total,
       (by_category->>'student')::int + coalesce((by_category->>'early_career')::int,0) as young,
       round(100.0*((by_category->>'student')::int
             + coalesce((by_category->>'early_career')::int,0))/total,1) as young_pct
from audience_composition order by captured_at;
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
├── crawler.py         # 登录 + 面板/单帖 DOM 抓取 + 关注者列表爬 + XHR 发现器
├── extract.py         # DOM 文本 → 指标（双语 parser，纯函数）
├── classify.py        # headline → 8 类（确定性关键词规则，纯函数）
├── audience_members.py# Connections.csv 解析 + profile_key 归一（纯函数）
├── sink_supabase.py   # → profile_stats / engagement_snapshots / audience_members（supabase-py）
├── review.py          # CLI：login/pull/.../audience + import-connections/followers/classify/set-categories
├── renderer.py        # 单帖分析 → report.md（纯渲染 + run.sh 的抓取/渲染入口）
├── run.sh             # cheat-retro Path B 调用的 wrapper（fetch → render → report.md）
├── test_extract.py    # parser 单测（合成数据，含 JP+EN）
├── test_sink.py       # 行映射单测
├── test_audience.py   # 分类规则 + CSV 解析 + 成员行映射单测
├── test_crawler.py    # share→activity 归一单测（含假 page 异步集成测）
├── test_renderer.py   # render_report 单测（合成数据，纯函数）
├── schema.sql         # audience_snapshots + audience_members 建表（其余表用账号已有的）
└── daily.sh           # cron wrapper
```
