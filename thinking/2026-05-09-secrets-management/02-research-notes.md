# 02 — Research notes

Distilled findings on per-cloud secret management and the pre-commit /
detection layer. Citations at the end of each section.

## The numbers worth keeping in mind

- AI-service credentials (OpenAI, Anthropic, Google Gemini, etc.) leaked
  to GitHub **surged 81% year-on-year** in 2025–26.
- A separate scan found **24,008 secrets** embedded in MCP configuration
  files on GitHub. Anything we ship that touches `.mcp.json` should
  treat MCP files as a leak surface in their own right.
- Sources:
  [TurboGeek — AI coding tools and 29M leaked secrets (2026)](https://www.turbogeek.co.uk/ai-coding-tools-secrets-leaked-2026/),
  [linou518 — Complete 2026 Secrets Management Guide](https://dev.to/linou518/is-your-api-key-still-running-naked-the-complete-2026-secrets-management-guide-4m7n).

## Defense-in-depth, in order

This is the order the layers should fire in. Each one alone is a single
point of failure.

1. **`.gitignore`** — file never enters the index.
2. **Pre-commit hook (gitleaks)** — file blocked at `git commit`.
3. **GitHub secret scanning + push protection** — push blocked at the
   server side. Free for public repos and most paid orgs.
4. **Provider rotation hooks** — if one slipped through, the key gets
   rotated automatically (GitHub partner program with major providers).
5. **`git filter-repo` / GitHub support** — last-resort cleanup.

`sunaba` ships into layers 1 and 2. Layer 3 the user enables on
GitHub. Layers 4 and 5 are not in scope.

Sources:
[gitleaks/gitleaks](https://github.com/gitleaks/gitleaks),
[OneUptime — secret-scanning gitleaks](https://oneuptime.com/blog/post/2026-01-25-secret-scanning-gitleaks/view).

## The "single source of truth" rule

The leak path that gets agents the most often is **fragmentation**:

```
repo/
├── .env             # prod-shaped values, committed by accident
├── web/.env.local   # subset, also committed
├── api/.env         # different subset
└── .env.example     # template — ok to commit
```

The fix is simple to state and worth saying out loud in every agent
file:

> One `.env` at the repository root for local development. Nowhere else.
> Sub-packages read from the root via the runtime's standard mechanism
> (`dotenv` from project root, `next` reads root, `vite` reads root, etc.).
> Anything that needs secrets in CI / preview / production reads them
> from the platform's secret store, not from a file in the repo.

## `.gitignore` baseline (what `sunaba` should generate)

A baseline that covers the common AI-coding-agent leak family:

```gitignore
# Environment files (never commit)
.env
.env.*
!.env.example
!.env.*.example
.dev.vars

# Cloud credentials
.aws/
.azure/
.gcloud/
gcloud-config/
*.pem
*.key
*.p12
*.pfx
id_rsa*
id_ed25519*

# Service accounts / SDK credentials
**/serviceAccount*.json
**/service-account*.json
**/*-firebase-adminsdk-*.json
credentials.json

# Agent-local state (not actually secrets, but commonly conflated)
.claude/settings.local.json
.codex/
.gemini/

# direnv
.envrc

# Common build / cache
.venv/
node_modules/
__pycache__/
*.pyc
.DS_Store
```

`.env.example` is whitelisted because committing a *template* (with
empty or placeholder values) is the canonical way to tell collaborators
which keys exist.

The `.claude/settings.local.json` line matters specifically because
Claude Code uses that file for per-developer state and it has been a
documented leak source.

## Per-cloud secret stores

Compact reference. The proposal will turn this into per-cloud pages
under `docs/secrets/` linked from `SECURITY.md`.

### Vercel

- **Surface.** Project Settings → Environment Variables. Three scopes:
  *Development*, *Preview*, *Production*. Plus per-deployment.
- **Sensitive flag.** As of 2026, `vercel env add` defaults to
  *sensitive* for prod / preview / custom. Sensitive values cannot be
  read back from the dashboard or `vercel env ls` — only the build /
  runtime can read them.
- **Local mirror.** `vercel env pull .env.local` writes a local copy.
  This file is in `.gitignore` by Vercel default and **must stay
  there**.
- **Public exposure.** Anything with `NEXT_PUBLIC_` prefix is shipped to
  the browser. Never put a secret behind that prefix.
- **Size limits.** 64 KB total per deployment; Edge Functions /
  Middleware: 5 KB per variable.
- Sources:
  [Vercel — Environment variables](https://vercel.com/docs/environment-variables),
  [Vercel — Environments](https://vercel.com/docs/deployments/environments),
  [Vercel — `vercel env`](https://vercel.com/docs/cli/env).

### Firebase

- **Surface.**
  - For Cloud Functions: **Firebase Functions config** (`firebase
    functions:config:set`) is deprecated for new projects in favor of
    **Google Cloud Secret Manager**, accessed from Functions via
    `defineSecret(...)` (Functions v2).
  - For Hosting / SSR: same Secret Manager, accessed via the Cloud Run
    integration.
  - Firebase Admin SDK credentials live in
    `*-firebase-adminsdk-*.json` files which **must never** be
    committed (already covered by `.gitignore` baseline above).
- **Local emulator.** Use `.runtimeconfig.json` only inside the
  Functions emulator dir; never at repo root and never committed.

### Azure

- **Surface.** **Azure Key Vault** for secret storage; **Managed
  Identity** for retrieval; **App Configuration** for non-secret
  feature flags. Never put secrets in App Configuration.
- **AI gateway pattern (the user's primary ask).** This is the lever
  worth documenting in detail:
  ```
  Foundry agent
       │
       ▼  (Managed Identity, no key)
  Azure API Management ── policy: subscription-key-from-Key-Vault
       │
       ▼  (real Gemini key, never seen by the agent)
  Google Generative Language API
       │
       ▼
  Cosmos DB  (request/response logs, agent thread state)
  ```
  - As of late 2025, Microsoft Foundry supports
    **bring-your-own-model** with APIM as a first-class gateway.
  - APIM has a built-in **OpenAI-compatible Google Gemini API** import
    flow that maps Gemini's chat completions endpoint.
  - The Foundry agent calls APIM with its own subscription key (or via
    Managed Identity); APIM substitutes in the upstream Gemini key from
    Key Vault using a `set-header` policy.
  - **Cosmos DB** is the standard Foundry storage for agent threads,
    metadata, and any logs the APIM `log-to-eventhub` /
    `event-hubs-logger` pipeline forwards.
- Sources:
  [MS Learn — Import OpenAI-compatible Google Gemini API to APIM](https://learn.microsoft.com/en-us/azure/api-management/openai-compatible-google-gemini-api),
  [MS Learn — Cosmos DB integration with Foundry Agent Service](https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/azure-agent-service),
  [Badr Kacimi — APIM as AI Gateway for Foundry (Apr 2026)](https://medium.com/@badrkacimi/azure-api-management-as-an-ai-gateway-for-microsoft-foundry-enterprise-model-governance-at-scale-64953cbf3da0),
  [Journey of the Geek — Foundry BYO AI Gateway pt 2 (Mar 2026)](https://journeyofthegeek.com/2026/03/09/microsoft-foundry-apim-and-model-gateway-connections-part-2/).

### AWS

- **Surface.**
  - **Secrets Manager** — primary. Rotation, fine-grained IAM,
    encryption with KMS.
  - **Systems Manager Parameter Store** — cheaper alternative for
    static-ish secrets. Use *SecureString* for anything sensitive.
  - **IAM Roles + STS** — for compute (EC2 / ECS / Lambda / EKS), prefer
    role assumption over static `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.
- **Anti-pattern flagged for the agent file.** A common agent failure
  is to write `aws_access_key_id = AKIA...` into `~/.aws/credentials`
  *inside the repo*. The agent file should explicitly say: credentials
  belong in the host's `~/.aws`, never in the project tree.

### GCP

- **Surface.**
  - **Secret Manager** — primary. Versioned secrets, IAM, automatic
    encryption.
  - **Workload Identity Federation** — preferred for non-GCP compute
    (GitHub Actions, etc.) so no JSON service-account keys exist at all.
  - **Service Account JSON keys** — fallback only. If they exist, they
    belong outside the repo (and `.gitignore` covers
    `*-firebase-adminsdk-*.json` and `serviceAccount*.json` patterns).
- **Application Default Credentials** — local dev should use `gcloud
  auth application-default login`, not a JSON key file.

## Pre-commit secret scanning

`gitleaks` is the de-facto choice in 2026:

- 160+ secret patterns, including OpenAI / Anthropic / Google AI keys.
- Runs as a single Go binary; no Python dependency.
- Pre-commit integration via either the `pre-commit` framework or a
  raw `.git/hooks/pre-commit` script.
- Companion: GitHub Action for layer-3 protection.

What `sunaba` should ship:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.x.x   # pinned to a specific tag in the actual template
    hooks:
      - id: gitleaks
```

Plus a tiny `gitleaks.toml` allowlist for `.env.example` etc.

## What this means for `sunaba` templates

The proposal in `05-proposal.md` will:

1. Expand the generated `.gitignore`.
2. Add a "secrets" section to the harness `AGENTS.md`.
3. Add a `pre-commit-config.yaml` + `gitleaks.toml` to the harness
   stack (silent on success, blocking on failure — fits the
   harness-PR pattern from the prior doc).
4. Add `docs/secrets/{vercel,firebase,azure,aws,gcp}.md` linked from
   `SECURITY.md`. The Azure page documents the
   Foundry → APIM → Gemini → Cosmos pattern in detail because it's
   the highest-leverage move for any user actually deploying agent
   workloads.
