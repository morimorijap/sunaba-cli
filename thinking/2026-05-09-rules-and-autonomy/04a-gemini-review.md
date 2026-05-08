# 04a — Reviewer notes: Gemini 3.1 Pro Preview

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gemini-3.1-pro-preview` (Google Gemini CLI MCP).
> Date: 2026-05-09.
>
> Lightly reformatted. Substance unchanged.

## Headline position

> **One stack: `--stack autopilot`** (rules + autonomy together).
> Distinct from `--stack harness` but dependent on it.
> Multi-target rule render.
> Verifier MUST stay a deterministic bash script — never an LLM subagent.
> Drop the cross-agent fairness pretense; ship Claude-Code-and-Cursor first.

## A. Maturity scoring

- **Rules — 2/5.** Flat `AGENTS.md` only. No glob scoping. Context
  pollution per file is inevitable.
- **Subagents — 2/5.** Role templates exist as character sheets;
  zero operational dispatch protocol.
- **Autonomous loop — 2/5.** Stop hook returns non-zero. Re-engage
  semantics unenforced; no budget cap.
- **Branch / repo protection — 2/5.** `permissions.deny` blocks
  `--force` only. No pre-commit / pre-push hook for `main`. No
  checkpoint primitives.
- **Cross-agent fairness — 1/5.** Whole structure is
  Claude-Code-shaped.

## B. Strategic positions

1. **Stack topology.** **One stack — `--stack autopilot`.** *"Rules
   without an autonomous loop are just hints; an autonomous loop
   without file-scoped rules is a loose cannon. They are
   conceptually unified."*
2. **Relation to harness.** Distinct but dependent. `harness` =
   foundational scaffolding (logging, basic permissions, base
   roles). `autopilot` = the engine that runs autonomously inside
   that scaffold.
3. **Path-scoped rules.** **Multi-target render.** Maintain ONE
   canonical source in templates; render to `.cursor/rules/*.mdc`,
   `.claude/rules/*.md`, and hierarchical `AGENTS.md`
   subdirectories.

## C. Concrete additions

### MUST — Branch protection hook

```sh
# .git/hooks/pre-push
if [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ]; then
  echo "Agents cannot push to main"
  exit 1
fi
```

Plus `permissions.deny` updates. Lives in `--stack autopilot`.
Compatibility risk: low (opt-in only).

### MUST — Budget cap script (`.claude/hooks/budget-check.sh`)

Tracks iteration count via a local dotfile
(`.claude/run_state/iteration`). Fails the Stop hook if iterations
exceed the maximum.

> *"Without this, autonomy is a financial liability. A looping
> agent is the single worst UX possible."*

Lives in `--stack autopilot`. Compatibility risk: moderate (state
across hook executions).

### MUST — Multi-target rule engine in `sunaba-cli`

Source of truth: `src/sunaba_cli/templates/rules/<name>.md` with
custom frontmatter:

```yaml
---
name: frontend-testing
globs: ["app/**/*.tsx", "components/**/*.tsx"]
description: "Testing constraints for React components"
---
```

Render targets when `--stack autopilot` is selected:

- `.cursor/rules/frontend-testing.mdc` (Cursor format)
- `.claude/rules/frontend-testing.md` (Claude `paths:`)
- Append to `app/AGENTS.md`, `components/AGENTS.md` (Codex
  hierarchy)

Compatibility risk: high (touches core rendering logic) but
strictly additive when gated behind the stack.

### SHOULD — Checkpoint protocol (`claudedocs/checkpoints/`)

Markdown templates so the agent has a save state to resume from
when the budget cap kills a run. Low risk.

### COULD — "Fairness" shim for Codex / Gemini

> *"High effort, low reward. (See push-back below.)"*

## D. Subagent dispatch protocol

Canonical file: `claudedocs/DISPATCH_PROTOCOL.md` that the
orchestrator is instructed to follow.

1. **When to dispatch the planner.**
   *Threshold:* dispatch if the task touches >1 file or both `src/`
   and `tests/` simultaneously. Single-file bug fixes bypass.
2. **Where the planner writes.**
   `claudedocs/plans/{YYYY-MM-DD-slug}.md`. **Crucially, the plan
   MUST contain a `# Verification Criteria` section with the exact
   shell commands to run.**
3. **Reviewer vs. verifier.**
   - **Reviewer.** Dispatched *before* tests run. Reads `git diff`.
     Checks taste, architectural regressions, plan adherence.
   - **Verifier.** Purely mechanical. Does **not** read the plan.
     Executes `verify.sh` and reports stderr to the orchestrator.
