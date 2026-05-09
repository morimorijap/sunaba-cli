# 04a — Reviewer notes: Gemini 3.1 Pro Preview

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gemini-3.1-pro-preview` (Google Gemini CLI MCP).
> Date: 2026-05-09.
>
> Lightly reformatted. Substance unchanged.

## Headline position

> **Fold into `autopilot`.** Don't introduce a separate
> `--stack multi-agent`.
> **Hybrid conflict resolution** (optimistic + advisory `owns:`
> with serialization for overlap).
> **Default cohort cap = 4** via
> `SUNABA_AUTOPILOT_MAX_CONCURRENCY=4`.
> **Markdown task list** at `claudedocs/plans/<slug>-tasks.md`.

## A. Maturity scoring

- **Coordination surface — 2/5.** Plans / checkpoints exist; no
  shared ledger or per-task status.
- **File-ownership rules — 1/5.** No mechanism to claim a file.
- **Sharding policy — 1/5.** dispatch protocol explains *when* to
  use a planner; nothing about sizing or parallelizing.
- **Conflict resolution — 1/5.** Missing entirely.
- **Cross-agent fairness — 3/5.** Claude / Codex have role files;
  Gemini stays manual.

## B. Concrete additions

### Stack topology — fold into `autopilot`

> *"Multi-agent parallelism is fundamentally an execution strategy
> for an autopilot session. It strictly depends on the deterministic
> verify hook (`SUNABA_BUDGET_EXCEEDED` / `SUNABA_VERIFY_FAILED`).
> Creating a separate `--stack multi-agent` introduces unnecessary
> matrix complexity."*

### Conflict resolution — hybrid

> *"Templates cannot reliably enforce filesystem locks (`flock`)
> across disparate agent environments (Docker vs macOS vs Cloud
> IDE). The 2026 industry consensus is correct: rely on agents
> declaring intent (`owns: [paths]`) in a shared task list. If two
> tasks declare overlapping paths, the orchestrator serializes
> them. If they don't, they run in parallel `git worktree`s. Git
> handles the final merge."*

### Cohort cap — 4, gated by `SUNABA_AUTOPILOT_MAX_CONCURRENCY`

> *"Above 4, you risk Docker resource starvation and context
> exhaustion for the orchestrator managing the fan-out."*

### MUST

- **`claudedocs/plans/<slug>-tasks.md`** — the shared task list.
  Markdown for cross-agent readability.
- **Update `subagent-dispatch.md`** with the sharding flowchart
  and parallel-mode protocol.

### SHOULD

- **`templates/autopilot/scripts/init-worktrees.sh`** — automates
  `git worktree add .sunaba/worktrees/shard-1`, reduces orchestrator
  hallucination on setup.

### COULD

- A small Python helper (`sunaba-task-sync`) for safe append/update
  with optimistic concurrency (modification-time check before write).

## C. Coordination surface

Format: Markdown file at `claudedocs/plans/<YYYY-MM-DD>-<slug>-tasks.md`.

```md
# Task List: <slug>

## Orchestrator State
- Concurrency Cap: 4
- Active Shards: 2

## Tasks

### [Task ID: 01] Database Schema Update
- **Status:** `done`
- **Claimed-By:** `claude-shard-1`
- **Owns:** `src/db/schema.py`, `src/db/migrations/`
- **Dependencies:** None

### [Task ID: 02] Update User API endpoints
- **Status:** `in-progress`
- **Claimed-By:** `claude-shard-2`
- **Owns:** `src/api/users.py`, `tests/api/test_users.py`
- **Dependencies:** `[Task ID: 01]`
```

Atomicity: **optimistic write + retry**. *"2026 agents are
generally good at reading before writing and resolving merge
conflicts if they stomp on a markdown file."*

Dispatch flow:

1. Orchestrator writes task list, including `Owns:` for each task.
2. Orchestrator spawns subagent in `worktree-1` with scoped
   prompt: *"You are an implementer. Execute Task 02 from
   `<slug>-tasks.md`. Your worktree is
   `.sunaba/worktrees/shard-1`. Update task status when done."*
3. Subagent runs. On `SUNABA_BUDGET_EXCEEDED` or verify failure,
   updates status to `failed` and writes
   `claudedocs/checkpoints/<slug>-task-02-checkpoint.md`.
4. Orchestrator polls task list. Decides serialize / re-prompt /
   halt.

## D. Sharding flowchart

```text
[ START: Evaluate Planned Changes ]
       |
       v
