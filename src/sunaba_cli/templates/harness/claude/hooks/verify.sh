#!/usr/bin/env bash
# Silent on success, verbose on failure. Exit 2 to re-engage the agent.
set -uo pipefail

fail=0
out="$(mktemp)"
trap 'rm -f "$out"' EXIT

check() {
  local label="$1"
  shift
  if ! "$@" >"$out" 2>&1; then
    echo "FAILED: $label" >&2
    cat "$out" >&2
    fail=1
  fi
}

if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
  check "uv run pytest -q" uv run pytest -q
fi

if [ -f package.json ]; then
  if [ -f node_modules/.package-lock.json ] || [ -d node_modules ]; then
    npm run lint --if-present >/dev/null 2>&1 \
      || check "npm run lint" npm run lint --if-present
    npm run typecheck --if-present >/dev/null 2>&1 \
      || check "npm run typecheck" npm run typecheck --if-present
    npm test --if-present >/dev/null 2>&1 \
      || check "npm test" npm test --if-present
  fi
fi

[ "$fail" -eq 0 ] || exit 2
