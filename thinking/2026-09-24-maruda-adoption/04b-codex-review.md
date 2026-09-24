# 04b — Codex CLI review

> Reviewer: **Codex CLI** 0.156.1, model `gpt-5.5`,
> `model_reasoning_effort=high`. Invoked non-interactively
> (`codex --search exec -s read-only`) against
> [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) on
> 2026-09-24. Web search was active; observed queries covered the
> gitleaks README (configuration, `--log-opts`), GitHub's secure-use
> reference and workflow `permissions`, repository security
> advisories, runner labels, and the MIT License text.
>
> Output reproduced verbatim below. Maintainers' synthesis lives in
> [`05-proposal.md`](05-proposal.md).

---

1. **Defect 1 Fix.** Yes: `[extend] useDefault = true` is the right fix for gitleaks 8.30. Gitleaks documents that a custom config replaces defaults unless you extend them, and `.gitleaks.toml` in the target path is auto-loaded. Source: [Gitleaks configuration docs](https://github.com/gitleaks/gitleaks#configuration).  
   I would keep top-level `[allowlist]` for Phase 1 unless you intentionally require gitleaks `>=8.25`; `[[allowlists]]` is the newer form, but the old form remains a backwards-compatibility shim until v9 in current source. Source: [gitleaks config.go](https://github.com/gitleaks/gitleaks/blob/master/config/config.go).  
   The `.env*.example` path allowlist is narrowly anchored, but it is still a filename-level bypass. Better default: only allowlist exact generated placeholder patterns/fingerprints if feasible. If you keep the path allowlist, document loudly that real secrets in `.env.example` will be ignored.

2. **Action → Binary.** Dropping `gitleaks-action` is reasonable: it avoids the org-repo license trap, gives a pinned binary, and reduces opaque action behavior. You lose PR comments, summaries, and artifact/report conveniences; gitleaks can still emit SARIF if you later add upload, but that requires broader permissions such as `security-events: write`. Sources: [gitleaks-action v2 license/benefits](https://github.com/gitleaks/gitleaks-action/blob/master/v2.md), [Gitleaks reporting](https://github.com/gitleaks/gitleaks#reporting), [GitHub permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions).  
   Install step is mostly fine for `ubuntu-latest`: GitHub’s standard Ubuntu runner is x64. Source: [GitHub runner labels](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job). I’d improve it with `set -euo pipefail`, `curl --retry`, `mktemp -d` + `trap`, and install to `$RUNNER_TEMP/bin` to avoid `sudo`.  
   Full history on every PR is defensible for newly generated repos, but hostile to existing repos. I’d default to full history on `push`/`workflow_dispatch`, and document an optional PR range scan using `--log-opts`, which gitleaks supports. Source: [gitleaks git log-opts](https://github.com/gitleaks/gitleaks#commands).

3. **Existing Historical Leaks.** Document both, but recommend `.gitleaksignore` fingerprints first for a small number of known, rotated, reviewed findings. It is precise and reviewable. Source: [Gitleaks `.gitleaksignore`](https://github.com/gitleaks/gitleaks#gitleaksignore).  
   `--baseline-path` is better for onboarding a repo with many historical findings, but it is easier to let it become permanent debt. If documented, say: rotate/revoke first, generate a redacted baseline, review it, and plan to burn it down. Source: [Gitleaks baseline](https://github.com/gitleaks/gitleaks#creating-a-baseline).

4. **Pin Maintenance.** Frozen pre-commit SHAs are worth it for this stack. `pre-commit autoupdate --freeze` is an official workflow and stores commit hashes with `# frozen:` comments. Source: [pre-commit autoupdate docs](https://pre-commit.com/#pre-commit-autoupdate).  
   Avoid two unsynchronized truth sources: add one update script/test that sets `GITLEAKS_VERSION`, tarball SHA256, and frozen pre-commit rev together, then asserts the pre-commit comment matches the binary version. Dependabot will help with SHA-pinned GitHub Actions and version comments, but not the gitleaks binary/pre-commit pair. Sources: [Dependabot GitHub Actions docs](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions), [Dependabot SHA comment updates](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/).  
   `actions/checkout` v7 is fine for GitHub-hosted runners if SHA-pinned. For GHES/old self-hosted runner audiences, v4 is more conservative. GitHub recommends full-length SHA pinning. Source: [GitHub secure use reference](https://docs.github.com/en/actions/reference/security/secure-use).

5. **Disclosure.** Use several channels: release notes, a GHSA, README note, and a `sunaba` warning when it detects the old no-op config or missing `[extend] useDefault = true`. GitHub advisories are intended for publishing vulnerability information for public repos. Source: [GitHub repository security advisories](https://docs.github.com/en/code-security/concepts/vulnerability-reporting-and-management/repository-security-advisories).  
   I would call this a vulnerability: a security scanner template silently disabled the scanner’s default rules, creating false assurance in downstream projects. Severity can be modest/medium, but the impact is real because users opted into `--stack secrets`.

6. **Attribution.** The three-part credit is appropriate and a little generous, which is good. MIT requires preserving the copyright and permission notice for copies or substantial portions. Source: [MIT License text](https://opensource.org/license/mit).  
   Make sure `THIRD_PARTY_NOTICES.md` includes maruda’s copyright notice, MIT text, repo URL, commit, and adapted files. Header comments in generated templates are useful because those files leave sunaba and enter user repos. Avoid implying endorsement.

7. **What’s Missing.** Add tests that prove `.gitleaks.toml` is auto-loaded, not only explicit-config loaded; prove `.env` is detected while `.env.example` is allowed; and prove the integration test fails if `[extend]` is removed.  
   Add `timeout-minutes`, consider `ubuntu-24.04` instead of `ubuntu-latest` for less image drift, and keep `pull_request_target` out of generated workflows.  
   Do not generate or overwrite users’ `.gitleaksignore`; document it as a user-owned escape hatch. Since `sunaba rebuild` overwrites stack files, any generated ignore file would become dangerous maintenance debt.