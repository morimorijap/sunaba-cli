# 02 — Research notes

> Part of [`2026-09-24-security-ci-gates/`](README.md). Facts
> verified on 2026-09-24 against the linked sources, or measured
> locally as stated.

## maruda's gates (the starting point)

[northraystudio/maruda](https://github.com/northraystudio/maruda)
@ [`99dd798`](https://github.com/northraystudio/maruda/tree/99dd7981e7947e4ae500225f811f5db0a03c3c7e)
(MIT, © 2026 NorthRay Studio株式会社) generates:

- `security-scan.yml` (`harness/templates/github/security-scan.yml`):
  - gitleaks (adopted in PR #27);
  - `trivy-fs` via `aquasecurity/trivy-action@ed142fd… # v0.36.0`
    with step-level `continue-on-error: true` (L45-64);
  - `semgrep` via `pip install semgrep==1.162.0`, then
    `semgrep --config p/security-audit --config p/owasp-top-ten
    <lang packs> .` (L66-84), **without `--error`**;
  - an npm/pnpm audit job that needs `npm ci` or `pnpm install`
    first (`setup.sh:710-741`).
- `setup.sh --protect` (`setup.sh:881-918`): classic
  `PUT …/branches/$BRANCH/protection` with `strict: true`,
  `enforce_admins: true`, no force-push or deletion, and contexts
  equal to job names. Trivy and PR Agent are deliberately excluded.
- A **gate maturity ladder** (README.md:147-156): Stage 0
  gitleaks + semgrep block and trivy informs → 1 trivy blocks →
  2 `--protect` → 3 stricter rulesets and audit level.
- `.semgrepignore` restating Semgrep's defaults, with the policy
  "smallest unit; prefer `# nosemgrep: <rule-id>` with a reason".

## Semgrep

- **Exit codes** ([CLI reference](https://semgrep.dev/docs/cli-reference)):
  "0: … found no errors (or did find errors, but the `--error` flag
  is **not** being used). 1: … found issues in your code (while using
  the `--error` flag). 2: Semgrep failed." Codes 3-14 are other
  failures.
- **Measured** with Semgrep 1.178.0 on a seven-finding sample:
  exit 0 without `--error`, exit 1 with it (see 01).
- **Metrics:** `--metrics=off` works with registry packs
  (`p/security-audit`, `p/owasp-top-ten`). Measured, and the only
  source-level restriction is on `--config auto`
  ([`Scan_CLI.ml`](https://github.com/semgrep/semgrep/blob/develop/src/osemgrep/cli_scan/Scan_CLI.ml):
  "Cannot create auto config when metrics are off").
- **Recommended CI shape**
  ([sample CI configs](https://semgrep.dev/docs/semgrep-ci/sample-ci-configs)):
  a job with `container: image: semgrep/semgrep`,
  `permissions: contents: read`, and `semgrep scan` for Community
  Edition.
- **Image:** `semgrep/semgrep:1.178.0` (released 2026-09-23). Its
  multi-arch index digest is
  `sha256:32e459968daabe7ab86968184a29109b9564aa00392401156f9788452b42786b`
  (Docker Hub tags API and registry HEAD agree). `latest` still
  pointed at 1.177.0 when checked.
- **`.semgrepignore`** replaces the defaults: "In the absence of a
  user-generated `.semgrepignore`, Semgrep refers to its repository's
  default template"
  ([ignoring files](https://semgrep.dev/docs/ignoring-files-folders-code)).
  The defaults already skip `node_modules/`, `build/`, `dist/`,
  `vendor/`, `.venv/`, `test/`, `tests/`, and `*.min.js`.
- **Registry rules are fetched at run time** from semgrep.dev. The
  engine version is pinned; the rule content is not.
- **Dogfood:** on sunaba itself the two packs report 0 findings
  (one warn-level partial parse of a bash arithmetic line).

## Trivy and the March 2026 supply-chain compromise

- [GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23)
  (critical, published 2026-03-21): "On March 19, 2026, a threat
  actor used compromised credentials to publish a malicious Trivy
  v0.69.4 release, force-push 76 of 77 version tags in
  `aquasecurity/trivy-action` to credential-stealing malware, and
  replace all 7 tags in `aquasecurity/setup-trivy` with malicious
  commits." Malicious Docker Hub images 0.69.5 and 0.69.6 followed on
  March 22. The payload read `Runner.Worker` memory and swept runner
  credentials. The advisory recommends: "Pin GitHub Actions to full,
  immutable commit SHA hashes." Images referenced by digest were not
  affected.
- Lesson for a template generator: a tag-pinned
  `trivy-action@0.x` in any generated project would have run the
  credential stealer. maruda's SHA pin (`ed142fd`, v0.36.0, post-incident)
  is safe. But the action installs Trivy through `setup-trivy`,
  which is a second indirection that has to be trusted.
- **Release binary:** Trivy v0.74.0 (2026-08-14, immutable release,
  commit `e1fd17a0…b994`). `trivy_0.74.0_checksums.txt` lists
  `2ae6fe3e…4371a  trivy_0.74.0_Linux-64bit.tar.gz`. Every asset
  also has a cosign `.sigstore.json` bundle.
- **Measured** with the checksum-verified macOS build of 0.74.0:
  - `trivy fs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`
    on an npm lockfile with lodash 4.17.20, minimist 1.2.5, and
    dev-only handlebars 4.7.6 → exit 1, three findings (lodash ×2,
    minimist). **The dev dependency was excluded by default.**
  - On sunaba's `uv.lock` → exit 0.
- One tool covers npm, pnpm, yarn, bun, uv, poetry, pip, Go, Cargo,
  and more lockfiles, with no install step. maruda's npm/pnpm audit
  job needs `npm ci` or `pnpm install` (running install scripts in
  CI) and is Node-only.

## Lockfile-only audits (alternatives measured)

npm 11 (`npm audit --omit=dev --audit-level=high`), pnpm 12
(`pnpm audit --prod --audit-level high`), yarn berry 4
(`yarn npm audit -R --environment production --severity high`), and
bun 1.4 (`bun audit --prod --audit-level=high`) all work with only a
lockfile and exit 1 on findings. Each needs its own toolchain on the
runner, and at runtime we cannot tell which one a project uses
without detection logic.

## GitHub merge gates

- **Rulesets:** `POST /repos/{o}/{r}/rulesets`
  ([docs](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset)).
  - `conditions.ref_name.include` accepts `~DEFAULT_BRANCH`.
  - A `required_status_checks` rule takes `{context}` entries and
    `strict_required_status_checks_policy`.
  - `non_fast_forward` and `deletion` rules block force pushes and
    deletions.
  - Multiple rulesets can apply to a branch, while "only one branch
    protection rule applies"
    ([about rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)).
- **Classic protection:** `PUT …/branches/{b}/protection`.
  `required_status_checks.contexts` is deprecated in favour of
  `checks`.
- **Plan limits:** both are "available in public repositories with
  GitHub Free … and in public and private repositories with GitHub
  Pro, GitHub Team, and GitHub Enterprise Cloud". Neither works on a
  **free private** repository.
- **Context names** are the job's `name:` (else the job id). GitHub
  warns: "make sure that job names are unique across all workflows."
- **Path filters:** "A workflow is skipped by path filtering … |
  Associated checks stay in a 'Pending' state and block merging |
  Avoid requiring workflows that can be skipped"
  ([troubleshooting required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)).
  A job skipped by `if:` reports Success.
