# 04b — Reviewer notes: OpenAI Codex CLI (gpt-5.5, high reasoning)

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gpt-5.5` via `codex exec --model gpt-5.5 -c model_reasoning_effort=high`.
> Date: 2026-05-09.
>
> Original reply was bilingual (English headings, Japanese body).
> Translated and lightly edited for our doc style.

## Headline position

> **Two stacks: `--stack rules` and `--stack autopilot`.**
> Different opt-in boundaries, different blast radius.
> Multi-target rule render.
> **Codex CLI has its own native subagents, hooks, and rules
> as of May 2026** — first-class templates, not a thin shim.
> Gemini stays an honest gap.

## Important factual correction (vs. the brief)

The brief framed Codex CLI as having "Task delegation via prompts
but no separate context window" and Gemini CLI as "GEMINI.md only;
no path scoping." The first claim is **out of date as of
2026-05-09**:

- **Codex CLI** ships `.codex/agents/*.toml` subagents, native
  hooks, rules, AGENTS.md hierarchy, and `codex exec --sandbox
  workspace-write` for autonomy.
- **Gemini CLI** does load hierarchical `GEMINI.md` files (closest
  wins), though it has no glob-scoped rule format and no Stop hook
  for re-engage. So Gemini is a real gap, but a smaller one than
  the brief suggested.

Sources:
[Claude memory/rules](https://code.claude.com/docs/en/memory),
[Claude hooks](https://code.claude.com/docs/en/hooks),
[Claude auto mode](https://claude.com/blog/auto-mode),
[Codex subagents](https://developers.openai.com/codex/subagents),
[Codex hooks](https://developers.openai.com/codex/hooks),
[Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md),
[Codex non-interactive](https://developers.openai.com/codex/noninteractive),
[Gemini GEMINI.md](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html).

## A. Maturity scoring

| Axis | Score | Notes |
|---|---:|---|
| Rules | 2/5 | Claude / Cursor strong. Codex / Gemini need a hierarchy-of-files render. |
| Subagents | 3/5 | Both Claude *and Codex* have native subagents. Gemini is the gap. |
| Autonomous loop | 2/5 | Stop hook works; budget / structured failure / stop conditions undefined. |
| Branch / repo protection | 2/5 | `permissions.deny` alone is insufficient. Need git hooks + docs. |
| Cross-agent fairness | 3/5 | Claude / Codex can be brought close to parity. Gemini is the honest gap. |

## B. Strategic positions

### Two stacks, not one

> **Add `--stack rules`. Add `--stack autopilot`. `autopilot` should
> recommend / require `harness`, but should not be folded into it.**

Rationale: rules is a low-risk **context improvement**. Autopilot
**changes agent behavior** (Stop, continuation, push, budget). The
opt-in boundaries differ.

### Multi-target rules with a single canonical source

> *"Maintaining each tool's format by hand will drift early."*

Canonical source under `templates/rules/<name>.rule.md`:

```md
---
name: python-tests
description: Python tests use pytest fixtures, not unittest classes.
globs:
  - "tests/**/*.py"
alwaysApply: false
targets:
  - claude
  - cursor
  - codex
  - gemini
---

# Python test rules

