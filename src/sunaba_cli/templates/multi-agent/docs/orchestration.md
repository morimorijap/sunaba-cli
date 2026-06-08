# Multi-agent orchestration

The cooperative protocol that lets multiple agent instances
(Claude Code / Codex CLI / Antigravity CLI) work on this project in
parallel without overwriting each other's edits.

> **Default is serial.** This protocol kicks in only when the
> orchestrator has decided — via [`sharding.md`](sharding.md) — that
> the task is genuinely parallelizable.

## The four invariants

1. **One source of truth.** Every coordination state lives in
   `.agents/multi-agent/tasks.yaml`. Not in agent memory, not in
   chat, not in commit messages.
2. **Declared ownership.** Every task carries an `owns:` glob
   list. No two `claimed` / `in_progress` tasks may have
   overlapping `owns:`.
3. **Atomic transitions.** Status changes go through the helper
   (`scripts/agent-task.py`). The helper takes a `flock` on
   `.agents/multi-agent/tasks.lock` before reading, mutates,
   validates against `schema.json`, and writes via `rename`.
4. **Physical isolation per shard.** Implementation runs in a
   dedicated `git worktree` (`.sunaba/worktrees/<task-id>`).
   File-system conflicts surface at merge, not mid-edit.

## End-to-end flow

```
[ Orchestrator ]
   │
   │ 1. plan + sharding decision (see sharding.md)
   │ 2. write tasks.yaml with owns:, depends_on:, status: pending
   │ 3. for each independent task, dispatch a subagent with the
   │    scoped prompt (see subagent-prompt-template.md)
   ▼
[ Subagent (in worktree) ]
   │
   │ 4. python scripts/agent-task.py claim <id> --agent <id>
   │ 5. python scripts/agent-task.py start <id>
   │ 6. edit only files matching the task's owns:
   │ 7. run the per-shard verifier (autopilot's verify.sh)
   │ 8. python scripts/agent-task.py complete <id>     # success
   │    OR fail <id> --reason ...                       # tests fail
   │    OR block <id> --reason needs_owns_expansion ... # scope creep
   ▼
[ Orchestrator (polls tasks.yaml) ]
   │
   │ 9. on completed: rebase + merge worktree branch back
   │    on failed/blocked: re-plan, narrow owns:, or escalate
```

## Helper script: cheat sheet

```sh
# Inspect
python scripts/agent-task.py list
python scripts/agent-task.py status        # human-readable summary

# Claim → start → work → finish
python scripts/agent-task.py claim T001 --agent claude-shard-1
python scripts/agent-task.py start T001
# ... edits ...
python scripts/agent-task.py complete T001

# Failure paths
python scripts/agent-task.py fail T001 --reason "tests fail in parser edge case"
python scripts/agent-task.py block T001 --reason needs_owns_expansion --files src/foo.ts

# Pre-edit ownership check (use BEFORE editing)
python scripts/agent-task.py check-owns T001 src/parser/foo.ts
# exit 0 = path is in T001's owns:; exit 2 = NOT owned, refuse to edit

# Overlap diagnostic (orchestrator uses this when planning)
python scripts/agent-task.py overlap T001 T002
# exit 0 = no overlap; exit 2 = overlap, must serialize
```

## Worktree layout

```
.sunaba/worktrees/
  T001/    # git worktree for task T001
  T002/    # git worktree for task T002
  ...
```

Setup:

```sh
git worktree add .sunaba/worktrees/T001 -b shard/T001
```

Cleanup after merge:

```sh
git worktree remove .sunaba/worktrees/T001
git branch -D shard/T001
```

## Failure modes the protocol prevents

- **Silent overwrite.** Two agents write the same file in the
  same working tree. Prevented by per-shard worktrees + `owns:`
  declaration before claim.
- **Lost claim.** Two agents both think they own task T001.
  Prevented by `flock`-protected claim transition.
- **Wasted parallelism on small tasks.** Prevented by
  `sharding.md`'s flowchart, which biases toward serial.
- **Runaway spend.** Capped by
  `SUNABA_MULTI_AGENT_MAX` (default 4) plus the autopilot
  stack's per-shard `SUNABA_AUTOPILOT_MAX_*` budgets.

## Failure modes the protocol does **not** prevent

- A misbehaving agent that ignores the protocol entirely.
  Mitigations: discipline injected into `AGENTS.md`, `git
  worktree` isolation, autopilot's branch protection, reviewer
  subagent reading `git diff` before merge.
- Semantic merge conflicts (two shards make logically
  incompatible changes that both pass their own tests).
  Mitigation: orchestrator-side sharding (don't dispatch shards
  with overlapping `owns:`).
- Stale claims when an agent crashes mid-task.
  Mitigation: the helper script's `fail` command reclaims a
  task; lock-file lingering is documented in the state
  `README.md` recovery section.
