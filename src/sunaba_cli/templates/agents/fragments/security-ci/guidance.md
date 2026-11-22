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

## Project Semgrep rules

When a confirmed bug can be described as a code pattern, propose a rule
in `.semgrep/rules/<rule-id>.yml` with a `semgrep --test` fixture next
to it (`docs/security/README.md`, "Project rules"). Project rules block
merges like registry rules; run the rule over the whole repository and
show the user every hit before adding it. Never put application code
in `.semgrep/`: it is excluded from the scan.

## What not to do

- Don't edit `.github/workflows/security-scan.yml` to make a check
  pass: no removing `--error`, no `continue-on-error`, no `paths:`
  filters, no job-level `if:` that skips the scan, no renaming jobs.
- Don't change the `SUNABA_TRIVY_BLOCKING` repository variable.
- Don't create a `.semgrepignore` that excludes source directories,
  and don't allowlist whole files.
- Don't delete or weaken a rule in `.semgrep/` to make a check pass.
- Don't run `scripts/protect-branch.sh` without being asked. It
  changes repository settings for everyone.
