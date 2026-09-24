# 03 — LLM consultation brief (security CI gates, Phase 2)

> Self-contained brief sent to external reviewers (Codex CLI
> `gpt-5.5`, and fugu `fugu-ultra-v1.1` via Codex CLI). They have
> **not** seen the conversation that led here.

---

## You are reviewing

**`sunaba-cli`** (<https://github.com/morimorijap/sunaba-cli>, MIT)
is a Python CLI that scaffolds disposable devcontainer sandboxes for
AI coding agents (Claude Code, Codex CLI, Antigravity CLI). It is a
**template generator**. Users opt into "stacks"
(`--stack python`, `--stack nextjs`, `--stack secrets`, …). A stack
is a JSON file whose `_files` map copies templates **verbatim**:
there is no variable substitution and no per-language rendering.
`sunaba rebuild` re-emits every stack file and **always overwrites**.
Generated projects can be Python, Node (npm/pnpm/yarn/bun), or
anything else; the template cannot know which.

The existing `--stack secrets` already emits a hardened gitleaks
workflow. It has one job, named `Secret Scan (Gitleaks)`, and uses:

- actions SHA-pinned with `# vX.Y.Z` comments;
- a version-pinned, SHA-256-verified gitleaks binary;
- `permissions: contents: read`;
- a fail-closed guard.

Nothing makes any check *required*, so a red check does not block a
merge.

We are adapting ideas from
[northraystudio/maruda](https://github.com/northraystudio/maruda)
(MIT). maruda generates:

- Semgrep (`pip install semgrep==1.162.0`, `--config p/security-audit
  --config p/owasp-top-ten`, **no `--error`**, so it never fails on
  findings);
- Trivy through a SHA-pinned `aquasecurity/trivy-action` with
  `continue-on-error: true`;
- an npm/pnpm audit job that runs `npm ci` or `pnpm install` first;
- a `setup.sh --protect` that calls the classic branch-protection API
  on the default branch only;
- a "gate maturity ladder": Stage 0 gitleaks + semgrep block and
  trivy informs, then trivy blocks, then protection is applied, then
  thresholds tighten.

## Facts we verified (2026-09-24)

- **Semgrep 1.178.0 exit codes:** `semgrep scan` exits 0 with
  findings unless `--error` is passed (then 1); 2 or higher means
  failure. Measured on a sample with seven findings: 0 without
  `--error`, 1 with it.
- **Semgrep metrics:** `--metrics=off` works with `p/…` registry
  packs; only `--config auto` requires metrics.
- **Semgrep image:** `semgrep/semgrep:1.178.0` has multi-arch index
  digest `sha256:32e459…786b`. Semgrep's docs recommend a `container:`
  job with that image.
- **Semgrep rules:** registry rules are downloaded at run time. The
  engine is pinned; the rule content is not.
- **Trivy compromise:** Trivy was compromised in March 2026
  (GHSA-69fq-xp46-6x23, critical). A malicious v0.69.4 binary was
  published, 76 of 77 `trivy-action` tags and all `setup-trivy` tags
  were force-pushed to a credential stealer that read
  `Runner.Worker` memory, and malicious Docker Hub images followed.
  Commit-SHA pins and image digests were safe.
- **Trivy release:** Trivy v0.74.0 is an immutable release that
  publishes `trivy_0.74.0_checksums.txt` and a cosign bundle per
  asset.
- **Trivy measurements** (`trivy fs --scanners vuln --severity
  HIGH,CRITICAL --ignore-unfixed`, v0.74.0):
  - on an npm lockfile it reported prod deps only (lodash, minimist)
    and skipped a dev-only handlebars, with no `npm install`;
  - with `--exit-code 3`, findings exit 3 and errors (bad path,
    unreachable DB) exit 1;
  - it covers npm, pnpm, yarn, bun, uv, poetry, pip, Go, and Cargo
    lockfiles.
- **GitHub plans:** repository rulesets and classic branch protection
  are available on public repos (Free) and on private repos only with
  Pro/Team/Enterprise. **Neither works on free private repos.**
- **Required checks:** a required check whose workflow is skipped by
  `paths:` filters stays "Pending" and blocks merging. Check context
  names are job `name:` values.

## The proposal under review

A new opt-in stack **`--stack security-ci`** that emits:

**1. `.github/workflows/security-scan.yml`**, which has no `paths:`
filters, so every PR produces every context.

```yaml
name: security-scan
on: { pull_request: , push: , workflow_dispatch: }
permissions: { contents: read }
jobs:
  semgrep:
    name: SAST (Semgrep)
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    container:
      image: semgrep/semgrep:1.178.0@sha256:32e459968daabe7ab86968184a29109b9564aa00392401156f9788452b42786b
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
        with: { persist-credentials: false }
      - run: semgrep scan --error --metrics=off --config p/security-audit --config p/owasp-top-ten .

  trivy:
    name: Dependency Scan (Trivy)
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    env:
      # Stage 0: findings are reported as warnings. Set to "true" to block.
      TRIVY_BLOCKING: "false"
    steps:
      - uses: actions/checkout@<sha> # v7.0.1
        with: { persist-credentials: false }
      - name: Install Trivy (pinned, SHA-256 verified)   # v0.74.0, Linux-64bit, like gitleaks
      - name: Scan lockfiles
        run: |
          set +e
          trivy fs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed \
                   --exit-code 3 --no-progress .
          code=$?
          set -e
          case $code in
            0) ;;                                   # clean
            3) if [ "$TRIVY_BLOCKING" = true ]; then exit 1; fi
               echo "::warning title=Trivy::HIGH/CRITICAL vulnerabilities found (informational; set TRIVY_BLOCKING=true to gate)" ;;
            *) echo "::error title=Trivy did not complete::exit $code"; exit 1 ;;  # fail closed
          esac
```

Trivy replaces maruda's npm/pnpm audit. It needs no install step and
covers every ecosystem. Trivy's "informational" mode keeps the job
**green but annotated**, instead of using `continue-on-error`. That
means the job can be a required check from day one, and becomes
blocking by flipping one env var.

**2. `scripts/protect-branch.sh`**, which uses `gh api`:

- It creates or updates one repository ruleset named
  `sunaba security gates` (idempotent: it looks up the ruleset by
  name, then PUTs by id).
- Target: `~DEFAULT_BRANCH` plus any `--branch <name>` (for example
  `staging`). This fixes maruda protecting only the default branch.
- Rules:
  - `required_status_checks` for `SAST (Semgrep)` and
    `Dependency Scan (Trivy)`, plus `Secret Scan (Gitleaks)` when
    `.github/workflows/gitleaks.yml` exists;
  - `non_fast_forward` and `deletion`;
  - no bypass actors.
- `--strict` turns on "require branch up to date"; the default is
  off.
- `--dry-run` prints the JSON.
- It detects the free-private-repo case (403 or 404 with a plan
  message) and explains the options: make the repo public, upgrade
  the plan, or rely on the local pre-push hook.

**3. `docs/security/README.md`**: the maturity ladder, triage
(`# nosemgrep: <rule-id>` with a reason; a `.trivyignore` entry with
an expiry and a reason), and how to run the gates locally.

**4. `docs/security/THIRD_PARTY_NOTICES.md`**: maruda's MIT notice.
Adapted files carry header comments.

**5.** A short agent-instructions fragment ("never weaken or bypass
a gate; fix the finding or add a reasoned `nosemgrep`"), and `gh`
added to the host-tool check.

**Deliberately not shipped:** `.semgrepignore` and `.trivyignore`.
They are user-owned, and `rebuild` would overwrite them. Creating a
`.semgrepignore` also *replaces* Semgrep's default ignore list.

**sunaba dogfoods it:** sunaba's own repo adds the same
`security-scan.yml`, and a test asserts that it stays identical to
the template. Today both scanners report 0 findings on sunaba.

**Tests** follow the existing style: assertions on the workflow text,
the `run:` blocks extracted and executed with bash against fake or
real binaries, and `protect-branch.sh` run with a fake `gh` on
`PATH` that captures the API calls and payloads.

## Questions

1. **Rulesets vs classic branch protection** for a generated helper
   in 2026. Any pitfalls with `~DEFAULT_BRANCH`, idempotent update by
   name, `strict_required_status_checks_policy`, or requiring checks
   by context without an `integration_id`?
2. **Trivy delivery.** After GHSA-69fq-xp46-6x23, is a pinned,
   checksum-verified release binary better than a SHA-pinned
   `trivy-action` (which installs Trivy via `setup-trivy`)? Should we
   also verify the cosign bundle, given that it adds a cosign install
   step? Is replacing npm/pnpm audit with Trivy alone a coverage
   regression (advisory sources, transitive or prod-only accuracy)?
3. **Semgrep.** Is a digest-pinned `container:` image the right
   delivery, or `pip install semgrep==X` with `--require-hashes`, or
   `uvx`? Are `p/security-audit` + `p/owasp-top-ten` a sensible
   language-agnostic default? Registry rules are fetched live
   (engine pinned, rules not): is that acceptable, or should the
   template vendor a rules snapshot? Should Dependabot PRs be
   skipped, as Semgrep's sample config does?
4. **Informational mode.** Is "green job plus warning annotation,
   flip an env var to block" better than `continue-on-error`? Is our
   exit-code mapping for Trivy correct and fail-closed?
5. **Required contexts.** Should Trivy be required from day one,
   since it is green while informational? What should the script do
   when the workflows have never run, so GitHub doesn't yet know the
   contexts?
6. **User-owned ignore files.** Is not shipping `.semgrepignore` or
   `.trivyignore` right, given `rebuild` overwrites stack files?
7. **What are we missing** before this ships (for example the
   container job and `actions/checkout` on the Alpine-based Semgrep
   image, the DB download source and rate limits for Trivy,
   concurrency, SARIF)?

Please answer concisely, numbered to match. Cite sources for factual
claims.
