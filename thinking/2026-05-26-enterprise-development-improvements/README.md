# Improving the enterprise-development essay

> Status: **draft / in review**. Started 2026-05-26.

A second-pass review of the sibling Japanese essay
[`thinking/2026-05-26-enterprise-development/README.md`](../2026-05-26-enterprise-development/README.md)
("Notes on large-scale enterprise system development under
AI-driven development"). The essay is good — it covers the right
surface area and ships two reusable artefacts (an `AGENT.md`
skeleton and a task-handoff template) — but it does not clear the
[`thinking/`](../README.md) bar on two of the three criteria:
**sourced** (zero citations) and **decision-oriented** (no
TL;DR, no rejected-alternatives register). It is also longer than
it needs to be: §4.3, §4.4, and §8.2 say the same thing.

This folder is the review record and the revision spec. **No
prose has been rewritten yet** — the rewrite is PR 2 (see
[`05-proposal.md` §10](05-proposal.md#10-next-actions)).

## How this proposal was developed

Per [`thinking/README.md`](../README.md), non-trivial sunaba
changes go through an open consultation. This one was reviewed by
two external models, both invoked from the CLI against the same
self-contained [brief](03-llm-consultation-brief.md):

- **Codex CLI** — `gpt-5.5`, `model_reasoning_effort=high`
  (`codex exec`, read-only sandbox, web search active).
- **Gemini CLI** — `gemini-3-flash-preview` (`gemini -p`,
  `--approval-mode plan`, `--skip-trust`).

Both reviews are reproduced verbatim in
[`04a`](04a-gemini-review.md) / [`04b`](04b-codex-review.md); the
synthesised plan lives in [`05-proposal.md`](05-proposal.md).
Notably, the two reviewers **independently converged** on:

- the same three "missing 2026 topics" (evals, agent security /
  prompt injection, observability / agent traces);
- the same three load-bearing redundancies (§4.3 / §4.4 / §8.2);
- the same recommendation (option F-3) to keep the essay
  project-agnostic and ship a separate sunaba-mapping companion;
- the same finding that §2's linear flowchart should be replaced
  wholesale rather than patched with feedback arrows.

Where they diverged (§3 — keep vs. cut; §10 — framing of human
role; canary citation — AWS vs. Google SRE), the proposal records
the choice and the reason.

## The decisions, in brief

1. **Reframe the thesis** from "AI changes speed, not scope" to
   "enterprise AI development is *context architecture plus
   verification architecture*."
2. **Replace** §2's linear `A → … → H` flowchart with a four-loop
   lifecycle (Discovery → Specification → Build → Operate, with
   feedback edges and an explicit human-decision node).
3. **Consolidate** §4.3 + §4.4 + §8.2 into one section,
   *The Layered Context Principle*, structured around five tiers
   (system prompt → AGENT.md → playbooks → specs/tests →
   retrieved detail).
4. **Add eight inline citations** for the load-bearing empirical
   claims (Liu et al. 2024, ISO/IEC 25010:2023, AWS Well-Architected
   Reliability, Azure transient-fault handling, Yao et al. 2022,
   OpenAI evals + *Accelerate*, Anthropic Claude Code memory,
   Google SRE Book), plus OWASP LLM Top 10 for the new
   agent-security material.
5. **Replace** §5's prose phase table with a five-column
   *checklist matrix*, and §9's prose docs table with a
   `docs/` skeleton — with four new rows
   (`agent-security.md`, `data-classification.md`,
   `observability.md`, `evals.md`).
6. **Expand §6 Quality Gates** with three new gates:
   evals, agent-security / tool-scope review, and
   observability / committed traces.
7. **Keep the essay project-agnostic.** Ship a separate
   `docs/agents/enterprise.md` companion that maps each
   principle to a sunaba stack (`rules`, `harness`, `autopilot`,
   `secrets`, `multi-agent`, `evidence/e2e/`).
8. **Translate** the revised essay to English, with `README.ja.md`
   carrying the updated Japanese version — matching the repo's
   existing main-README bilingual convention.

Net result: a target ~25 % line reduction with a sharper thesis,
inline sourcing, and a decision-oriented ending.

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what the
   current essay does well (breadth, two reusable artefacts) and
   ten candidate improvement axes (sourcing, redundancy, the §2
   diagram, the two prose tables, etc.).
2. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) —
   self-contained brief for the external reviewers. Quotes the
   essay verbatim in §0 so the reviewers do not need access to
   any other file.
3. [`04a-gemini-review.md`](04a-gemini-review.md) — Gemini CLI
   `gemini-3-flash-preview`, verbatim.
4. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI
   `gpt-5.5`, high reasoning, verbatim.
5. [`05-proposal.md`](05-proposal.md) — synthesised proposal:
   eight decisions, the new §2 diagram, source matrix,
   replacement tables, three new quality gates, sunaba-mapping
   companion plan, alternatives considered, next actions.

## Constraints (same spirit as the prior proposals)

- **Documentation change, not code.** This proposal does not
  touch sunaba's templates or `src/`. PR 2 (the essay rewrite)
  will modify
  `thinking/2026-05-26-enterprise-development/README.md` and add
  `README.ja.md` next to it. PR 3 (the optional sunaba-mapping
  companion) is the only proposal here that might land in
  `docs/agents/`.
- **Preserve the original.** The pre-revision Japanese essay is
  not deleted. The PR-2 commit overwrites
  `2026-05-26-enterprise-development/README.md` in place, but
  this folder remains as the change history; readers needing the
  pre-revision text can git-log to recover it.
- **Bar-clearing.** The revised essay must clear all three
  `thinking/` criteria: self-contained, sourced, decision-oriented.
  The current essay clears only the first.
- **Project-agnostic principle layer.** The essay stays portable
  — readable as a stand-alone document by anyone not using
  sunaba. The sunaba mapping is the companion's job.
