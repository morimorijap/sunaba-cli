# 03 — LLM consultation brief (secret-scan hardening, Phase 1)

> Self-contained brief sent to external reviewers (Codex CLI
> `gpt-5.5`, and fugu `fugu-ultra-v1.1` via Codex CLI). They have
> **not** seen the conversation that led here.

---

## You are reviewing

A small open-source CLI, **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>, MIT). It scaffolds
disposable devcontainer sandboxes for AI coding agents (Claude Code,
Codex CLI, Antigravity CLI). It is a **template generator**: it
writes files into a new project, then gets out of the way. Users opt
into "stacks" (`--stack python`, `--stack secrets`, …); each stack is
a JSON file whose `_files` map copies templates verbatim (no
variable substitution) into the project. `sunaba rebuild` re-emits
all stack files and **always overwrites** them.

## Background

`--stack secrets` emits, among docs:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
```

```toml
# .gitleaks.toml
title = "sunaba generated gitleaks config"

[allowlist]
description = "Templates and example files only — never real local secrets."
paths = [
  '''^\.env\.example$''',
  '''^\.env\..*\.example$''',
]
```

```yaml
# .github/workflows/gitleaks.yml
name: gitleaks
on: { pull_request: , push: , workflow_dispatch: }
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
```

We found, and reproduced with gitleaks 8.30.1:

1. **The `.gitleaks.toml` disables all detection.** Gitleaks loads
   `<repo>/.gitleaks.toml` automatically, and a config without
   `[extend] useDefault = true` has zero rules. With the file present
   a repo containing an AWS key id and a GitHub PAT scans clean
   (exit 0); without it, 2 leaks (exit 1). Affects the pre-commit
   hook and CI alike. Adding `[extend] useDefault = true` fixes it
   and the `.env.example` allowlist still works.
2. **`gitleaks-action@v2` needs a paid `GITLEAKS_LICENSE` on
   organization repos**; the template does not set one, so the job
   fails on org repos.
3. Actions pinned by mutable tag; gitleaks binary version chosen by
   the action, not verified; no `permissions:`.

A related project, [northraystudio/maruda](https://github.com/northraystudio/maruda)
(MIT), runs gitleaks from the release tarball with a pinned version
and SHA-256 check, SHA-pins every action, and has a test that audits
all generated `uses:` lines for 40-hex pins (with a probe that proves
the audit catches a tag). We intend to adopt those ideas, with
credit.

## The proposal under review

**A. `.gitleaks.toml`**

```toml
# Adapted from northraystudio/maruda (MIT) … (header comment)
title = "sunaba generated gitleaks config"

# Inherit gitleaks' default rules. Without this block a custom config
# REPLACES the defaults and detects nothing.
[extend]
useDefault = true

# Allowlist the smallest possible unit (an exact regex, a stopword, or
# a fingerprint in .gitleaksignore). Do not allowlist whole
# directories — that becomes a secret-scan bypass.
[allowlist]
description = "Committed env templates only — never real local secrets."
paths = [
  '''^\.env\.example$''',
  '''^\.env\..*\.example$''',
]
```

**B. `.github/workflows/gitleaks.yml`**

```yaml
name: gitleaks

on:
  pull_request:
  push:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  scan:
    name: Secret Scan (Gitleaks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Install gitleaks (pinned + SHA-256 verified)
        env:
          GITLEAKS_VERSION: 8.30.1
          GITLEAKS_SHA256: 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
        run: |
          curl -sSfL -o gitleaks.tar.gz \
            "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
          echo "${GITLEAKS_SHA256}  gitleaks.tar.gz" | sha256sum -c -
          tar -xzf gitleaks.tar.gz gitleaks
          sudo install gitleaks /usr/local/bin/gitleaks
          rm -f gitleaks gitleaks.tar.gz

      - name: Scan full git history
        run: gitleaks git --redact --verbose --log-opts="--all" .
```

**C. `.pre-commit-config.yaml`** — `rev: 83d9cd684c87d95d656c1458ef04895a7f1cbd8e  # frozen: v8.30.1`
(the commit behind tag v8.30.1; pre-commit's `autoupdate --freeze`
style).

**D. Tests** — (a) a structural test that `.gitleaks.toml` contains
`useDefault = true`; (b) an integration test that runs the real
`gitleaks` binary (skipped when absent) on a temp repo with a planted
key and asserts the generated config *detects* it and still
allowlists `.env.example`; (c) a SHA-pin audit over every `uses:`
line of every generated workflow, plus a probe that the audit
regex rejects `@v4`; (d) the pre-commit `rev` must be 40-hex.

**E. sunaba's own CI** — SHA-pin `actions/checkout` / `setup-uv`,
add `permissions: contents: read`, and add a gitleaks job (same
install step) that scans sunaba's full history and runs test (b)
with the binary present. Two historical false positives (a Markdown
heading matched by `generic-api-key`) go into a root
`.gitleaksignore` by fingerprint.

**F. Attribution** — header comment in each adapted template naming
the upstream file at commit `99dd798` and our changes; a root
`THIRD_PARTY_NOTICES.md` with maruda's MIT notice; `## Sources` in
the proposal; Acknowledgements in README.

Pins are maintained by Dependabot: generated projects already get a
`dependabot.yml` with the `github-actions` ecosystem, which updates
SHA pins and their `# vX.Y.Z` comments. `GITLEAKS_VERSION`/`SHA256`
and the pre-commit `rev` are **not** Dependabot-managed.

## Questions

1. **Defect 1 fix.** Is `[extend] useDefault = true` sufficient and
   correct for gitleaks 8.30? Should we migrate the deprecated-ish
   top-level `[allowlist]` to the newer `[[allowlists]]` array form,
   or does that break older gitleaks versions users may have
   locally? Is a *path* allowlist for `.env*.example` consistent with
   "smallest unit" or should it be narrower?
2. **Action → binary.** Trade-offs of dropping `gitleaks-action`
   (loses PR comments / job summary / SARIF upload)? Anything wrong
   with the install step (runner arch, `sudo`, `rm`)? Is
   `--log-opts="--all"` on every PR acceptable, or should PRs scan
   only `base..head` and push/dispatch scan everything?
3. **Existing projects with historical leaks.** A full-history scan
   will turn CI red immediately on a repo that already leaked (even
   if rotated). Should the template document `.gitleaksignore`
   fingerprints, `--baseline-path`, or both? Which is the better
   default guidance?
4. **Pin maintenance.** Is a frozen SHA in pre-commit worth the
   friction vs. a tag? How should we keep `GITLEAKS_VERSION`/`SHA256`
   and the pre-commit rev in sync (they are two places)? Is
   `actions/checkout` v7 a safe default for generated projects on
   GitHub-hosted runners, or should templates stay on an older
   major?
5. **Disclosure.** Every project generated with `--stack secrets`
   had a silent no-op scanner. `sunaba rebuild` would overwrite the
   file with the fix, but users must run it. How should we notify:
   release notes only, a GitHub Security Advisory on sunaba-cli, a
   `sunaba` warning when it detects the old file, or several? Is this
   a vulnerability in sunaba by the usual definition?
6. **Attribution.** Is the three-part credit (header comment, NOTICE
   file, docs) appropriate for adapting ~15 lines of workflow YAML
   and one policy sentence from an MIT project? Anything missing?
7. **What are we missing?** Anything else in this Phase 1 scope that
   you would change before merging?

Please answer concisely, numbered to match. Cite sources for
factual claims about gitleaks, GitHub Actions, Dependabot, or
pre-commit behaviour.
