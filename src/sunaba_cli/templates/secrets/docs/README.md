# docs/secrets/

How and where to keep secrets out of this repository, by cloud.

> **Read first:** the AGENTS.md "Secrets" section. Tools and
> documentation help, but they do not protect a real, billing-enabled
> API key from an autonomous agent that decides to exfiltrate it.
> The only architectural mitigation against that failure mode is the
> [Azure Foundry → APIM → Gemini → Cosmos](azure-foundry-apim-gemini-cosmos.md)
> pattern (or a non-Azure equivalent gateway).

## Pages

- [Vercel](vercel.md)
- [Firebase / Google Cloud](firebase.md)
- [AWS](aws.md)
- [GCP](gcp.md)
- [Azure: Foundry → APIM → Gemini → Cosmos (the "key behind a proxy" pattern)](azure-foundry-apim-gemini-cosmos.md)

## Defense-in-depth, in order

1. **`.gitignore`** — file never enters the index.
2. **Pre-commit hook (gitleaks)** — file blocked at `git commit`.
3. **GitHub secret scanning + push protection** — push blocked
   server-side. Enable in repo settings.
4. **Provider rotation hooks** — major providers participate in
   GitHub's partner program and auto-rotate found keys.
5. **`git filter-repo` / GitHub support** — last-resort cleanup.

`sunaba`'s `--stack secrets` ships layers 1 and 2, plus a CI scan
(`.github/workflows/gitleaks.yml`): every commit a pull request adds,
and the full history on every push — it catches commits made with
`--no-verify` or from a machine without the hook. Layer 3 you enable.
Layers 4 and 5 are out of scope.

## When gitleaks reports a finding

1. **Real secret:** remove it from the current tree, then rotate or
   revoke it at the provider. Deleting it from the file (or even from
   history) does not un-leak it. Check the provider's logs for use
   during the exposure window.
2. **After rotation, or a false positive:** add that one finding's
   `Fingerprint` (printed by `gitleaks git --report-path r.json`, e.g.
   `<commit>:<file>:<rule>:<line>`) to a `.gitleaksignore` file at the
   repository root, with a comment saying why. Fingerprints are the
   smallest possible unit — prefer them over widening `.gitleaks.toml`.
   Review `.gitleaksignore` changes like code; consider a CODEOWNERS
   entry for it, `.gitleaks.toml`, and `.github/workflows/`.
3. **Never** allowlist a whole file or directory in `.gitleaks.toml`,
   and never weaken the CI workflow to get a green check. The CI scan
   ignores inline `gitleaks:allow` comments on purpose.

Adopting this stack in a repository with a long history? The CI scan
reads every commit on push, so a secret leaked years ago fails the
first run. Triage those findings once with the steps above. With too
many to review one by one, gitleaks' `--baseline-path` can exclude an
existing report — rotate first, review the baseline before committing
it, and plan to burn it down.

If the CI job fails with "gitleaks did not complete", git itself
reported an error during the scan. gitleaks would otherwise report
"no leaks found" without having scanned anything, so the job fails
closed; fix the git error rather than the workflow.

## Credits

Parts of the generated workflow and `.gitleaks.toml` are adapted from
northraystudio/maruda — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
