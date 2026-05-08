# 02 — Research notes

Distilled from external sources. Written so the proposal stands without
re-reading them.

## OpenAI — *Harness engineering: leveraging Codex in an agent-first world*

- The "harness" is everything around the model: system prompt, tools,
  context, sub-agents, hooks.
- As models improve, harness engineering doesn't become obsolete — the
  scaffolding migrates to harder problems (longer-horizon tasks, multi-day
  memory, evaluator agents).
- Source: `openai.com/index/harness-engineering` (OpenAI blog).

## Martin Fowler — *Harness engineering for coding agent users*

- **Three regulation categories** of harness:
  - **Maintainability** — internal code quality. Most achievable today via
    existing tooling (linters, type checkers, dead-code detection).
  - **Architecture-fitness** — fitness functions, performance budgets,
    observability standards.
  - **Behaviour** — functional correctness. The weakest area; "this approach
    puts a lot of faith into the AI-generated tests, that's not good enough
    yet."
- **Two control flavors:**
  - *Feedforward* / **guides**: prevent issues before the agent acts (rules
    files, type systems, schemas).
  - *Feedback* / **sensors**: observe after action (linters, tests). Should
    produce LLM-friendly signals.
- **Computational vs inferential** controls: deterministic linters/tests
  run in milliseconds; AI reviewers operate slower and non-deterministically.
- **Keep quality left**: distribute checks by cost — fast at pre-commit,
  expensive at post-integration, drift detection in production.
- Concept of **harnessability**: not all codebases are equally governable.
  Strong typing, clear module boundaries, established frameworks all act as
  "ambient affordances" that make a codebase amenable to agent control.

## HumanLayer — *Skill Issue: Harness Engineering for Coding Agents*

Most concrete operational guidance we found.

- **`AGENTS.md` / `CLAUDE.md` discipline:**
  - Keep under 60 lines.
  - Don't auto-generate.
  - Every rule should be earned by a real failure.
  - 6–8 worked examples per critical workflow beats prose.

- **MCP servers:** "every irrelevant tool description is an instruction the
  agent has to process." Connect only servers actually used. For tools the
  model already knows (GitHub, Docker, common databases), prefer
  CLI + shell. Wrap verbose APIs in lightweight CLIs that return only what
  the agent needs.

- **Skills (Claude Code skill format):**
  ```
  example-skill/
  ├── SKILL.md              # entry index
  ├── response_template.md
  └── CLIs/
      ├── linear-cli
      └── tunnel-cli
  ```
  Loaded on-demand, not always-on.

- **Sub-agents:** treat them as a *context firewall*. Delegate work that
  needs verbose tool calls (codebase exploration, log analysis, big diffs).
  Return condensed results with `path:line` citations. Use cheaper models
  (Sonnet/Haiku) for sub-agents, reserve Opus for orchestration.
  **Anti-pattern:** role-based sub-agents ("frontend engineer") don't work.

- **Hooks:**
  - Run typecheck / lint / build on `Stop`. Exit code 2 to re-engage the
    agent if anything failed.
  - **Success silent, failure verbose.** Passing 4,000 lines of test output
    pollutes context.
  - Auto-deny dangerous tool calls (e.g. `git push --force`, schema
    migrations) via PreToolUse.

- **Evolution:** start minimal. Add a rule when the agent actually fails.
  Don't pre-build a 200-line `CLAUDE.md` for hypothetical failures — it
  just slows the agent down.

## Addy Osmani — *Agent Harness Engineering*

- **Four pillars**: system prompt & knowledge, tools & integrations, context
  management, sub-agent orchestration.
- **The ratchet pattern**: each line in `AGENTS.md` should be traceable to a
  specific past failure.
- **Working backward from behavior**: derive harness components from desired
  behaviors, not from "tools we happen to have."
- **Planner / evaluator separation**: self-evaluation underperforms. Split
  generation and evaluation into distinct agents with pre-negotiated
  done-conditions.
- **"A decent model with a great harness beats a great model with a bad
  harness."** Cited evidence: harness-only changes moved a coding agent from
  Terminal Bench Top 30 to Top 5.
- **Context efficiency stack (in order):** compaction → tool-call
  offloading → progressive-disclosure skills.

## Red Hat — *Harness engineering: structured workflows for AI-assisted
development*

- **Harness as code.** Skills, prompts, MCP configs, hook scripts are
  software. Version them, review them in PRs, refactor them when they drift.
- Promotes shared, repo-level harness rather than per-developer
  configuration.

## `ai-boost/awesome-harness-engineering` (resource map)

Categories that matter for sunaba:

- **Permissions & authorization** — structured authorization beyond prompts
  (Open Agent Passport, Claude Code auto-mode rules). Pre-action verification.
- **Memory & state** — three-tier (core / archival / recall). `Letta`,
  `mem0`, `engram`.
- **Evals & verification** — benchmarking utilities, skill testing, CI.
- **Templates** — reusable harness configurations.

## What converges across all sources

If you strip everything down, every source agrees on these five ideas:

1. **Harness > model.** Configuration changes can outweigh model upgrades.
2. **Earn every rule.** Don't pre-write rules for hypothetical failures.
3. **Sensors beat instructions.** A failing typecheck is more reliable than
   "please run the typecheck."
4. **Context is a budget.** Loaded MCP tools, irrelevant rules, and
   verbose tool output all spend it.
5. **Sub-agents are for isolation, not for role-play.** Use them when the
   work needs context the parent shouldn't see.

These five are what the sunaba proposal needs to reflect.
