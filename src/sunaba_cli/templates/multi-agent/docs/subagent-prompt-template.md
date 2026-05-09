# Subagent dispatch prompt template

When the orchestrator decides to parallelize, it dispatches each
shard with a *scoped* prompt — the subagent must not look beyond
its own task. Use this template verbatim or adapt the bracketed
fields.

## Template

```md
You are shard implementer for task {{id}}.

Read `.agents/multi-agent/tasks.yaml` first.

You may edit ONLY files matching:
{{owns_block}}

Do not broaden scope. If you find that another file is required:

  STOP. Do not edit it. Run:
    python scripts/agent-task.py block {{id}} \
      --reason needs_owns_expansion \
      --files <file-1> <file-2> ...
  Then return to the orchestrator with status `blocked`.

## Workflow

1. Claim:
     python scripts/agent-task.py claim {{id}} --agent {{agent_id}}
2. Start:
     python scripts/agent-task.py start {{id}}
3. Before each edit, verify ownership:
     python scripts/agent-task.py check-owns {{id}} <file>
4. Edit. Stay inside `owns:`.
5. Run the verifier (which records SUNABA_VERIFY_FAILED /
   SUNABA_BUDGET_EXCEEDED on stderr):
     {{verify_command}}
6. On verifier exit 0:
     python scripts/agent-task.py complete {{id}}
   On verifier exit 2 (failure with budget remaining):
     # the autopilot loop re-engages you with the failure log;
     # fix the failing checks and re-run step 5.
   On verifier exit 1 (budget exceeded):
     python scripts/agent-task.py fail {{id}} \
       --reason "budget exceeded; see .sunaba/autopilot/last-failure.log"

## Return format

Return ONLY:
- task id and final status
- files changed (paths)
- tests run (commands)
- remaining risk (one sentence) or `none`
- whether the declared `owns:` was sufficient (`yes` / `no — needs <paths>`)

Do not summarize the implementation in prose. The orchestrator
reads the diff itself.
```

## Field reference

| Field | Source |
|---|---|
| `{{id}}` | Task ID from `tasks.yaml` (e.g. `T001`). |
| `{{owns_block}}` | The task's `owns:` array, rendered one entry per line as ``- `pattern` ``. |
| `{{agent_id}}` | A unique agent identifier. Convention: `<kind>-<task-id>` (e.g. `claude-T001`, `codex-T002`). |
| `{{verify_command}}` | The autopilot stack's `bash .claude/hooks/verify.sh` (or `.codex/hooks/verify.sh` for Codex shards). |

## What the orchestrator does NOT include

- A summary of the overall plan. The subagent doesn't need it
  and including it bloats per-shard token cost. The shard's
  scope is its `owns:` and its acceptance test.
- Read access to other shards' work. Each subagent operates in
  its own `git worktree` and sees only its branch.
- The full task list. The subagent reads `tasks.yaml` itself
  via the helper; the orchestrator doesn't paste it into the
  prompt.
