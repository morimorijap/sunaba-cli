# Antigravity CLI (`agy`) and the autopilot stack — status & caveats

Gemini CLI has been folded into the **Antigravity CLI** (`agy`). The
`--stack autopilot` flow is built around a Stop-hook re-engage loop, a
structured failure protocol, glob-scoped path rules, and subagent dispatch
with separate context windows.

The autopilot stack's first-class templates target **Claude** and
**Codex CLI**. `agy` ships hooks, subagents, and plugins, so more of this
flow is reachable than it was on the old Gemini CLI — but the exact hook
event names and headless behavior are **not yet verified end-to-end here**.
Treat the items below as status, not guarantees, and test before relying on
auto re-engage with `agy`.

## What works today, regardless of CLI

- **The structured `verify.sh`** can be invoked manually
  (`bash .claude/hooks/verify.sh`).
- **`.githooks/pre-push`** branch protection — git-level, not agent-level,
  so it works under any CLI.
- **Rule fallback docs** under `docs/agents/rules/<name>.md` (from
  `--stack rules`) — readable on demand.
- **`AGENTS.md`** is the customization file `agy` reads (the same one
  sunaba generates), plus per-stack guidance in `docs/agents/<stack>.md`.

## Likely reachable on `agy` (verify before depending on it)

- **Hooks** (`hooks.json`, including a stop hook): `agy` supports hooks, so
  a Stop-hook re-engage loop comparable to Claude's may be configurable.
  The event names / payload shape differ from Claude's and are unconfirmed.
- **Subagents**: `agy` supports subagents; mapping the planner / reviewer /
  verifier roles onto them is plausible but untemplated here.
- **Skills & Plugins**: extensions are now `agy` plugins (`agy plugin`).

## Recommended posture for now

Until the `agy` hook/subagent wiring is templated and tested, treat `agy`
as a single-shot agent in this stack: plan, implement, verify, and review
by hand. The role files in `.claude/agents/` and `.codex/agents/` document
the discipline; you can adopt it on `agy` even though sunaba does not yet
wire the runtime to enforce it. Contributions that template the `agy`
hooks.json + subagents for autopilot are welcome.
