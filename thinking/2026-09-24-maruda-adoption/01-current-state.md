# 01 — Current state: `--stack secrets` and sunaba's own CI

> Part of [`2026-09-24-maruda-adoption/`](README.md). Snapshot of
> `main` at `17bf87e` (2026-09-24).

## What `--stack secrets` emits today

[`templates/stacks/secrets.json`](../../src/sunaba_cli/templates/stacks/secrets.json)
writes nine files via `_files` and adds two `bootstrap.sh` lines
(`pip install --user pre-commit`, then `pre-commit install` when
`.git` exists). The three files that do the actual scanning:

| Emitted path | Source | Content |
|---|---|---|
| `.pre-commit-config.yaml` | `secrets/pre-commit-config.yaml` | `repo: gitleaks/gitleaks`, `rev: v8.24.2` (a mutable tag), `id: gitleaks` |
| `.gitleaks.toml` | `secrets/gitleaks.toml` | `title` + one `[allowlist]` for `^\.env\.example$` / `^\.env\..*\.example$` — **nothing else** |
| `.github/workflows/gitleaks.yml` | `secrets/github-workflow-gitleaks.yml` | `actions/checkout@v4` (`fetch-depth: 0`) + `gitleaks/gitleaks-action@v2`; no `permissions:` |

The design is in
[`2026-05-09-secrets-management/05-proposal.md`](../2026-05-09-secrets-management/05-proposal.md),
which already said "the exact pin should be the latest stable
release at landing time. **Do not pin to `main`**" (L232-234) — but
landed tag pins, not commit pins.

## Defect 1 (critical): the generated `.gitleaks.toml` disables detection

Gitleaks resolves its config as `--config` → `GITLEAKS_CONFIG` →
`GITLEAKS_CONFIG_TOML` → **`<target>/.gitleaks.toml`** → built-in
default ([gitleaks README, v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)).
A custom config **replaces** the default rule set unless it contains
`[extend] useDefault = true`. Ours does not, so it defines an
allowlist and **zero rules**.

Because the file sits at the repository root, every consumer picks
it up: the pre-commit hook (`gitleaks git --pre-commit --staged`),
`gitleaks-action`, and a developer's manual `gitleaks git`.

Reproduced on 2026-09-24 with gitleaks 8.30.1 (checksum-verified
release binary) in a throwaway repo containing an AWS access key id
and a GitHub PAT:

```
--- with sunaba's .gitleaks.toml
INF 1 commits scanned.
INF no leaks found                       exit=0
--- without it
WRN leaks found: 2                       exit=1
```

Adding `[extend] useDefault = true` restores detection (both leaks,
plus a PAT in `config.env`) while still allowlisting `.env.example`
and `.env.local.example`. **Every project generated with
`--stack secrets` since it shipped has had a no-op secret scanner.**
None of the tests in
[`tests/test_secrets.py`](../../tests/test_secrets.py) run gitleaks;
they only assert substrings (`[allowlist]`, `.env.example`).

## Defect 2 (high): the CI workflow fails for organization repos

`gitleaks/gitleaks-action` requires a `GITLEAKS_LICENSE` secret
(a free key, but one that needs registration at gitleaks.io)
"for organizations, not required for user accounts"
([gitleaks-action README](https://github.com/gitleaks/gitleaks-action#environment-variables)).
The template sets only `GITHUB_TOKEN`, so the job errors on any
org-owned repository — exactly the enterprise audience the
[enterprise essay](../2026-05-26-enterprise-development/README.md)
targets.

## Defect 3 (medium): supply-chain pinning is by mutable tag

- `actions/checkout@v4`, `gitleaks/gitleaks-action@v2` — major-version
  tags; whoever controls the tag controls the code that runs with
  `GITHUB_TOKEN`. GitHub's own hardening guide says pinning to a full
  commit SHA "is currently the only way to use an action as an
  immutable release"
  ([Secure use reference — pin actions to a full-length commit SHA](https://docs.github.com/en/actions/reference/security/secure-use#pin-actions-to-a-full-length-commit-sha)).
- The gitleaks binary version is whatever the action chooses; nothing
  is checksum-verified.
- No `permissions:` block → the job gets the repository-default token
  scope.
- pre-commit `rev: v8.24.2` is a tag; pre-commit's own
  `autoupdate --freeze` convention is `rev: <sha>  # frozen: vX.Y.Z`.

## Defect 4 (low): stale docs

- [`secrets/docs/README.md`](../../src/sunaba_cli/templates/secrets/docs/README.md)
  says the stack "ships layers 1 and 2" — it also ships a CI scan.
- README / README.ja describe the pre-commit pin as a "pinned tag".

## sunaba's own CI

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs
pytest on 3.11–3.13 and `uv build`. It uses `actions/checkout@v4` and
`astral-sh/setup-uv@v5` (tag-pinned), has no `permissions:`, and runs
no secret scan. A full-history `gitleaks git --log-opts=--all` over
this repository today reports two findings, both the same
`generic-api-key` false positive on a Markdown heading in
`thinking/2026-05-09-secrets-management/04b-codex-review.md` in two
historical commits (`7e2ce8f`, `0c70669`). No real secret.

## What is *not* in scope here

SAST (Semgrep), dependency audit (Trivy, npm/pnpm audit), GitHub
branch protection, and the LLM security-review skills are Phases 2–3
of the adoption plan (see [README](README.md)). This folder decides
Phase 1 only.