4. **Codex / Gemini equivalents.**
   *Document as Claude-only.* The runtime to shim distinct context
   windows into Codex / Gemini does not exist. Rules and hooks
   apply, but parallel/isolated subagent dispatch is exclusively
   Claude Code 2.0.

## E. The autonomous loop

### Re-engage protocol

When `verify.sh` exits 2, it MUST output a structured payload to
stderr:

```
[AUTONOMY:VERIFIER_FAILED] Command: <cmd>. Exit Code: <x>.
Tail 20 lines of output: <...>.
ACTION REQUIRED: Propose a fix, do not summarize.
```

> *"Forces the agent out of apology loops and directly into
> fix-mode."*

### Budget cap

**Iteration count, file-based.** Wall-clock timers are brittle
across machines; token counts can't reliably be read from inside
the hook.

`verify.sh` increments `.claude/run_state/attempts.txt`. If
`attempts > 5`, exit `3` (Fatal) instead of `2` (Retry):

```
[AUTONOMY:BUDGET_EXCEEDED] Loop terminated to prevent runaway API spend.
```

### Branch protection

`.git/hooks/pre-push` plus updated `permissions.deny` to forbid
`git push origin main` and `git checkout main`. Agents work on
branches matching `agent/*` or `feature/*`.

### Checkpoints

- Successful task completion → `claudedocs/checkpoints/{ts}-success.md`.
- Budget cap hit → `claudedocs/checkpoints/{ts}-failed-budget.md`
  including the diff and current state.

## F. Rules format — multi-target render

> *"Shipping only `.claude/rules/*.md` abandons Cursor users (who
> need `.mdc` `globs:`) and Codex users (who need `AGENTS.md`
> subdirectories). We are a template generator. Our superpower is
> generating boilerplate so the user doesn't have to."*

Source of truth: `src/sunaba_cli/templates/rules/<name>.md` with
the frontmatter shown in C above. Renders to all three targets
when `--stack autopilot` is selected.

> *"Why not single source? Because the ecosystem hasn't converged.
> We cannot wait for standardization that might not arrive until
> 2027."*

## G. Tests (structural pytest)

1. **Rule format validity.** Multi-target renderer parses YAML
   frontmatter and outputs valid `.mdc` and `.claude/rules/`
   formats.
2. **Subagent role completeness.** `planner.md`, `reviewer.md`,
   `verifier.md` all carry the required boilerplate (name,
   description, instructions).
3. **Budget cap trigger.** Bash-level test calls `verify.sh` in a
   loop, mocks underlying test command failure, asserts the 6th
   iteration exits with code 3 (fatal) rather than 2 (retry).
4. **Branch protection.** Git-level test in temp sandbox asserts a
   simulated `git push` to `main` is intercepted by the pre-push
   hook.

## H. Top-3 picks

1. **Budget cap script.** Without it, autonomy is a financial
   liability.
2. **Multi-target scoped rules.** Glob-scoped activation is the
   highest-leverage way to improve agent accuracy per turn.
3. **Structured verifier re-engage.** Restructure stderr output to
   `[AUTONOMY:VERIFIER_FAILED] ... ACTION REQUIRED:` directives.
   Directly attacks the apology loop.

## I. Push-back

1. **Drop cross-agent fairness for autonomy.**
   > *"Stop pretending we can make Gemini CLI and Codex CLI do
   > Auto Mode right now. The constraints of the tools are
   > hardware-level (no distinct context windows, no standard
   > re-engage hooks). Attempting to build a hacky 'fairness shim'
   > will result in a fragile, unmaintainable mess. Ship this
   > stack as explicitly optimized for Claude Code and Cursor."*

   *(Note for our synthesis: the Codex reviewer disputes this
   claim with a concrete factual correction — see
   [`04b-codex-review.md`](04b-codex-review.md). Codex CLI as of
   May 2026 has native subagents, hooks, and rules.)*

2. **Do not use the verifier as an LLM subagent.**
   > *"The verifier MUST be a deterministic bash script
   > (`verify.sh`). Using an LLM to verify an LLM's code without
   > deterministic tests is an ouroboros of hallucination."*

   The verifier *role file* should be a dumb orchestrator that
   knows how to invoke `verify.sh` and parse the budget cap.

3. **One stack, not two.**
   > *"Rules are useless without the engine; the engine is useless
   > without the rules. Do not split this into `--stack rules` and
   > `--stack autopilot`. It is all `--stack autopilot`."*

   *(The Codex reviewer disputes this; see synthesis.)*
