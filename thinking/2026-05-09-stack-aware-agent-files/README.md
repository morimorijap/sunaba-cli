# Stack-aware agent files for sunaba-cli

> Status: **draft / in review**. Started 2026-05-09.

A user runs:

```bash
sunaba new myapp --stack python --stack nextjs --stack azure --stack agents
```

The generated `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `skills.md` are
the same boilerplate regardless of which stacks were chosen. They never
say "this is a Python + Next.js project on Azure." That's a missed
opportunity, and from the agent's perspective it's also wasteful — the
agent has to re-discover the obvious from `pyproject.toml`,
`package.json`, etc., on every fresh session.

This folder works through how to make the generated agent-instruction
surface **stack-aware** without:

- blowing past HumanLayer's 60-line ratchet budget on `AGENTS.md`,
- duplicating the same content across three files (`AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`),
- hard-coding stack content inside `cli.py`,
- and breaking the existing JSON-only deep-merge composer.

## Five candidate strategies

We came in with five options to compare. The reviewers can pick one,
combine them, or propose something else.

- **A. Composed single file.** Each stack JSON contributes a section to
  the root `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` via a new
  `_agents_md` / `_claude_md` / `_gemini_md` overlay key.
- **B. Multiple files at root.** Generate `AGENTS.md` (base) plus
  `AGENTS.python.md`, `AGENTS.nextjs.md`, `AGENTS.azure.md`. The base
  file `@`-includes them.
- **C. Skills + minimal root.** `AGENTS.md` stays at ≤60 lines; the
  detailed per-stack guidance moves to
  `.claude/skills/<stack>/SKILL.md` (Claude only, progressive
  disclosure). Codex / Gemini get a slightly fuller composed file
  because they don't load skills.
- **D. Hybrid.** Minimal root `AGENTS.md` + per-stack pointers; deep
  guidance in `.claude/skills/<stack>/SKILL.md`; mirror the same
  content as `docs/agents/<stack>.md` so non-Claude agents can find it
  on demand.
- **E. Subdirectory AGENTS.md.** When a stack genuinely owns a
  subdirectory (Next.js → `web/`), place an additional `AGENTS.md`
  *inside that subdirectory*. Spec-aligned (the AGENTS.md spec says
  the closest file to the edited file wins).

`SECURITY.md` is treated separately — see `02-research-notes.md`. We
think it should *not* be stack-composed; the secrets-management
thinking already routed per-cloud content to `docs/secrets/<cloud>.md`,
which is a better fit.

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what each agent file
   contains today and why it's hostile to multi-stack projects.
2. [`02-research-notes.md`](02-research-notes.md) — the AGENTS.md spec
   on hierarchy, Claude Skills' three-level disclosure, Cursor rules
   for comparison.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) —
   brief sent to Codex / Gemini Pro Preview for independent critique.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — Gemini 3.1 Pro Preview.
   Argues for delimiter-based injection of Markdown content stored in
   `stacks/*.json`.
5. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI (`gpt-5.5`,
   high reasoning). Argues for separate Markdown fragments under
   `templates/agents/fragments/<stack>/` plus a thin "index" root.
6. [`05-proposal.md`](05-proposal.md) — synthesized proposal:
   **Strategy D + thin A** with three explicit positions on the
   reviewer disagreements.

## Constraints

Same as the prior two design docs:

- **Templates only** — `sunaba-cli` is a generator, not a runtime.
- **No backwards-incompatible churn** for existing
  `sunaba new` / `rebuild` / `sync` users.
- **Opt-in over default** for anything that materially changes what
  lands on disk.
- **Cross-agent fairness.** Claude is not the only agent that runs
  inside a sunaba container. Whatever we ship has to give Codex and
  Gemini equivalent (not identical) signal.
