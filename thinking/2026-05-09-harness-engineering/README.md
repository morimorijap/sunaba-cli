# Harness engineering for sunaba-cli

> Status: **draft / in review**. Started 2026-05-09.

`sunaba-cli` already gives users a fresh, isolated container with three coding
agents pre-installed. That covers the *infrastructure* side of running coding
agents safely. It does **not** yet cover the *control system* side —
the harness — that determines whether those agents produce reliable code.

This folder works through what to add.

## What is "harness engineering"?

The term has converged across the industry in early 2026:

> **Agent = Model + Harness.**
> The harness is everything around the model: the system prompt, the tool
> surface, the context it can see, the sub-agents it can spawn, the hooks that
> verify its work, and the feedback signals it consumes.

Key references we're working from:

- OpenAI — *Harness engineering: leveraging Codex in an agent-first world*
  (`openai.com/index/harness-engineering`)
- Martin Fowler — *Harness engineering for coding agent users*
  (three regulation categories: maintainability, architecture-fitness,
  behaviour; feedforward *guides* vs feedback *sensors*; computational vs
  inferential)
- HumanLayer — *Skill Issue: Harness Engineering for Coding Agents*
  (keep `AGENTS.md` under 60 lines; success-silent / failure-verbose hooks;
  sub-agents as a context firewall; CLIs over MCP servers when the model
  already knows the tool)
- Addy Osmani — *Agent Harness Engineering*
  (four pillars: system prompt, tools, context, sub-agents; the **ratchet
  pattern**: every line in `AGENTS.md` should trace back to a specific past
  failure; planner/evaluator separation)
- Red Hat — *Harness engineering: structured workflows for AI-assisted
  development*
- `ai-boost/awesome-harness-engineering` — current resource map (memory tiers,
  permissions, evals, A2A protocols, context compaction)

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what sunaba generates today
   and where the harness is thin.
2. [`02-research-notes.md`](02-research-notes.md) — distilled notes from the
   sources above. Written so the proposal stands without re-reading them.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) — the brief
   we send to external reviewers (Codex / Gemini Pro Preview) so they can
   critique the proposal independently.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — independent review from
   `gemini-3.1-pro-preview` (via Gemini CLI MCP).
5. [`04b-codex-review.md`](04b-codex-review.md) — independent review from
   OpenAI Codex CLI (`gpt-5.5`, high reasoning effort).
6. [`05-proposal.md`](05-proposal.md) — synthesized proposal: what to add,
   in what priority, where the reviewers disagreed and how we resolved it,
   and what we explicitly chose not to do.

## Constraints we're working under

- **No backwards-incompatible churn.** Existing users running
  `sunaba new` / `sunaba rebuild` shouldn't see surprises.
- **Opt-in over default.** Anything that adds context weight or supply-chain
  surface lands behind a stack flag, not in `base/`.
- **Honest README.** The current README has a deliberate "what sunaba does
  *not* protect you from" section. Anything we add must continue to be that
  honest.
