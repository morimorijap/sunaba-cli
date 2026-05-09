#!/usr/bin/env bash
# Codex CLI Stop-equivalent verifier. Same body as the Claude variant —
# Codex shares the .sunaba/autopilot/ state directory so iteration counts
# accumulate across both runtimes.
exec bash "$(dirname "$0")/../../.claude/hooks/verify.sh" "$@"
