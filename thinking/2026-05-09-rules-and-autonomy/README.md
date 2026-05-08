# Rules and subagents-driven autonomy for sunaba-cli

> Status: **draft / in review**. Started 2026-05-09.

The harness-engineering proposal added planner / reviewer / verifier
sub-agent role files plus on-demand skills. That's the *scaffolding*
for autonomous work. It is not the autonomous environment itself.

This folder works through the next layer:

1. **Rules** — file-glob-scoped instructions (Cursor `.mdc` style)
   that activate only for the files actually being edited.
2. **Subagents** — operational patterns for the planner / reviewer /
   verifier roles, plus equivalents for Codex CLI and Gemini CLI.
3. **AI 自走環境 (autonomy)** — permissions, hooks, budgets,
   checkpoints, and recovery primitives that let an agent keep working
   without per-step human approval, while keeping the blast radius
   bounded.

These three are one proposal because they form a stack: rules tell
the agent *what to do where*, subagents *delegate work safely*, and
the autonomy layer *keeps the loop running*.

## What 2026 looks like in this space

Convergent moves in the last few months:

- **Claude Code 2.0** ships native subagents under `.claude/agents/`
  with their own context windows and tool subsets. Auto-mode adds
  outbound + return safety checks on subagent dispatch.
- **Cursor's `.cursor/rules/*.mdc`** with glob frontmatter is the
  reference implementation for path-specific rules. Claude Code added
  path-specific rules natively in early 2026.
- **AGENTS.md** continues to be the cross-tool baseline (Codex, Cursor,
  Copilot, Windsurf). Tool-specific files specialize on top.
- **Ralph Loop** and similar autonomous-loop patterns have moved from
  "experimental" to "common" — agents that re-engage themselves after
  Stop hooks fire, until a verifier signals done.
- **Anthropic's Auto Mode** (May 2026, InfoQ) explicitly positions
  itself as autonomous coding *with human approval gates* — i.e., the
  question is not "should we automate?" but "where do the gates
  belong?"

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what the harness PR
   already gives us, and where the gap to "actually autonomous" lies.
2. [`02-research-notes.md`](02-research-notes.md) — distilled notes on
   Cursor rules, Claude Code subagents 2.0, Auto Mode safety gates,
   Ralph Loop, AGENTS.md hierarchy.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) —
   brief sent to Codex / Gemini Pro Preview for independent critique.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — Gemini 3.1 Pro Preview.
5. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI (`gpt-5.5`,
   high reasoning).
6. [`05-proposal.md`](05-proposal.md) — synthesized proposal: where
   rules live, how subagents are invoked, how the autonomous loop
   stays bounded, and what we explicitly don't ship.

## Constraints (same as the prior three)

- **Templates only** — sunaba is a generator, not a runtime.
- **Cross-agent fairness** — Claude is not the only agent. Whatever
  we ship has to give Codex / Gemini equivalent autonomy *or*
  honestly say "Claude-only" and provide an off-switch.
- **Opt-in for material change.** Autonomy that runs without
  approval prompts is **always** opt-in.
- **No backwards-incompatible churn** for `sunaba new` / `rebuild` /
  `sync`.
- **Honest about limits.** The harness PR's "what sunaba does NOT
  protect you from" list grows here, not shrinks.
