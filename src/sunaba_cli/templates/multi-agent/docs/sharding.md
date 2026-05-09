# Sharding flowchart

The orchestrator follows this flowchart **before** writing
`tasks.yaml`. The default is serial; parallel mode is the
exception, not the rule.

## Decision tree

```
START
  │
  │── 1. Is this a one-line fix, typo, config tweak, or single
  │      failing test?
  │        YES → SERIAL, one agent.
  │        NO
  │
  │── 2. Does the task require an ordered schema / API / data-model
  │      change first?
  │        YES → SERIAL for the foundation, then re-evaluate.
  │        NO
  │
  │── 3. Can the work be divided into non-overlapping `owns:` sets?
  │        NO  → SERIAL (or reviewer-only parallelism).
  │        YES
  │
  │── 4. Are there at least 3 independent files / modules /
  │      components?
  │        NO  → SERIAL unless exploration-only.
  │        YES
  │
  │── 5. Do shards have independent verification commands or
  │      focused tests?
  │        NO  → max 2 agents (one implementer + one reviewer /
  │                test author).
  │        YES
  │
  │── 6. Is the expected work larger than the coordination
  │      overhead?
  │        Heuristic: > 30 min human work, > 5 files, OR
  │        > 2 components.
  │        NO  → SERIAL.
  │        YES
  │
  │── 7. Any shared file in `owns:` (package manifest, migration
  │      index, central router, generated client, lockfile,
  │      global config)?
  │        YES → create a prerequisite serial task for the shared
  │              edits, then re-evaluate without it.
  │        NO
  │
  │── 8. Cohort size:
  │        3-5 file groups   → 2 agents
  │        6-10 file groups  → 3 agents
  │        11+ file groups   → min(4, $SUNABA_MULTI_AGENT_MAX)
  │
END
```

## Worked examples

| Task shape | Decision | Why |
|---|---|---|
| Fix typo in `README.md` | Serial | Step 1. |
| Add a column to `users` table + update one Python model | Serial | Step 2 (data-model change). |
| Refactor frontend `app/` (50 files) | Serial — too coupled | Step 3 (shared types). |
| Frontend `app/` + Backend `api/` + tests for both | Parallel × 2 | Steps 3–6 pass; the two halves don't share files. |
| Codebase-wide rename across 60 files in 8 modules | Parallel × 4 | Step 8: 11+ file groups → min(4, cap). |
| Add 4 unrelated GitHub Actions workflow files | Parallel × 2 | Independent, > 3 files, but small (step 6 caps it at 2). |

## Why the bias toward serial

- **Coordination has overhead.** The orchestrator must write
  `tasks.yaml`, dispatch each subagent with a scoped prompt, and
  poll for completion. For small tasks, that overhead is
  measured in agent-minutes — bigger than the wallclock the
  parallelism saves.
- **Token spend multiplies.** Each subagent loads its own
  baseline context. Two parallel implementers cost roughly twice
  as much as one serial implementer for the same logical work.
- **Small tasks are tightly coupled.** The bug fix for a single
  failing test is *a* code change, not multiple. Splitting it
  invents seams that don't exist in the code.

## Why a hard cap of 4

Industry convention as of 2026 is 4–8 concurrent worktrees per
developer. Above 4, Docker resource pressure (memory / CPU) and
human review attention become the bottleneck — not the agents.
We ship 4 as the default cap; users can lift it via
`SUNABA_MULTI_AGENT_MAX` if they have evidence the bottleneck has
moved.

## Reading the helper script

When deciding shard count, run:

```sh
python scripts/agent-task.py overlap T001 T002
```

If it exits 2 (overlap), serialize them — set T002's
`depends_on: [T001]` and dispatch only T001.

```sh
python scripts/agent-task.py status
```

prints the cohort summary. Useful in the orchestrator's prompt
to confirm "how many agents are running right now."
