# 01 — Current state of secrets in sunaba

## What sunaba already does well

- **Secrets are opt-in.** API keys are injected into the container only
  when the user passes a stack that asks for them.
  - [`templates/stacks/agents.json`](../../src/sunaba_cli/templates/stacks/agents.json)
    declares `remoteEnv` for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
    `GEMINI_API_KEY`, sourced from `${localEnv:...}`.
  - [`templates/stacks/neon.json`](../../src/sunaba_cli/templates/stacks/neon.json)
    declares `NEON_API_KEY`.
  - [`templates/stacks/nextjs.json`](../../src/sunaba_cli/templates/stacks/nextjs.json)
    declares `VERCEL_TOKEN`.
  - The base container starts with `remoteEnv: {}` (see
    [`templates/base/devcontainer.json`](../../src/sunaba_cli/templates/base/devcontainer.json#L12)),
    so unflagged projects do not see any host secrets.
- **`.gitignore` covers `.env` and `.env.local`.** The template in
  [`cli.py`](../../src/sunaba_cli/cli.py#L364) emits:
  ```
  .venv/
  node_modules/
  __pycache__/
  .env
  .env.local
  *.pyc
  .DS_Store
  ```
- **README says it plainly.** The README's "what sunaba does NOT protect
  you from" section already names *secret visibility inside the
  container*: "once you pass `--stack agents`, *any* process in the
  container — including any AI agent — can read your API keys via
  environment variables."

## The five gaps the user has flagged

### 1. `.gitignore` is shallow

It catches `.env` and `.env.local` but not the rest of the family that
keys actually leak through:

- `.env.development`, `.env.production`, `.env.staging`, `.env.*.local`
- `.envrc` (direnv) — not a key file but commonly tweaked to `export
  OPENAI_API_KEY=...`
- `*.pem`, `*.key`, `id_rsa*`, `id_ed25519*` — agent-written keypairs
- `.aws/credentials`, `.azure/`, `.gcloud/`, `serviceAccount.json`,
  `*-firebase-adminsdk-*.json` — cloud credential files agents
  occasionally drop into the repo
- `.codex/`, `.claude.json`, `.gemini/` at the repo root if the user
  ever runs the CLIs against `$PWD` outside a sunaba container.

### 2. No "single source of truth" guidance

Today nothing stops an agent from creating `web/.env`, `api/.env`, and
`.env.local` for the same project, each with a partially-overlapping copy
of the keys. Once that happens, the next refactor accidentally commits
one of them. Both the agent file (`AGENTS.md`) and the security doc
should say: **one `.env` at the repo root for local dev only, never more
than one**.

### 3. No cloud-side guidance for production secrets

Once a project deploys to Vercel, Firebase, AWS, GCP, or Azure, the
secret should not live in any `.env` file at all. Each platform has a
managed-secrets surface (Vercel Environment Variables, Firebase
Functions config / Secret Manager, AWS Secrets Manager + Parameter
Store, GCP Secret Manager, Azure Key Vault). `sunaba` ships zero
guidance for these today — neither in `SECURITY.md` nor in the per-stack
agent rules.

### 4. No "key behind a proxy" pattern documented

The user specifically asked for the **Azure pattern**: a Foundry-hosted
agent calls **Gemini through Azure API Management (APIM)**, with the
real Gemini key stored in Key Vault and APIM doing the substitution.
This pattern (broadly: "the client never sees the upstream key") is the
single biggest jump in posture for any production deployment, and it's
not documented anywhere in the project.

### 5. No pre-commit safety net

The repo has no `pre-commit` hook, no `gitleaks` / `trufflehog`
configuration, and no GitHub Actions check that scans pushed branches
for secrets. The harness `verify.sh` from the previous design doc only
runs typecheck/test, not secret scanning.

## What should change

This is the agenda for `02-research-notes.md` and `05-proposal.md`:

1. Expand the generated `.gitignore` to cover the actual key-leak file
   family.
2. Add a short, opinionated "secrets" section to the harness `AGENTS.md`
   with the **one `.env` at repo root** rule, and the **never write keys
   to source files** rule.
3. Add per-cloud pages under `SECURITY.md` (or `docs/secrets/<cloud>.md`
   linked from `SECURITY.md`) for: Vercel, Firebase, Azure (with the
   Foundry + APIM + Cosmos pattern called out specifically), AWS, GCP.
4. Add a `secret-scan` pre-commit hook to the harness stack — blocks
   commits, silent on success.
5. Decide whether `--stack secrets` is worth introducing as a peer to
   `--stack harness`, or whether the secret-scan hook + docs should be
   folded into the existing `harness` stack from the prior PR.
