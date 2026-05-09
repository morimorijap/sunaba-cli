# 04b — Reviewer notes: OpenAI Codex CLI (gpt-5.5, high reasoning)

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gpt-5.5` via `codex exec --model gpt-5.5 -c model_reasoning_effort=high`.
> Date: 2026-05-09.
>
> Translated from bilingual original; substance unchanged.

## Headline position

> **Separate stack — `--stack multi-agent`**, distinct from
> `autopilot` but recommending it. Different opt-in boundary,
> different blast radius.
> **Hybrid conflict resolution** (optimistic + `owns:` with
> serialization for overlap). Pessimistic locks too heavy for a
> template generator; full-optimistic doesn't prevent silent
> overwrites.
> **Default cohort cap = 4** via `SUNABA_MULTI_AGENT_MAX=4`.
> **YAML task list** + JSON Schema validation.
> **Helper script with `flock`** for atomic claim / status
> transitions.

## Why a separate stack

> *"`autopilot` is the layer that makes serial delegation safe
> within a single session. `multi-agent` is the layer that handles
> simultaneous work by multiple actors. They share the verify hook
> and role files, but the user-facing cost, conflict risk, and
> operational burden are different. So `multi-agent` should
> recommend / require autopilot but not be folded in — existing
> autopilot users shouldn't be surprised by cohort semantics."*

Sources cited:
[Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams),
[Claude Code worktrees](https://code.claude.com/docs/en/tutorials),
[Anthropic — Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler),
[git-worktree docs](https://git-scm.com/docs/git-worktree.html),
[OpenAI Codex app](https://openai.com/index/introducing-the-codex-app/),
[Gemini CLI subagents](https://github.com/google-gemini/gemini-cli/blob/main/docs/core/subagents.md).

## A. Maturity scoring

| Axis | After PR #16 | Target with `multi-agent` |
|---|---:|---:|
| Coordination surface | 2 | 5 |
| File-ownership rules | 2 | 5 |
| Sharding policy | 3 | 5 |
| Conflict resolution | 2 | 4 |
| Cross-agent fairness | 3 | 4 |

> *"Current posture is strong for serial subagent delegation but
> weak for concurrent writers. The missing primitive is not 'more
> agent roles'; it is a shared, parseable coordination surface
> that every agent can consult before editing."*

## B. Concrete additions

### MUST

1. **`templates/agents/fragments/multi-agent/{summary,tools,guidance}.md`**
   — uses the stack-aware composition mechanism (PR #14) to inject
   the protocol into root `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`.
   Example guidance content:

   ```md
   Before editing, read `.agents/multi-agent/tasks.yaml`.
   Do not edit files outside the current task's `owns:` list.
   If your required file overlaps another active task's `owns:`,
   stop and report `blocked_by_overlap`.
   Update task status before and after work.
   Use a separate git worktree for implementation shards when
   available.
   ```

2. **`templates/multi-agent/.agents/multi-agent/tasks.yaml`** — the
   shared task ledger:

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
       failure: null
   ```

3. **`templates/multi-agent/docs/multi-agent-orchestration.md`** —
   public protocol doc (when to parallelize, ownership rules,
   conflict handling, failure return format).

4. **`templates/multi-agent/scripts/agent-task.py`** — small
   helper for cooperative atomic writes:

   ```bash
   python scripts/agent-task.py claim T001 --agent codex-1
   python scripts/agent-task.py complete T001
   python scripts/agent-task.py fail T001 --reason "tests fail in parser edge case"
   python scripts/agent-task.py check-owns T001 src/parser/foo.ts
   ```

   > *"This is not a daemon. It is a generated helper script. It
   > gives templates a cooperative atomic write primitive."*

### SHOULD

- **`docs/sharding-flowchart.md`** — standalone flowchart used by
  orchestrators.
- **`docs/subagent-prompt-template.md`** — scoped prompt template
  for one shard at a time.
- **`.agents/multi-agent/README.md`** — manual editing,
  recovery, stale claims, worktree cleanup.
- README stack-section update — *"requires autopilot verifier"*.

### COULD

- **`schema.json`** — JSON Schema for `tasks.yaml` validation.
- **`scripts/agent-shard-plan.py`** — heuristic checker that
  suggests `serial`, `2`, `3`, or `4` shards based on declared
  file groups.
- Agent-specific role files
  (`.claude/agents/multi-agent-implementer.md` etc.).

## C. Coordination surface

```text
.agents/multi-agent/tasks.yaml
.agents/multi-agent/tasks.lock
```

Schema fields:

```yaml
id: string
title: string
status: pending | claimed | in_progress | blocked | review | completed | failed
claimed_by: string | null
agent_kind: claude | codex | gemini | human | null
owns: string[]
depends_on: string[]
branch: string | null
worktree: string | null
started_at: string | null
updated_at: string | null
failure:
  kind: overlap | test_failure | dependency_missing | unclear_scope | other
  detail: string
  next_action: string
```

Atomicity via `flock`:

```text
open .agents/multi-agent/tasks.lock
flock exclusive
read tasks.yaml
validate schema
apply transition
write tasks.yaml.tmp
fsync
rename tasks.yaml.tmp -> tasks.yaml
release lock
```

Fallback if `flock` is unavailable: optimistic read-modify-write
with file-hash check and retry. Document this as weaker.

Dispatch prompt template:

```md
You are shard implementer for task {{id}}.

Read `.agents/multi-agent/tasks.yaml`.
You may edit only:
{{owns}}

Do not broaden scope. If another file is required, stop and return:
status: blocked
reason: needs_owns_expansion
files: [...]

Before edits, claim the task. After edits, run:
{{verify_command}}

Return:
- files changed
- tests run
- remaining risk
- whether ownership was sufficient
```