1. Are there schema, core API, or shared type changes?
   ├─ YES ──> [ SERIAL MODE ] Run foundational changes FIRST.
   |          Don't parallelize until schema is verified and merged.
   └─ NO ───> Continue to #2.
       |
       v
2. Does the plan touch only 1 file, or 2-4 files in a single
   tightly coupled module?
   ├─ YES ──> [ SERIAL MODE ] Sharding overhead exceeds benefits.
   └─ NO ───> Continue to #3.
       |
       v
3. Are the changes naturally separable? (Frontend vs Backend,
   Feature A vs Feature B)
   ├─ NO ───> [ SERIAL MODE ] High merge / collision risk.
   └─ YES ──> [ PARALLEL MODE ]
              - Decompose into discrete Tasks.
              - Assign `Owns:` paths.
              - Ensure NO OVERLAP across active tasks.
              - Spawn up to $SUNABA_AUTOPILOT_MAX_CONCURRENCY worktrees.
```

## E. Conflict resolution — hybrid (optimistic + advisory)

Why not pessimistic locks: *"Pessimistic file locks (e.g.
`flock` or `.lock` files per source file) cause agents to deadlock
frequently. They forget to release the lock, or a budget crash
leaves a stale lock behind, halting the entire pipeline until a
human intervenes."*

How it works:

1. Orchestrator declares `Owns: [paths/or/globs]` per task.
2. If Task A's owns intersect Task B's, B's `Dependencies:`
   include A. **Never dispatch overlapping tasks in parallel.**
3. Subagents work in isolated `git worktree`s.
4. **Git is the ultimate pessimistic lock.** If the orchestrator
   slips up, merge conflicts surface at integration; the
   orchestrator resolves or halts for a human.

## F. Cross-agent matrix

| Capability | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| Orchestrator | Yes — excellent at markdown ledgers + native agent tool | Yes — non-interactive `codex exec` | **No** — lacks native autonomous spawn |
| Subagent | Yes — runs in worktree, follows scoped prompts | Yes | Yes — pointed at a worktree by a human / external script |
| Observe / write task list | Trivial | Trivial | Trivial |
| Honest gap | Currently the only platform that natively maintains the orchestrator loop without external bash | Requires custom scaffolding for fan-out | Relies on **human orchestration** for parallel fan-out |

## G. Tests

```python
def test_task_list_schema_parses():
    # Parse a mock <slug>-tasks.md, extract Task ID / Status /
    # Claimed-By / Owns via regex.

def test_sharding_flowchart_heuristics():
    # Input: ['src/db.py']                 → Serial
    # Input: ['src/frontend/app.tsx',
    #         'src/backend/main.py']        → Parallel(2)
    # Input: ['src/types/shared.ts',
    #         'src/frontend/app.tsx']       → Serial (shared schema)

def test_overlap_detection():
    # `Owns: src/api/*` overlaps with `Owns: src/api/users.py`.
```

## H. Top-3 picks

1. **Shared task list convention** (`claudedocs/plans/<slug>-tasks.md`).
2. **Sharding flowchart** in `subagent-dispatch.md`.
3. **`Owns:` field discipline** — orchestrator declares ownership
   per task, prevents 90% of parallel collisions before a subagent
   spawns.

## I. Push-back

- **Don't ship pre-commit / runtime enforcement** of the
  `Owns:` list. *"Too brittle and violates the 'templates only'
  constraint. Rely on agent prompt adherence + physical isolation
  via `git worktree`."*
- **Don't default to parallel.** *"Massive context-window token
  waste (every subagent loads baseline context) and slow down
  simple changes via orchestration overhead."*
