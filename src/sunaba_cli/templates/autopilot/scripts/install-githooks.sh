#!/usr/bin/env sh
# Wire .githooks/* into Git's hook directory. Idempotent.
set -e

if [ ! -d .git ]; then
  echo "skipping git hook install: .git not present" >&2
  exit 0
fi

git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "installed git hooks (.githooks/* via core.hooksPath)"
