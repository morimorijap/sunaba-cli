# 05 — Proposal

> Synthesized from research notes and the two independent reviews
> ([`04a-gemini-review.md`](04a-gemini-review.md),
> [`04b-codex-review.md`](04b-codex-review.md)).
> Status: **draft for PR review**. Not implemented yet.

## TL;DR

We adopt a **new opt-in stack — `--stack multi-agent`** with:

1. **YAML shared task list** at `.agents/multi-agent/tasks.yaml`,
   schema-validated, the canonical coordination surface every agent
   reads before editing and writes after.
2. **Hybrid conflict resolution.** Tasks declare `owns:` paths.
   Overlapping `owns:` among in-flight tasks → orchestrator
   serializes them. No-overlap shards run in parallel `git worktree`s.
3. **Default cohort cap = 4** via `SUNABA_MULTI_AGENT_MAX=4`.
4. **`scripts/agent-task.py` helper** with `flock`-based atomic
   claim / status transitions. Cooperative atomic write primitive,
   not enforcement — agents can still bypass it, but the helper is
   *easier* to use than not, which is the right default-correct
   shape for a template generator.
5. **Sharding flowchart** documented in
   `docs/multi-agent/sharding.md` and injected into root agent files
   via the stack-aware fragment mechanism.
6. **Stack-aware fragments** under
   `templates/agents/fragments/multi-agent/{summary,tools,guidance}.md`
   so the protocol's invariants land in `AGENTS.md` / `CLAUDE.md` /
   `GEMINI.md` automatically when the stack is selected.

The recommended invocation:

```bash
sunaba new myapp \
  --stack python --stack agents \
  --stack harness --stack rules --stack autopilot \
  --stack multi-agent
```

`--stack multi-agent` recommends — but does not force — `autopilot`.
The cohort-level verify cap reuses
`SUNABA_AUTOPILOT_MAX_*` budgets when autopilot is also selected.

## Maturity score (consensus + targets)

| Axis | After PR #16 | Target with multi-agent |
|---|---:|---:|
| Coordination surface | 2 | 5 |
| File-ownership rules | 1–2 | 5 |
| Sharding policy | 1–3 | 5 |
| Conflict resolution | 1–2 | 4 |
| Cross-agent fairness | 3 | 4 |

## Where the reviewers disagreed

### Disagreement 1 — Stack topology

- **Gemini.** Fold into `autopilot`. *"Multi-agent is fundamentally
  an execution strategy for an autopilot session."*
- **Codex.** Separate `--stack multi-agent`. *"`autopilot` is
  serial-delegation safety; `multi-agent` is concurrent-actor
  coordination. Different cost / risk / operational burden.
  Existing `autopilot` users shouldn't be surprised by cohort
  semantics on upgrade."*

**Decision: separate `--stack multi-agent`.** Codex's framing
respects the project's "opt-in for material change" constraint
better. A user adopting `--stack autopilot` has signed up for the
serial Stop-hook loop; cohort semantics (multiple agents,
worktrees, claim list) are a *further* commitment. Composition is
the answer to Gemini's concern: the recommended invocation pairs
them, and the protocol cross-references the autopilot verify hook.

### Disagreement 2 — Task list format

- **Gemini.** Markdown for "cross-agent readability."
- **Codex.** YAML for "machine-readable, schema-validatable."

**Decision: YAML.** Codex wins on substance. The task list is
read+written by *agents*, not humans-as-primary-readers. YAML
parses with `tomllib`/`yaml.safe_load` cleanly; Markdown requires
regex parsing every agent has to re-derive. JSON Schema validation
catches malformed entries early. We mitigate Gemini's "humans need
to read it" concern by shipping a small `agent-task.py status`
command that prints the YAML as a readable table.

### Disagreement 3 — Atomicity primitive

- **Gemini.** Optimistic write + retry. *"2026 agents are good at
  reading before writing and resolving merge conflicts."*
- **Codex.** Helper script with `flock`. *"A cooperative atomic
  write primitive."*

