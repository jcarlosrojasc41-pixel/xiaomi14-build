#!/usr/bin/env bash
# Run from a network-enabled user terminal after inspecting this public-only repository.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$root"
python3 scripts/check-public.py
test -z "$(git status --porcelain)" || { echo 'Commit reviewed changes before publishing.' >&2; exit 1; }
gh api user --jq .login | python3 -c 'import sys; assert sys.stdin.read().strip() == "LushShepherd", "Unexpected GitHub account"'
if git remote get-url origin >/dev/null 2>&1; then
  test "$(git remote get-url origin)" = 'https://github.com/LushShepherd/xiaomi14-build.git'
  test "$(gh repo view LushShepherd/xiaomi14-build --json visibility --jq .visibility)" = 'PUBLIC'
  git push origin main
else
  gh repo create LushShepherd/xiaomi14-build --public \
    --description 'Pinned build recipe for personal PixelOS 17 on Xiaomi 14 (houji CN); no device backups or proprietary binaries.' \
    --source "$root" --remote origin --push
fi
git push origin refs/tags/working-20261112-kit-v1
gh repo view LushShepherd/xiaomi14-build --json url,visibility
