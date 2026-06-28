# LinkedIn 受众驱动的内容策略

由 `audience_members` / `audience_composition` 分析得出（见同级 adapter）。把"我受众是谁"
变成"我该发什么"。所有数字来自 2026-06-28 的真实快照。

## 受众现状（baseline t0）

- 总计 **4,169** 人，其中 **82% 资深**（professional 54% + leadership 28%）
- 学生仅 **1.9%**（78 人），年轻人（student + early_career）合计 **3.9%**
- 即：你的 1st-degree 网络高度偏资深 —— 而 1st-degree 决定每条帖子的初始分发

## 内容表现（已追踪的 20 帖）

- 平均曝光 ~10.6k；两条爆款：**67k**（Anthropic 95% 分析自动化）、**43k**（AI Builder Intern 招聘）
- 赢的帖子都是一个形状：**关于 agentic analytics / AI adoption 的、带具体数字或反共识观点**
- 入门向 "learning AI" 帖只有 ~2.3k —— 资深网络不是它的受众，早期互动不够，被算法掐住

## 核心机制（为什么这样发）

资深内容拉曝光 → 曝光把招聘/桥梁帖推出去 → 招聘帖转化学生 → 更广的盘子互动后续内容 → 循环。

一次接受 ~649 个请求（~225 学生 + ~424 资深）后，预计学生数 ~4×、年轻人占比 ~3.9%→8%。
**已验证：招聘/桥梁内容 = 年轻受众增长引擎。**

## 内容打法（按杠杆排序）

| # | 草稿 | 服务谁 | 机制 |
|---|---|---|---|
| 1 | [jobs-hub](drafts/01-jobs-hub.md) | 资深发岗 + 学生找岗 | 众包评论 → 评论是头号排序信号 |
| 2 | [jobs-roundup](drafts/02-jobs-roundup.md) | 学生 | 招聘帖做成**系列**（franchise 复利），靠反共识筛选体现你的声音 |
| 3 | [skills-bridge](drafts/03-skills-bridge.md) | 学生 + 资深转发 | 把你的专家观点翻译成学生职业建议 |
| 4 | [build-in-public-audience](drafts/04-build-in-public-audience.md) | 资深 / builder | 把 agentic analytics 用在自己 LinkedIn 上，build-in-public |

## 怎么用

1. 先发 **#1**（最省力、最高互动、还为 #2 喂数据）。
2. 用 adapter 挖网络里的招聘联系人喂 #2（recruiter + leadership 连接）：
   ```sql
   select full_name, headline, company from audience_members
   where category in ('recruiter_hr','leadership') and headline ilike '%hiring%'
   order by company;
   ```
3. #2 长成 LinkedIn newsletter → 订阅者比单帖复利更好。
4. 每发完一轮接受请求，跑测量循环看年轻人占比有没有涨（见 adapter README）。

## 写作声音（来自你的爆款）

陈述式开头 + 一个具体数字 + 反共识 + 短句、无废话、第一人称。结尾给互动钩子。
反例：泛泛的"AI 很重要"。正例："一个 $4.17/月的 App 比很多企业数据栈的分析 agent 还强。"