- Use pytest fixtures.
- Do not introduce `unittest.TestCase`.
- Prefer `uv run pytest -q`.
```

Render targets:

| Tool | Output |
|---|---|
| Claude | `.claude/rules/python-tests.md` with `paths:` |
| Cursor | `.cursor/rules/python-tests.mdc` with `globs:` / `alwaysApply:` |
| Codex | nearest practical `AGENTS.md` / `AGENTS.override.md` for directory-scoped rules, plus a root index |
| Gemini | nearest practical `GEMINI.md` for directory-scoped rules, plus a root index |

> *"Globs that cannot map cleanly to a directory hierarchy should
> render to Claude / Cursor exactly, and to Codex / Gemini as
> `docs/agents/rules/<name>.md` plus an index note. Do not pretend
> exact parity."*

## C. Concrete additions

### MUST 1 — `--stack rules`

```text
src/sunaba_cli/templates/stacks/rules.json
src/sunaba_cli/templates/rules/python-tests.rule.md
src/sunaba_cli/templates/rules/nextjs-api.rule.md
```

**Why:** prevents global-instruction pollution. Concrete failure
case: agent applies a frontend Zod rule while editing a Python
test file. Compatibility risk: low (new stack only).

### MUST 2 — Subagent dispatch protocol

`src/sunaba_cli/templates/autopilot/docs/subagent-dispatch.md`:

- **Planner** dispatch only when the task touches **3+ files**,
  unknown code, schema/API changes, auth/secrets, infra, or the
  user explicitly asks for a plan.
- Planner writes `claudedocs/plans/<slug>.md`.
- Implementer owns edits and updates checkpoints.
- Reviewer reads the diff for behavior, regressions, missing
  tests.
- Verifier runs checks **and compares against the plan's
  acceptance criteria**.
- Verifier is **not** a taste reviewer.

Claude role files stay in `.claude/agents/*.md`. **Codex gets
native equivalents** (this is the factual correction):

```text
.codex/config.toml
.codex/agents/planner.toml
.codex/agents/reviewer.toml
.codex/agents/verifier.toml
```

Gemini gets docs only:

```text
docs/agents/gemini-autopilot-limitations.md
```

Marked "manual protocol, no native Stop loop."

### MUST 3 — Structured verify / Ralph Loop

Files:

```text
.claude/hooks/verify.sh
.codex/hooks/verify.sh
.sunaba/autopilot/.gitignore
claudedocs/checkpoints/.gitkeep
```

Failure output is **structured**, not raw stderr:

```text
SUNABA_VERIFY_FAILED
iteration: 2/5
elapsed_minutes: 11/30
failed_command: uv run pytest -q
failure_log: .sunaba/autopilot/last-failure.log
next_action: Fix the failing tests, then rerun the verifier.
```

> *"Why: prevents blind loop repetition."*

Budget defaults via env vars:

```sh
SUNABA_AUTOPILOT_MAX_ITERS=5
SUNABA_AUTOPILOT_MAX_MINUTES=30
SUNABA_AUTOPILOT_MAX_CHANGED_FILES=25
```

If verification fails *and* budget remains: exit 2 (continue loop).
If budget exceeded: exit 1, stop, emit a human-review message.

> Note on budget: Codex uses **both** iteration count *and*
> wall-clock minutes; Gemini argued only iteration count is
> reliable. We synthesize both in `05-proposal.md`.

### SHOULD — Branch protection

```text
.githooks/pre-push
scripts/install-githooks.sh
```

Hook sketch:

```sh
#!/usr/bin/env sh
protected='refs/heads/main refs/heads/master'

while read local_ref local_sha remote_ref remote_sha; do
  for ref in $protected; do
    if [ "$remote_ref" = "$ref" ]; then
      echo "sunaba autopilot blocks push to $remote_ref" >&2
      exit 1
    fi
  done
done
```

Also deny in Claude settings and Codex rules — but **don't rely on
those alone**. Belt-and-braces against agents that try to bypass
configuration.

## D. Autonomous loop

### Re-engage protocol

- `verify.sh` writes full logs to
  `.sunaba/autopilot/last-failure.log`.
- Emits a short structured summary to stderr.
- Claude Stop hook: exit 2 continues.
- Codex Stop hook: also continues — Codex docs say Stop can return
  `decision: "block"` or exit 2 to create a continuation prompt.
- Gemini: no equivalent native Stop loop. Document the manual
  `gemini` retry workflow only.

### Checkpoints

`claudedocs/checkpoints/<slug>.md`. Written by the orchestrator /
implementer:

- after a plan is accepted,
- before a broad edit,
- after each failed verification pass,
- before the final response.

## E. Rules format — multi-target render

> Same conclusion as Gemini.

Pick multi-target render. Don't ship `.claude/rules` alone. Cursor
`.mdc` and Claude `paths:` are too similar to justify manual
divergence; Codex / Gemini need best-effort hierarchy docs.
Canonical source under `templates/rules/*.rule.md` keeps PR review
clean.

## F. Tests (structural)

- canonical rule frontmatter parses
- `globs` compile with `fnmatch.translate`
- Claude render uses `paths:`
- Cursor render uses `globs:` and `alwaysApply:`
- Codex / Gemini render either directory-local files or the docs
  fallback
- `.claude/agents/*.md` have `name` / `description`
- `.codex/agents/*.toml` parse with `tomllib`
- Stop hook returns exit 2 on failed verifier within budget
- Stop hook returns non-2 when budget exceeded
- pre-push hook blocks `refs/heads/main`
- `rebuild --remove autopilot` reports orphans, does not delete

## G. Top-3 picks

1. **Structured Stop verifier with budget cap.** Autonomy keystone.
2. **Subagent dispatch protocol + plan / checkpoint paths.** Role
   files become operational.
3. **Branch protection via git hook + permission/rules deny.**
   Prevents the highest-cost mistake.

## H. Push-back

> *"This is no longer Claude-only versus everyone else."*

Codex now has enough native surface to deserve first-class
templates: `.codex/agents/`, hooks, rules, and `codex exec
--sandbox workspace-write`.

Gemini remains the honest gap. **Don't simulate parity with a
brittle shell loop.** Ship docs and hierarchical `GEMINI.md`
support; label native autonomous loop as unavailable.

Final recommendation: **land `rules` first, then `autopilot`.**
Keep both opt-in. `harness` stays the base scaffold; `autopilot`
is the behavior-changing layer.
