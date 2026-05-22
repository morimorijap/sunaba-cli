# 03 — LLM consultation brief (E2E evidence artifacts)

> Self-contained brief for external reviewers (Codex CLI gpt-5.5,
> high reasoning; Gemini gemini-3-flash-preview). They have **not**
> seen the conversation.

---

## You are reviewing

A small open-source CLI called **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>). It is a **template
generator** for disposable devcontainer sandboxes pre-wired for three
coding agents (Claude Code, OpenAI Codex CLI, Google Gemini CLI).
sunaba writes files into a new project; it is **not** a runtime
daemon and has no live process.

Five feature stacks already shipped (`harness`, stack-aware agent
files, `secrets`, `rules` + `autopilot`, `multi-agent`). Relevant
existing pieces:

- A **`playwright` stack** that installs Chromium + Linux deps and a
  cache volume. Environment only — no test files, no agent guidance.
- A base **`.mcp.json`** that *unconditionally* wires two
  browser-driving MCP servers — `@playwright/mcp@latest` and
  `chrome-devtools-mcp@latest` — for all three agents.
- Per-stack **agent-file fragments** under
  `templates/agents/fragments/<stack>/{summary,tools,guidance}.md`,
  composed into the generated `AGENTS.md` / `CLAUDE.md` /
  `GEMINI.md`. There is currently **no `playwright` fragment**.
- The `harness` stack ships `claudedocs/traces/` for reasoning
  traces (harness-only).

## What we want to add now

A documented **E2E evidence convention**. When an agent drives a
browser (via the Playwright MCP, the Chrome DevTools MCP, or a
Playwright script), it should produce a **durable, committed,
reviewable artifact** of what it did — instead of screenshots
vanishing into a temp dir and the narrative living only in the chat
transcript.

The user's proposed shape:

```
E2E/YYYY-MM-DD-xxxxx/
├── README.md     ← what was tested, the steps, the result (pass/fail)
└── *.png         ← screen captures backing the narrative
```

One dated folder per browser-verification session. The `README.md`
answers: **what did you do, and what was the result?**

## Constraints (same spirit as the prior five proposals)

- **Templates only.** sunaba writes files; it cannot force an agent
  to take a screenshot or write a README. This is a **cooperative**
  convention, like our multi-agent stack — honest about that limit.
- **Cross-agent fairness.** Claude Code, Codex CLI, Gemini CLI all
  get the Playwright MCP. The convention must be agent-neutral, or
  honestly mark per-agent gaps.
- **Opt-in for material change.** No backwards-incompatible churn to
  `sunaba new` / `rebuild` / `sync`.
- **Must not fight Playwright's own artifacts.** Playwright already
  owns `test-results/` (failure screenshots/videos/traces) and
  `playwright-report/` (HTML report), both gitignored. Our `E2E/`
  is a *different lifecycle*: human-curated, append-only, committed.
- **Binary bloat is the real cost.** Committing PNGs bloats git
  history permanently. Any recommendation must address this head-on.

## What we want back

Long-form Markdown welcome — this becomes a public design doc. Cite
sources for external claims. Take explicit positions; don't hedge.

### A. Maturity scoring (1–5)

Score sunaba *as it is today* on:

- **Evidence durability** — does a browser-verification survive the
  session as a committed artifact?
- **Reviewability** — can a PR reviewer see *proof* behind a
  "verified X" claim?
- **Agent guidance** — does the generated `AGENTS.md` tell the agent
  the convention?
- **Cross-agent parity** — same story for Claude / Codex / Gemini?

### B. Directory + naming contract

Take a position on:

- **`E2E/` vs `e2e/`** — uppercase (user's spelling) vs lowercase
  (POSIX-friendly, matches `tests/`, `docs/`). Pick one, argue.
- **`xxxxx`** — what is the suffix? Free-text slug? Zero-padded
  sequence? Short random id? Time (`HHMMSS`)? It must disambiguate
  two runs on the same day and stay sortable.
- Should the folder live at **repo root** (`E2E/`) or under an
  existing dir (`docs/e2e/`, `tests/e2e/runs/`, `claudedocs/e2e/`)?
- One folder **per run**, or per *feature* with runs inside?

### C. The `README.md` run-report schema

Give a concrete template. What sections are mandatory? It must
capture: scope/goal, environment (URL, branch, commit, browser),
steps taken, the **result (pass/fail/partial)**, screenshots
referenced inline, follow-ups / bugs found. Should it have YAML
frontmatter so it is machine-parseable? Show the full template.

### D. Where it plugs into sunaba

Be specific with file paths:

- A **new `--stack e2e`**? Folded into the existing `playwright`
  stack? A always-on scaffold like `SECURITY.md`?
- The missing **`playwright` agent fragment**
  (`templates/agents/fragments/playwright/{summary,tools,guidance}.md`)
  — what does `guidance.md` say?
- Should sunaba wire the Playwright MCP server's **`--output-dir`**
  in `.mcp.json` to a scratch path so screenshots land predictably?
  If so, what path, and how does it interact with curation?
- `.gitignore` lines.

### E. The binary-bloat decision

Pick **one** primary policy and argue it:

1. Commit a curated handful of PNGs per run + a retention cap
   (keep last N runs).
2. Gitignore `E2E/` entirely — local-only evidence, never committed.
3. Commit only the `README.md`; gitignore the PNGs.
4. Something else.

Address: downscaling screenshots, Git LFS (worth it or overkill for
this project?), and what the retention number N should be.

### F. Cross-agent matrix

For Claude Code, Codex CLI, Gemini CLI: can each one (a) drive the
Playwright MCP, (b) reliably follow a "write the folder + README"
convention, (c) read a prior run folder as memory? Honest gaps.

### G. Tests

`sunaba` uses `pytest` with structural + subprocess-E2E tests.
Propose **structural** tests for whatever lands (scaffold emitted,
fragment composed into `AGENTS.md`, `.gitignore` lines present,
`TEMPLATE.md` parses).

### H. Top-3 picks

If only three things land in this PR, which three?

### I. Push-back

If the framing is wrong — "don't commit screenshots at all", "this
belongs in CI not the repo", "`E2E/` collides with `tests/test_e2e.py`",
"just use Playwright's HTML report" — say so now.

---

## Length and format

Long-form welcome. Markdown. File/code snippets in fenced blocks.
Cite sources for opinions grounded in external references.
