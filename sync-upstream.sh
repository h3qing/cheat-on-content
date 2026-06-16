#!/usr/bin/env bash
#
# Pull upstream (XBuilderLAB/cheat-on-content) into this fork's main.
# Our customizations live ON main and are additive (new dirs only), so this merge
# stays conflict-free. See SYNCING.md.
#
# Usage: bash sync-upstream.sh
set -euo pipefail

echo "→ fetching upstream"
git fetch upstream

echo "→ merging upstream/main into main"
git checkout main
git merge --no-edit upstream/main

echo ""
echo "✓ merged upstream's latest into main (our additive dirs don't conflict)."
echo "  Review, then push:  git push origin main"
