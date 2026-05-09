# `.agents/multi-agent/`

Coordination state for the cooperative multi-agent protocol.

## Files

- **`tasks.yaml`** — the shared task list. Every agent reads this
  *before* editing and writes back via the helper script. The
  schema is in `schema.json`.
- **`schema.json`** — JSON Schema describing `tasks.yaml`. Used by
  the helper script to validate every transition.
- **`tasks.lock`** — created on demand by the helper script for
  `flock`-based atomic transitions. Safe to delete when no agent
  is mid-claim. Never commit.

## Convention

| Field        | Meaning |
|---|---|
| `id`         | `T###` task identifier (sortable). |
| `status`     | `pending` → `claimed` → `in_progress` → `review` → `completed`. Side-states: `blocked`, `failed`. |
| `claimed_by` | Free-form agent ID (e.g. `claude-shard-1`). |
| `agent_kind` | `claude` / `codex` / `gemini` / `human`. |
| `owns`       | Glob patterns for files this task may edit. **No two in-flight tasks may have overlapping `owns`.** |
| `depends_on` | List of task IDs that must complete first. |
| `branch`     | Optional feature branch the shard works on. |
| `worktree`   | Optional `git worktree` path the shard uses. |
| `failure`    | Object describing why a task is `failed` or `blocked`. |

## Recovery

- **Stale claim** (a `claimed` / `in_progress` task whose agent
  crashed): use
  `python scripts/agent-task.py fail <id> --reason "stale claim"`
  and re-plan.
- **Lock file lingering**: if no agent is currently writing,
  `rm .agents/multi-agent/tasks.lock` is safe.
- **Schema drift**: edit `tasks.yaml` by hand and re-run any helper
  command — it validates against `schema.json` and refuses
  malformed input.

## Honest limit

This is **cooperative** coordination. The helper script makes the
right thing easy, but nothing prevents a misbehaving agent from
editing files outside its `owns:` list. The defense-in-depth is
the discipline injected into `AGENTS.md` / `CLAUDE.md` /
`GEMINI.md`, the per-shard `git worktree`, the autopilot stack's
verifier and branch protection, and a reviewer subagent reading
`git diff` before merge.
