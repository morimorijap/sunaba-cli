# 04a — fugu review

> Reviewer: **fugu** `fugu-ultra-v1.1` (Sakana provider), run through
> Codex CLI 0.156.1 with the maintainer's `fugu` profile
> (`codex -p fugu -m fugu-ultra-v1.1 -c model_reasoning_effort=max exec
> -s read-only`), against
> [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) on
> 2026-09-24. Web search was active; observed queries covered the
> gitleaks README and config source, gitleaks issues, pre-commit's
> `autoupdate --freeze`, actions/checkout, and GitHub's Dependabot
> ecosystem table.
>
> This review replaces an earlier Antigravity CLI review of the same
> brief, at the maintainer's request.
>
> Output reproduced verbatim below. Fact-checks by the maintainer:
> gitleaks/gitleaks#2129 is open and reproduces on 8.30.1 (a stderr-writing
> textconv driver gives `0 commits scanned`, exit 0); `--ignore-gitleaks-allow`
> and `--timeout` exist in 8.30.1; the gitleaks-action license key is
> **free** but required for organizations (the brief's "paid" was wrong);
> Dependabot lists a `pre-commit` ecosystem. Maintainers' synthesis lives
> in [`05-proposal.md`](05-proposal.md).

---

## 1. Defect 1 fix

- **Yes.** For Gitleaks 8.30, `[extend] useDefault = true` is the correct fix: it loads the built-in rules and merges the repository configuration into them. Without extension, a custom configuration defines the complete rule set. ([github.com](https://github.com/gitleaks/gitleaks?utm_source=openai))
- **Keep `[allowlist]` for this Phase 1 hotfix.** Gitleaks 8.30 treats it as a deprecated compatibility form scheduled for removal in v9. Global `[[allowlists]]` arrived in 8.25; 8.24.2 only models the singular global form. Migrating during `rebuild` could therefore make the exception ineffective for users invoking an older system Gitleaks. Migrate separately when sunaba declares Gitleaks ≥8.25. ([github.com](https://github.com/gitleaks/gitleaks/blob/v8.24.2/config/config.go))
- The current path allowlist is **not consistent with “smallest possible unit.”** It exempts every matching file, including a real credential accidentally pasted into one. Prefer, in order:
  1. example values that do not resemble secrets;
  2. an exact line/placeholder regex, ideally combined with the path using `condition = "AND"` after adopting `[[allowlists]]`;
  3. an explicitly reviewed inline or finding-specific exception.
- If the path exception must remain, describe it honestly as a whole-file exception and at least prevent `.*` from spanning directories:

```toml
paths = [
  '''^\.env\.example$''',
  '''^\.env\.[^/]+\.example$''',
]
```

Gitleaks supports both inline `gitleaks:allow` comments and fingerprint-based ignores, although fingerprints remain documented as experimental. ([github.com](https://github.com/gitleaks/gitleaks))

## 2. Action → binary

- **Dropping the action is reasonable.** It gives you a verified scanner version, avoids organization-license configuration, and permits `contents: read` only. The trade-off is that you must implement event ranges, summaries, comments, artifacts, and uploads yourself. The CLI can still generate SARIF; you lose the action’s automatic plumbing, not SARIF capability. Gitleaks Action v2 is now deprecated, and its organization usage required a license key; historically its v2 documentation offered one organization repository free, so “paid for every organization repository” is slightly too broad. ([github.com](https://github.com/gitleaks/gitleaks-action/security?utm_source=openai))
- The proposed Gitleaks 8.30.1 Linux x64 checksum is correct, and `ubuntu-latest` currently denotes an x64 GitHub-hosted runner. The architecture is therefore correct for this exact runner but not portable to ARM or arbitrary self-hosted runners. ([github.com](https://github.com/gitleaks/gitleaks/releases?utm_source=openai))
- Improve the installer:
  - use `set -euo pipefail`;
  - download and extract under a `mktemp` directory in `$RUNNER_TEMP`;
  - install into `$RUNNER_TEMP/bin` instead of using unnecessary `sudo`;
  - add curl retries and connection/overall timeouts;
  - assert `gitleaks version` reports `8.30.1`;
  - either document x64-only operation or map `RUNNER_ARCH` to x64/arm64 artifacts.
  - `rm -f` is harmless, but a cleanup trap is cleaner.
- **Do not scan `--all` on every PR.** Use `base.sha..head.sha`; this scans all PR commits, including a secret introduced and later deleted within the PR. GitHub documents that `GITHUB_SHA` on `pull_request` is the synthetic merge commit, while `fetch-depth: 0` fetches full history. ([github.com](https://github.com/actions/checkout/blob/main/README.md?utm_source=openai))
- For pushes and manual runs:
  - scanning full history reachable from `HEAD` is a reasonable simple default;
  - reserve `--all` for a deliberate all-refs sweep, because it includes every fetched ref, not merely the current branch;
  - an efficient alternative is push-range scans plus a scheduled/manual full-history scan.

## 3. Existing projects with historical leaks

Document **both**, with this remediation order:

1. remove the credential from the current tree;
2. revoke or rotate it;
3. investigate exposure and consider history rewriting;
4. only then suppress the reviewed historical finding.

Neither an ignore nor a baseline remediates a credential.

- **Default guidance:** `.gitleaksignore` fingerprints for a small number of reviewed findings. They are precise and auditable, though Gitleaks labels the mechanism experimental. ([github.com](https://github.com/gitleaks/gitleaks))
- **Brownfield escape hatch:** `--baseline-path` when a repository has too many existing findings for individual review during initial adoption. Gitleaks defines a baseline as a prior report whose existing findings are excluded from subsequent results. Treat the baseline as potentially sensitive, review it before committing, and never recommend regenerating it automatically whenever CI fails. ([github.com](https://github.com/gitleaks/gitleaks))
- Thus: **fingerprints first, baseline for bulk migration**, with an explicit review/rotation checklist.

## 4. Pin maintenance

- **The frozen pre-commit SHA is worth the friction.** The hook executes third-party code on developer machines, and `pre-commit autoupdate --freeze` explicitly supports storing immutable hashes with version comments. ([pre-commit.com](https://pre-commit.com/))
- Dependabot now supports the `pre-commit` ecosystem and understands `rev: <sha> # frozen: <version>`. Add a separate `package-ecosystem: pre-commit` entry if independent hook updates are acceptable. ([docs.github.com](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories))
- If CI and pre-commit must remain exactly synchronized, use one machine-readable lock file containing:
  - Gitleaks version;
  - release SHA-256 per supported architecture;
  - release-tag commit SHA.
  
  Provide one updater script that rewrites both templates and a CI test that verifies every embedded value against that lock. Dependabot alone cannot coordinate the arbitrary binary version/checksum with the pre-commit revision.
- **`actions/checkout` v7 is a suitable GitHub-hosted default as of September 24, 2026.** The proposed SHA is the v7.0.1 release commit. Current GitHub-hosted runners satisfy its runtime requirements; document the Node 24/minimum-runner requirement if self-hosted runners or older GHES installations are in scope. There is no reason to remain on an older major solely for GitHub-hosted projects. ([github.com](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1))

## 5. Disclosure

Use **several channels**:

1. Publish a GitHub Security Advisory with affected sunaba versions, impact, fixed version, detection instructions, and remediation.
2. Add prominent release notes and a `CHANGELOG` entry.
3. Add a temporary README notice.
4. Have `sunaba` warn when it recognizes the generated title plus the vulnerable configuration shape; use an exact old-file hash as the highest-confidence signal.
5. When `rebuild` applies the fix, print a specific security-fix message and tell users to commit/stash first because rebuild overwrites files.
6. Tell affected users to run a full scan after fixing the configuration and rotate any newly discovered credentials.

**Yes, this is reasonably classified as a vulnerability in sunaba-cli.** An advertised security control was silently generated in a disabled state. It is a protection-mechanism failure in the generator, even though sunaba did not itself expose a credential. A GHSA is appropriate; requesting a CVE is optional.

Release notes alone are insufficient because generated projects have no dependency relationship that guarantees their owners will see later sunaba releases.

## 6. Attribution

The three-part credit is appropriate and conservative. Two adjustments:

- Ensure the full MIT notice **travels with generated copies**. A notice only in sunaba’s source repository does not accompany the emitted workflow. Generate a namespaced file such as `.sunaba/THIRD_PARTY_NOTICES.md`, avoiding a generic root file that rebuild might overwrite.
- Use the full 40-character upstream commit, original file path, copyright holder, and wording such as “adapted and modified.” Do not imply upstream endorsement.

The header, README acknowledgement, and proposal sources are useful documentation, but the generated notice should carry the actual license text.

## 7. What is missing

Before merging, I would add:

- **Fail-closed scanner handling.** Open Gitleaks issues report Git failures or stderr causing `0 commits scanned`, `no leaks found`, and exit 0. Capture scanner output, preserve its real exit status, and fail on `ERR` or “partial scan” indications. Pass Git options such as `--no-ext-diff --no-textconv` to reduce repository-configured diff-helper interference, and add a regression test for scanner execution failure. Do not reject every zero-commit result blindly, because a deletion-only range can legitimately have no additions. ([github.com](https://github.com/gitleaks/gitleaks/issues/2129))
- **Protect scanner policy files.** Treat `.gitleaks.toml`, `.gitleaksignore`, and the workflow as security-sensitive. Add CODEOWNERS/required review guidance; for stronger isolation, PR scans can use the configuration and ignore file from the trusted base revision rather than the PR-controlled versions. GitHub recommends CODEOWNERS for workflow changes and explicit least-privilege permissions. ([docs.github.com](https://docs.github.com/en/code-security/tutorials/secure-your-organization/protect-against-threats?utm_source=openai))
- **Consider disabling inline bypasses in CI.** Unless intentionally supported, pass `--ignore-gitleaks-allow`; otherwise a PR can suppress a finding by appending the documented inline marker. ([github.com](https://github.com/gitleaks/gitleaks))
- **Parse YAML for the pin audit.** Check both `jobs.*.steps[*].uses` and job-level `jobs.*.uses`; allow local `./...` actions and require full 40-hex SHAs for remote actions/reusable workflows. Keep the negative probe. GitHub identifies full commit SHAs as the immutable action reference. ([docs.github.com](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository?utm_source=openai))
- **Refine the integration test.** Detect a realistic planted secret in an ordinary file. Do not make the core security test prove that a realistic credential in `.env.example` is ignored. If the path exception remains, separately test its exact boundaries and prove lookalike/nested paths are not exempt.
- Ensure the dedicated CI test **fails rather than skips** when the pinned Gitleaks binary is expected to be installed.
- Add both job-level `timeout-minutes` and a Gitleaks command timeout.
- Keep `permissions: contents: read` and `persist-credentials: false`; those are good Phase 1 defaults.