**Decision: helper script (Codex), with optimistic fallback
(Gemini's intuition retained).** The helper makes the right thing
*easy* — agents call `python scripts/agent-task.py claim T001
--agent claude-1` instead of manipulating YAML by hand. When
`flock` is unavailable (some Docker / Cloud IDE environments), the
script falls back to optimistic read-modify-write with file-hash
verification, documented as the weaker path.

The proposal is **not** to enforce locks. The proposal is to make
the cooperative path the path of least resistance.

## What we add

### 1. New stack: `--stack multi-agent`

`templates/stacks/multi-agent.json`:

```json
{
  "_description": "Cooperative multi-agent orchestration: shared task list, owns:-based conflict avoidance, sharding flowchart, atomic claim helper. Recommends --stack autopilot. Templates only — coordination is cooperative, not enforced.",
  "_files": {
    ".agents/multi-agent/tasks.yaml":               "multi-agent/state/tasks.yaml",
    ".agents/multi-agent/schema.json":              "multi-agent/state/schema.json",
    ".agents/multi-agent/README.md":                "multi-agent/state/README.md",
    "scripts/agent-task.py":                        "multi-agent/scripts/agent-task.py",
    "docs/multi-agent/orchestration.md":            "multi-agent/docs/orchestration.md",
    "docs/multi-agent/sharding.md":                 "multi-agent/docs/sharding.md",
    "docs/multi-agent/subagent-prompt-template.md": "multi-agent/docs/subagent-prompt-template.md"
  }
}
```

Plus the stack-aware fragments under
`templates/agents/fragments/multi-agent/{summary,tools,guidance}.md`
which the existing PR #14 mechanism injects into root agent files.

### 2. The shared task list (YAML)

`templates/multi-agent/state/tasks.yaml`:

```yaml
version: 1
cohort:
  id: example
  max_agents_env: SUNABA_MULTI_AGENT_MAX
  default_max_agents: 4
tasks:
  - id: T001
    title: Refactor parser error handling
    status: pending
    claimed_by: null
    agent_kind: null
    owns:
      - src/parser/**
      - tests/parser/**
    depends_on: []
    branch: null
    worktree: null
    started_at: null
    updated_at: null
    failure: null
```

`templates/multi-agent/state/schema.json` is a JSON Schema (not
shown in full here) covering the field shapes and the `status`
enum (`pending` / `claimed` / `in_progress` / `blocked` / `review`
/ `completed` / `failed`).

### 3. The helper script

`templates/multi-agent/scripts/agent-task.py`:

```python
#!/usr/bin/env python3
"""Cooperative atomic claim / status helper for the sunaba multi-agent
shared task list. Uses flock when available; falls back to optimistic
read-modify-write with file-hash verification.

Usage:
    python scripts/agent-task.py list
    python scripts/agent-task.py claim T001 --agent codex-1
    python scripts/agent-task.py start  T001
    python scripts/agent-task.py complete T001
    python scripts/agent-task.py fail   T001 --reason "tests fail in parser edge case"
    python scripts/agent-task.py block  T001 --reason needs_owns_expansion --files src/foo.ts
    python scripts/agent-task.py check-owns T001 src/parser/foo.ts
    python scripts/agent-task.py overlap T001 T002
    python scripts/agent-task.py status
"""

# Implementation sketch. Real script ~150 lines.
# - argparse subcommands.
# - YAML I/O via the standard library where possible (we accept a
#   `pyyaml` requirement here because the script is opt-in and not
#   part of sunaba-cli's runtime).
# - Atomic transition: open lock file, flock LOCK_EX, read, validate
#   against schema, mutate, write to .tmp, fsync, rename.
# - On platforms without flock: fall back to compute-and-compare hash
#   of tasks.yaml; retry with backoff up to N times.
# - Exit codes: 0 success, 2 overlap, 3 stale claim, 4 schema error,
#   5 lock timeout.
```

### 4. Sharding flowchart

`templates/multi-agent/docs/sharding.md` carries the full text of
the flowchart Codex wrote, lightly tightened. Excerpt:

```text
1. One-line fix / typo / config tweak / single failing test?
       YES → SERIAL.
2. Schema / API / data-model change required first?
       YES → SERIAL for the foundation, then re-evaluate.
3. Can the work be divided into non-overlapping `owns:` sets?
       NO  → SERIAL or reviewer-only parallelism.
4. At least 3 independent files / modules / components?
       NO  → SERIAL unless exploration-only.
5. Independent verification commands or focused tests per shard?
       NO  → max 2 agents (one implementer + one reviewer / test author).
6. Expected work > coordination overhead?
       Heuristic: > 30 min human work, > 5 files, or > 2 components.
       NO  → SERIAL.
7. Any shared file in `owns:` (package manifest, migration index,
   central router, generated client, lockfile, global config)?
       YES → prerequisite serial task for the shared edits.
8. Cohort size:
       3-5 file groups   → 2 agents
       6-10 file groups  → 3 agents
       11+ file groups   → min(4, $SUNABA_MULTI_AGENT_MAX)
```

### 5. Subagent dispatch prompt template

`templates/multi-agent/docs/subagent-prompt-template.md`:

```md
You are shard implementer for task {{id}}.

Read `.agents/multi-agent/tasks.yaml`.
You may edit only:
{{owns}}

Do not broaden scope. If another file is required, stop and return:
status: blocked
reason: needs_owns_expansion
files: [...]

Before edits, claim the task:
    python scripts/agent-task.py claim {{id}} --agent {{agent_id}}

After edits, run:
    {{verify_command}}

Return:
- files changed
- tests run
- remaining risk
- whether ownership was sufficient
```

### 6. Stack-aware fragments

`templates/agents/fragments/multi-agent/summary.md` (1 line for
root indexes):

```md
- **multi-agent**: cooperative parallel orchestration via
  `.agents/multi-agent/tasks.yaml` + `owns:`-based conflict
  avoidance. See `docs/multi-agent/orchestration.md`.
```

`templates/agents/fragments/multi-agent/tools.md`:

```md
- `git worktree` — physical isolation between shards.
- `python scripts/agent-task.py` — atomic claim / status helper.
- The autopilot verifier (`SUNABA_AUTOPILOT_MAX_*` budgets) — runs
  per shard.
```

`templates/agents/fragments/multi-agent/guidance.md` (full
discipline as an excerpt embedded in `docs/agents/multi-agent.md`
and Claude skill):

```md
# Multi-agent stack

Before editing in a multi-agent context:

- Read `.agents/multi-agent/tasks.yaml`.
- Identify your task by ID.
- Do not edit files outside the current task's `owns:` list.
- If your required file overlaps another active task's `owns:`,
  stop and report `blocked_by_overlap`.
- Update task status before and after work via the helper:
  `python scripts/agent-task.py claim|start|complete|fail|block ...`.
- Use a separate `git worktree` for implementation shards when
  available (`git worktree add .sunaba/worktrees/<task-id>`).

The protocol is **cooperative, not enforced**. A misbehaving
agent can ignore it. Discipline + branch protection
(autopilot's `.githooks/pre-push`) + per-shard verifier are the
defense-in-depth.

See `docs/multi-agent/sharding.md` for when to parallelize.
```

## What sunaba's main code has to change

- **`cli.py`**: no new mechanism. The existing `_files` (PR #12)
  emits the static templates. The existing fragment composer
  (PR #14) injects guidance into root agent files. Phase 5 is
  almost entirely templates + a Python script.
- **`tests/test_multi_agent.py`**: structural tests for the new
  schema + sharding heuristic functions (test the helper script's
  pure functions in isolation).

## Tests

```python
def test_multi_agent_stack_listed():
    assert "multi-agent" in available_stacks()

def test_multi_agent_emits_expected_paths():
    files = _build_config_files("p", ["multi-agent"])
    expected = {
        ".agents/multi-agent/tasks.yaml",
        ".agents/multi-agent/schema.json",
        ".agents/multi-agent/README.md",
        "scripts/agent-task.py",
        "docs/multi-agent/orchestration.md",
        "docs/multi-agent/sharding.md",
        "docs/multi-agent/subagent-prompt-template.md",
    }
    assert expected.issubset(set(files.keys()))

def test_tasks_yaml_parses_and_matches_schema():
    files = _build_config_files("p", ["multi-agent"])
    import yaml, json, jsonschema
    data = yaml.safe_load(files[".agents/multi-agent/tasks.yaml"])
    schema = json.loads(files[".agents/multi-agent/schema.json"])
    jsonschema.validate(data, schema)

def test_default_cohort_cap_is_four():
    files = _build_config_files("p", ["multi-agent"])
    data = yaml.safe_load(files[".agents/multi-agent/tasks.yaml"])
    assert data["cohort"]["default_max_agents"] == 4

def test_sharding_one_file_bug_is_serial():
    # Pure-function test of the helper script's recommend_agents().
    from scripts_under_test import recommend_agents
    assert recommend_agents(files=1, components=1, has_schema_change=False) == 1

def test_sharding_schema_change_forces_serial_first():
    from scripts_under_test import sharding_decision
    decision = sharding_decision(files=10, components=5, has_schema_change=True)
    assert decision.first_step == "serial_foundation"

def test_overlap_detection_glob_vs_concrete():
    from scripts_under_test import has_overlap
    assert has_overlap(["src/auth/**"], ["src/auth/login.ts"])
    assert not has_overlap(["src/auth/**"], ["src/billing/index.ts"])

def test_agents_md_includes_multi_agent_summary():
    files = _build_config_files("p", ["multi-agent"])
    assert "multi-agent" in files["AGENTS.md"]
    assert "tasks.yaml" in files["AGENTS.md"]

def test_multi_agent_does_not_leak_into_devcontainer():
    files = _build_config_files("p", ["multi-agent"])
    import json
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    for k in dc:
        assert not k.startswith("_"), k

def test_multi_agent_idempotent_regeneration():
    a = _build_config_files("p", ["multi-agent"])
    b = _build_config_files("p", ["multi-agent"])
    assert a == b
```

## README + SECURITY updates

`README.md` stack table:

```diff
 | `autopilot` | ... |
+| `multi-agent` | Cooperative parallel-agent orchestration: shared YAML task list at `.agents/multi-agent/tasks.yaml`, `owns:`-based conflict avoidance, hybrid resolution (overlap → serialize), default cohort cap 4 via `SUNABA_MULTI_AGENT_MAX`, sharding flowchart in `docs/multi-agent/sharding.md`, lock-protected helper script (`scripts/agent-task.py`). Templates only — coordination is cooperative, not enforced. **Recommended together with `--stack autopilot`** (per-shard verifier + branch protection). |
```

`SECURITY.md` — append to the existing Autonomy section:

```diff
+## Multi-agent
+
+`--stack multi-agent` ships a **cooperative** orchestration
+protocol — a shared YAML task list, an `owns:`-based ownership
+convention, and a `flock`-protected helper script for atomic
+claims. It does **not** enforce ownership; an agent that ignores
+the protocol can still overwrite another agent's work. The
+defense-in-depth is:
+
+1. The discipline injected into `AGENTS.md` / `CLAUDE.md` /
+   `GEMINI.md` (via stack-aware fragments).
+2. Physical isolation via `git worktree` per shard.
+3. The autopilot stack's branch protection (`.githooks/pre-push`)
+   and per-shard verifier with budget caps.
+4. A reviewer subagent (the autopilot stack's
+   `.claude/agents/reviewer.md`) reading `git diff` before merge.
+
+Multi-agent **multiplies token spend** by the cohort size. The
+cohort cap (`SUNABA_MULTI_AGENT_MAX`, default 4) is the primary
+guard against runaway cost.
```

## What we explicitly do **not** do in this PR

- **Don't fold into `autopilot`.** Different opt-in boundary.
- **Don't ship a runtime daemon / scheduler.** Helper script + YAML
  + git worktree only. Cooperative coordination, not enforcement.
- **Don't rely on Markdown for the task list.** YAML +
  schema-validation is the right tool for an agent-readable
  ledger.
- **Don't default to parallel.** The orchestrator's first move
  is the sharding flowchart, which biases toward serial.
- **Don't enforce `owns:` via pre-commit hooks.** Too brittle;
  too easy for legitimate edits to slip past. The discipline lives
  in the protocol; reviewer subagent + git merge are the
  enforcement layers.
- **Don't ship cross-agent runtime IPC.** The agents communicate
  through the file system (`tasks.yaml`). No message bus, no
  daemon, no socket.

## Rebuild consistency

Same orphan-reporting machinery as the prior four proposals.
Specifically for `--remove multi-agent`:

- Orphan paths: `.agents/multi-agent/`, `scripts/agent-task.py`,
  `docs/multi-agent/`.
- The orphan report prompts the user to delete manually. The
  shared task list may carry in-flight work — automatic deletion
  would lose state.
- Stack-aware fragments stop injecting; the next
  `sunaba sync` (in stack-aware mode) regenerates root agent files
  without the multi-agent summary line.

## Implementation order (revised)

This is the fifth and final stack in the current series. Lands
after PR #16. Soft dependencies on:

1. PR #12 (`_files` mechanism) — required.
2. PR #14 (stack-aware fragments) — required for
   `templates/agents/fragments/multi-agent/`.
3. PR #16 (autopilot) — recommended, not required. The
   multi-agent stack works without autopilot; users just lose the
   per-shard verifier and branch protection.

## Sources

- [MindStudio — Inside Claude Code's Shared Task List](https://www.mindstudio.ai/blog/claude-code-agent-teams-shared-task-list)
- [MindStudio — Parallel Agents and Shared State](https://www.mindstudio.ai/blog/claude-code-agent-teams-parallel-shared-task-list)
- [Claude Directory — Worktrees Guide](https://www.claudedirectory.org/blog/claude-code-worktrees-guide)
- [Anthropic Engineering — Building a C compiler with parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- [Claude Code — Agent Teams docs](https://code.claude.com/docs/en/agent-teams)
- [Claude Code — tutorials (worktrees)](https://code.claude.com/docs/en/tutorials)
- [git-worktree(1)](https://git-scm.com/docs/git-worktree.html)
- [OpenAI — Codex app](https://openai.com/index/introducing-the-codex-app/)
- [Gemini CLI subagents](https://github.com/google-gemini/gemini-cli/blob/main/docs/core/subagents.md)
- Prior internal proposals:
  [`2026-05-09-harness-engineering`](../2026-05-09-harness-engineering/),
  [`2026-05-09-stack-aware-agent-files`](../2026-05-09-stack-aware-agent-files/),
  [`2026-05-09-secrets-management`](../2026-05-09-secrets-management/),
  [`2026-05-09-rules-and-autonomy`](../2026-05-09-rules-and-autonomy/).
