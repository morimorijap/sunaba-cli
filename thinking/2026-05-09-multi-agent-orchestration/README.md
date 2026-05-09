# Multi-agent orchestration for sunaba-cli

> Status: **draft / in review**. Started 2026-05-09.

The first four thinking proposals built up the harness for a *single*
agent operating in a sunaba sandbox: scaffolding (`harness`), context
shaping (`stack-aware-agent-files`), secret hygiene (`secrets`), and
the autopilot loop (`rules-and-autonomy`). The autopilot stack
introduced subagent **roles** — planner, reviewer, verifier — but
specifies them as a **serial** dispatch chain.

This proposal works through what changes when the user wants to run
multiple agents — or multiple Claude Code instances — *in parallel*
inside one project. Two concerns drive it:

1. **One file should not be edited by multiple agents at the same
   time.** The sandbox makes file editing fast and cheap, which makes
   double-write conflicts catastrophic when an agent silently
   overwrites another's work.
2. **Job decomposition should match workload.** Two agents are wrong
   for a one-line bug fix; one agent is wrong for an eight-component
   refactor. The orchestrator needs an explicit policy for *how many
   agents* and *which slices*.

## What sunaba already has (and what it doesn't)

- `templates/autopilot/docs/subagent-dispatch.md` — dispatch protocol
  for planner / reviewer / verifier. **Serial only.** Says nothing
  about parallel implementers, file ownership, or shard sizing.
- `_files` collision rule (later wins) — applies at *generation time*,
  not at *agent runtime*. Doesn't help when two parallel implementers
  touch the same source file.
- `claudedocs/{plans,checkpoints}/` — exists, but the schema doesn't
  carry a "who is touching what" claim list.
- Branch protection (`.githooks/pre-push`) — prevents pushes to main
  but doesn't sequence parallel branches against each other.

The gap is **a coordination surface**: a shared, declarative claim
list that orchestrator and subagents read and write to negotiate file
ownership before edits begin.

## What 2026 looks like in this space

Claude Code Agent Teams (May 2026), Codex CLI's `codex exec` parallel
mode, and several community patterns converge on a similar shape:

- **Orchestrator + shared task list.** A single coordinating agent
  decomposes the goal into a list of tasks; subagents claim,
  execute, and complete them.
- **Worktrees for isolation.** Each subagent operates in its own
  `git worktree`. File-level conflicts are detected at merge time,
  not in the middle of an edit.
- **Status flags as locks.** A task in the shared list has a
  `status: claimed-by: <agent-id>` field. Atomic writes (or
  optimistic-concurrency replay) prevent two agents from claiming
  the same task.
- **Task decomposition as the primary conflict avoidance.** Locking
  is the fallback; designing the slices so they don't overlap is
  the first move.
- **Practical limit ~4–8 concurrent worktrees per developer.**

Sources:
[MindStudio — Inside Claude Code's Shared Task List](https://www.mindstudio.ai/blog/claude-code-agent-teams-shared-task-list),
[MindStudio — Parallel Agents and Shared State](https://www.mindstudio.ai/blog/claude-code-agent-teams-parallel-shared-task-list),
[Claude Directory — Claude Code Worktrees Guide](https://www.claudedirectory.org/blog/claude-code-worktrees-guide),
[Anthropic — Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler).

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what sunaba ships
   today for parallel agent work, and where the gap is.
2. [`02-research-notes.md`](02-research-notes.md) — the 2026
   industry conventions distilled.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) —
   brief for Codex / Gemini Pro Preview.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — Gemini 3.1 Pro Preview.
5. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI (gpt-5.5,
   high reasoning).
6. [`05-proposal.md`](05-proposal.md) — synthesized proposal:
   coordination surface, locking discipline, sharding policy.

## Constraints (same as the prior proposals)

- **Templates only.** sunaba writes files; it is not a runtime daemon.
- **Cross-agent fairness.** Three agents in the sandbox. Whatever we
  ship must give Codex / Gemini equivalent or honestly mark a
  feature "Claude-only."
- **Opt-in for material change.** Anything that introduces locking
  semantics is opt-in.
- **Honest about limits.** A template cannot prevent a malicious
  agent from ignoring the protocol; this proposal is about
  cooperative coordination, not enforcement.
