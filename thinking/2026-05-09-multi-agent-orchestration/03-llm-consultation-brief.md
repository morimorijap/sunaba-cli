# 03 — LLM consultation brief (multi-agent orchestration)

> Self-contained brief for external reviewers (Codex CLI gpt-5.5,
> Gemini Pro Preview). They have **not** seen the conversation.

---

## You are reviewing

A small open-source CLI called **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>). Template generator for
disposable devcontainer sandboxes pre-wired for three coding agents
(Claude Code, OpenAI Codex CLI, Google Gemini CLI). It is a TEMPLATE
GENERATOR — it writes files, not runtime tooling.

Four feature stacks have already shipped (PRs #12, #14, #15, #16):

- `harness` — `.claude/settings.json` + Stop hook + planner / reviewer
  / verifier role files + ratchet `AGENTS.md` + `claudedocs/`.
- `stack-aware-agent-files` — per-stack composition of `AGENTS.md` /
  `CLAUDE.md` / `GEMINI.md` / `skills.md` from `templates/agents/
  fragments/<stack>/{summary,tools,guidance}.md`. Delimiter
  injection + USER-region preservation across `sunaba sync`.
- `secrets` — expanded `.gitignore` baseline + gitleaks pre-commit
  + per-cloud docs + `sync-gitignore` subcommand + Foundry → APIM
  → Gemini → Cosmos doc.
- `rules` + `autopilot` — `_rules` multi-target renderer (Cursor
  `.mdc` / Claude `.md` / Codex+Gemini docs fallback) + structured
  Stop verifier with budget caps + first-class subagent role files
  for Claude AND Codex CLI + branch protection git hooks +
  subagent-dispatch.md operational protocol + Gemini honest-gap doc.

## What we want to add now

A **fifth** layer covering **multi-agent orchestration** — running
multiple agent instances (Claude Code, Codex CLI, possibly mixed)
against the same project in parallel without:

1. **Two agents editing the same file at the same time** (silent
   overwrites are catastrophic).
2. **Wrong-sized job decomposition** (parallelizing a one-line bug
   fix burns spend; not parallelizing an 8-component refactor wastes
   wallclock).

The autopilot PR (PR #16) ships a **serial** subagent dispatch
(planner → implementer → reviewer → verifier). The user wants the
**parallel** equivalent — when *should* it kick in, and how do
multiple implementers coordinate file ownership.

## What 2026 looks like in this space

- **Claude Code Agent Teams (May 2026):** orchestrator + shared task
  list + git worktrees per subagent + status flags as locks.
- **Anthropic's "C compiler with parallel Claudes" writeup:** scoped
  per-shard prompts; coordinator costs scale linearly; per-shard
  verification; failure isolation.
- **Practical limits:** 4–8 concurrent worktrees per developer
  before resource pressure becomes the bottleneck.
- **2026 consensus across tools:** task decomposition is primary
  conflict avoidance; locking is fallback; default to serial, opt
  into parallel.

## Constraints

Same as the prior four proposals:

- **Templates only.** sunaba writes files, no runtime daemon.
- **Cross-agent fairness.** Three agents in the sandbox. Whatever
  we ship should give Codex / Gemini equivalent autonomy *or*
  honestly mark a feature "Claude+Codex only."
- **Opt-in for material change.** Multi-agent is an opt-in stack,
  not default behavior.
- **No backwards-incompatible churn** for `sunaba new` / `rebuild`
  / `sync`.
- **Honest about limits.** A template cannot prevent a malicious
  agent from ignoring the protocol. This is cooperative
  coordination, not enforcement.

## What we want back

### A. Maturity scoring (1–5)

Across these axes:

- **Coordination surface** — does the project ship a shared task
  list / claim list / dispatch table?
- **File-ownership rules** — can a subagent answer "may I edit
  this file right now" before editing?
- **Sharding policy** — is there a written rule for "1 agent vs N"
  given a task shape?
- **Conflict resolution** — what happens when two shards land on
  the same file?
- **Cross-agent fairness** — can Claude / Codex / Gemini all
  participate?

### B. Concrete additions, must / should / could

For each:

- **What** (file path, content sketch).
- **Why** (specific failure pattern it prevents).
- **Where it lives** — a new `--stack multi-agent` (or similar)?
  Folded into `autopilot`? Inside the autopilot's existing
  `subagent-dispatch.md`?
- **Compatibility risk** — what changes for users on prior stacks?

You **must** take a position on:

- **One stack or fold into autopilot?** Multi-agent depends on
  autopilot's verify hook, so they're entangled — but the cohort
  semantics differ enough that a separate stack might be cleaner.
- **Optimistic claim + late merge** vs **pessimistic file lock**
  vs **hybrid (advisory `owns:` field with serialization for
  overlap)** — pick one and argue.
- **Default cohort cap.** Industry says 4–8. What number do we
  ship as the default, and which env var gates it?
- **Sharding decision rules.** Write them as a flowchart the
  orchestrator follows.

### C. Coordination surface design

Concrete:

- File path + format for the shared task list.
- Schema (`status`, `claimed-by`, `owns`, dependencies).
- Atomicity guarantee on writes (filesystem `flock`? `git`-based?
  optimistic write+retry?).
- How the orchestrator dispatches to subagents (prompt template,
  scoped to one task at a time).
- How a subagent's failure flows back to the coordinator.

### D. Sharding flowchart

Write the orchestrator's decision rules. The output should be a
yes/no / branching structure a Claude or Codex orchestrator can
follow without ambiguity. Cite the heuristics from the research
notes (file count, naturally separable layers, schema changes
first, etc.).

### E. Conflict resolution

Pick: optimistic / pessimistic / hybrid. Argue why. Specify what
the orchestrator does when two shards' `owns:` declarations
overlap.

### F. Cross-agent matrix

For each of Claude, Codex, Gemini:

- Can it act as **orchestrator**?
- Can it act as **subagent**?
- How does it observe / write the shared task list?
- What's the honest gap?

### G. Tests

`sunaba` uses `pytest`. Propose **structural** tests: claim list
schema parses, the sharding flowchart's heuristics are encoded as
testable functions, etc.

### H. Top-3 picks

If only three things land in this PR, which three move the
multi-agent posture the most?

### I. Push-back

If anything in the framing is wrong — "you don't need a shared
task list, just rely on git", "default to parallel not serial",
"sharding heuristics are too brittle to template" — say so. Drop
bad ideas now.

---

## Length and format

Long-form welcome. This becomes a public design doc. Markdown.
Code/file snippets in fenced blocks. Cite sources for opinions
that come from external references.
