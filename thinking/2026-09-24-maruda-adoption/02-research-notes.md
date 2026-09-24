# 02 — Research notes: what maruda does, and what to take

> Part of [`2026-09-24-maruda-adoption/`](README.md).

## Source

[northraystudio/maruda](https://github.com/northraystudio/maruda) —
MIT License, Copyright (c) 2026 NorthRay Studio株式会社. Read at
commit
[`99dd798`](https://github.com/northraystudio/maruda/tree/99dd7981e7947e4ae500225f811f5db0a03c3c7e)
(2026-09-20). All 51 tracked files were read; its own test suite
(`bash harness/tests/run.sh`) passed 137/137 locally.

The pointer to maruda came from a ChatGPT research conversation
("CIセキュリティ調査", 2026-09-24) that summarised maruda's CI
security gates and flagged the Semgrep `--error` gap. Every claim
below was re-checked against the source; the ChatGPT summary itself
is not cited as evidence.

## What maruda is

A Claude Code plugin (repo root = plugin + marketplace, ADR 0005)
shipping ten skills, plus a bash installer
(`harness/scripts/setup.sh`, 956 lines) that writes hooks, rules,
`CLAUDE.md`, and GitHub workflows into a target project. It frames
this as "harness engineering" with a **gate maturity ladder**
(README.md:147-156): Stage 0 gitleaks + semgrep block and trivy is
informational → Stage 1 trivy blocks → Stage 2 branch protection →
Stage 3 stricter thresholds.

## Ideas relevant to Phase 1 (secret scanning / supply chain)

| # | maruda | Where | Take? |
|---|---|---|---|
| M1 | Gitleaks run from the **release tarball, version-pinned and SHA-256-verified** before execution, instead of `gitleaks-action` | `harness/templates/github/security-scan.yml:22-43` | **Yes.** Also removes the org-license failure (defect 2). |
| M2 | Full-history scan: `fetch-depth: 0` + `--log-opts="--all"` | same, L27-28, L43 | **Yes.** |
| M3 | Every `uses:` pinned to a 40-hex SHA with a `# vX.Y.Z` comment | all three workflow templates | **Yes.** |
| M4 | A test that audits every generated `uses:` line for SHA pins, plus a probe proving the detector itself flags a mutable tag ("guard the guard") | `harness/tests/run.sh:248-264` | **Yes**, ported to pytest. |
| M5 | `.gitleaks.toml` with `[extend] useDefault = true` and the policy "allowlist the smallest possible unit … never whole files or directories" | `harness/templates/github/gitleaks.toml:1-14` | **Yes** — `useDefault` is the fix for defect 1. |
| M6 | `continue-on-error` only on informational scanners; required checks never include advisory jobs | `security-scan.yml:53-64`; `setup.sh:894-901` | Later (Phase 2). |

## Where we deliberately differ from maruda

- **`gitleaks git`, not `gitleaks detect`.** `detect` is the pre-8.19
  spelling; `git` is the current subcommand (gitleaks README v8.30.1)
  and is what gitleaks' own pre-commit hook calls.
- **`--redact`.** maruda prints matched secrets to the Actions log
  (`--verbose` without redaction). On a public repo the log is
  public; redact.
- **`permissions: contents: read`.** maruda's gitleaks job has no
  `permissions:` block (its trivy job does). We set it at workflow
  level.
- **Semgrep `--error`.** maruda's Semgrep job lacks `--error`
  (`security-scan.yml:80-84`), so its "hard gate" exits 0 with
  findings. Recorded here for Phase 2; not relevant to Phase 1.

## Other maruda ideas recorded for later phases

- `.new` proposal files instead of overwriting (`setup.sh:183-198`);
  jq merge of `settings.json` (`setup.sh:248-256`).
- `setup.sh --protect` → `gh api PUT …/branches/$BRANCH/protection`
  (`setup.sh:881-918`); it protects only the default branch even
  when an integration branch is configured.
- Strict CI preflights: missing npm scripts / zero pytest tests fail
  with `::error` annotations (`setup.sh:462-640`).
- Skills: `vulnerability-scan` (two-layer automated + LLM manual
  OWASP review, output to `docs/security-audit/*.md|json`),
  `report-to-issues`, `software-evaluation`, `spec-doc`.
- PreToolUse bash-guard hook (`harness/templates/hooks/pre-bash-guard.sh`)
  with a deny/allow test matrix; its regex has false positives
  (`--follow-tags` matches `-f`).

## Attribution approach

MIT requires the copyright and permission notice to be included
with "all copies or substantial portions". Phase 1 adapts short
workflow snippets and a policy sentence rather than copying files,
but we credit anyway, three ways:

1. A header comment in each adapted template naming the upstream
   file at the pinned commit and listing our changes.
2. A root `THIRD_PARTY_NOTICES.md` carrying maruda's full MIT notice.
3. `## Sources` in [05-proposal.md](05-proposal.md) and an
   Acknowledgements line in both READMEs.
