# Adapter: x-discover（X / Twitter 选题发现）

engagement-aware 选题发现：抓 X search 里某关键词下**互动最高**的推文（views/likes/RT/replies/bookmarks），
作为"什么在 X 上驱动量"的信号源 → 喂给 `source_signals`。

> **不逆向签名**：用 Playwright 持久化登录态，让页面自己发带签名的 GraphQL 请求，我们**被动拦截**
> `SearchTimeline` 响应并解析。和 `xhs-explore` / `douyin-session` 同思路。

## 为什么走 Playwright 登录态（而不是 Chrome 扩展）
浏览器扩展驱动你真实浏览器能跑，但标签易抖动、不能无人值守。这里用**独立持久化登录态**
（`.auth-x/`），一次登录后 **headless 可跑**、可挂 cron，稳定。

## 安装 / 用法
```bash
export CHEAT_PROJECT_ROOT=~/linkedin-tracker          # cookie 存这里的 .auth-x/
PY=~/linkedin-tracker/.venv/bin/python                # playwright 已装

# 一次性登录（弹窗，邮箱/密码/2FA）
$PY crawler.py login

# 发现：某关键词下 top 互动推文 → JSON（agent 据此筛 relevance 写 source_signals）
$PY crawler.py discover "AI agents"
$PY crawler.py discover "agentic analytics"
```

`discover` 输出每条：`id / author / url(permalink) / text / views / likes / retweets / replies / bookmarks`，
按 views→likes 排序。**bookmarks 高 = 高收藏率 = 可操作/高价值**，是很强的 selection 信号。

## 选题选择（2x/周）
发现是 engagement-aware；最终落 `source_signals` 时由 agent 打 relevance（对标你的 pillars）。
配合 rubric 的"预测 reach × relevance × freshness × source-engagement"做 weekly picks（见 megaphone ROADMAP）。

## 风险 / 注意
- **TOS**：抓公开搜索结果、个人用途；别高频。
- `.auth-x/` 含会话 cookie，**别提交 git**（已忽略）。
- X 改版偶尔会动 `SearchTimeline` queryId / 字段；失效时重看 `discover` 抓到的 GraphQL。

## 文件
```
adapters/trend-sources/x-discover/
├── README.md
└── crawler.py   # login + search(keyword) → 解析 SearchTimeline → 按互动排序的推文
```
