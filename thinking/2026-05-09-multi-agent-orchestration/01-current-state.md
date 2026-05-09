# 01 — Current state

## What sunaba ships for parallel-agent work today

After PRs #12, #14, #15, and #16, the project provides:

- **Subagent role files** under `.claude/agents/`
  (planner / reviewer / verifier) and `.codex/agents/*.toml`. These
  describe **roles** — what each kind of agent does — not how
  multiple instances of the *same* role coordinate.
- **`subagent-dispatch.md`** — a flowchart for **serial** dispatch
  (planner → implementer → reviewer → verifier). Skip rules and
  budget caps are documented. **There is no fan-out section.**
- **`claudedocs/plans/<slug>.md`** — a place for the planner to
  write. Plan format is goal / scope / acceptance criteria / risks.
  No claim list, no per-task `status` field, no parallel slice
  schema.
- **`claudedocs/checkpoints/<slug>.md`** — resumability hooks. Used
  by the implementer between coherent slices. Single-agent shape.
- **`_files` collision rule (later wins)** — applies at template
  generation, not at agent runtime.
- **`.sunaba/autopilot/`** — runtime state for the verify hook
  (iteration counter, last-failure log). Ignored by `.gitignore`.

## What the existing scaffolding *almost* provides

- A claim list could live as a thin extension to the plan file
  format. The planner already produces a scoped plan; adding a
  per-shard `claimed-by` column gives orchestrator + subagents
  somewhere to negotiate.
- `claudedocs/checkpoints/` could carry "this agent is editing this
  file right now" claims. The semantics are different from
  resumability checkpoints, but the directory and write discipline
  are reusable.
- `git worktree` is already part of the project's own development
  workflow (the four implementation PRs each ran in a worktree).
  Documenting the user-side equivalent is mostly prose.

## What's missing

### A shared, declarative coordination surface

Today there is no canonical place to record:

- Which task a subagent has claimed.
- Which files that task may touch.
- Which files **no other** subagent may touch while the task is
  active.
- Whether the task succeeded, failed, or is blocked by another
  task.

Without this, parallel subagents either:

- Trust the orchestrator's verbal hand-off and risk silent
  overwrites, or
- Refuse to parallelize anything that's not obviously
  non-overlapping (the safe-but-slow default).

### Workload sharding policy

The dispatch protocol's planner section says *when* to dispatch a
planner. It does not say:

- How big a slice should be (in files / lines / commits).
- What the *minimum task size* is below which parallelization
  hurts more than it helps.
- What the *maximum concurrency* is for this project (the 2026
  industry consensus is 4–8 concurrent worktrees per developer;
  the project has no equivalent).
- How to detect "this task is unsharded-able" and fall back to a
  single implementer.

### File-ownership rules

Agents need to be able to answer two questions before editing a
file:

1. *"May I edit this file right now?"*
2. *"If yes, am I claiming it for the duration of my edit, and how
   do I record that?"*

No documented answer exists. The closest thing today is "the
implementer does the edits" — but that assumes one implementer.

### Conflict resolution

When parallel subagents land on the same file (despite
decomposition), the project has no documented "who wins" rule. The
choices are:

- **Worktree merge later.** Each subagent works in a worktree;
  conflicts surface at merge. Standard git, well-understood, but
  pushes the conflict to a single point that may need a human.
- **Optimistic claim.** Subagent grabs the claim first, others
  back off. Requires a write-once claim list with atomic semantics.
- **Pessimistic lock.** Subagent must acquire a lock before
  editing. Higher overhead, simpler reasoning.

The proposal in [`05-proposal.md`](05-proposal.md) takes a position
on which of these to ship.

### Cross-agent fairness for orchestration

Claude Code 2.0 ships native subagent dispatch via the Agent tool.
Codex CLI 2026 has subagents under `.codex/agents/`. Gemini CLI
remains the gap. The autopilot proposal already documents that.
What's missing is the *parallel* equivalent — when running many
Claude or Codex instances at once, what's the protocol? When using
Gemini, is parallelization possible at all (manual `git worktree`
per terminal session)?

## What the proposal must keep working

- Existing **serial** dispatch from the autopilot PR. The serial
  flow is the right default for small tasks; the parallel flow is
  an opt-in for genuinely big work.
- The **Stop-hook re-engage** loop. Per-shard verify must still
  exit 2 / 1 / 0 deterministically.
- The **budget caps**. Parallelism multiplies token spend; the
  caps must apply *across* the parallel cohort, not per-shard.
- The **honest-about-limits** posture. Multi-agent is the
  highest-leverage move on big work; it is also the highest-risk if
  the discipline isn't in place. Document that.
