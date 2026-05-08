# 04b — Reviewer notes: OpenAI Codex CLI (gpt-5.5, high reasoning)

> Independent review of the proposal in `03-llm-consultation-brief.md`.
> Model: `gpt-5.5` via `codex exec --model gpt-5.5 -c model_reasoning_effort=high`.
> Date: 2026-05-09.
>
> Original reply was bilingual (English headings, Japanese commentary).
> Translated and lightly edited for clarity. Substance unchanged.

## Headline position

> **`--stack harness` should be introduced.**
> Make the existing `base/` no heavier. Add a Claude-Code-flavored,
> editable harness scaffold as **opt-in**, mounted via a new file-emission
> mechanism on stack JSON.

This directly opposes the Gemini reviewer, who argues the harness should
live in `base/` instead. See [`05-proposal.md`](05-proposal.md) for how we
resolve that disagreement.

## A. Maturity scoring (1–5)

| Axis | Score | Notes |
|---|---:|---|
| System prompt | 2 | `AGENTS.md` / `CLAUDE.md` present but generic. No failure-derived ratchet rules, no per-stack rules. |
| Tools | 3 | Devcontainer + CLIs + MCP well-covered. No tool budget — `.mcp.json` is always-on and heavy. |
| Context | 2 | `skills.md` exists but it's not progressive-disclosure. OpenAI's "make the repo a system of record" not yet achieved. |
| Sub-agents | 1 | MCP-based delegation is wired but no operational templates. HumanLayer's "context firewall" pattern undefined. |
| Feedback sensors | 1 | sunaba itself has pytest, but the **generated** project has no hooks / check scripts. |
| Permissions | 1 | No allow/deny defaults for Claude Code. Both safety and friction-reduction are unaddressed. |
| Evals | 1 | No structural regression tests for the harness. |
| Observability | 1 | No `claudedocs/`, no trace log location, no path back from failure to ratchet rule. |

Read against Fowler's framework: **feedforward guides** are thin and
**feedback sensors** are essentially absent. Reflecting the
maintainability / architecture-fitness / behaviour split into the
templates would tighten the design.

## B. Concrete additions

### MUST — `--stack harness` + stack-gated file emission

Stack JSONs today drive devcontainer composition. Add a way for a stack to
emit **arbitrary files** outside the deep-merge path:

```json
{
  "_description": "Claude Code harness templates: skills, hooks, permissions, sub-agent roles, and trace docs",
  "_files": {
    ".claude/settings.json": "harness/claude/settings.json",
    ".claude/agents/planner.md": "harness/claude/agents/planner.md",
    ".claude/agents/reviewer.md": "harness/claude/agents/reviewer.md",
    ".claude/skills/impact-map/SKILL.md": "harness/claude/skills/impact-map/SKILL.md",
    ".claude/skills/verify-change/SKILL.md": "harness/claude/skills/verify-change/SKILL.md",
    "claudedocs/README.md": "harness/claudedocs/README.md",
    "claudedocs/traces/.gitkeep": "harness/claudedocs/traces/.gitkeep"
  }
}
```

Implementation goes in `cli.py::_build_config_files()`. Read `_files`,
copy each source under `templates/` to the relative destination.
**Why this design:** treats the harness as code reviewed in PRs (Red Hat).
**Composes via:** new `stacks/harness.json`. Independent of the existing
deep-merge — file emission is its own thing.
**Compat risk:** none. Existing `sunaba new` / `rebuild` / `sync` are
unaffected unless `--stack harness` is passed.

### MUST — Concise ratchet-style `AGENTS.md` overlay

Leave `base`'s `AGENTS.md` untouched. The `harness` stack ships a
stronger version. Cap at 60 lines. Each durable rule must trace to a past
failure or a hard external constraint.

```md
# AGENTS.md

## Operating Rules
- Start by reading the task, `git status`, and the smallest relevant files.
- Prefer repo-local scripts over ad hoc shell pipelines.
- Do not add new dependencies unless the task requires them and the trade-off is documented.
- When a check fails, fix the cause or record the blocker; do not mark work complete.
- Keep changes scoped to the requested behavior.

## Ratchet Log
Each durable rule below must trace to a past failure or hard external constraint.

- Do not overwrite generated secrets, `.env`, or user-local auth state.
  Reason: generated sandboxes may mount persistent CLI credentials.
- Do not edit unrelated files while regenerating harness artifacts.
  Reason: `sunaba rebuild` users may have local modifications.
```

