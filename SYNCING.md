# Staying in sync with upstream (XBuilderLAB/cheat-on-content)

This fork carries our LinkedIn + Megaphone customizations **on `main`**, while still folding in
upstream's ongoing development. It stays painless because our changes are **additive**.

## Setup
- `origin` = `h3qing/cheat-on-content` (your fork) · `upstream` = `XBuilderLAB/cheat-on-content`
- Our work is **additive new dirs** (`adapters/perf-data/linkedin-session/`, `adapters/content-pipeline/`)
  plus a few root docs. We never edit upstream's `SKILL.md`, `skills/`, or `shared-references/` — so
  `git merge upstream/main` brings their updates in **without conflicts**.

## Pull the latest from upstream (anytime)
```bash
bash sync-upstream.sh     # fetch upstream + merge upstream/main into main
git push origin main      # after you've reviewed
```

## The rule that keeps merges clean
**Be additive, in your own namespace; consume upstream's contracts — don't fork the core.**
- Custom code → new dirs. Never edit upstream's `SKILL.md` / `skills/` / `shared-references/`.
- Build the LinkedIn flywheel by **adapting upstream's `cheat-predict` / `cheat-retro` / `cheat-bump` skills**
  (supply a LinkedIn rubric + data), not a parallel engine — so upstream's flywheel improvements flow in
  on the next merge.

## Recently shipped upstream (run `git log --oneline upstream/main` for live)
- `xhs-explore` (Xiaohongshu) + `bilibili-stat` perf-data adapters
- `cheat-persona` skill + `audience.md`
- retro observations → `rubric-memo.md`
