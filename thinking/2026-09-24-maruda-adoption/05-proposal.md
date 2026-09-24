# 05 — Proposal: harden `--stack secrets` (Phase 1 of the maruda adoption)

> Part of [`2026-09-24-maruda-adoption/`](README.md). Synthesises
> [01](01-current-state.md), [02](02-research-notes.md), the
> [brief](03-llm-consultation-brief.md), and the two independent
> reviews ([fugu](04a-fugu-review.md), [Codex](04b-codex-review.md)).
> **Implemented in the same PR.**

## TL;DR

The secrets stack's generated `.gitleaks.toml` has been silently
turning gitleaks off. This PR fixes it and stops depending on an
action that needs a license key on org repos. It pins everything by
commit or checksum, and makes the CI scan fail closed when git itself
errors (a second silent-pass path, gitleaks#2129). It also adds tests
that execute the real binary and the real workflow script, so the
stack can never again pass its own tests while detecting nothing.

## Decisions

| # | Decision | Reviewers | Why |
|---|---|---|---|
| D1 | Add `[extend] useDefault = true` to `.gitleaks.toml` | Both agree | Without it the custom config replaces the default rules (01 §Defect 1). |
| D2 | **Drop the `.env*.example` path allowlist entirely**; ship `[[allowlists]]` only as a commented example | Both: a path allowlist is not "smallest unit" and hides a real key pasted into the file | We tested ten typical placeholders (`KEY=`, `your-…`, `<…>`, `changeme`, `xxxx…`, `postgres://user:password@localhost`) against gitleaks 8.30.1 default rules: **zero findings**. The allowlist bought nothing. |
| D3 | The commented example uses `[[allowlists]]`, with a note that it needs gitleaks ≥ 8.25 | Both: keep `[allowlist]` if older local gitleaks must work | Nothing is active any more, so there is no compatibility risk. When a user uncomments it, the pinned 8.30.1 (pre-commit and CI) supports it. |
| D4 | Replace `gitleaks/gitleaks-action@v2` with the release binary: pinned `GITLEAKS_VERSION`, `sha256sum -c` against `GITLEAKS_SHA256` | Both agree | The action needs a (free, registration-only) `GITLEAKS_LICENSE` on org repos, and the template never set one (01 §Defect 2). The binary is verified and needs only `contents: read`. We accept losing PR comments and the summary. SARIF is a follow-up (F3). |
| D5 | **Scan range by event:** `pull_request` scans `base.sha..head.sha`; `push` scans the full history of the pushed ref; `workflow_dispatch` scans `--all` | Both: not `--all` on PRs. fugu: `--all` sweeps every fetched ref, so keep it for deliberate sweeps | A PR scan catches a secret added and removed within the PR, and does not block on unrelated old leaks. Verified locally: a clean PR on leaky history passes, and a PR adding a key fails. PR SHAs pass through `env:`, not inline `${{ }}` in `run:`. |
| D6 | **Fail closed.** Pass `--log-opts="--no-ext-diff --no-textconv …"` and `--no-color`, tee the log, and fail the job on any `ERR` line with a `::error` annotation | fugu (cited gitleaks#2129) | Reproduced on 8.30.1: a diff driver that writes to stderr makes `gitleaks git` print `0 commits scanned` / `no leaks found` and exit 0. The flags stop repository-configured helpers from altering what gitleaks reads. The guard catches every other git failure, including a bad PR range. The guard earned its place during development: an empty push range left a trailing space in `--log-opts`, git rejected the resulting `''` argument, and only the guard turned that into a failure. |
| D7 | `--ignore-gitleaks-allow` in CI | fugu | Otherwise any PR can suppress a finding by appending `gitleaks:allow` to the line. Exceptions go through a reviewed `.gitleaksignore` fingerprint. Local pre-commit keeps gitleaks' default behaviour. |
| D8 | Install hardening: `set -euo pipefail`; `curl --retry 3 --connect-timeout 10 --max-time 120`; extract into `$RUNNER_TEMP/bin` and add it to `$GITHUB_PATH` (no `sudo`); assert `gitleaks version` equals `GITLEAKS_VERSION`; `timeout-minutes: 10`; `runs-on: ubuntu-24.04` | Both | `ubuntu-24.04` is x64 and does not drift the way `ubuntu-latest` does. A comment ties the image to the `linux_x64` archive. |
| D9 | `gitleaks git --redact` | Proposal-side (maruda uses `detect --verbose` without redaction) | `detect` has been deprecated since v8.19. Unredacted matches would land in public Actions logs. |
| D10 | `permissions: contents: read` at workflow level; `persist-credentials: false` | Both agree | Least privilege; the job never pushes. |
| D11 | SHA-pin every action with a `# vX.Y.Z` comment: `actions/checkout@3d3c42e… # v7.0.1`, and `astral-sh/setup-uv@c18668a… # v10.2.0` in sunaba's CI | Both: v7 is fine on GitHub-hosted runners; for GHES or old self-hosted runners, document Node 24 / minimum runner | Dependabot's `github-actions` ecosystem, already in generated projects, updates SHA pins and their comments. |
| D12 | pre-commit `rev: 83d9cd6…  # frozen: v8.30.1` | Both agree | `pre-commit autoupdate --freeze` style. A test keeps the frozen version equal to the CI's `GITLEAKS_VERSION`. |
| D13 | Tests (listed below) | Codex asked for real-binary tests; fugu asked that core tests prove detection, fail rather than skip in CI, and cover scanner failure | Every hardening flag has a negative control. Removing `useDefault`, `--no-textconv`, `--ignore-gitleaks-allow`, or the ERR guard each makes its own test fail. Leak tests assert the failure came from `leaks found:`, not from a git error. |
| D14 | sunaba's own CI gets SHA pins, `permissions`, and a `gitleaks` job. The job uses the same install step and fail-closed scan of the full history, then runs the binary-backed tests with `SUNABA_REQUIRE_GITLEAKS=1` so they cannot silently skip | — | Two historical false positives (`generic-api-key` matching a Markdown heading, commits `7e2ce8f` and `0c70669`) go into a root `.gitleaksignore` by fingerprint, with a reason. |
| D15 | **Disclosure:** `sunaba sync` warns about projects that still have the no-op config and shows the two-line manual fix. Release notes, `SECURITY.md` note, version 0.2.3. A GHSA is recommended; the maintainer publishes it | Both: GHSA + release notes + CLI warning, and both call it a vulnerability. fugu: release notes alone are insufficient, because generated projects do not depend on sunaba | The warning recommends the manual edit over `sunaba rebuild`, because `rebuild` currently drops `--no-devcontainer` mode and the AGENTS.md USER region (F5). It offers `rebuild --dry-run` for a reviewed full regeneration. |
| D16 | Do **not** generate `.gitleaksignore` | Codex | It is a user-owned escape hatch that `rebuild` would overwrite. `docs/secrets/README.md` documents the fingerprint workflow, the remediation order (remove → rotate → check exposure → then suppress), `--baseline-path` for bulk brownfield adoption, and a CODEOWNERS suggestion for scanner policy files. |
| D17 | **Attribution travels with generated files.** `--stack secrets` emits `docs/secrets/THIRD_PARTY_NOTICES.md` with maruda's full MIT notice; the adapted templates' headers point to it. The root `THIRD_PARTY_NOTICES.md`, README Acknowledgements, and this Sources section cover sunaba itself | fugu: a notice only in sunaba's repo does not travel with the emitted workflow. Codex: avoid implying endorsement | `docs/secrets/` is already stack-owned, so a namespaced path is not needed. Headers use the full 40-hex upstream commit, the file path, the copyright holder, and "adapted and modified". |

### Tests (D13)

- `.gitleaks.toml` has `useDefault = true` and no path allowlists.
- Workflow text: hardening flags, checksum verification, no
  `gitleaks-action`, no `pull_request_target`, no `sudo`.
- pre-commit `rev` is a 40-hex frozen commit whose version equals
  `GITLEAKS_VERSION`. sunaba's CI installs the same version and
  checksum as the template.
- **Real binary:** the config is auto-loaded and detects a planted
  key; a real key in `.env.example` is detected; placeholders are
  clean.
- **Real workflow script** (the `run:` block extracted from the
  generated YAML and executed with bash):
  - push fails on a leak and passes when clean;
  - the PR range ignores old history but catches a new key;
  - inline `gitleaks:allow` is ignored;
  - a stderr-writing textconv driver cannot hide a leak;
  - a git error fails closed.
- **SHA-pin audit** over every stack's generated workflows and
  sunaba's own. A probe proves the audit rejects `@v4`, `@main`,
  short SHAs, and pins without a version comment.
- **E2E:** `sunaba sync` warns on the legacy config and stays
  silent on the current one.

## Where we deliberately differ from maruda

- `gitleaks git --redact` instead of `gitleaks detect --verbose` (D9).
- Per-event ranges instead of `--all` everywhere (D5).
- A fail-closed guard and `--no-textconv` (D6); maruda's scan has
  the same gitleaks#2129 exposure.
- Workflow-level `permissions`, no `sudo`, and a version assertion
  (D8, D10).
- No path allowlist (D2). maruda also ships none; its example is
  commented out.

## Alternatives considered and rejected

- **Keep `gitleaks-action` and document `GITLEAKS_LICENSE`.** It
  forces a registration step on every org user of a free scaffold,
  and still runs a binary nobody verified.
- **Keep a narrowed `.env*.example` path allowlist** (fugu's
  `[^/]+` variant). It still hides real keys in those files, and
  placeholders do not need it (D2 test).
- **Multi-arch install via `RUNNER_ARCH`.** The generated workflow
  runs on a pinned x64 image; arch branches would never be exercised.
- **YAML-parsed pin audit** (fugu). It would add a PyYAML test
  dependency to a click-only project. The line regex already matches
  both step-level and job-level `uses:`, including reusable-workflow
  paths, and its probe proves it can fail.
- **gitleaks `--timeout`.** The job-level `timeout-minutes` already
  bounds the run.
- **Dependabot `pre-commit` ecosystem in generated projects**
  (fugu). It would bump the hook independently of the CI's pinned
  binary, which is exactly the drift D12 prevents. Revisit with F2.
- **Only document the bug, no CLI warning.** Users who never read
  release notes would keep a scanner that does nothing.

## Follow-ups (not in this PR)

- **F1: publish a GHSA** for `sunaba-cli`: "`--stack secrets`
  generated a `.gitleaks.toml` that disabled gitleaks' default rules",
  affected ≤ 0.2.2, fixed in 0.2.3. Include detection and
  remediation steps, and tell affected users to run a full scan and
  rotate anything it finds. Maintainer action.
- **F2: one lock file plus an updater** for gitleaks version,
  per-arch SHA-256, and release commit, rewriting both templates and
  sunaba's CI. Both reviewers asked for this. Parity is already
  enforced by tests.
- **F3: optional SARIF upload** (`--report-format sarif` +
  `github/codeql-action/upload-sarif`, which needs
  `security-events: write`).
- **F4: PR scans against trusted config** (fugu). Read
  `.gitleaks.toml` and `.gitleaksignore` from the base revision so a
  PR cannot weaken its own scan. Until then, the docs recommend
  CODEOWNERS on those files.
- **F5: fix `rebuild`'s pre-existing gaps.** Persist
  `--no-devcontainer` in the registry and splice the AGENTS.md USER
  region. After that, `rebuild` can print a security-fix message
  when it replaces the legacy config (fugu).
- **F6: Phase 2** (new opt-in stack, own `thinking/` folder):
  Semgrep **with `--error`** (maruda's gate omits it), Trivy as
  informational, npm/pnpm audit, strict CI preflights, and
  `gh api` branch protection that also covers an integration branch.
  Required checks must not be coupled with `paths:` filters.
- **F7: Phase 3 skills:** `vulnerability-scan` and
  `report-to-issues`, adapted with frontmatter and Semgrep rulesets
  aligned with CI.

## Sources

**Adapted from** (MIT, © 2026 NorthRay Studio株式会社, commit `99dd798`):

- [northraystudio/maruda — `harness/templates/github/security-scan.yml` L22-43](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/templates/github/security-scan.yml#L22-L43):
  pinned, SHA-256-verified gitleaks install; SHA-pinned checkout; full-history scan.
- [northraystudio/maruda — `harness/templates/github/gitleaks.toml`](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/templates/github/gitleaks.toml):
  `[extend] useDefault = true` and the smallest-unit allowlist policy.
- [northraystudio/maruda — `harness/tests/run.sh` L248-264](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/tests/run.sh#L248-L264):
  SHA-pin audit with a probe that guards the guard.
- [northraystudio/maruda — `docs/adr/0006-plugin-release-process.md`](https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/docs/adr/0006-plugin-release-process.md):
  "This repository runs no CI on itself" (context for 02).

**Reference:**

- [gitleaks README at v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md):
  - config precedence and auto-loading;
  - `[extend] useDefault`;
  - `[[allowlists]]` since v8.25.0;
  - `detect` deprecated in v8.19.0;
  - `--log-opts`, `--redact`, `--ignore-gitleaks-allow`, `--baseline-path`;
  - `.gitleaksignore` fingerprints.
- [gitleaks/gitleaks#2129](https://github.com/gitleaks/gitleaks/issues/2129):
  `gitleaks git` reports "no leaks found" with exit 0 when `git log`
  writes to stderr (open; reproduced on 8.30.1).
- [gitleaks `.pre-commit-hooks.yaml` at v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/.pre-commit-hooks.yaml):
  the hook runs `gitleaks git --pre-commit --redact --staged`.
- [gitleaks v8.30.1 checksums](https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt):
  `551f6fc8…70eb  gitleaks_8.30.1_linux_x64.tar.gz`.
- [gitleaks-action README](https://github.com/gitleaks/gitleaks-action#environment-variables):
  `GITLEAKS_LICENSE` is required for organizations; the key is free
  after registration.
- [GitHub Docs — Secure use reference: pin actions to a full-length commit SHA](https://docs.github.com/en/actions/reference/security/secure-use#pin-actions-to-a-full-length-commit-sha).
- [GitHub changelog — Dependabot updates version comments on SHA-pinned actions (2022-10-31)](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/).
- [GitHub Docs — Dependabot supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories):
  lists `pre-commit`.
- [pre-commit — `autoupdate --freeze`](https://pre-commit.com/#pre-commit-autoupdate).
- [actions/checkout v7.0.0 release notes](https://github.com/actions/checkout/releases/tag/v7.0.0).
- [MIT License (OSI)](https://opensource.org/license/mit).

**Origin of the idea:** a ChatGPT research conversation
("CIセキュリティ調査", 2026-09-24) pointed at maruda's CI security
gates and its Semgrep `--error` gap. Every claim above was
re-verified against the sources listed; the conversation itself is
not cited as evidence.
