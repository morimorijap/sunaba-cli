# Multi-agent stack

Before editing in a multi-agent context:

- Read `.agents/multi-agent/tasks.yaml`. Identify your task ID.
- Do **not** edit files outside the current task's `owns:` list.
  Use `python scripts/agent-task.py check-owns <id> <file>` to
  confirm; exit 0 means owned, exit 2 means refuse to edit.
- If your required file overlaps another active task's `owns:`,
  stop and run
  `python scripts/agent-task.py block <id> --reason needs_owns_expansion --files <paths>`.
- Update task status before and after work via the helper:
  `claim` / `start` / `complete` / `fail` / `block`.
- When possible, use a separate `git worktree` for implementation
  shards: `git worktree add .sunaba/worktrees/<task-id>`.

The protocol is **cooperative, not enforced**. A misbehaving agent
can ignore it. Defense-in-depth:

- Discipline injected into `AGENTS.md` / `CLAUDE.md`
  (this guidance plus the `summary.md` line in the
  "Selected stacks" section).
- Physical isolation via `git worktree` per shard.
- The autopilot stack's branch protection (`.githooks/pre-push`)
  and per-shard verifier with budget caps.
- A reviewer subagent reading `git diff` before merge.

See [`docs/multi-agent/sharding.md`](../../../../docs/multi-agent/sharding.md)
for when to parallelize. Default is serial; parallel mode is the
exception.

## Sharding decision summary

The orchestrator runs the flowchart from `sharding.md` before
writing `tasks.yaml`. Cohort cap is `SUNABA_MULTI_AGENT_MAX`
(default 4). One-line fixes, schema changes, and tightly coupled
modules stay serial. Naturally separable work with > 5 files
across > 2 components shards 2–4 ways.

## Cooperative claim cycle (cheat sheet)

```sh
# 1. Confirm before editing
python scripts/agent-task.py check-owns T001 src/parser/foo.py

# 2. Claim and start
python scripts/agent-task.py claim T001 --agent claude-T001 --kind claude
python scripts/agent-task.py start T001

# 3. Edit (only files matching T001's owns:)
# 4. Run the per-shard verifier
bash .claude/hooks/verify.sh

# 5. Complete (or fail / block)
python scripts/agent-task.py complete T001
```
