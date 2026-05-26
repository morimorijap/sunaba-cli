# 01 — Current state

## What this folder is reviewing

The sibling folder
[`2026-05-26-enterprise-development/`](../2026-05-26-enterprise-development/README.md)
contains a single 557-line Japanese essay,
**「AI駆動開発における大規模業務システム開発の注意点」**
("Notes on large-scale enterprise system development under
AI-driven development"). It is a standalone discussion document —
no `01-current-state.md`, no consultation brief, no proposal — and
it is not yet wired into the `thinking/README.md` index.

This folder is a **second pass** on that essay. We are not
rewriting the content from scratch; we are asking: where is it
strong, where is it weak, and what would a 2026-style design doc
look like once external reviewers (Codex CLI `gpt-5.5` high
reasoning + Gemini CLI `gemini-3-flash-preview`) have pushed back
on it?

## What the essay covers

Eleven top-level sections, all H2, plus an unnumbered preamble:

| # | Section (translated) | Type |
|---|---|---|
| 1 | Basic premise — AI speeds parts of the work, not the whole | prose |
| 2 | Enterprise dev big picture | mermaid flowchart + prose |
| 3 | General AI-agent architecture (ReAct loop) | mermaid flowchart |
| 4 | Four "things to watch" sub-points (4.1–4.4) | prose |
| 5 | Per-phase notes (analysis → deploy) | wide table |
| 6 | Quality gates in AI-driven development | mermaid + bullet list |
| 7 | Task-handoff template | fenced markdown |
| 8 | Four anti-patterns (8.1–8.4) | prose + mermaid |
| 9 | Minimum docs to write down for a large system | table |
| 10 | Human role shift (maker → designer / evaluator) | mermaid + bullets |
| 11 | Summary | prose |

## What it gets right

- **Breadth.** It names the things AI-driven enterprise work
  actually misses: authz, audit, data migration, rollback,
  non-functional requirements, idempotency in batches,
  retries / timeouts / circuit breakers on external calls. None
  of this is wrong.
- **Concrete artefacts.** Section 4.4 ships a usable `AGENT.md`
  skeleton, and Section 7 ships a usable task-handoff template.
  These are the parts a reader can lift and apply tomorrow.
- **Honest framing of AI.** The thesis — *AI speeds the parts;
  the human still owns the whole* — is the right thesis, and
  it is stated up-front and revisited in the conclusion.
- **Mermaid for the right things.** The ReAct loop in §3 and the
  quality-gate pipeline in §6 are genuinely clearer as diagrams
  than they would be as prose.

## What is weak or improvable

These are the candidate improvement axes — not yet decisions.

1. **Length / signal density.** 557 lines, top-to-bottom prose,
   no TL;DR. A reader who only has five minutes cannot extract
   the decisions. Other docs in `thinking/` (e.g.
   `2026-05-22-e2e-evidence-artifacts/README.md`, currently on a
   sibling branch in PR #22) lead with a "decisions in brief" block.

2. **Redundancy across sections.**
   §4.4 ("`AGENT.md` is a TOC, not a giant rulebook") and §8.2
   ("anti-pattern: cram everything into `AGENT.md`") are the same
   point stated twice. §4.3 ("don't overload the system prompt")
   restates it a third time at a slightly different layer. The
   essay would shrink ~15 % without losing content if these were
   consolidated.

3. **No external sources.** `thinking/README.md` says external
   claims must link to the original. The essay makes empirical
   claims ("AI does not auto-satisfy non-functional requirements",
   "agents miss authz", "batches must be idempotent") with no
   citations to OpenAI, Anthropic, Google, OWASP ASVS, ISO/IEC
   25010, the AWS / Azure / GCP Well-Architected frameworks, or
   anything else a reviewer could check. This is the biggest gap
   versus the `thinking/` bar.

4. **Heading hierarchy is flat.** Sub-sections 4.1–4.4 and
   8.1–8.4 are emitted as `## 4.1`, `## 4.2`, etc. — all the same
   level as the section above them. A renderer (and a reader)
   sees them as ten unrelated H2 sections, not as two clusters
   of four. They should be `### 4.1` etc.

5. **§2's flowchart is misleading.** It draws the lifecycle as
   `A → B → C → D → E → F → G → H` (single arrow, linear). Real
   enterprise development is iterative, with at minimum a feedback
   edge from G ("implement / test") back to F ("detailed design")
   and from H ("deploy / operate / migrate") back to D
   ("non-functional"). Linearity is the criticism the doc itself
   levels at naive AI usage; the diagram contradicts the prose.

6. **No connection to its host project.** This essay sits inside
   `sunaba-cli`, a template generator that already ships
   `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `skills.md` per
   stack, plus `--stack rules`, `--stack autopilot`,
   `--stack secrets`, `--stack multi-agent`, and the
   `evidence/e2e/` proposal. The essay never references any of
   these. A reader who lands on it from the repo cannot tell
   whether it is *advocating for* sunaba's existing patterns,
   *critiquing them*, or *unaware of them*.

7. **Two tables that should be checklists.** §5 (per-phase notes)
   and §9 (minimum docs) are presented as descriptive tables —
   "this is what one might do." They would be more useful as
   yes/no checklists with link slots, because that is how a team
   actually uses them on a Friday afternoon.

8. **No "considered and rejected" register.** Other
   `thinking/` docs end with an "alternatives considered"
   section that records the design choices not taken (e.g.,
   `evidence/e2e/` vs `E2E/`, single-PR vs multi-PR). This essay
   states positions but never names what it *isn't* saying — so a
   reader cannot tell which claims were considered and rejected
   vs. which were never considered at all.

9. **Language mismatch.** All other `thinking/` docs are in
   English; this one is in Japanese. (The repo's main
   `README.md` and `README.ja.md` already follow an
   English-primary, Japanese-mirror convention.) For the
   improvement folder, the user has opted for **English** to
   match the rest of `thinking/`.

10. **No place in the `thinking/` index.** The folder exists on
    disk and has a commit (`138b9a4 docs(thinking): add E2E
    evidence-artifact design notes` left it unreferenced) but
    it is not listed in [`thinking/README.md`](../README.md).
    Either it should be indexed, or its successor (this folder
    plus a revised essay) should be.

## The shape of the improvement

We are **not** proposing to throw the essay out. The structural
plan to bring to the external reviewers is:

- **Keep**: the §3 ReAct diagram, the §4.4 `AGENT.md` skeleton,
  the §6 quality-gate pipeline, the §7 task template, the §10
  human-role framing.
- **Tighten**: collapse §4.3 + §4.4 + §8.2 into one section
  on context architecture; flatten redundancies; add a TL;DR.
- **Source**: add citations for every load-bearing empirical
  claim. If a claim cannot be sourced, mark it as the author's
  opinion explicitly.
- **Fix**: H3 sub-sections; iterative arrows in §2; turn §5 and
  §9 tables into checklists.
- **Connect**: a final section mapping the essay's
  recommendations onto sunaba's existing stacks (`harness`,
  `rules`, `autopilot`, `secrets`, `multi-agent`,
  `evidence/e2e/`) so a reader knows what is "use this stack
  today" vs. what is "advice the repo does not yet implement."
- **Translate**: produce the revised version in English, with
  the original Japanese essay preserved untouched as the
  source-of-record.

What the external reviewers should sharpen:

- which of the eleven sections to **cut entirely** vs. keep
- whether the proposed §2 diagram fix is the right fix
- which empirical claims most need sourcing and what the
  authoritative source is
- the right TL;DR shape for a doc of this kind
- whether the sunaba-mapping section should live in this doc
  or as a separate `docs/agents/enterprise.md` artefact in the
  main project

Those questions are formalised in
[`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
