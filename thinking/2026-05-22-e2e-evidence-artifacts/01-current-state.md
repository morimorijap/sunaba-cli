# 01 — Current state: Playwright / browser E2E in sunaba

> Part of [`2026-05-22-e2e-evidence-artifacts/`](README.md).

## What sunaba ships today

sunaba already wires up browser automation in three places, but it
stops short of telling an agent **what to do with the output**.

### 1. The `playwright` stack

[`templates/stacks/playwright.json`](../../src/sunaba_cli/templates/stacks/playwright.json)
installs everything needed to *run* a browser:

- Chromium browser binary + Linux system deps
  (`npx playwright@latest install --with-deps chromium`).
- A persistent `playwright-cache` volume mounted at
  `~/.cache/ms-playwright` so the ~150 MB download survives container
  rebuilds.
- The `ms-playwright.playwright` VS Code extension.

It is purely an **environment** stack. It installs no test files, no
config, no agent guidance.

### 2. The Playwright + Chrome DevTools MCP servers

[`templates/base/mcp.json`](../../src/sunaba_cli/templates/base/mcp.json)
registers **two** browser-driving MCP servers, unconditionally — they
ship even if the user never selects the `playwright` stack:

```json
"playwright":      { "command": "npx", "args": ["@playwright/mcp@latest", "--browser", "chromium"] },
"chrome-devtools": { "command": "npx", "args": ["chrome-devtools-mcp@latest"] }
```

So **every** sunaba project gives all three agents (Claude Code,
Codex CLI, Gemini CLI) a live tool to navigate pages, click, type,
and call `browser_take_screenshot`.

### 3. `tests/test_e2e.py` — a name collision, not the thing

The repo's own [`tests/test_e2e.py`](../../tests/test_e2e.py) is the
CLI's end-to-end suite: it shells out to `sunaba new` and asserts on
emitted files. It has nothing to do with *browser* E2E. Worth naming
explicitly so this proposal's `E2E/` directory is not confused with
it.

## The gap

An agent today *can* drive a browser, but the moment the MCP session
ends, the evidence is gone:

- `browser_take_screenshot` writes PNGs into the MCP server's
  ephemeral output dir (a temp/session path). Nothing copies them
  into the repo.
- The "what did the agent actually verify" narrative lives only in
  the chat transcript — which is not committed, not reviewable in a
  PR, and not visible to the next agent.
- The `harness` stack ships `claudedocs/traces/` as a home for
  *reasoning* traces, but nothing routes *browser* evidence there,
  and `claudedocs/` is harness-only.
- There is **no `playwright` agent fragment** under
  `templates/agents/fragments/` (only `python`, `nextjs`, `agents`,
  `multi-agent` exist). So the generated `AGENTS.md` / `CLAUDE.md` /
  `GEMINI.md` say *nothing* about how to use the Playwright MCP or
  where to put what it produces.

Concretely, the failure pattern is:

> An agent is asked "check the login flow works." It drives the
> browser via the Playwright MCP, takes three screenshots, declares
> success in chat, and ends the turn. The screenshots are in
> `/tmp`. A reviewer reading the PR sees a one-line "verified login"
> claim with **no artifact behind it**. The next agent re-does the
> same exploration from scratch.

## What the user asked for

A documented convention: when an agent runs Playwright (via MCP or
script), it creates a dated run folder —

```
E2E/YYYY-MM-DD-xxxxx/
├── README.md          ← what was tested, steps, result (pass/fail)
└── *.png              ← screen captures backing the narrative
```

— so that browser verification becomes a **durable, reviewable,
commit-able artifact** instead of a disposable chat side effect.

This proposal works out the directory contract, the run-report
schema, where it plugs into the sunaba template system, and the
binary-bloat / retention questions that committing PNGs raises.
