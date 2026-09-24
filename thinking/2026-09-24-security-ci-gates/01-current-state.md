# 01 — Current state: what gates a generated project's merges today

> Part of [`2026-09-24-security-ci-gates/`](README.md). Snapshot of
> `main` at `24cf69c` (sunaba 0.2.3, 2026-09-24).

## What sunaba already generates

| Concern | Where | Enforced where |
|---|---|---|
| Secret scanning | `--stack secrets`: gitleaks pre-commit hook plus `.github/workflows/gitleaks.yml` (hardened in [PR #27](../2026-09-24-maruda-adoption/05-proposal.md)) | CI job `Secret Scan (Gitleaks)`, which **nothing marks as required** |
| Local verification | `--stack harness`: `.claude/hooks/verify.sh` (pytest / npm lint, typecheck, test) run by a Claude Code Stop hook | Agent session only |
| Push guard | `--stack autopilot`: `.githooks/pre-push` refuses `refs/heads/main\|master` | Local, bypassable with `--no-verify`; `SECURITY.md` says so |
| Dependency updates | `base/dependabot.yml`: `devcontainers`, `docker`, `github-actions` weekly; plus `pip` / `npm` via `_dependabot` from the `python` / `nextjs` stacks | Update PRs only — no vulnerability gate |

## What is missing

1. **No SAST.** Nothing inspects code for injection, SSRF, XSS, or
   unsafe deserialisation. Coding agents write a lot of glue code at
   trust boundaries (route handlers, SQL, subprocess calls). That is
   exactly where pattern-based SAST pays off.
2. **No dependency-vulnerability gate.** Dependabot proposes
   upgrades, but a PR that adds a package with a known CRITICAL CVE
   merges green.
3. **No server-side merge gate.** Even the gitleaks job is advisory:
   without branch protection, or a ruleset marking it required, a red
   check does not block the merge button. The autopilot pre-push hook
   is local and opt-out.
4. **No documented promotion path.** Users get either nothing or,
   with `secrets`, one scanner. Nothing explains how to go from
   "informational" to "blocking" without drowning a new project in
   false positives.

The enterprise essay already lists "Security Scan" and "Dependency
Scan" among the minimum quality gates
([`2026-05-26-enterprise-development/README.md`](../2026-05-26-enterprise-development/README.md),
§6). The
[rules-and-autonomy proposal](../2026-05-09-rules-and-autonomy/05-proposal.md)
settled on "branch protection via git hook + permission deny" and
never discussed GitHub-side protection.

## Constraints of the generator

These shape the design (see `src/sunaba_cli/cli.py`):

- **`_files` copies templates verbatim** (`_build_stack_files`). There
  is no variable substitution and no per-language emission. So a
  generated workflow cannot be tailored to "this is a pnpm project";
  it has to **detect at CI runtime**. maruda does the opposite: its
  installer interviews the user and renders language-specific jobs.
- **`rebuild` always overwrites** stack files, and currently drops
  `--no-devcontainer` mode and the AGENTS.md USER region. Anything a
  user is expected to edit (ignore lists, thresholds) must survive
  that or be documented as user-owned.
- **Host requirement warnings** (`_STACK_HOST_REQUIREMENTS`) exist
  for `--no-devcontainer`; a branch-protection helper needs `gh`.
- **`_write_files` chmods only `*.sh`.** Scripts need the extension.
- **No PyYAML** in tests (click is the only runtime dependency);
  workflow tests assert on text or execute extracted `run:` blocks
  (the pattern PR #27 introduced).

## Evidence gathered so far

- maruda's Semgrep job (`security-scan.yml:78-84` at `99dd798`) omits
  `--error`. Measured on 2026-09-24 with Semgrep 1.178.0 against a
  seven-finding Flask/Express sample (`shell=True` with request
  input, string-formatted SQL, `eval(req.query.code)`):
  `semgrep scan --metrics=off --config p/security-audit --config
  p/owasp-top-ten .` exits **0**, and with `--error` it exits **1**.
  Both runs used registry rulesets with `--metrics=off` and neither
  errored.
- maruda's `--protect` (`setup.sh:881-918`) protects only the default
  branch, uses the classic protection endpoint, and couples required
  contexts to job display names. Its `ci.yml` uses `paths:` filters,
  so a docs-only PR never produces the required contexts.