**Why:** Osmani / HumanLayer — root `AGENTS.md` is the highest-leverage
prompt surface, but it loses its grip the longer it gets.
**Composes via:** when `--stack harness` is passed, replace
`templates/agents/AGENTS.md` (or generate `AGENTS.harness.md` first; tools
read root names, so eventual replacement is more useful).
**Compat risk:** `sunaba sync` always copies fixed agent files today; if we
hook this into `sync`, behavior changes. Safe path: leave `sync` alone,
have `rebuild --stack harness` be the only entry point.

### MUST — `.claude/settings.json` with permissions + hooks

```json
{
  "permissions": {
    "allow": [
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(rg:*)",
      "Bash(uv run pytest:*)",
      "Bash(npm test:*)",
      "Bash(npm run lint:*)",
      "Bash(npm run typecheck:*)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)",
      "Bash(git reset --hard:*)",
      "Bash(sudo:*)"
    ]
  },
  "hooks": {
    "Stop": [
      { "matcher": "",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/verify.sh" }] }
    ]
  }
}
```

`.claude/hooks/verify.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ -f pyproject.toml ]; then
  uv run pytest
fi

if [ -f package.json ]; then
  npm run lint --if-present
  npm run typecheck --if-present
  npm test --if-present
fi
```

**Why:** "instructed" is not enough — there must be a layer that
**enforces at runtime**. Osmani frames hooks as the enforcement layer,
silent on success, verbose on failure.
**Composes via:** lives under the `harness` stack. Stack-independent
because file existence checks (`if [ -f pyproject.toml ]`) make it a no-op
on stacks that aren't installed.
**Compat risk:** harness-only. Stop hooks change Claude session behavior,
so call this out clearly in the README.

### SHOULD — Progressive-disclosure skills

`.claude/skills/impact-map/SKILL.md`:

```md
# impact-map

Use this before implementation when the requested change touches unfamiliar code.

## Output
- Files likely to change
- Existing symbols or commands to reuse
- Risks and unknowns
- A short checkpoint for human review

Do not edit files in this skill. Return only the map.
```

`.claude/skills/verify-change/SKILL.md`:

```md
# verify-change

Use after implementation and before final response.

## Steps
1. Inspect `git diff --stat` and `git diff`.
2. Run the smallest relevant checks.
3. Report failures with exact command output summary.
4. Record unresolved risk in `claudedocs/traces/` only when useful.
```

**Why:** `skills.md` as a flat list spends context on every turn. Skills
loaded on-demand keep the context small. HumanLayer treats
skills / hooks / sub-agents as the three primary harness levers.
**Composes via:** the harness stack's `_files`. Existing `skills.md` stays
in place for other agents; README notes "Claude Code prefers `.claude/skills/`".
**Compat risk:** none — pure additions.

### SHOULD — Sub-agent role templates

`.claude/agents/planner.md`:

```md
# planner

You produce repository-grounded plans only.

- Read code before proposing files.
- Return an impact map, assumptions, and acceptance criteria.
- Do not edit files.
- Keep output short and cite paths.
```

`.claude/agents/reviewer.md`:

```md
# reviewer

You review diffs for bugs, regressions, missing tests, and harness drift.

- Findings first, ordered by severity.
- Cite file paths and lines.
- Do not rewrite the implementation unless explicitly asked.
```

`.claude/agents/verifier.md`:

```md
# verifier

You run checks and summarize evidence.

- Prefer existing project commands.
- Success: concise.
- Failure: include exact failing command and actionable next step.
```

**Why:** Sub-agents are not role-play. They are a **context firewall** —
HumanLayer's primary value claim is keeping intermediate tool calls out of
the parent context.
**Composes via:** `harness` stack only. Independent of the MCP wiring —
this is the Claude Code native pattern.
**Compat risk:** none.

