# 02 — Research notes

Compact reference. Sources at the end of each section.

## Claude Code Agent Teams (May 2026)

The dominant 2026 pattern in this space:

- **Orchestrator + shared task list.** A single coordinator agent
  decomposes the goal into a list of discrete tasks. The list lives
  in a project-local file readable + writable by every subagent.
- **Status flags as locks.** Each task carries a `status:` field
  (`pending` / `claimed-by:<id>` / `in-progress` / `done` /
  `failed` / `blocked`). Atomic file writes (or optimistic
  concurrency with retry) prevent two subagents from claiming the
  same task simultaneously.
- **Task decomposition as primary conflict avoidance.** The
  orchestrator tries to slice the work so subagents don't share
  files. Locking is the fallback when overlap is unavoidable.
- **Worktrees for isolation.** Each subagent gets its own `git
  worktree` directory. File-level conflicts surface at merge time,
  not mid-edit. This is the same pattern the four sunaba
  implementation PRs used internally.

Source:
[MindStudio — Inside Claude Code's Shared Task List](https://www.mindstudio.ai/blog/claude-code-agent-teams-shared-task-list),
[MindStudio — Parallel Agents and Shared State](https://www.mindstudio.ai/blog/claude-code-agent-teams-parallel-shared-task-list),
[Claude Directory — Worktrees Guide](https://www.claudedirectory.org/blog/claude-code-worktrees-guide).

## Practical concurrency limits

> "As of mid-2026, teams are running 4–8 concurrent worktrees per
> developer reliably."

Above ~8 concurrent worktrees, Docker resource pressure, IDE
indexing churn, and human attention all become the bottleneck —
not the agents themselves. The right *default* concurrency for
sunaba is 1 (serial autopilot). The right *cap* for opt-in
parallel mode is in the 4–8 range.

## Anthropic — *Building a C compiler with a team of parallel Claudes*

Operational lessons from a real parallel run:

- Each subagent gets a **scoped prompt** that names its slice
  precisely. Loose prompts produce overlapping work.
- **Coordinator costs scale linearly** with the number of
  subagents. The coordinator stays cheap because its prompt is
  short — task list summary plus the next dispatch.
- **Verification must run per-shard.** Merging passes only if every
  shard's verifier passes.
- **Failure isolation matters.** A failing shard should not cascade
  to halt the others; it should fail in place and the coordinator
  should decide whether to retry, reassign, or split further.

Source:
[Anthropic Engineering — Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler).

## Workload sharding heuristics

Combining Anthropic's lessons with HumanLayer's harness writeup,
the dominant heuristics for "should I parallelize?":

| Signal | Recommended action |
|---|---|
| Single file | **Don't parallelize.** Run serial. |
| 2–4 files, all in one module | Run serial. The orchestrator's overhead exceeds the wallclock saving. |
| 5+ files, naturally separable (e.g. `src/`, `tests/`, `docs/`) | Parallelize 2–3 ways. |
| Refactor touching many files non-trivially | Parallelize 2–4 ways with explicit per-shard scope. Add file-claim discipline. |
| Codebase-wide rename / API change | Parallelize 4–8 ways. Worktrees + claim list mandatory. |

Independent variables:

- Are the files **naturally separable** (different layers /
  modules)? If yes, sharding is cheap.
- Does each shard **need to read** the same context (e.g. shared
  type definitions)? If yes, fan-out is fine but each shard pays
  the read cost.
- Are there **schema changes** any shard must agree on? If yes,
  produce the schema first (serial), then fan out.

## File-ownership patterns surveyed

Three options for "may I edit this file?":

### A. Optimistic claim + late conflict

Each subagent writes a claim entry to the shared task list on
start, edits in its worktree, and resolves conflicts at merge time
via standard git. **Lowest overhead, highest tolerance for
mistakes.**

### B. Pessimistic per-file lock

Each subagent acquires a named lock (filesystem `flock`,
filesystem-backed claim file, etc.) before editing. **Highest
discipline, hardest to bypass when an agent ignores it.**

### C. Hybrid: optimistic by default + advisory lock entries

Default to optimistic. The shared task list carries an `owns:
[paths]` field that subagents read before claiming new tasks. If
two tasks declare overlapping `owns:`, the orchestrator serializes
them. **Industry consensus in 2026.**

## Cross-agent considerations

| Capability | Claude Code 2.0 | Codex CLI | Gemini CLI |
|---|---|---|---|
| Native subagent spawn | Native (Agent tool) | Native (`codex exec` non-interactive) | Not native |
| Reads shared task list | Trivial (file in repo) | Trivial | Trivial |
| Writes to shared task list with optimistic concurrency | Possible (file write) | Possible | Possible |
| Operates in a worktree | Yes | Yes | Yes |
| Auto re-engage on Stop hook failure | Yes (autopilot PR) | Yes | No |

Implication: parallel mode is reachable for Claude and Codex with
the same template. Gemini gets a manual variant — the user runs
multiple `gemini` terminals against multiple worktrees by hand.

## What converges across sources

If you strip the marketing, the 2026 consensus is:

1. **Shared task list is the coordination primitive.** Not a
   message bus, not direct agent-to-agent communication. A file.
2. **Worktrees are the file-isolation primitive.** Conflicts
   surface at git merge, not at edit time.
3. **Decomposition is the conflict-avoidance primitive.**
   Locking is the fallback.
4. **Default to serial, opt into parallel.** Parallelism multiplies
   spend; small tasks don't earn it.
5. **Caps apply to the cohort.** Per-shard budget caps are useful
   but the cohort cap is what saves you from runaway spend.
