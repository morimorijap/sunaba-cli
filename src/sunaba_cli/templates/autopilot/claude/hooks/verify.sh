#!/usr/bin/env bash
# autopilot Stop hook — structured failure output, budget-capped Ralph Loop.
#
# Exit codes:
#   0  all checks passed; loop terminates cleanly
#   2  verification failed AND budget remains  → Claude/Codex Stop loop continues
#   1  budget exceeded                         → loop terminates, human review required
set -uo pipefail

STATE=".sunaba/autopilot"
mkdir -p "$STATE"

: "${SUNABA_AUTOPILOT_MAX_ITERS:=5}"
: "${SUNABA_AUTOPILOT_MAX_MINUTES:=30}"
: "${SUNABA_AUTOPILOT_MAX_CHANGED_FILES:=25}"

ITER_FILE="$STATE/iteration"
START_FILE="$STATE/run-start"
LOG="$STATE/last-failure.log"
: > "$LOG"

if [ ! -f "$ITER_FILE" ]; then
  echo 0 > "$ITER_FILE"
  date +%s > "$START_FILE"
fi

iter=$(cat "$ITER_FILE")
iter=$((iter + 1))
echo "$iter" > "$ITER_FILE"

start=$(cat "$START_FILE")
now=$(date +%s)
elapsed_min=$(( (now - start) / 60 ))

run_check() {
  local label="$1"; shift
  local out
  if ! out=$("$@" 2>&1); then
    {
      echo "------ $label ------"
      echo "$out"
    } >> "$LOG"
    return 1
  fi
  return 0
}

failed=0

if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
  run_check "uv run pytest -q" uv run pytest -q || failed=1
fi
if [ -f package.json ]; then
  if [ -d node_modules ]; then
    run_check "npm run lint" sh -c 'npm run lint --if-present 2>&1' || failed=1
    run_check "npm run typecheck" sh -c 'npm run typecheck --if-present 2>&1' || failed=1
    run_check "npm test" sh -c 'npm test --if-present 2>&1' || failed=1
  fi
fi

if command -v git >/dev/null 2>&1 && git rev-parse HEAD >/dev/null 2>&1; then
  changed=$(git diff --name-only HEAD | wc -l | tr -d ' ')
  if [ "$changed" -gt "$SUNABA_AUTOPILOT_MAX_CHANGED_FILES" ]; then
    cat <<EOF >&2
SUNABA_BUDGET_EXCEEDED kind=changed-files iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES changed_files=$changed/$SUNABA_AUTOPILOT_MAX_CHANGED_FILES next_action=Stop autonomous loop. Human review required for the size of this change.
EOF
    rm -f "$ITER_FILE" "$START_FILE"
    exit 1
  fi
fi

if [ "$failed" -eq 0 ]; then
  rm -f "$ITER_FILE" "$START_FILE"
  exit 0
fi

if [ "$iter" -ge "$SUNABA_AUTOPILOT_MAX_ITERS" ] \
   || [ "$elapsed_min" -ge "$SUNABA_AUTOPILOT_MAX_MINUTES" ]; then
  cat <<EOF >&2
SUNABA_BUDGET_EXCEEDED kind=iteration-or-time iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES failure_log=$LOG next_action=Stop autonomous loop. Human review required.
EOF
  rm -f "$ITER_FILE" "$START_FILE"
  exit 1
fi

cat <<EOF >&2
SUNABA_VERIFY_FAILED iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES failure_log=$LOG next_action=Read $LOG, propose a fix that addresses the failing checks specifically. Do not summarize.
EOF
exit 2
