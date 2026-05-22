# E2E evidence artifacts for sunaba-cli

> Status: **draft / in review**. Started 2026-05-22.

sunaba already wires three coding agents (Claude Code, Codex CLI,
Gemini CLI) to drive a real browser: the `playwright` stack installs
Chromium, and the base `.mcp.json` ships a Playwright MCP server and
a Chrome DevTools MCP server to every project. What it does **not**
do is tell an agent what to do with the result.

So today a browser verification is disposable. An agent navigates,
clicks, calls `browser_take_screenshot`, says "login works," and
ends the turn — and the screenshots are in a temp dir, the narrative
is in an uncommitted transcript, and the next agent starts over.

This proposal makes browser verification a **durable, committed,
reviewable artifact**. When an agent verifies behaviour in a browser
it writes one dated folder per session:

```text
evidence/e2e/YYYY-MM-DD-<slug>/
├── README.md          ← what was tested, the steps, the result
└── NN-<name>.png      ← curated screenshots, referenced inline
```

— a run report a PR reviewer can read and a future agent can treat
as memory.

## How this proposal was developed

Per [`thinking/README.md`](../README.md), non-trivial sunaba changes
go through an open consultation. This one was reviewed by two
external models, both invoked from the CLI against the same
self-contained [brief](03-llm-consultation-brief.md):

- **Codex CLI** — `gpt-5.5`, high reasoning effort (`codex exec`,
  read-only sandbox, web search on).
- **Gemini CLI** — `gemini-3-flash-preview` (`gemini -p`, read-only
  approval mode).

Both reviews are reproduced verbatim in
[`04a`](04a-gemini-review.md) / [`04b`](04b-codex-review.md); the
synthesised decisions live in [`05-proposal.md`](05-proposal.md).

## The decisions, in brief

- **`evidence/e2e/YYYY-MM-DD-<slug>/`** — lowercase, repo root. The
  `evidence/` prefix separates test *artifacts* from test *code*
  (the repo already has `tests/test_e2e.py`). Both reviewers
  rejected the user's literal uppercase `E2E/`.
- **`README.md` run report** — YAML frontmatter + six mandatory
  sections (Scope, Environment, Steps, Evidence, Result,
  Follow-ups). Result is exactly `pass` / `fail` / `partial`.
  A `evidence/e2e/TEMPLATE.md` ships as the starting point.
- **Folded into the `playwright` stack** — not a new `--stack e2e`,
  not an always-on scaffold. Adds the missing `playwright` agent
  fragment so the convention reaches all three agents.
- **Playwright MCP `--output-dir` → `.sunaba/e2e-scratch/`** — a
  gitignored landing pad; the agent curates keepers into the run
  folder.
- **Binary bloat** — commit a curated 1–3 screenshots (5 hard cap),
  downscaled; keep the last 5 run folders; no Git LFS.

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what sunaba ships
   for browser E2E today, and the gap.
2. [`02-research-notes.md`](02-research-notes.md) — 2026 conventions:
   Playwright's own artifacts, the Playwright MCP, ADR, CI artifacts,
   the binary-bloat cost.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) —
   self-contained brief for the external reviewers.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — Gemini
   `gemini-3-flash-preview`, verbatim.
5. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI `gpt-5.5`,
   high reasoning, verbatim.
6. [`05-proposal.md`](05-proposal.md) — synthesised proposal:
   directory contract, run-report schema, sunaba wiring, bloat
   policy, tests.

## Constraints (same spirit as the prior proposals)

- **Templates only.** sunaba writes files; it cannot force an agent
  to take a screenshot or write a report. This is a **cooperative**
  convention, like the `multi-agent` stack — honest about that.
- **Cross-agent fairness.** The artifact is plain files in the repo,
  readable by Claude / Codex / Gemini alike. Nothing routes through
  `claudedocs/` or a Claude-only path.
- **Must not fight Playwright.** Playwright owns `test-results/` and
  `playwright-report/` (machine-lifecycle, gitignored). `evidence/e2e/`
  is the different, human-lifecycle, committed artifact.
- **Opt-in.** Ships with the `playwright` stack only; no change to
  `sunaba new` / `rebuild` / `sync` defaults.
