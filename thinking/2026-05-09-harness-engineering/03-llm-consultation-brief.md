# 03 — LLM consultation brief

> This is the self-contained brief we send to external reviewers
> (OpenAI Codex CLI, Gemini Pro Preview) so they can critique the proposal
> independently. They have **not** seen the conversation in which sunaba was
> designed; this document gives them everything they need.

---

## You are reviewing

A small open-source CLI called `sunaba-cli`. It scaffolds disposable
devcontainer sandboxes for AI coding agents (Claude Code, OpenAI Codex CLI,
Google Gemini CLI). Project: <https://github.com/morimorijap/sunaba-cli>.

For a given project the CLI emits:

- `.devcontainer/{devcontainer.json,bootstrap.sh}` (skipped with
  `--no-devcontainer`)
- `.github/dependabot.yml`
- `.vscode/settings.json` (file-watcher exclusions)
- `.mcp.json` (Claude Code → Codex / Gemini / Playwright / Chrome
  DevTools / NotebookLM via MCP)
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `skills.md`
- `.gitignore`

Stacks (composable): `python` `nextjs` `aws` `azure` `gcp` `neon` `agents`
(injects API keys) `docker` `playwright`.

The current agent files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `skills.md`)
are roughly 10 generic lines each — "use feature branches, run tests,
follow existing style."

## What we want from you

We want sunaba to ship a **harness engineering–shaped** scaffold rather than
a sandbox-only scaffold. The vocabulary is from:

- OpenAI — "Harness engineering: leveraging Codex in an agent-first world"
- Martin Fowler — "Harness engineering for coding agent users" (three
  regulation categories: maintainability / architecture-fitness / behaviour;
  feedforward *guides* vs feedback *sensors*; computational vs inferential)
- HumanLayer — "Skill Issue: Harness Engineering for Coding Agents" (keep
  `AGENTS.md` ≤60 lines; success-silent / failure-verbose hooks; sub-agents
  as a context firewall; CLIs over MCP for tools the model already knows)
- Addy Osmani — "Agent Harness Engineering" (four pillars; the **ratchet
  pattern**: every rule traceable to a past failure; planner/evaluator
  separation)
- Red Hat — "Structured workflows for AI-assisted development" (harness as
  code, reviewed in PRs)

## Hypothesized gaps (we'd like you to challenge these)

1. **`AGENTS.md` / `CLAUDE.md` are too thin.** Generic advice, no per-stack
   rules, no failure-derived ratchet content.
2. **No skills directory.** No `.claude/skills/<name>/SKILL.md` with bundled
   helper scripts. `skills.md` is a flat list, not a progressive-disclosure
   surface.
3. **No hooks.** No `.claude/settings.json` with PreToolUse / PostToolUse /
   Stop hooks. No silent-on-success typecheck/lint/test wiring per stack.
4. **No permissions.** Users hit approval prompts for every shell call.
   No `permissions.allow` / `permissions.deny` defaults.
5. **No sub-agent templates.** `.claude/agents/<role>.md` for planner /
   reviewer / verifier doesn't exist. The MCP-based sub-agent capability is
   wired, but no operational pattern is documented.
6. **MCP is always-on.** `playwright` / `chrome-devtools` / `notebooklm`
   load even on backend-only projects. They burn context and add
   supply-chain surface.
7. **No evals / observability.** No `claudedocs/` for design notes / trace
   logs, no harness regression tests.
8. **Possible new stack: `--stack harness`** that bundles items 1–5 (and
   maybe 7) so a user can opt into a Claude-Code-flavored harness in one
   flag.

## Constraints we are working under

- **No backwards-incompatible churn.** Existing `sunaba new` /
  `sunaba rebuild` users must not see surprises.
- **Opt-in over default.** Anything that adds context weight or supply-chain
  surface lands behind a stack flag, not in `base/`.
- **Honest about supply chain.** The README has a deliberate "things sunaba
  does NOT protect you from" section. Anything new must continue to be that
  honest.
- **Templates only.** sunaba is a generator. The artifacts ship as files
  the user can edit and commit. We are not building a runtime.

## What we want back, in this shape

### A. Maturity scoring (1–5) on each axis

System prompt · tools · context · sub-agents · feedback sensors ·
permissions · evals · observability.

### B. Concrete additions, prioritized

For each item:

- **What** (file path, content sketch or full snippet)
- **Why** (the specific agent failure pattern it addresses)
- **How it composes** (does it live under `base/` or under a stack? does
  it interact with the deep-merge composer?)
- **Compatibility risk** (does this change behavior for anyone running
  `sunaba sync` today?)

Use priority labels: **must**, **should**, **could**.

### C. `--stack harness` design (or argue against introducing it)

What goes in, what stays out, what its README entry should say.

### D. Test strategy

We test sunaba with `pytest`. Generated harness artifacts are not
unit-testable as-is. Propose **structural tests** (template schema, JSON
shape, idempotent regeneration) rather than behavioral tests.

### E. Your top-3 picks

If we can only land three things, which three move sunaba's harness
engineering posture the most?

### F. Things you'd push back on

If anything in our hypothesized gaps is wrong, or we're solving a
non-problem, say so. We'd rather drop a bad idea here than implement it.

---

## Length and format

Long-form is welcome. We are going to land this as a public design doc, so
clarity matters more than brevity. Markdown. Code/file snippets in fenced
blocks. Cite the source for any opinion that comes from one of the named
references above so we can trace it later.
