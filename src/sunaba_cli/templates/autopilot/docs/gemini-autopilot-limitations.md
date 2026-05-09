# Gemini CLI and the autopilot stack

`--stack autopilot` is built around a Stop-hook re-engage loop and a
structured failure protocol. **Gemini CLI as of May 2026 does not
provide** a Stop hook, glob-scoped path rules, or native subagent
dispatch with separate context windows.

The autopilot stack is therefore explicitly Claude- and Codex-CLI
shaped. Gemini gets best-effort coverage where the runtime allows and
honest documentation everywhere else.

## What works for Gemini in this stack

- **Hierarchical `GEMINI.md`** files — the closest one to the file
  being edited wins. (Stack-aware composition writes per-stack
  guidance into `docs/agents/<stack>.md` which Gemini can find on
  demand.)
- **The structured `verify.sh`** can be invoked manually
  (`bash .claude/hooks/verify.sh`). Gemini just won't auto re-engage
  on exit 2.
- **`.githooks/pre-push`** branch protection — that's git-level, not
  agent-level, so it works regardless of which CLI you're running.
- **Rule fallback docs** under `docs/agents/rules/<name>.md` (from
  `--stack rules`) — Gemini can read them when context retrieval
  surfaces them.

## What does NOT work

- Native autonomous loop. There is no Gemini equivalent of "Stop exit
  2 → re-prompt." The Ralph Loop is Claude/Codex-only.
- Glob-scoped rules that don't map to a directory. Those are rendered
  to `docs/agents/rules/<name>.md` for human reference; Gemini will
  read them only if its context happens to surface them.
- Sub-agent dispatch with isolated context windows (Codex 2.0 ships
  this, Gemini does not).

## Manual protocol

Treat Gemini as a single-shot agent in this environment. Plan,
implement, verify, and review by hand. The role files in
`.claude/agents/` and `.codex/agents/` document the discipline; you
can adopt that discipline on Gemini even though the runtime won't
enforce it.
