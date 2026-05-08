# 01 — Current state

## What the harness PR already provides

[`2026-05-09-harness-engineering/05-proposal.md`](../2026-05-09-harness-engineering/05-proposal.md)
introduces:

- `.claude/settings.json` with `permissions.allow` /
  `permissions.deny` and a Stop hook calling
  `.claude/hooks/verify.sh`.
- `.claude/agents/{planner,reviewer,verifier}.md` as **role
  templates** for sub-agent dispatch.
- `.claude/skills/{impact-map,verify-change}/SKILL.md` for
  on-demand procedural skills.
- `claudedocs/` for trace and decision notes.
- A 60-line ratchet `AGENTS.md`.

This is the **scaffold** for autonomous work. It is not yet the
autonomous environment.

## What "autonomous environment" actually requires

Working from the published autonomous-loop patterns
(Ralph Loop, Anthropic Auto Mode, Cursor Agent mode), an
agent runs autonomously when **all** of the following hold:

1. **Sufficient permissions.** Common safe tools must be in
   `permissions.allow` so the agent does not hit approval prompts on
   `git status`, `npm test`, `uv run pytest`, etc. (The harness PR
   covers this.)
2. **A Stop hook that re-engages on failure.** When verification
   fails, the hook exits non-zero (typically code 2) so the harness
   re-prompts the agent with the failure output.
3. **A verifier the agent trusts.** The Stop hook must run real
   checks (typecheck, lint, tests) so its verdict is meaningful.
   (The harness PR's `verify.sh` is silent-success / verbose-failure;
   that's the right shape.)
4. **A planner that produces a checkable plan.** Without a plan
   structured as testable acceptance criteria, the verifier has
   nothing to compare against.
5. **A reviewer separate from the implementer.** Self-review
   underperforms (Osmani, citing Cursor evidence).
6. **File-glob scoped rules.** The agent should not be told about
   "tailwind config" while editing a Python test. Cursor `.mdc`
   files with `globs:` solve this; Claude Code added native
   path-specific rules in early 2026; AGENTS.md handles it via
   subdirectory hierarchy.
7. **Bounded blast radius.** Branch protection (work on a feature
   branch, never main), budget caps (token / wallclock limits), and
   recovery primitives (checkpoints, rollback).
8. **Cross-agent equivalents.** Codex CLI and Gemini CLI both run
   inside sunaba sandboxes. Whatever autonomy Claude gets, the
   other two need an honest analog or an explicit "Claude-only"
   marker.

The harness PR ships items 1, partial 2 (the hook exists; re-engage
semantics are documented but not enforced), partial 4 (planner
template exists, but acceptance-criteria *output* discipline isn't
specified), partial 5 (templates exist, dispatch protocol doesn't),
and **none of 3, 6, 7, or 8 in operationally usable form**.

## What's specifically missing

### Rules layer (item 6)

No path-scoped rules. The harness `AGENTS.md` is a single, flat,
≤60-line file. There is no:

- `.cursor/rules/*.mdc` for Cursor.
- `.claude/rules/<name>.md` (or whatever Claude's path-specific format
  is in 2026) for Claude.
- Subdirectory `AGENTS.md` files for the AGENTS.md spec hierarchy
  (deferred in the stack-aware-agent-files PR).

The stack-aware-agent-files PR covers *project-wide* stack guidance.
It does **not** cover *file-glob-scoped* rules (e.g., "for tests/*.py
use pytest fixtures, never unittest"; "for app/api/*.ts validate body
with Zod"; "for terraform/* always run `terraform plan` before
`apply`").

### Subagent dispatch protocol (items 4, 5)

`.claude/agents/{planner,reviewer,verifier}.md` are *role* files —
they tell the subagent *who they are*. Nothing tells the orchestrator
*when to dispatch*. Concrete questions left open:

- When is "before implementation" — at the start of every task, or
  only on tasks of some complexity?
- Does the planner write its plan to `claudedocs/plans/` so the
  verifier can read it?
- Does the verifier reject implementations that don't satisfy the
  plan's acceptance criteria, or just run tests?
- For Codex CLI / Gemini CLI, what's the subagent equivalent? They
  don't load Claude `.claude/agents/`.

### Autonomous-loop primitives (items 2, 3, 7)

The harness Stop hook exits non-zero on failure. That's *necessary*
but not *sufficient* for autonomy:

- **Re-engage protocol.** The harness re-prompts the agent on exit
  code 2, but with what message? If the agent gets the same prompt
  back, it loops. The verify hook's failure summary needs to feed
  back as actionable context.
- **Budget cap.** No mechanism prevents an agent from looping
  forever. A token budget, a wallclock budget, or a max-iteration
  count is the standard guard.
- **Branch protection.** No mechanism stops the agent from running
  `git push origin main`. The harness PR's `permissions.deny` lists
  `git push --force` but not unforced pushes to main.
- **Checkpoint / resume.** The harness PR proposes
  `claudedocs/traces/`. Trace notes are a record-only thing. A
  *checkpoint* is "if I'm interrupted at minute 17 of a 25-minute
  task, here's where to pick up."

### Cross-agent fairness (item 8)

Everything in the harness PR (and the proposed additions in this
PR) is Claude-Code-shaped. Codex CLI has subagents via
`AGENTS.md` hierarchy + native task delegation. Gemini CLI's
autonomy story is thinner. We need to either:

- Provide parallel scaffolding for the other two agents, or
- Mark the autonomy stack as "Claude-only for now" and document the
  gap.

## What this means for the proposal

The proposal in `05-proposal.md` will:

1. Add a **rules** layer (`.cursor/rules/*.mdc` +
   `.claude/skills/<name>/SKILL.md` mirrors with `when:` /
   `globs:` discipline; `AGENTS.md` content unchanged).
2. Define a **subagent dispatch protocol** as a concrete document
   with prescribed handoffs, not just role templates.
3. Add an **autonomy stack** (working name `--stack autopilot`)
   that bundles: a richer permissions list, the Ralph-style
   continuation hook, branch protection, a budget cap, and a
   checkpoint directory.
4. Take a position on cross-agent autonomy: ship Claude-Code-shaped
   first; provide minimum-viable Codex / Gemini hooks; document the
   gap honestly.

## Constraints we keep

- The autonomous environment is **always opt-in**. `--stack
  autopilot` (or whatever we call it) is never default.
- Whatever we ship must compose with the existing `--stack harness`,
  `--stack secrets`, and stack-aware-agent-files proposals.
  Implementation order stays harness → others.
