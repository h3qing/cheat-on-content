#!/usr/bin/env bash
#
# Pull upstream (XBuilderLAB/cheat-on-content) into this fork, keeping our additive
# customization branch rebased on top. See SYNCING.md.
#
# Usage: bash sync-upstream.sh [branch]   (default branch: feat/linkedin-session-adapter)
set -euo pipefail

BRANCH="${1:-feat/linkedin-session-adapter}"

echo "→ fetching upstream"
git fetch upstream

echo "→ fast-forwarding main to upstream/main"
git checkout main
git merge --ff-only upstream/main
git push origin main

echo "→ rebasing $BRANCH onto main"
git checkout "$BRANCH"
git rebase main

echo ""
echo "✓ synced. Our additions replayed on top of upstream's latest."
echo "  Review, then push:  git push --force-with-lease origin $BRANCH"