## D. Sharding flowchart

```text
START
 |
 |-- Is the task a one-line fix, typo, config tweak, or single
 |   failing test?
 |      YES -> SERIAL, one agent.
 |      NO
 |
 |-- Does the task require an ordered schema/API/data-model
 |   change first?
 |      YES -> SERIAL for schema/API foundation, then re-evaluate.
 |      NO
 |
 |-- Can the work be divided into non-overlapping file ownership
 |   sets?
 |      NO -> SERIAL or reviewer-only parallelism.
 |      YES
 |
 |-- Are there at least 3 independent files / modules / components?
 |      NO -> SERIAL unless exploration-only.
 |      YES
 |
 |-- Do shards have independent verification commands or focused
 |   tests?
 |      NO -> max 2 agents (one implementer + one reviewer / test
 |              author).
 |      YES
 |
 |-- Is expected work larger than coordination overhead?
 |      Heuristic: >30 min human work, >5 files, or >2 components.
 |      NO -> SERIAL.
 |      YES
 |
 |-- Any shared files in `owns:` (package manifest, migration index,
 |   central router, generated client, lockfile, global config)?
 |      YES -> create a prerequisite serial task for shared edits.
 |      NO
 |
 |-- Cohort size:
 |      3-5 file groups   -> 2 agents
 |      6-10 file groups  -> 3 agents
 |      11+ file groups   -> min(4, SUNABA_MULTI_AGENT_MAX)
 |
END
```

> *"This reflects the Anthropic C compiler lesson: parallelism
> worked when failures could be split into independent tests /
> files; it failed when all agents hit the same giant task and
> overwrote each other."*

## E. Conflict resolution — hybrid

Rules:

1. Every task **must** declare `owns:` before implementation.
2. Overlapping `owns:` among `claimed` / `in_progress` tasks is
   **prohibited** unless the overlap is read-only.
3. If overlap appears: coordinator pauses the later task, marks
   it `blocked`, narrows `owns:` or creates a serial prerequisite,
   reruns the sharding decision.
4. If two completed branches touch the same file: merge earlier
   first, rebase later, assign a resolver task with `owns:`
   limited to conflicting files, verifier runs after resolution.

> *"Worktrees reduce simultaneous filesystem overwrite risk, but
> they do not solve semantic merge conflict. Git worktrees are
> still the right isolation primitive because Git officially
> supports multiple working trees."*

## F. Cross-agent matrix

| Agent | Orchestrator | Subagent | Shared list access | Honest gap |
|---|---|---|---|---|
| Claude Code | Yes | Yes | Reads / writes `tasks.yaml`; native Agent Teams have task list concepts | Native Agent Teams state lives under Claude-managed paths; sunaba shouldn't pretend to control that runtime state |
| Codex CLI | Yes | Yes | Reads / writes repo files; can follow `AGENTS.md`; Codex app supports parallel worktrees | Cross-agent task locking is template-level, not a Codex-native shared scheduler |
| Gemini CLI | **Partial** | Yes | Reads / writes repo files; `.gemini/agents/*.md` for custom subagents | Gemini subagents are good for isolated delegation, but cross-process mixed-agent orchestration remains cooperative |

> *"All three can participate in the repo-level protocol because
> it is just files plus Git. Claude may have the richest native
> team UX; Codex has strong parallel/worktree surfaces; Gemini
> can participate honestly as a subagent and limited orchestrator
> through the file protocol."*

## G. Tests

```python
def test_multi_agent_generates_tasks_yaml():
    assert ".agents/multi-agent/tasks.yaml" in generated_files

def test_tasks_yaml_schema_parses():
    data = yaml.safe_load(tasks_yaml)
    validate(data, schema)

def test_overlapping_owns_blocks_claim():
    active    = task("T1", status="in_progress", owns=["src/auth/**"])
    candidate = task("T2", owns=["src/auth/login.ts"])
    assert has_overlap(active, candidate)

def test_sharding_one_file_bug_is_serial():
    assert recommend_agents(files=1, components=1, has_schema_change=False) == 1

def test_schema_change_forces_serial_first():
    assert decision(...).first_step == "serial_foundation"

def test_default_cap_is_four():
    assert default_multi_agent_cap() == 4
```

## H. Top-3 picks

1. **`.agents/multi-agent/tasks.yaml` + schema** — shared source
   of truth.
2. **`docs/sharding-flowchart.md`** injected into agent files —
   prevents wasteful parallelism and under-sharding.
3. **`scripts/agent-task.py`** with lock-protected
   claim / update / check-owns — turns the protocol from prose
   into a repeatable cooperative workflow.

## I. Push-back

- **Don't rely on Git alone.** *"Git catches conflicts late; the
  user's stated catastrophic failure is simultaneous same-file
  editing or silent overwrite. Git worktrees help with filesystem
  isolation, but without declared ownership agents still produce
  competing edits that waste review time."*
- **Don't default to parallel.** *"Claude's own docs frame Agent
  Teams as higher-overhead and better for independent work, not
  sequential or same-file tasks. The default should remain serial;
  multi-agent should be opt-in and the orchestrator should still
  choose serial for small or tightly coupled work."*
- **Don't overbuild locking.** *"A template generator should not
  ship a scheduler daemon. A lock-protected helper script plus
  clear `owns:` protocol is the right size: enforceable enough for
  cooperative agents, honest about limits, and portable across
  Claude, Codex, and Gemini."*
