# Security CI gates (`--stack security-ci`)

> Status: **implemented** (this PR). Started 2026-09-24. Phase 2 of
> [adopting ideas from northraystudio/maruda](../2026-09-24-maruda-adoption/README.md).

Until now, sunaba-generated projects had no SAST and no
dependency-vulnerability gate. Even the gitleaks check could not block
a merge, because nothing marked it required. This folder designs an
opt-in stack that adds:

- a **Semgrep** SAST gate;
- a **Trivy** dependency gate;
- a **ruleset helper** that makes both required, but only once they
  have proven they pass.

## How this proposal was developed

Following [`thinking/README.md`](../README.md), the maintainer did the
groundwork first:

- measured Semgrep's exit codes and found that maruda's gate cannot
  fail;
- researched the March 2026 Trivy compromise;
- checked Trivy's exit codes, coverage, and `.trivyignore` expiry
  against real binaries;
- verified the Trivy release's Sigstore bundle.

Two models then reviewed the same [brief](03-llm-consultation-brief.md):

- **fugu** `fugu-ultra-v1.1`, max reasoning, via Codex CLI's `fugu`
  profile: [04a](04a-fugu-review.md).
- **Codex CLI** `gpt-5.5`, high reasoning, web search:
  [04b](04b-codex-review.md).

Both reviewers endorsed rulesets, the direct Trivy binary, the
digest-pinned Semgrep container, green-plus-warning informational
mode, and not shipping ignore files. fugu added two release blockers,
both adopted:

- **The Trivy mode must survive `rebuild`.** It is now a repository
  variable.
- **The helper must not require checks that never passed.** It now
  runs a preflight and binds each check to the GitHub Actions app.

It also caught that vendoring Semgrep registry rules would breach
their license.

## Files

1. [`01-current-state.md`](01-current-state.md): what gates merges
   today (nothing does), and the generator's constraints.
2. [`02-research-notes.md`](02-research-notes.md): maruda's gates,
   Semgrep facts, the Trivy compromise, lockfile-only audits, and
   GitHub rulesets.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md): the
   brief.
4. [`04a-fugu-review.md`](04a-fugu-review.md) /
   [`04b-codex-review.md`](04b-codex-review.md): the reviews, verbatim.
5. [`05-proposal.md`](05-proposal.md): 18 decisions, tests, the
   differences from maruda, rejected alternatives, follow-ups, and
   sources.

## What a user does

```sh
sunaba new app --stack python --stack secrets --stack security-ci
# push; let the checks pass on the default branch, then:
scripts/protect-branch.sh --dry-run
scripts/protect-branch.sh --branch staging
# later, after triaging dependency warnings:
gh variable set SUNABA_TRIVY_BLOCKING --body true
```
