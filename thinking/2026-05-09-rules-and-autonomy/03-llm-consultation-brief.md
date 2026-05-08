# 03 — LLM consultation brief (rules + subagents + autonomy)

> Self-contained brief sent to external reviewers (Codex / Gemini Pro
> Preview). They have **not** seen the conversations that led here.

---

## You are reviewing

A small open-source CLI called **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>). Template generator
for disposable devcontainer sandboxes pre-wired for three coding
agents (Claude Code, OpenAI Codex CLI, Google Gemini CLI). Stacks
(composable): `python` `nextjs` `aws` `azure` `gcp` `neon` `agents`
`docker` `playwright`.

Three proposals are already in flight, all in the project's
[`thinking/`](.) folder:

- **harness-engineering** — `--stack harness`: `.claude/settings.json`
  with permissions + Stop hook, `.claude/hooks/verify.sh` (silent
  success / verbose failure), `.claude/skills/{impact-map,verify-change}/SKILL.md`,
  `.claude/agents/{planner,reviewer,verifier}.md` as **role
  templates**, ratchet `AGENTS.md`, `claudedocs/`.
- **stack-aware-agent-files** — composes `AGENTS.md` / `CLAUDE.md` /
  `GEMINI.md` / `skills.md` from per-stack fragments.
- **secrets-management** — `--stack secrets` with gitleaks
  pre-commit, per-cloud docs, the Foundry → APIM → Gemini → Cosmos
  "key behind a proxy" page.

## What we want to add now

A fourth layer — **rules + subagents + autonomy** — that turns the
harness scaffold into an environment where agents can run with
minimal per-step approval, while keeping the blast radius bounded.

Three concerns in one PR because they form a stack:

