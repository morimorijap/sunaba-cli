# 04a — fugu review

> Reviewer: **fugu** `fugu-ultra-v1.1` (Sakana provider), run through
> Codex CLI 0.156.1 with the maintainer's `fugu` profile
> (`codex -p fugu -m fugu-ultra-v1.1 -c model_reasoning_effort=max exec
> -s read-only`), against
> [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) on
> 2026-09-24. Web search was active; observed queries covered the
> rulesets REST reference, the Actions runner's container step host,
> Semgrep's `p/security-audit` page, and GitHub docs on check runs,
> skipped jobs, and SARIF upload.
>
> Output reproduced verbatim below. Maintainer fact-checks: the Semgrep
> Rules License does prohibit redistribution ("This license does not
> allow you to distribute the rules"); the Trivy v0.74.0 Linux-64bit
> Sigstore bundle verifies (`sigstore verify github --repository
> aquasecurity/trivy --ref refs/tags/v0.74.0`: OK). Synthesis in
> [`05-proposal.md`](05-proposal.md).

---

1. **Prefer repository rulesets.** They match the multi-branch requirement, support `~DEFAULT_BRANCH`, and can aggregate protections in one managed object. `strict_required_status_checks_policy: false` is the “loose” mode; `true` requires the PR branch to be current with its base. Rulesets and classic protection have the same relevant plan limitation, so classic protection is not a useful fallback for free private repositories. ([docs.github.com](https://docs.github.com/en/rest/repos/rules?utm_source=openai))

   Implementation details:

   - Normalize `--branch staging` to `refs/heads/staging`, validate it, and deduplicate it from the resolved default branch.
   - List with `includes_parents=false`, paginate, match repository-owned rulesets exactly, and abort if more than one name match exists.
   - `PUT` by ruleset ID is correct. Send the complete desired state, including `bypass_actors: []`, then GET and compare the result. ([docs.github.com](https://docs.github.com/en/rest/repos/rules))
   - Consider `do_not_enforce_on_create: true` so a named branch that does not yet exist can be created.
   - Omitting `integration_id` means “any source.” Bootstrap the context, inspect a genuine GitHub Actions check run, and then bind its `app.id`; otherwise another write-capable source can report the same context. ([docs.github.com](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets))
   - Do not classify every 403/404 as a plan problem; first distinguish authentication, repository identity, administration permission, and visibility errors.

2. **Use the direct, pinned release binary.** A full-SHA-pinned `trivy-action` is not inherently unsafe—the incident specifically recommends full commit pins—but the direct binary removes the additional action/setup execution chain. Hard-code the archive SHA-256 in the template; do not download both the archive and its checksum from the same release and treat that alone as independent verification. The March 2026 compromise affected mutable action/setup tags and a release binary, while v0.74.0 is now an immutable release with per-asset Sigstore bundles. ([github.com](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23?pubDate=20260526))

   Verify the Cosign bundle **during the sunaba maintainer’s version-update process**, including signer identity, issuer, transparency-log time, release commit, and final asset digest. Runtime Cosign verification is optional once that reviewed digest is embedded; adding it requires securely bootstrapping Cosign itself. ([github.com](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23?pubDate=20260526))

   Trivy is not an exact semantic replacement for native audit commands:

   - It detects transitive Node dependencies, but excludes development dependencies by default; use `--include-dev-deps` if CI/build tooling is in scope.
   - It supports textual `bun.lock`, not `bun.lockb`.
   - Its Node advisory inputs include GitHub Advisory Database and Ecosystem Security Working Group data, but source timing and matching can still differ from native package-manager services. ([trivy.dev](https://www.trivy.dev/docs/latest/guide/coverage/language/nodejs/))
   - Document that a missing or stale lockfile means incomplete coverage. Also reconsider `--ignore-unfixed`: it is reasonable for a blocking gate, but it hides relevant vulnerabilities from an informational report.

3. **The digest-pinned container is the best of the three Semgrep delivery choices.** It controls the engine and its Python dependencies as one artifact and follows Semgrep’s documented container-job pattern. A correct `pip --require-hashes` installation would require a complete platform-aware hashed dependency set; `uvx semgrep==X` still creates and resolves an isolated tool environment unless backed by a maintained lock. ([semgrep.dev](https://semgrep.dev/docs/semgrep-ci/sample-ci-configs))

   I would **not** make `p/security-audit` plus `p/owasp-top-ten` a universal blocking default for unknown repositories. Keep that pair as a broad audit/informational policy until representative projects are baselined, or ship a smaller sunaba-owned, low-noise blocking ruleset alongside the broad audit.

   Live registry rules mean the scan is not reproducible: policy can change without a sunaba release, and registry availability becomes a fail-closed dependency. However, do not vendor the packs wholesale without reviewing every rule’s license or obtaining permission—the Semgrep Rules License disallows distributing Semgrep-maintained rules. Prefer live fetching with explicit drift documentation, a content-hash mechanism if Semgrep’s resolved format permits it, or sunaba-owned permissively licensed rules. ([semgrep.dev](https://semgrep.dev/legal/rules-license/?utm_source=openai))

   **Do not skip Dependabot PRs.** This workflow needs no secrets and only read access, which fits Dependabot’s restricted token. A job-level skip reports success and could satisfy the required context without scanning anything. ([docs.github.com](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-on-actions?utm_source=openai))

4. **Explicit exit-code translation is better than `continue-on-error`.** It distinguishes accepted findings from installation, database, path, and scanner failures. For the exact v0.74.0 invocation you measured, the mapping is sound: `0` clean, `3` selected findings, everything else fail closed. Keep a real-binary regression test for that contract; Trivy defines `--exit-code` as the code used when security issues are found. ([github.com](https://github.com/aquasecurity/trivy/blob/main/schema/trivy-config.json?utm_source=openai))

   Two changes are important:

   - Validate `TRIVY_BLOCKING` as exactly `true` or `false`; malformed values should fail.
   - Do not store maturity only in an overwritten workflow. `sunaba rebuild` would reset it to `"false"`. Use a repository variable such as `vars.SUNABA_TRIVY_BLOCKING`, with an explicit default and validation.

   Also write the policy state and finding summary to `$GITHUB_STEP_SUMMARY`; a green required check with only a log annotation can misleadingly look vulnerability-free.

5. **Yes, require Trivy from day one.** Initially, the requirement means “Trivy installed, obtained its data, and completed successfully,” not “the repository has no findings.” That is a useful operational gate.

   Do not activate protection blindly. GitHub requires a required status check to have completed successfully in the repository during the preceding seven days, and workflow contexts are derived from job names. ([docs.github.com](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks?utm_source=openai))

   Recommended bootstrap:

   1. Commit and push the workflows.
   2. Inspect check runs on the current default-branch head for every exact context.
   3. Require a genuine, successful, non-skipped run from the GitHub Actions App.
   4. Create/update the ruleset—initially disabled if necessary—bind the observed `app.id`, then activate it.

   If a context is missing, stale, red, or from the wrong source, exit with instructions rather than installing an active ruleset that may wedge the repository. An explicit escape hatch may exist, but should not be the default.

6. **Not shipping either ignore file is correct.** They are repository policy, and `rebuild` must not erase reviewed exceptions or restore template defaults.

   - For Semgrep, require the exact rule ID in `nosemgrep` plus an adjacent rationale. Document clearly that adding `.semgrepignore` replaces Semgrep’s default ignore list.
   - Plain `.trivyignore` supports expiry syntax and comment-based reasons. If you recommend `.trivyignore.yaml` for machine-readable `expired_at` and `statement`, note that it is currently experimental and must be supplied explicitly with `--ignorefile`; the proposed command does not yet do that. ([trivy.dev](https://trivy.dev/docs/dev/configuration/filtering/?utm_source=openai))
   - Recommend review protection for ignore files and inline suppressions. Do not generate `CODEOWNERS`, because sunaba cannot know the appropriate user or team.

7. **Address these before release:**

   - **Protect the gate from changing itself.** Required checks identify job names, not trusted workflow-file identities, and skipped jobs count as success. `integration_id` prevents another App from spoofing a context but does not prevent a PR from weakening a workflow that still runs under GitHub Actions. Offer or document required review/CODEOWNERS protection for `.github/workflows/**`, the protection script, suppressions, and the `CODEOWNERS` file itself. ([docs.github.com](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules?utm_source=openai))
   - **Smoke-test the exact Semgrep combination.** The image is Alpine-based, but the Actions runner explicitly selects an Alpine-compatible Node runtime for JavaScript actions on x64, so this is not a known glibc incompatibility. Still dogfood the exact image digest, checkout SHA, runner label, a real finding, and a scanner failure on every update. ([github.com](https://github.com/semgrep/semgrep/blob/develop/Dockerfile?utm_source=openai))
   - **Handle live Trivy data explicitly.** The engine is pinned, but its DB is not; Trivy currently tries `mirror.gcr.io/aquasec` and then GHCR. Add bounded retries, optionally cache the DB without preventing refresh, and record DB metadata in the summary. Distinguish “zero findings” from “no supported dependency files found.” ([trivy.dev](https://trivy.dev/docs/dev/configuration/db/?utm_source=openai))
   - **Add `merge_group`** if merge queues are supported, and use a concurrency key containing the workflow, event type, and PR/ref so a feature-branch `push` run cannot cancel the corresponding PR run. ([docs.github.com](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks?utm_source=openai))
   - **Keep SARIF optional.** Uploading requires `security-events: write`; private/internal repositories also need GitHub Code Security. Console output and job summaries are the correct universal baseline. ([docs.github.com](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/integrate-with-existing-tools/upload-sarif-file?utm_source=openai))
   - **Expand protection-script tests:** pagination, parent/name collisions, invalid branches, nonexistent branch creation, absent/stale/skipped/wrong-source checks, 401/403/404/422 handling, partial API failure, and post-PUT read-back.
   - **Preflight existing repositories.** Broad Semgrep rules may immediately be red. Refuse activation until every intended blocking context is genuinely green or has been deliberately baselined.
   - Treat the durable `TRIVY_BLOCKING` setting and gate self-protection as release blockers; otherwise `rebuild` or a workflow-editing PR can silently weaken the advertised enforcement.