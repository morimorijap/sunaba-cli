# Security CI stack

`.github/workflows/security-scan.yml` runs two gates on every push and
pull request. Full reference: `docs/security/README.md`.

| Check | Blocks |
|---|---|
| `SAST (Semgrep)` | Yes |
| `Dependency Scan (Trivy)` | Only when the repository variable `SUNABA_TRIVY_BLOCKING` is `true` |

## When a check fails

- **Semgrep:** fix the code. Only for a verified false positive, add
  `# nosemgrep: <rule-id> — <reason>` on that single line.
- **Trivy:** upgrade the dependency. Only when no fix is usable, add
  the ID to `.trivyignore` with a reason and an `exp:YYYY-MM-DD`.
- **Scanner error** ("did not complete", exit 2+): re-run it and fix
  the cause. The job fails closed on purpose.

## What not to do

- Don't edit `.github/workflows/security-scan.yml` to make a check
  pass: no removing `--error`, no `continue-on-error`, no `paths:`
  filters, no job-level `if:` that skips the scan, no renaming jobs.
- Don't change the `SUNABA_TRIVY_BLOCKING` repository variable.
- Don't create a `.semgrepignore` that excludes source directories,
  and don't allowlist whole files.
- Don't run `scripts/protect-branch.sh` without being asked. It
  changes repository settings for everyone.
