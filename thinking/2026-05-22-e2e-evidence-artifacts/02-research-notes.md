# 02 — Research notes: test-evidence conventions in 2026

> Part of [`2026-05-22-e2e-evidence-artifacts/`](README.md). Distils the
> external conventions this proposal builds on.

## A. Playwright's own artifact model

Playwright already has a mature, opinionated artifact story — and it
is important that our `E2E/` convention does **not** fight it.

- **`test-results/`** — Playwright writes per-test failure artifacts
  here: screenshots, videos, and `.zip` traces. Driven by config
  (`screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`,
  `trace: 'on-first-retry'`). Gitignored by default.
- **`playwright-report/`** — the HTML reporter output. A
  self-contained, browsable report. Also gitignored.
- **Trace Viewer** — `.zip` traces opened with
  `npx playwright show-trace`; a time-travel DOM + network + console
  snapshot. The richest evidence format Playwright produces.

Source: [Playwright — Trace Viewer](https://playwright.dev/docs/trace-viewer),
[Playwright — Reporters](https://playwright.dev/docs/test-reporters).

**Implication.** Playwright's artifacts are *machine-lifecycle*:
regenerated every run, keyed to pass/fail, disposable, gitignored.
The user's `E2E/YYYY-MM-DD-xxxxx/` is a *different* lifecycle —
**human-lifecycle, append-only, committed evidence of an agent
session**. The two should coexist: keep `test-results/` gitignored;
treat `E2E/` as curated, hand-picked proof.

## B. The Playwright MCP server

`@playwright/mcp` (the server in our `.mcp.json`) exposes browser
tools to an agent: `browser_navigate`, `browser_click`,
`browser_take_screenshot`, `browser_snapshot` (accessibility tree),
`browser_console_messages`, etc.

- It accepts an **`--output-dir`** flag that controls where
  screenshots / PDFs / traces are written. Without it, output lands
  in a per-session temp directory.
- `browser_take_screenshot` takes an optional `filename`.
- It can be launched with `--save-trace` to emit a Playwright trace
  for the whole MCP session.

Source: [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp).

**Implication.** We can point the MCP server's `--output-dir` at a
run folder so screenshots land in the right place *by construction*,
rather than relying on the agent to copy files. This is the single
highest-leverage integration hook.

## C. Architecture Decision Records (ADR)

The `YYYY-MM-DD-xxxxx` shape the user proposed is the **ADR pattern**
applied to test runs: one immutable, dated, self-contained Markdown
file (or folder) per decision/event, in a flat directory, named so
it sorts chronologically.

Source: [adr.github.io](https://adr.github.io/),
[joelparkerhenderson/architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record).

ADR conventions worth borrowing:

- **Immutability.** A landed record is not edited; a later record
  supersedes it. Good fit for "evidence of what happened on date X."
- **Sequence vs. date.** Classic ADR uses a zero-padded sequence
  (`0001-`). The user wants a date prefix. Date sorts chronologically
  *and* is self-describing; a date alone collides if two runs happen
  the same day — hence the `-xxxxx` suffix (slug or short id).
- **A fixed template** so every record has the same sections.

## D. CI artifact + agent run-log conventions

- **GitHub Actions** `actions/upload-artifact` is the standard way to
  preserve test output off the runner; artifacts are named, dated by
  run, and retention-capped (default 90 days). Evidence in CI is
  *not* committed to git — it lives in the artifact store.
- **Agent run logs (2026).** The emerging pattern across coding
  agents is a committed, human-readable run report: Claude Code's
  `claudedocs/`, "session summaries", post-task reports. The value is
  cross-agent, cross-session memory — the *next* agent reads it.

**Implication.** There is a real tension: CI says "don't commit
binary artifacts." The user explicitly wants screenshots committed.
The resolution (developed in the proposal) is a **retention policy** —
commit a small curated set, downscale, and prune old runs — plus an
honest "or gitignore `E2E/` and treat it as local-only" escape hatch.

## E. Binary bloat — the one real cost

PNG screenshots are binary blobs. Committing them means:

- Every screenshot is permanent in git history even after deletion
  (`git clone` re-downloads all of it forever).
- Diffs are useless (binary).
- A chatty agent taking 20 screenshots per run inflates the repo
  fast.

Mitigations the proposal must choose between / combine:

1. **Retention cap** — keep only the last N run folders; older ones
   pruned in the same commit (history still grows, but working tree
   stays small).
2. **Curation** — the agent commits 1–5 *chosen* screenshots, not
   every frame. The MCP `--output-dir` gets a scratch subdir; only
   promoted images are `git add`-ed.
3. **Downscale** — cap width (e.g. 1280px) / use lossy compression.
4. **Gitignore escape hatch** — `E2E/` ignored entirely; artifacts
   are local review aids, never committed. Honest, zero-bloat, but
   loses the cross-agent-memory benefit.

## F. What this means for sunaba's constraints

sunaba is a **template generator**, not a runtime. It cannot *make*
an agent take a screenshot. Everything here ships as:

- a directory scaffold (`E2E/` with a `.gitkeep` + a `TEMPLATE.md`),
- a `.gitignore` policy,
- agent guidance (`AGENTS.md` / `CLAUDE.md` / `GEMINI.md` fragment)
  that tells a *cooperating* agent the convention,
- optionally an `--output-dir` wired into `.mcp.json`.

It is cooperative, like the multi-agent proposal — a template cannot
enforce that an agent writes the README.