### SHOULD — MCP slimming

The current `.mcp.json` is always-on. Stage it instead:

- `base/`: `codex`, `gemini-cli` only
- `playwright` stack: `playwright`, `chrome-devtools`
- `notebooklm`: opt-in via a future `docs` / `research` stack

**Why:** every MCP server adds tool descriptions to every prompt and
contributes supply-chain surface. Osmani: "every irrelevant tool
description is an instruction the agent has to process."
**Composes via:** add `_mcpServers` merge to stack JSON. Don't yank
existing entries from `base/mcp.json` — deprecate gradually (warning in
next minor, slim in next major).
**Compat risk:** medium. Some users may already depend on Playwright MCP
being default. **Do this in a separate PR, not bundled with the first
harness stack.**

### COULD — `claudedocs/` (trace + decision docs)

```md
# claudedocs

Repository-local notes for agent-facing context.

- `decisions/`: durable design decisions
- `traces/`: short failure notes that may become ratchet rules
- `evals/`: harness regression scenarios
```

**Why:** OpenAI emphasizes versioned, repo-local artifacts as the agent's
"system of record."
**Composes via:** harness stack file emission.
**Compat risk:** none.

## C. `--stack harness` design

Yes, introduce it. It's the cleanest fit with the project's stated
constraints (opt-in, templates only, no backwards-incompatible churn).

**In:**

- `.claude/settings.json`
- `.claude/hooks/verify.sh`
- `.claude/skills/impact-map/SKILL.md`
- `.claude/skills/verify-change/SKILL.md`
- `.claude/agents/planner.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/verifier.md`
- `claudedocs/README.md`
- `claudedocs/traces/.gitkeep`
- *Optional:* harness-flavored `AGENTS.md`

**Out:**

- New MCP servers
- New npm / Python dependencies
- Forced CI workflow additions
- Auto PR / push / deploy hooks
- Always-on heavy test runs in hooks

README entry:

```md
| `harness` | Claude Code-oriented harness templates: permissions, hooks, skills, sub-agent role files, and trace docs. Opt-in because it changes agent behavior and adds context surface. |
```

Add to the security section:

```md
`--stack harness` adds Claude Code settings and hooks. These files are templates
committed into your project, so review them like code. Hooks can run local
commands during agent sessions; permissions reduce common prompts but are not a
security boundary.
```

## D. Test strategy

Structural, not behavioral.

- `available_stacks()` includes `harness`.
- `compose(["harness"])` produces a devcontainer dict that does **not**
  carry `_files` through.
- `_build_config_files("p", ["harness"])` emits `.claude/settings.json`
  and the other harness paths.
- `.claude/settings.json` parses as JSON and contains
  `permissions.allow` / `permissions.deny` / `hooks`.
- `AGENTS.md` (harness-flavored) is ≤60 lines.
- `.claude/hooks/verify.sh` passes `bash -n`.
- With `--stack python --stack harness`, the verify script's
  pyproject branch fires (or its no-op skip is observable).
- Idempotent: same input → identical files dict.
- Path safety: `_files` rejects `..` or absolute destinations.
- `--no-devcontainer --stack harness` still emits `.claude/*` but skips
  `.devcontainer/*`.

## E. Top-3 picks

1. **`--stack harness` + `_files` emission.**
   Without this, you can't safely opt-in any of the rest.
2. **`.claude/settings.json` permissions + silent-success/verbose-failure
   verify hook.**
   Most direct cure for the "agent-failure-loop" problem.
3. **`.claude/skills` + sub-agent templates.**
   Keeps context thin while making planner/reviewer/verifier separation
   operational.

## F. Push-back / drop

- Don't make `AGENTS.md` thick. The current one is too thin, but the
  answer is a 60-line ratchet rulebook plus skills, **not** a long
  manual.
- MCP-always-on really should be revisited, but **not in the first
  harness PR.** Compatibility risk is real and easy to underestimate.
- Evals / observability matter, but sunaba is a generator, not a runtime.
  `claudedocs/` plus structural tests is enough for now. Going further
  (runtime telemetry collection) crosses the product boundary.
