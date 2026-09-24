# Changelog

All notable changes to `sunaba-cli`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
follow [Semantic Versioning](https://semver.org/). Before 0.3.0 the
project was installed from `main` and never tagged.

## [0.3.0] — 2026-09-24

The first tagged release. It fixes a security bug in `--stack secrets`
and adds opt-in CI security gates.

### Security

- **`--stack secrets` detected nothing** ([#27]). The generated
  `.gitleaks.toml` lacked `[extend] useDefault = true`, so it replaced
  gitleaks' default rules with an empty set. gitleaks loads that file
  automatically, so the pre-commit hook and the CI scan in every
  project generated with the stack reported "no leaks found".
  - **Affected:** every project generated with `--stack secrets`
    before this release.
  - **Fix:** add these two lines to `.gitleaks.toml`, or review a full
    regeneration with `sunaba rebuild <name> --dry-run`:
    ```toml
    [extend]
    useDefault = true
    ```
  - `sunaba sync` now warns about affected registered projects.

### Added

- **`--stack security-ci`** ([#28]), opt-in merge gates in
  `.github/workflows/security-scan.yml`:
  - `SAST (Semgrep)`: `p/security-audit` + `p/owasp-top-ten`, run with
    `--error` so findings block, from a digest-pinned image.
  - `Dependency Scan (Trivy)`: every lockfile type (npm, pnpm, yarn,
    bun, uv, poetry, pip, Go, Cargo, …).
    - Runs from a pinned, checksum-verified release binary.
    - Informational until the repository variable
      `SUNABA_TRIVY_BLOCKING` is `true`.
    - Writes a job summary.
  - No `paths:` filters, so both checks can be required.
  - Every scanner failure fails the job.
- **`scripts/protect-branch.sh`** (with `--stack security-ci`) makes
  the checks required through a GitHub repository ruleset.
  - It covers the default branch plus any `--branch`, for example
    `staging`.
  - It blocks force pushes and branch deletion, with no bypass.
  - A preflight refuses to require checks that have not yet passed,
    and each check is bound to GitHub Actions.
  - It is idempotent and supports `--dry-run`.
- `docs/security/` with the gate maturity ladder, triage, gate
  self-protection, and scanner-update steps.
- `THIRD_PARTY_NOTICES.md`. Generated projects also get a copy under
  `docs/secrets/` or `docs/security/`.
- `CHANGELOG.md`.

### Changed

- The `--stack secrets` CI workflow ([#27]):
  - no longer uses `gitleaks/gitleaks-action`, which needs a license
    key on organization repositories;
  - runs a version-pinned, SHA-256-verified gitleaks binary;
  - scans the commits a PR adds, the full history of every pushed
    ref, and every ref on manual runs;
  - fails closed when git errors (gitleaks/gitleaks#2129);
  - ignores inline `gitleaks:allow` and redacts matches;
  - runs with `permissions: contents: read`.
- `--stack secrets` also changed in these ways:
  - The pre-commit hook is frozen to the gitleaks v8.30.1 commit
    instead of a tag.
  - `.gitleaks.toml` no longer allowlists `.env*.example` by path, so
    a real key pasted into an example file is caught.
- Every GitHub Action in generated workflows, and in sunaba's own CI,
  is pinned to a full commit SHA.
- `sunaba --version` reports the real version. It said 0.2.1 while the
  package was 0.2.2.

### Internal

- sunaba's CI now:
  - scans its own history with gitleaks;
  - runs the generated `security-scan.yml` on itself;
  - runs contract tests against the real gitleaks and Trivy binaries;
  - audits every workflow for SHA-pinned actions and digest-pinned
    images.
- The `main` branch is protected by the `sunaba security gates`
  ruleset.

### Credits

The hardened gitleaks workflow, the gitleaks policy, the SHA-pin audit,
and the security-ci gate layout, maturity ladder, and protection helper
are adapted from
[northraystudio/maruda](https://github.com/northraystudio/maruda) (MIT,
© 2026 NorthRay Studio株式会社). Design records are in
[`thinking/2026-09-24-maruda-adoption/`](thinking/2026-09-24-maruda-adoption/)
and
[`thinking/2026-09-24-security-ci-gates/`](thinking/2026-09-24-security-ci-gates/).

## Before 0.3.0 (untagged)

Installed from `main`. Highlights, oldest first:

- The initial release: composable devcontainer stacks for Claude Code,
  Codex, and Gemini CLI, plus MCP wiring.
- `--no-devcontainer` host-only mode ([#2]).
- The `playwright` stack ([#7]).
- Auth-state persistence across rebuilds ([#11]).
- `--stack harness` and the `_files` mechanism ([#12]).
- Stack-aware agent files ([#14]).
- `--stack secrets` and `sync-gitignore` ([#15]).
- `--stack rules` and `--stack autopilot` ([#16]).
- `--stack multi-agent` ([#17]).
- A `SECURITY.md` scaffold in every project ([#19]).
- Migration from Gemini CLI to the Antigravity CLI (`agy`) ([#26]).

[0.3.0]: https://github.com/morimorijap/sunaba-cli/releases/tag/v0.3.0
[#2]: https://github.com/morimorijap/sunaba-cli/pull/2
[#7]: https://github.com/morimorijap/sunaba-cli/pull/7
[#11]: https://github.com/morimorijap/sunaba-cli/pull/11
[#12]: https://github.com/morimorijap/sunaba-cli/pull/12
[#14]: https://github.com/morimorijap/sunaba-cli/pull/14
[#15]: https://github.com/morimorijap/sunaba-cli/pull/15
[#16]: https://github.com/morimorijap/sunaba-cli/pull/16
[#17]: https://github.com/morimorijap/sunaba-cli/pull/17
[#19]: https://github.com/morimorijap/sunaba-cli/pull/19
[#26]: https://github.com/morimorijap/sunaba-cli/pull/26
[#27]: https://github.com/morimorijap/sunaba-cli/pull/27
[#28]: https://github.com/morimorijap/sunaba-cli/pull/28
