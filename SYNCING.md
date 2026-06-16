# Staying in sync with upstream (XBuilderLAB/cheat-on-content)

This fork keeps **upstream's ongoing development** (new skills, the evolving flywheel) while carrying our
**LinkedIn + Megaphone customizations**. Two levels keep that painless.

## Current state (ideal)
- `origin` = `h3qing/cheat-on-content` (your fork) · `upstream` = `XBuilderLAB/cheat-on-content`
- `main` is an **exact mirror of upstream/main** (0 ahead, 0 behind — you never committed to it).
- All our work lives on branch **`feat/linkedin-session-adapter`** as **additive new dirs**:
  `adapters/perf-data/linkedin-session/`, `adapters/content-pipeline/`. We have **not** edited any of
  upstream's core files — so upstream updates can't conflict with ours.

## Pull the latest from upstream (anytime)
```bash
bash sync-upstream.sh          # fetch → fast-forward main → rebase our branch on top
git push --force-with-lease origin feat/linkedin-session-adapter   # after you've reviewed
```
What it does, manually:
```bash
git fetch upstream
git checkout main && git merge --ff-only upstream/main && git push origin main
git checkout feat/linkedin-session-adapter && git rebase main      # additive commits replay cleanly
```

## The rule that keeps merges clean (architecture)
**Be additive, in your own namespace; consume upstream's contracts — don't fork the core.**
- Put custom code in **new dirs** (your own adapters). Never edit upstream's `SKILL.md`, `skills/`, `shared-references/`.
- Build the LinkedIn flywheel by **adapting upstream's `cheat-predict` / `cheat-retro` / `cheat-bump` skills**
  (supply a LinkedIn rubric + the data adapter) — NOT a parallel engine. Then upstream's flywheel improvements
  flow to you on the next sync, instead of diverging.
- Need to change upstream behavior? Prefer config or a new file over editing theirs.

## Recently shipped upstream (reference — run `git log --oneline upstream/main` for live)
- `xhs-explore` (Xiaohongshu) + `bilibili-stat` perf-data adapters
- `cheat-persona` skill + `audience.md`
- retro observations → `rubric-memo.md`