1. **Rules.** File-glob-scoped instructions ("for tests/*.py use
   pytest fixtures, never unittest"; "for app/api/**/*.ts validate
   with Zod"). Cursor's `.cursor/rules/*.mdc` is the reference
   implementation. Claude Code added native path-specific rules in
   early 2026. AGENTS.md spec relies on subdirectory hierarchy.
2. **Subagents.** The harness PR ships `.claude/agents/{planner,
   reviewer,verifier}.md` as *role* files. There's no **dispatch
   protocol** specifying when to invoke whom, what each writes
   where, or how Codex / Gemini get an equivalent.
3. **Autonomy (AI 自走環境).** Re-engage on Stop-hook failure
   (Ralph Loop), bounded blast radius (branch protection, budget
   cap, checkpoints), and the cross-agent fairness question.

## What's known about the 2026 landscape

- **Anthropic Auto Mode** (May 2026) — autonomous coding *with
  human approval gates*: outbound check on dispatch, return check
  on completion, plus permission boundaries. The framing
  ("human approves the boundaries, agents work inside them") is
  the right one for sunaba.
- **Cursor `.mdc` rules** — `globs:` frontmatter, `alwaysApply`
  flag, glob-scoped activation.
- **Claude Code 2.0 subagents** — native `.claude/agents/<name>.md`
  with their own context windows, dispatched via the Agent tool.
- **Codex CLI** — Task delegation via prompts but no separate
  context window. Path scoping via subdirectory `AGENTS.md`.
  Sandbox flags via `codex exec -s`.
- **Gemini CLI** — `GEMINI.md` only; no path scoping; one-shot
  execution. Autonomy story is thinnest.
- **Ralph Loop** — re-invoke same prompt with stronger context
  each iteration until verifier passes; canonical autonomous-dev
  pattern.

## Constraints

- **Templates only.** sunaba writes files, not runtime.
- **Cross-agent fairness.** Three agents in the sandbox. Whatever
  we ship has to give Codex / Gemini equivalent autonomy *or*
  honestly mark a feature as "Claude-only" with an off-switch.
- **Opt-in for material change.** Anything that lets an agent skip
  approval prompts is opt-in. Always.
- **No backwards-incompatible churn** for `sunaba new` /
  `sunaba rebuild` / `sunaba sync`.
- **Honest about limits.** The README's "what sunaba does NOT
  protect you from" list grows with this PR, not shrinks.
- **Implementation order.** harness-engineering PR lands first;
  stack-aware and secrets follow. This PR depends on the harness
  PR's `_files` mechanism and the orphan-reporting code path
  introduced in the rebuild-consistency addendum.

## What we want back

### A. Maturity score (1–5)

Across these axes:

- **Rules** — path/glob-scoped activation.
- **Subagents** — operational dispatch protocol, not just role
  files.
- **Autonomous loop** — re-engage semantics, budget caps.
- **Branch / repo protection** — rollback, checkpoints, no
  pushing to main.
- **Cross-agent fairness** — Codex / Gemini parity vs honest gap.

### B. Concrete additions, must / should / could

For each:

- **What** — file path, content sketch / full snippet.
- **Why** — the specific autonomous-loop failure pattern it
  prevents.
- **Where it lives** — base / harness / a new stack
  (`--stack autopilot`?).
- **Compatibility risk** — does it change behavior for users on
  earlier stacks?

You **must** take a position on:

- Is this one stack (`--stack autopilot`) or two (rules separately
  from autonomy)?
- Should it be folded into `--stack harness` or stay distinct?
- Where do path-scoped rules live for **each** of Claude / Cursor
  users / Codex / Gemini? Ship one canonical source + render
  targets, or accept that each tool owns its own rule format?

### C. The subagent dispatch protocol

The harness PR ships planner / reviewer / verifier *role* files.
Specify the **operational protocol**:

- When does the orchestrator dispatch the planner? Always?
  Threshold-based?
- Where does the planner write the plan? `claudedocs/plans/<slug>.md`?
- Does the verifier read the plan or just run typecheck/tests?
- How does the reviewer differ from the verifier — reviewer reads
  diff for taste / regressions, verifier runs checks?
- Codex / Gemini equivalents — drop them, ship a thin shim, or
  document "Claude-only"?

### D. The autonomous loop

- Re-engage protocol: when `verify.sh` exits 2, what does the
  agent see on the next turn? Just stderr, or a structured
  failure summary?
- Budget cap mechanism: token counter? Wall-clock timer?
  Max-iteration count? File-based ("if checkpoint hasn't moved
  in N minutes, stop")?
- Branch protection: a pre-commit hook that refuses commits to
  main? `permissions.deny` for `git push origin main`?
- Checkpoints: what gets written to `claudedocs/checkpoints/`,
  by whom, when?

### E. Rules format — pick one or argue for multiple

Options:

- **Single canonical source.** Ship `.claude/rules/*.md` only;
  let users convert to `.mdc` if they want Cursor support.
- **Multi-target render.** One source under
  `templates/rules/<name>.md` with frontmatter; cli.py renders to
  `.cursor/rules/<name>.mdc` and `.claude/rules/<name>.md` (and a
  Codex-friendly subdir AGENTS.md note where applicable).
- **Don't ship rules at all** in this PR — argue why they're
  unnecessary on top of the stack-aware-agent-files PR.

Pick one. Argue.

### F. Test strategy

Structural tests for:

- Rules format validity (glob patterns parse).
- Subagent role files have required fields (name, description).
- Stop hook re-engages on exit code 2.
- Budget cap triggers when threshold exceeded.
- Branch-protection hook blocks `git push origin main`.

### G. Top-3 picks

If only three things land in this PR, which three move the
"autonomy posture" the most?

### H. Push-back

If anything in the framing is wrong — "rules layer is
unnecessary," "ship Claude-only and don't pretend at fairness,"
"autonomy is too dangerous to template" — say so. Drop bad ideas
now.

---

## Length and format

Long-form welcome. This becomes a public design doc. Markdown.
Code/file snippets in fenced blocks. Cite sources for opinions
that come from external references.
