# Adopting ideas from northraystudio/maruda

> Status: **Phase 1 implemented** (this PR). Phases 2–3 are planned,
> not started. Started 2026-09-24.

[northraystudio/maruda](https://github.com/northraystudio/maruda)
(MIT, © 2026 NorthRay Studio株式会社) is a Claude Code plugin and
installer that writes CI security gates, hooks, rules, and
diagnosis skills into a project. Several of its ideas fit sunaba's
opt-in stacks. This folder records what we take, what we change, and
why.

Checking maruda's gitleaks setup against our own turned up a
critical bug. **The `.gitleaks.toml` that `--stack secrets` generates
disables gitleaks' default rules.** Every project generated with it
has had a pre-commit hook and a CI scan that detect nothing. Phase 1
fixes that first.

## Adoption plan

| Phase | Scope | Status |
|---|---|---|
| **0** | This design folder | Done |
| **1** | Harden `--stack secrets`: working config, a checksum-verified gitleaks binary instead of a license-gated action, SHA-pinned actions, per-event scan ranges, a fail-closed scan (gitleaks#2129), real-binary and real-workflow-script tests, SHA-pin audit, notices that travel with generated files, and the same treatment for sunaba's own CI | **Implemented** |
| 2 | New opt-in security-CI stack: Semgrep (with `--error`), Trivy informational, npm/pnpm audit, strict CI preflights, and branch protection via `gh api` that also covers the integration branch | Planned (own `thinking/` folder) |
| 3 | Skills: `vulnerability-scan` (automated + LLM manual OWASP review), `report-to-issues`; later `software-evaluation`, `spec-doc` | Planned |
| 4 | Harness: PreToolUse bash guard (regex fixed, deny/allow matrix test), `.new` proposal files instead of overwrites, `settings.json` merge | Candidate |

## How this proposal was developed

Following [`thinking/README.md`](../README.md), the maintainer read
maruda at commit `99dd798`, re-verified every claim from a ChatGPT
research conversation against the source, and reproduced the gitleaks
bug with the real binary. Two external models then reviewed the same
self-contained [brief](03-llm-consultation-brief.md):

- **fugu** `fugu-ultra-v1.1`, max reasoning, via Codex CLI's `fugu`
  profile, read-only: [04a](04a-fugu-review.md). This replaced an
  earlier Antigravity CLI review of the same brief, at the
  maintainer's request.
- **Codex CLI** (`codex --search exec`, `gpt-5.5`, high reasoning,
  read-only): [04b](04b-codex-review.md)

Both reviewers agreed on the core fixes: `useDefault`, a binary
instead of the action, frozen pins, no `--all` on PRs, dropping the
`.env.example` path allowlist, and a GHSA plus a CLI warning. fugu
added three findings that changed the implementation, each verified
before adoption:

- gitleaks#2129: `gitleaks git` exits 0 having scanned nothing when
  git writes to stderr. Reproduced; now fail-closed.
- Inline `gitleaks:allow` can suppress CI findings. Now ignored in CI.
- The MIT notice must travel with generated files. Now emitted as
  `docs/secrets/THIRD_PARTY_NOTICES.md`.

[05](05-proposal.md) records each decision and the reason for it.

## Files

1. [`01-current-state.md`](01-current-state.md): what the secrets
   stack and sunaba's CI do today, and the four defects, including the
   reproduction of the no-op config.
2. [`02-research-notes.md`](02-research-notes.md): what maruda is,
   which ideas map to Phase 1, where we differ from maruda, and the
   ideas recorded for later phases.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md):
   the self-contained brief sent to the reviewers.
4. [`04a-fugu-review.md`](04a-fugu-review.md) /
   [`04b-codex-review.md`](04b-codex-review.md): the reviews,
   verbatim.
5. [`05-proposal.md`](05-proposal.md): 17 decisions, the test list,
   the rejected alternatives, follow-ups (GHSA, lock file and
   updater, SARIF, trusted-config PR scans, Phases 2–3), and sources.

## Attribution

Adapted files carry a header naming the upstream file at `99dd798`
and listing sunaba's changes. The full MIT notice is in
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) for sunaba
itself, and generated projects get
`docs/secrets/THIRD_PARTY_NOTICES.md`. This sets
the convention for future adaptations from other projects.
