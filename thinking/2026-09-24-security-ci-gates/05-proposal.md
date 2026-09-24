# 05 — Proposal: `--stack security-ci` (Phase 2 of the maruda adoption)

> Part of [`2026-09-24-security-ci-gates/`](README.md). Synthesises
> [01](01-current-state.md), [02](02-research-notes.md), the
> [brief](03-llm-consultation-brief.md), and the reviews by
> [fugu](04a-fugu-review.md) and [Codex](04b-codex-review.md).
> **Implemented in the same PR.**

## TL;DR

The new opt-in `--stack security-ci` adds two CI gates that can be
made *required*:

- **Semgrep SAST.** It blocks on findings. maruda's version never
  did, because it lacked `--error`.
- **Trivy dependency scan.** It covers every lockfile type. It warns
  until the repository variable `SUNABA_TRIVY_BLOCKING=true`, then
  blocks.

`scripts/protect-branch.sh` then makes the gates required through a
GitHub ruleset on the default branch and any integration branch, but
only after it has seen them pass. Every scanner is pinned by digest or
by checksum, and every failure path fails closed. sunaba runs the same
workflow on itself.

## Decisions

| # | Decision | Reviewers | Why |
|---|---|---|---|
| D1 | Semgrep runs `semgrep scan --error --metrics=off --config p/security-audit --config p/owasp-top-ten .` | Both: a reasonable broad default. fugu: noisy for unknown repos; keep it informational until baselined | Measured: without `--error`, seven findings exit 0. The stack is opt-in and the ladder says "blocks from day one" (maruda's intent). An existing repo that turns red is the signal the user opted into. The protect script refuses to *require* a red check (D9), so a noisy start cannot wedge merges. |
| D2 | Semgrep from `semgrep/semgrep:1.178.0@sha256:32e45…786b` as a job `container:` | Both: the right delivery; pip `--require-hashes` would need a full platform-aware lock | Semgrep's documented CI shape. The digest pins engine and dependencies as one artifact. A test enforces digest pins on every generated `image:`. |
| D3 | Registry rules stay live; the docs say the engine is pinned and the rules are not. **Vendoring is not recommended** | Codex: offer a freeze recipe. fugu: the Semgrep Rules License forbids redistributing the registry rules | Verified: "This license does not allow you to distribute the rules." The docs point regulated users to their own rule files instead. |
| D4 | Do not skip Dependabot PRs | Both | The workflow needs no secrets. A job skipped by `if:` reports Success and would satisfy a required check without scanning. |
| D5 | **Trivy from the release binary**: `TRIVY_VERSION` 0.74.0, `TRIVY_SHA256` hard-coded and verified, version asserted. Not `trivy-action` / `setup-trivy` | Both | After [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23), the direct binary has the smallest execution chain. The hash is embedded in the template, not fetched with the archive (fugu). The maintainer verified the asset's Sigstore bundle (`sigstore verify github --repository aquasecurity/trivy --ref refs/tags/v0.74.0`: OK), and the docs show how to repeat that on every bump. Runtime cosign was rejected: it would need a trusted cosign bootstrap. |
| D6 | **Trivy replaces maruda's npm/pnpm audit job** | Both: not a major regression for a language-agnostic template, if the limits are documented | One tool covers npm, pnpm, yarn, bun, uv, poetry, pip, Go and Cargo without `npm ci` (install scripts) or per-manager detection. Measured: prod dependencies only, transitive included. The limits are documented: dev dependencies skipped (`--include-dev-deps` to add them), `bun.lockb` unsupported, lockfile freshness, advisory-source differences. |
| D7 | Informational mode is a **green job with a `::warning` and a job summary**, not `continue-on-error` | Both | The job can be required from day one and still means "Trivy installed, got its data, completed". Exit code 3 means findings; 0 means clean; anything else fails closed. |
| D8 | **The mode lives in the repository variable `SUNABA_TRIVY_BLOCKING`** (default `false`), validated to be exactly `true` or `false` | fugu (release blocker) | A value written into the workflow would be reset by `sunaba rebuild`, which overwrites stack files, silently weakening the gate. A malformed value fails the job before scanning. |
| D9 | `scripts/protect-branch.sh` uses a **repository ruleset** named `sunaba security gates` on `~DEFAULT_BRANCH` + `refs/heads/<--branch>`, with `deletion`, `non_fast_forward`, required checks, no bypass actors, `do_not_enforce_on_create: true` and `--strict` opt-in | Both prefer rulesets. fugu asked for `do_not_enforce_on_create` | Rulesets fix maruda's default-branch-only protection, and multiple rulesets can coexist. Plan limits are the same as classic protection, so classic is no fallback for free private repos. |
| D10 | **Preflight before activation.** Every required context must have a completed, successful check run from `github-actions` on the default branch head, or the script stops and names the problem. Contexts are then **bound to that app's `integration_id`**. `--force` skips both | fugu (release blocker). Codex: warn that checks must run once | Requiring a check that never passed blocks every PR. Binding stops another app from reporting a same-named status. |
| D11 | Idempotent: looks up the ruleset by exact name among **repository-owned** rulesets (`includes_parents=false`, `source_type == Repository`), refuses on duplicates, PUTs by id, then **reads back** enforcement and contexts | Both (duplicates); fugu (read-back) | No silent second ruleset, and no guessing between two. |
| D12 | Required contexts come from the workflows present: `SAST (Semgrep)` + `Dependency Scan (Trivy)` with `security-scan.yml`, `Secret Scan (Gitleaks)` with `gitleaks.yml` | Both | A test checks that each context equals a real job `name:`, because a context no job reports blocks forever. |
| D13 | Workflow shape: no `paths:` filters; `merge_group` trigger; concurrency keyed by workflow, event, and PR number or ref, cancelling only PR runs; `permissions: contents: read`; `persist-credentials: false`; timeouts | Codex (concurrency), fugu (merge queue, key) | A path-skipped required check stays Pending. A branch push must not cancel the PR run. |
| D14 | Trivy DB download is its own step with **3 attempts**, then fail closed. The scan uses `--skip-db-update`. The job summary records mode, files scanned, findings and DB timestamp, and a `::notice` says when **no lockfile** was found | fugu; Codex (DB rate limits) | Tells "zero findings" apart from "nothing scanned". `GITHUB_TOKEN` does not help with DB rate limits. No `actions/cache`, to keep the action surface small (documented). |
| D15 | **Not shipped:** `.semgrepignore`, `.trivyignore`, `CODEOWNERS` | Both agree | They are user-owned policy that `rebuild` would overwrite. A `.semgrepignore` replaces Semgrep's defaults, and sunaba cannot know the owners. The docs cover `nosemgrep` with rule ID and reason, `.trivyignore` with `exp:` (verified to expire), and CODEOWNERS for the gate files. |
| D16 | Docs cover **gate self-protection**: a PR can edit the workflow and keep the job name, so workflows, the script, ignore files, `nosemgrep` comments and CODEOWNERS need required review | fugu | `integration_id` stops other apps, not a workflow-editing PR. This is documented as the user's step (see F2). |
| D17 | **Dogfooding.** sunaba's repo runs the generated `security-scan.yml` byte-for-byte (a test enforces it), plus a CI job that runs the real pinned Trivy against the template's own steps (`-k real_trivy`, `SUNABA_REQUIRE_TRIVY=1`) | fugu: prove the exact image, checkout and runner combination | maruda runs no CI on itself (ADR 0006). Today both scanners report 0 findings on sunaba. |
| D18 | `actionlint` 1.7.12 (checksum-verified) passes on every workflow; `gh` is added to the `--no-devcontainer` host check; an agent fragment says "fix findings, never weaken or bypass a gate, don't run protect-branch.sh unasked" | Codex (actionlint) | — |

### Tests

`tests/test_security_ci.py`, 47 tests plus 3 that need the real
binary:

- **Stack shape.** The expected paths are emitted; no ignore files
  are generated; nothing leaks into devcontainer.json.
- **Workflow text.** Covers `--error`, `--metrics=off`, the digest
  pin, no `paths:`, no `continue-on-error`, no
  `trivy-action`/`setup-trivy`, the checksum, the repository
  variable, `merge_group`, and the concurrency key.
- **Trivy steps executed with a fake `trivy` and `sleep`:**
  - the exit-code map (0/3/1/2 × blocking);
  - malformed mode values are rejected before any scan;
  - the summary contents;
  - the "nothing scanned" notice;
  - DB retry succeeds on the 3rd attempt and fails closed after 3.
- **Real Trivy 0.74.0** (gated):
  - a CRITICAL with a fix blocks;
  - informational mode stays green;
  - a clean lockfile passes.
- **protect-branch.sh with a fake `gh`:**
  - dry-run payload, integration branches with dedup, `--strict`, and
    gitleaks inclusion;
  - contexts equal the workflows' job names;
  - unsafe branch names are rejected;
  - POST with `integration_id` after the preflight;
  - PUT when a repository ruleset exists, ignoring inherited and other
    rulesets;
  - refusal on duplicate names;
  - five preflight refusals: missing, failed, in progress, wrong app,
    nothing ran;
  - `--force`;
  - API failure hints;
  - read-back mismatch.
- **Dogfood parity** (the repo workflow equals the template); an
  **E2E** check that `protect-branch.sh` is executable in a new
  project; digest-pin and Trivy-parity checks in
  `tests/test_supply_chain.py`.
- **Negative controls:** removing `--error`, the image digest, the
  blocking toggle, or the fail-closed branch each fails its own test.

## Where we deliberately differ from maruda

- **Semgrep:** `--error` added, `--metrics=off`, and a digest-pinned
  container instead of `pip install`.
- **Trivy:**
  - a checksum-verified binary instead of `trivy-action`;
  - one tool instead of Trivy plus npm/pnpm audit;
  - informational via a green, annotated job and a repository
    variable, instead of `continue-on-error`.
- **Protection:**
  - rulesets instead of classic protection;
  - integration branches, not only the default branch;
  - a preflight, app binding, read-back, and idempotent updates;
  - `strict` is opt-in (maruda: always on).
- **Triggers:** no `paths:` filters (maruda's `ci.yml` has them,
  which wedges required checks on docs-only PRs).
- **Not adopted from maruda:** language-specific build, test and
  lint jobs (`ci.yml`). They need per-language rendering, which
  sunaba's verbatim `_files` cannot do, and they are quality gates
  rather than security gates (F4).

## Alternatives considered and rejected

- **Semgrep informational by default** (fugu). It would contradict
  the stack's purpose. The preflight already prevents a red Semgrep
  from being made required.
- **A sunaba-owned, low-noise ruleset** (fugu). Maintaining rules is
  a project of its own, and our rules would be less reviewed than
  Semgrep's packs. Revisit if users report noise.
- **Runtime cosign verification.** It moves trust to a cosign
  installer. We verify at bump time instead.
- **Caching the Trivy DB with `actions/cache`.** It adds an action
  to trust. We retry instead, and cold runs take seconds.
- **Classic branch protection as a fallback.** It has the same plan
  limits and allows only one rule per branch.
- **SARIF upload.** It needs `security-events: write`, and Code
  Security on private repos. It stays optional (F3).
- **Generating CODEOWNERS.** sunaba cannot know the owners.

## Follow-ups (not in this PR)

- **F1:** a lock file plus an updater for the Semgrep digest, the
  Trivy version and hash, and the gitleaks pins (carried over from
  Phase 1 F2). It would also run the Sigstore check.
- **F2:** `protect-branch.sh --require-review` to add a
  pull-request rule with code-owner review for gate files. It is off
  by default, because a solo maintainer cannot approve their own PR.
- **F3:** optional SARIF upload for code-scanning users.
- **F4:** language quality gates (build, test, lint) with maruda's
  actionable preflights (missing npm scripts, zero pytest tests).
  They need runtime detection, since templates are verbatim.
- **F5:** Phase 3 skills: `vulnerability-scan` (LLM review of what
  SAST cannot see: authorization, IDOR, business logic) and
  `report-to-issues`.

## Sources

**Adapted from** (MIT, © 2026 NorthRay Studio株式会社, commit `99dd798`):

- [maruda — `harness/templates/github/security-scan.yml` L45-84](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/templates/github/security-scan.yml#L45-L84):
  the Semgrep job with `p/security-audit` + `p/owasp-top-ten`, and
  the Trivy fs job for HIGH/CRITICAL with `--ignore-unfixed`, informational.
- [maruda — `harness/scripts/setup.sh` L881-918](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/scripts/setup.sh#L881-L918):
  required checks via `gh api`, no admin bypass, no force push or deletion.
- [maruda — `README.md` L147-156](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/README.md#L147-L156):
  the gate maturity ladder.

**Reference:**

- [Semgrep CLI reference](https://semgrep.dev/docs/cli-reference)
  (exit codes, `--error`);
  [sample CI configs](https://semgrep.dev/docs/semgrep-ci/sample-ci-configs);
  [ignoring files](https://semgrep.dev/docs/ignoring-files-folders-code);
  [Semgrep Rules License](https://semgrep.dev/legal/rules-license/);
  [`Scan_CLI.ml`](https://github.com/semgrep/semgrep/blob/develop/src/osemgrep/cli_scan/Scan_CLI.ml)
  (`auto` needs metrics).
- [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23):
  the Trivy ecosystem supply-chain compromise, March 2026.
- [Trivy v0.74.0 release](https://github.com/aquasecurity/trivy/releases/tag/v0.74.0)
  and [checksums](https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_checksums.txt);
  [Node.js coverage](https://www.trivy.dev/docs/latest/guide/coverage/language/nodejs/).
- [GitHub — repository rulesets REST API](https://docs.github.com/en/rest/repos/rules);
  [about rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets);
  [available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets);
  [troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
- [npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit),
  [pnpm audit](https://pnpm.io/cli/audit),
  [yarn npm audit](https://yarnpkg.com/cli/npm/audit),
  [bun audit](https://bun.com/docs/install/audit):
  the lockfile-only alternatives measured in 02.
- [rhysd/actionlint](https://github.com/rhysd/actionlint) v1.7.12.
