# Third-party notices

`sunaba-cli` adapts material from the projects below. Each adapted file
carries a header comment naming its upstream source. Credit does not
imply that the upstream authors endorse `sunaba-cli`.

Generated projects get their own copy of the relevant notices:
`--stack harness` emits `.claude/hooks/THIRD_PARTY_NOTICES.md`,
`--stack secrets` emits `docs/secrets/THIRD_PARTY_NOTICES.md` and
`--stack security-ci` emits `docs/security/THIRD_PARTY_NOTICES.md`, so
the license travels with the adapted files it covers.

## northraystudio/maruda

- Repository: <https://github.com/northraystudio/maruda>
- Adapted from commit
  [`99dd7981e7947e4ae500225f811f5db0a03c3c7e`](https://github.com/northraystudio/maruda/tree/99dd7981e7947e4ae500225f811f5db0a03c3c7e)
  (2026-09-20); the `.semgrep/` project-rules check and conventions from
  [`5f9b323ccb69d325677006c00643b4dc08699a00`](https://github.com/northraystudio/maruda/tree/5f9b323ccb69d325677006c00643b4dc08699a00)
  (2026-11-07)
- Design records: [`thinking/2026-09-24-maruda-adoption/`](thinking/2026-09-24-maruda-adoption/),
  [`thinking/2026-09-24-security-ci-gates/`](thinking/2026-09-24-security-ci-gates/),
  [`thinking/2026-11-21-maruda-followup/`](thinking/2026-11-21-maruda-followup/)

| sunaba file | Adapted from | What was taken |
|---|---|---|
| `src/sunaba_cli/templates/secrets/github-workflow-gitleaks.yml` | `harness/templates/github/security-scan.yml` (L22-43) | Running gitleaks from a version-pinned, SHA-256-verified release archive; SHA-pinned `actions/checkout`; full-history scan |
| `src/sunaba_cli/templates/secrets/gitleaks.toml` | `harness/templates/github/gitleaks.toml` | `[extend] useDefault = true`; the "allowlist the smallest possible unit, never whole files or directories" policy |
| `.github/workflows/ci.yml` (`gitleaks` job) | `harness/templates/github/security-scan.yml` (L22-43) | Same install step as above |
| `tests/test_supply_chain.py` | `harness/tests/run.sh` (L248-264) | Auditing every `uses:` line for a 40-hex SHA pin, and a probe proving the audit rejects a mutable tag |
| `src/sunaba_cli/templates/security-ci/github-workflow-security-scan.yml` (also `.github/workflows/security-scan.yml`) | `harness/templates/github/security-scan.yml` (L45-84) | Semgrep with `p/security-audit` + `p/owasp-top-ten`; Trivy fs scan of HIGH/CRITICAL with `--ignore-unfixed`, informational at first |
| `src/sunaba_cli/templates/security-ci/scripts/protect-branch.sh` | `harness/scripts/setup.sh` (L881-918) | Making the security jobs required checks via `gh api`, with force push and deletion blocked and no admin bypass |
| `src/sunaba_cli/templates/security-ci/docs/README.md` | `README.md` (L147-156) | The gate maturity ladder |
| `src/sunaba_cli/templates/security-ci/github-workflow-security-scan.yml` (also `.github/workflows/security-scan.yml`), at `5f9b323` | `harness/templates/github/security-scan.yml` (L80-88) | Passing `--config .semgrep` only when it holds a rule file that is not a `*.test.yml` / `*.test.yaml` fixture |
| `src/sunaba_cli/templates/security-ci/docs/README.md` ("Project rules"), at `5f9b323` | `docs/semgrep-rules.md` | One rule per `semgrep --test` fixture; YAML fixtures named `*.test.yaml`; standard `metadata:` keys; authorization and business logic are not rules |
| `src/sunaba_cli/templates/harness/claude/hooks/pre-bash-guard.sh`, at `5f9b323` | `harness/templates/hooks/pre-bash-guard.sh` | The whole hook: argument-level `rm` / `git push` judgement, redirection stripping, substitution collapsing, the regex floor, the deny list. sunaba drops the pip toggle and reports a missing `jq` |
| `tests/test_bash_guard.py`, at `5f9b323` | `harness/tests/run.sh` (L193-279, L283-299) | The deny/allow matrix and the no-temp-file and broken-input checks |

```
MIT License

Copyright (c) 2026 NorthRay Studio株式会社

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
