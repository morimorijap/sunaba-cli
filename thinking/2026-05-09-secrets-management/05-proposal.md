# 05 — Proposal

> Synthesized from the research notes and the two independent reviews
> ([`04a-gemini-review.md`](04a-gemini-review.md),
> [`04b-codex-review.md`](04b-codex-review.md)).
> Status: **draft for PR review**. Not implemented yet.

## TL;DR

1. **Expand the generated `.gitignore` in the default scaffold.**
   Covers cloud credentials, agent local state, SSH keys, the wider
   `.env` family. No opt-in flag. No behavior change for any user
   running `sunaba new` — files just stop showing up in `git add`.
2. **Add a short "Secrets" section to the harness `AGENTS.md`,
   `CLAUDE.md`, `GEMINI.md`** with the *single root `.env`* rule and
   the *never write keys to source-controlled paths* rule.
3. **Introduce `--stack secrets`** as a new opt-in stack (peer of
   `--stack harness`). It ships:
   - `.pre-commit-config.yaml` pinning `gitleaks` to a specific
     release tag.
   - `.gitleaks.toml` with a minimal `.env.example` allowlist.
   - `docs/secrets/{README,vercel,firebase,aws,gcp,
     azure-foundry-apim-gemini-cosmos}.md`.
   - `.github/workflows/gitleaks.yml` (CI scan).
   - `_bootstrap` snippet that runs `pre-commit install` if `.git`
     exists.
4. **Update `SECURITY.md`** to link `docs/secrets/` and to say,
   verbatim, that cloud-managed secrets and pre-commit hooks **do not**
   protect against an autonomous agent that reads runtime env vars
   inside the container. The APIM-proxy doc is the only mitigation
   that survives a compromised agent.

The combined recommended invocation:

```bash
sunaba new myapp --stack python --stack agents --stack harness --stack secrets
```

## Maturity score (consensus)

| Axis | Score | Notes |
|---|---:|---|
| `.gitignore` coverage | 1–2/5 | Catches `.env*` family, misses everything else. |
| Agent rule clarity | 1–2/5 | No secrets section in any agent file. |
| Pre-commit detection | 0–1/5 | Nothing ships. |
| Per-cloud docs | 0–1/5 | None. |
| Key-behind-proxy docs | 0–1/5 | None. The pattern that survives a compromised container is undocumented. |

Both reviewers landed within ±1 on every axis.

## Where the reviewers disagreed

### Disagreement 1 — `gitleaks` in harness stack or new `secrets` stack?

- **Gemini:** fold into `harness`. *"Security should not be 'à la
  carte'. A separate `secrets` stack implies that running agents
  without secret protection is an acceptable supported path. It is
  not."*
- **Codex:** new `--stack secrets`. *"`harness` is about work quality;
  `secrets` is about leak prevention. Different responsibility.
  Commits getting blocked is a behavior change → opt-in."*

**Decision: new `--stack secrets`.**

Three reasons:

1. **Different blast radius.** `--stack harness` mostly adds files;
   `gitleaks` actively blocks `git commit`. That's a runtime behavior
   change and the project's stated constraint is "opt-in over default."
2. **Composition is the answer to Gemini's concern.** The
   recommended invocation is `--stack harness --stack secrets`. We
   document this combination as the canonical agent setup and link it
   from the README. That keeps secrets posture front-and-center
   without violating the opt-in promise.
3. **Replaceability.** `gitleaks` is the de-facto default in 2026 but
   may not always be. Keeping a dedicated stack means we can swap
   tools (or version-pin them) without touching the harness stack's
   work-quality machinery.

### Disagreement 2 — APIM logging: full payload vs metadata-first

- **Gemini:** APIM `<send-request>` writes raw request/response
  payloads to Cosmos for full audit.
- **Codex:** metadata first (`time`, `requestId`, `operation`,
  `callerIp`, `status`) via `log-to-eventhub`, with payload logging
  off by default. Full audit is opt-in and gated on an explicit
  retention/redaction policy.

**Decision: metadata first (Codex's framing).**

Reasoning: prompts and responses are user data. They include PII,
proprietary code, and (ironically) other secrets. Defaulting to
full-payload logging is itself a leak surface. We document the
metadata-only baseline as the recommended default; we mention
full-payload logging as an advanced option with a retention/redaction
checklist users have to fill in deliberately.

### Disagreement 3 — APIM caller auth: subscription key vs Entra token

- **Gemini:** shows Entra token validation as the recommended path
  (good).
- **Codex:** also recommends Entra token, **plus** documents the
  realistic caveat that Foundry's declarative action surface may not
  always support direct bearer tokens — in which case a Function /
  Logic App shim with its own Managed Identity is the pragmatic
  fallback. Subscription key is acceptable as a migration step but
  never the target.

**Decision: Codex's framing.** It's more grounded and includes the
shim fallback Gemini missed. We document the shim explicitly so
readers don't get stuck.

## What we add

### 1. `.gitignore` expansion (default scaffold)

Replace the current hard-coded gitignore in [`cli.py`](../../src/sunaba_cli/cli.py#L364)
with a `_default_gitignore()` helper:

```python
def _default_gitignore() -> str:
    return """\
# Environment files (never commit real values)
.env
.env.*
!.env.example
!.env.*.example
.envrc
.dev.vars

# Cloud and local credentials
.aws/
.azure/
.gcloud/
gcloud-config/
credentials.json
**/serviceAccount*.json
**/service-account*.json
**/*-firebase-adminsdk-*.json

# Private keys and certificates
*.pem
*.key
*.p12
*.pfx
id_rsa*
id_ed25519*

# Agent-local state
.claude/settings.local.json
.codex/
.gemini/

# Build / cache
.venv/
node_modules/
__pycache__/
*.pyc
.DS_Store
"""
```

**Important:** `sunaba rebuild` must **not** overwrite an existing
`.gitignore`. Both reviewers flagged this. Keep `.gitignore` out of
`_build_config_files()`'s diff/write loop; only `sunaba new` writes
it.

### 2. Agent files: add a Secrets section

Append to `templates/agents/AGENTS.md` (and the per-tool variants):

```md
## Secrets

- Local development uses **exactly one** `.env` file at the repository
  root. Do not create `web/.env`, `api/.env`, nested `.env.local`, or
  copies of key files.
- Never write API keys, tokens, private keys, Firebase admin SDK
  JSON, or cloud credential files into source-controlled paths.
- Production, preview, and CI secrets must come from the platform's
  secret store: Vercel Environment Variables, Google Secret Manager,
  AWS Secrets Manager, Azure Key Vault. See `docs/secrets/`.
- Runtime env vars inside this container are readable by every local
  process and agent. Cloud secret managers and `.gitignore` do not
  change that.
```

Lives in the existing base agent templates. Effective on the next
`sunaba sync`.

### 3. New stack: `--stack secrets`

`templates/stacks/secrets.json`:

```json
{
  "_description": "Secret hygiene scaffold: pre-commit gitleaks, gitleaks allowlist, per-cloud docs, and CI scan.",
  "_files": {
    ".pre-commit-config.yaml":                              "secrets/pre-commit-config.yaml",
    ".gitleaks.toml":                                        "secrets/gitleaks.toml",
    ".github/workflows/gitleaks.yml":                        "secrets/github-workflow-gitleaks.yml",
    "docs/secrets/README.md":                                "secrets/docs/README.md",
    "docs/secrets/vercel.md":                                "secrets/docs/vercel.md",
    "docs/secrets/firebase.md":                              "secrets/docs/firebase.md",
    "docs/secrets/aws.md":                                   "secrets/docs/aws.md",
    "docs/secrets/gcp.md":                                   "secrets/docs/gcp.md",
    "docs/secrets/azure-foundry-apim-gemini-cosmos.md":      "secrets/docs/azure-foundry-apim-gemini-cosmos.md"
  },
  "_bootstrap": [
    "# --- secrets ---",
    "if ! command -v pre-commit >/dev/null 2>&1; then pip install --user --quiet pre-commit; fi",
    "if [ -f .pre-commit-config.yaml ] && [ -d .git ]; then pre-commit install >/dev/null 2>&1 || true; fi"
  ]
}
```

This depends on the `_files` mechanism introduced by the harness PR. If
that PR has not landed, the secrets stack PR introduces `_files` first.

### 4. Templates under `templates/secrets/`

#### `templates/secrets/pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2   # bump in CI; do not use 'main'
    hooks:
      - id: gitleaks
```

The exact pin should be the latest stable release at landing time.
**Do not pin to `main`** — that re-introduces a supply-chain risk we
just told users to care about.

#### `templates/secrets/gitleaks.toml`

```toml
title = "sunaba generated gitleaks config"

[allowlist]
description = "Templates and example files only — never real local secrets."
paths = [
  '''^\.env\.example$''',
  '''^\.env\..*\.example$''',
]
```

Keep this minimal. **Do not** widen with regex-based fake-key
allowlists; they create gaps that hide real leaks.

#### `templates/secrets/github-workflow-gitleaks.yml`

```yaml
name: gitleaks

on:
  pull_request:
  push:
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Layer-3 protection. Catches what slipped past local hooks.

#### `templates/secrets/docs/README.md`

```md
# docs/secrets/

How and where to keep secrets out of this repository, by cloud.

> **Read first:** the AGENTS.md "Secrets" section. Tools and
> documentation help, but they do not protect a real, billing-enabled
> API key from an autonomous agent that decides to exfiltrate it.
> The only architectural mitigation against that failure mode is the
> [Azure Foundry → APIM → Gemini → Cosmos](azure-foundry-apim-gemini-cosmos.md)
> pattern (or a non-Azure equivalent gateway).

## Pages

- [Vercel](vercel.md)
- [Firebase / Google Cloud](firebase.md)
- [AWS](aws.md)
- [GCP](gcp.md)
- [Azure: Foundry → APIM → Gemini → Cosmos (the "key behind a proxy" pattern)](azure-foundry-apim-gemini-cosmos.md)

## Defense-in-depth, in order

1. **`.gitignore`** — file never enters the index.
2. **Pre-commit hook (gitleaks)** — file blocked at `git commit`.
3. **GitHub secret scanning + push protection** — push blocked
   server-side. Enable in repo settings.
4. **Provider rotation hooks** — major providers participate in
   GitHub's partner program and auto-rotate found keys.
5. **`git filter-repo` / GitHub support** — last-resort cleanup.

`sunaba`'s `--stack secrets` ships layers 1 and 2. Layer 3 you enable.
Layers 4 and 5 are out of scope.
```

#### `templates/secrets/docs/vercel.md`

```md
# Vercel

## Where secrets live

Vercel **Project Settings → Environment Variables**. Three scopes:
*Development*, *Preview*, *Production*. Secrets default to *sensitive*
in `vercel env add` for prod / preview — values cannot be read back
from the dashboard or `vercel env ls` once stored.

## Local dev

`vercel env pull .env.local` writes a local mirror. **`.env.local` is
in `.gitignore`** (and `sunaba`'s expanded baseline already covers it).

## Rules

- Anything prefixed `NEXT_PUBLIC_*` ships to the browser. **Never put
  a real secret behind that prefix.**
- Edit Vercel env vars in the dashboard or via `vercel env add`. Do
  not paste them into source files.
- Re-deploy after changing env vars; otherwise the build container
  still has the old values.

## One-line agent rule

> "Never write secrets to `.env.local` manually. Always run
> `vercel env add` and `vercel env pull`."
```

#### `templates/secrets/docs/firebase.md`

```md
# Firebase / Google Cloud

## Where secrets live

For **Cloud Functions v2**, use **Cloud Secret Manager** via
`defineSecret(...)`. The legacy `firebase functions:config:set` is
deprecated for new projects.

For **Hosting / SSR** that runs on Cloud Run, use the same Secret
Manager via the Cloud Run integration.

## Local dev

Use **Application Default Credentials**: `gcloud auth
application-default login`. Avoid downloading service-account JSON
keys.

## Rules

- **Never commit `*-firebase-adminsdk-*.json`** or any
  `serviceAccount*.json`. (sunaba's `.gitignore` covers these.)
- The Firebase emulator's `.runtimeconfig.json` belongs in the
  emulator dir only, not at repo root, never committed.

## One-line agent rule

> "Never download or create service-account JSON files. Authenticate
> exclusively via `gcloud auth application-default login`."
```

#### `templates/secrets/docs/aws.md`

```md
# AWS

## Where secrets live

- **AWS Secrets Manager** — primary, with rotation, KMS encryption,
  and fine-grained IAM.
- **Systems Manager Parameter Store** with `SecureString` — cheaper
  alternative for static-ish secrets.
- **IAM roles + STS** — for compute (EC2 / ECS / Lambda / EKS).
  Prefer role assumption over static `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY`.

## Local dev

**IAM Identity Center / SSO** for short-lived tokens
(`aws sso login`). Avoid long-lived `AKIA...` access keys.

## Rules

- **Never commit `aws_access_key_id` / `aws_secret_access_key`** to
  any file in the repo tree.
- The host's `~/.aws/` is mounted into the devcontainer if you have
  it; the *project tree's* `.aws/` is in `.gitignore`. Don't conflate
  them.

## One-line agent rule

> "Never request or create long-lived IAM access keys (`AKIA...`).
> Authenticate exclusively using `aws sso login`."
```

#### `templates/secrets/docs/gcp.md`

```md
# GCP

## Where secrets live

- **Google Secret Manager** — primary, versioned, IAM-gated.
- **Workload Identity Federation** — preferred for non-GCP compute
  (GitHub Actions, etc.) so no JSON keys exist at all.

## Local dev

**Application Default Credentials**:
`gcloud auth application-default login`.

## Rules

- **Never** drop `serviceAccount*.json` into the repo. If a
  service-account JSON is genuinely required, store it outside the
  repo and reference it by env var path.
- Workload Identity Federation eliminates JSON keys for CI; use it
  unless you have a specific reason not to.

## One-line agent rule

> "Never create or commit service-account JSON. Use ADC or Workload
> Identity Federation."
```

#### `templates/secrets/docs/azure-foundry-apim-gemini-cosmos.md`

This is the user's primary ask — it gets its own section below.

### 5. The Azure Foundry → APIM → Gemini → Cosmos page

The full content lives at
`templates/secrets/docs/azure-foundry-apim-gemini-cosmos.md`. Synthesized
from both reviewers, with Codex's framing on auth and logging.

```md
# Azure: Foundry → APIM → Gemini → Cosmos

> The "key behind a proxy" pattern. The agent never sees the upstream
> Gemini key; APIM injects it from Key Vault. Audit metadata is logged
> outside the agent's control.

## When you want this

The agent is going to call Google Gemini in production. You don't
want the upstream Gemini API key to ever land inside the container,
the agent's tool environment, or any commit log.

The pattern below is the only architectural mitigation that survives
a compromised agent. `.gitignore`, pre-commit hooks, and cloud
secret managers all stop short — once the agent process can read
the key from `os.environ`, none of those help.

## Architecture

```
Foundry agent (or Function/Logic App shim with Managed Identity)
       │
       │ Authorization: Bearer <Entra token>
       ▼
Azure API Management
       │  validate-azure-ad-token  (verifies the agent's identity)
       │  set-header x-goog-api-key from a Key-Vault-backed named value
       ▼
https://generativelanguage.googleapis.com   (Gemini)

Azure Cosmos DB                Azure Event Hubs
  • Foundry agent threads        ◄── APIM log-to-eventhub
  • optional sanitized audit         (metadata first; payloads
    records (via Function)            require explicit policy)
```

## Resources to create

1. **Azure Key Vault**
   - Secret: `gemini-api-key` (the upstream Google API key).
   - Grant the APIM instance's managed identity the
     **Key Vault Secrets User** role on the vault.

2. **Azure API Management**
   - Enable **system-assigned managed identity**.
   - Add a **Named Value** of type *Key Vault* called
     `gemini-api-key`, pointing at the vault secret URI without a
     version.
   - Import the Gemini API as either an OpenAI-compatible language
     model API (recommended; APIM has a built-in import flow) or as
     a passthrough HTTP API.
   - Caller auth: prefer **Entra token validation**
     (`validate-azure-ad-token`). Subscription keys are an acceptable
     migration step but **not** the target — they are static shared
     secrets.

3. **Microsoft Foundry project / agent**
   - Give the hosted agent (or its tool runtime) a Managed Identity.
   - In tool / action config, point at the **APIM URL only**. Do not
     reference the Gemini key anywhere.
   - **Caveat (real):** Foundry's declarative action surface may not
     always let you attach a Managed Identity bearer token directly.
     If that's the case for your version, place a thin **Azure
     Function (or Logic App) shim** between the agent and APIM. The
     shim has its own Managed Identity and forwards the agent's call
     to APIM with the Entra token attached. The Gemini key still
     never enters the agent.

4. **Azure Cosmos DB for NoSQL**
   - This is Foundry's standard storage for agent threads, vector
     stores, and metadata.
   - Optionally create an `audit` database for sanitized audit
     records written by the Function below.

5. **Optional: Event Hubs + Function (for audit)**
   - APIM `log-to-eventhub` posts metadata.
   - A Function consumes the stream, applies redaction / sampling,
     and writes audit records to Cosmos.
   - This split exists so you can decide payload retention
     deliberately rather than logging full prompts and responses
     by default.

## APIM policy (inbound)

Assumes named values:
- `aad-tenant-id` — Entra tenant ID.
- `apim-app-audience` — App ID URI / audience for this APIM API.
- `gemini-api-key` — Key-Vault-backed named value.

```xml
<policies>
  <inbound>
    <base />

    <validate-azure-ad-token tenant-id="{{aad-tenant-id}}">
      <required-claims>
        <claim name="aud">
          <value>{{apim-app-audience}}</value>
        </claim>
      </required-claims>
    </validate-azure-ad-token>

    <set-header name="x-goog-api-key" exists-action="override">
      <value>{{gemini-api-key}}</value>
    </set-header>

    <!-- Strip caller auth headers before forwarding upstream. -->
    <set-header name="Authorization" exists-action="delete" />
    <set-header name="Ocp-Apim-Subscription-Key" exists-action="delete" />

    <set-backend-service base-url="https://generativelanguage.googleapis.com" />
  </inbound>

  <backend>
    <forward-request />
  </backend>

  <outbound>
    <base />
    <log-to-eventhub logger-id="sunaba-ai-audit">
@{
  return new JObject(
    new JProperty("time",      DateTime.UtcNow.ToString("o")),
    new JProperty("requestId", context.RequestId),
    new JProperty("operation", context.Operation.Name),
    new JProperty("callerIp",  context.Request.IpAddress),
    new JProperty("status",    context.Response?.StatusCode)
  ).ToString();
}
    </log-to-eventhub>
  </outbound>

  <on-error>
    <base />
  </on-error>
</policies>
```

**What this policy logs:** timestamp, request ID, operation,
caller IP, status. Nothing else.

**What this policy does *not* log:** the prompt, the response, the
upstream `x-goog-api-key`, the agent's bearer token. If you want
prompt/response auditing, add it deliberately in the Function — with
an explicit retention period and redaction policy. Prompts and
responses are user data and can themselves contain secrets.

## Smallest end-to-end demo

```python
import os
import requests
from azure.identity import DefaultAzureCredential

APIM_URL   = os.environ["APIM_GEMINI_URL"]                     # e.g. https://contoso.azure-api.net/gemini/...
APIM_SCOPE = os.environ["APIM_APP_ID_URI"] + "/.default"

token = DefaultAzureCredential().get_token(APIM_SCOPE).token

resp = requests.post(
    APIM_URL,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    json={
        "contents": [{"parts": [{"text": "Reply with only: apim-ok"}]}]
    },
    timeout=30,
)
resp.raise_for_status()
print(resp.json())
```

Verify the win:

- `printenv | rg -i 'GEMINI|GOOGLE_API_KEY'` returns nothing on the
  agent host. The agent has no Gemini key.
- Removing the bearer token returns 401 from APIM.
- Key Vault access logs show the APIM identity reading
  `gemini-api-key`. The agent identity does not appear there.
- APIM / Event Hubs / Cosmos audit records contain no
  `x-goog-api-key` header.

## What lives where

| Data | Location |
|---|---|
| Real Gemini API key | Key Vault secret. APIM named value references it. |
| Caller identity verification | Entra token validated by APIM policy. |
| Agent thread state | Cosmos DB (Foundry standard storage). |
| Optional audit records | Cosmos DB `audit` database, written by Function from Event Hubs. |
| APIM platform metrics | APIM analytics / Azure Monitor / App Insights. |
| Raw upstream key | **Nowhere** in Foundry instructions, tool config, repo, `.env`, Cosmos, or logs. |

## Trade-offs

- **Latency.** Adds one network hop and policy execution. Typically
  ~30–50 ms; measure for your tier.
- **Cost.** APIM Consumption: first 1M calls free, then per-call
  pricing. Cosmos DB: storage + RU/s. Both are usually small relative
  to the Gemini bill.
- **Rotation.** Updating the Key Vault secret eventually propagates
  to APIM's named value cache. Schedule a rotation window.
- **Observability vs privacy.** Logging full prompts and responses
  gives complete audit trails. It also turns Cosmos into a new leak
  surface. Default to metadata; opt into payload audit only with a
  redaction / retention policy.
- **What this does *not* fix.** A compromised agent can still
  exhaust your Gemini quota, since it can call APIM as long as it
  holds a valid token. Add APIM rate-limit policies, set a
  conservative quota on the upstream Google project, and alert on
  anomalies.
```

## What sunaba's main code has to change

- **`cli.py`**: extract the gitignore string into `_default_gitignore()`;
  consume `_files` from chosen stacks (depends on the harness PR
  introducing the same mechanism — see `2026-05-09-harness-engineering`).
- **`compose.py`**: unchanged. `_files` is processed outside the
  deep-merge.
- **`sync.py`**: unchanged. The new agent file additions land via
  `templates/agents/AGENTS.md` etc., which `sync_project` already
  copies. Existing users get the secrets section on their next
  `sunaba sync`.
- **`tests/test_smoke.py`**: add the structural tests in section D.

## Tests (structural, not behavioral)

```python
def test_default_gitignore_covers_secret_file_family():
    text = cli_module._default_gitignore()
    for pat in [
        ".env.*", "!.env.example",
        "*.pem", "*.key", "*.p12", "*.pfx",
        "id_rsa*", "id_ed25519*",
        "**/serviceAccount*.json",
        "**/*-firebase-adminsdk-*.json",
        "credentials.json",
        ".claude/settings.local.json",
        ".envrc", ".aws/", ".azure/", ".gcloud/",
    ]:
        assert pat in text, f"missing {pat}"

def test_secrets_stack_listed():
    assert "secrets" in available_stacks()

def test_secrets_stack_emits_expected_paths():
    files = _build_config_files("p", ["secrets"])
    expected = {
        ".pre-commit-config.yaml",
        ".gitleaks.toml",
        ".github/workflows/gitleaks.yml",
        "docs/secrets/README.md",
        "docs/secrets/vercel.md",
        "docs/secrets/firebase.md",
        "docs/secrets/aws.md",
        "docs/secrets/gcp.md",
        "docs/secrets/azure-foundry-apim-gemini-cosmos.md",
    }
    assert expected.issubset(files.keys())

def test_pre_commit_pins_gitleaks_to_a_tag():
    text = _build_config_files("p", ["secrets"])[".pre-commit-config.yaml"]
    assert "gitleaks/gitleaks" in text
    assert "id: gitleaks" in text
    assert "rev: v" in text
    assert "rev: main" not in text
    assert "rev: HEAD" not in text

def test_agent_template_has_secrets_section():
    text = (TEMPLATES_DIR / "agents" / "AGENTS.md").read_text()
    lower = text.lower()
    assert "## secrets" in lower
    assert "single" in lower or "exactly one" in lower
    assert "repository root" in lower

def test_rebuild_does_not_overwrite_existing_gitignore(tmp_path):
    # sunaba new writes .gitignore; sunaba rebuild must not touch it.
    # Implementation detail: .gitignore stays out of _build_config_files diff/write.
    # Test by inspecting that _build_config_files does not include ".gitignore".
    files = _build_config_files("p", ["secrets"])
    assert ".gitignore" not in files
```

## README + SECURITY updates

`README.md` stack table:

```diff
 | `harness`   | Claude Code-oriented harness templates. |
+| `secrets`   | Secret hygiene scaffold: `pre-commit` with `gitleaks`, per-cloud docs (Vercel / Firebase / AWS / GCP / Azure), and a CI scan. **Opt-in because it changes commit-time behavior.** |
```

Recommended invocation block in the README:

```diff
 # Python microservice
 sunaba new api --stack python --stack agents
+
+# Recommended baseline for an agent project on a deploy target
+sunaba new app --stack python --stack agents --stack harness --stack secrets
```

`SECURITY.md` — add a "Secrets" section:

```diff
+## Secrets
+
+`sunaba-cli` ships defense-in-depth for secret hygiene, but each
+layer has clear limits:
+
+- The default `.gitignore` excludes the common secret-file family
+  (cloud credentials, SSH keys, Firebase admin SDK JSON, agent
+  local state, the wider `.env.*` family). It only covers
+  *untracked* files.
+- `--stack secrets` adds `pre-commit` with `gitleaks`, a
+  `.gitleaks.toml` allowlist, and a CI scan. This blocks commits
+  with detected secrets; it does not protect already-tracked
+  files.
+- Per-cloud guidance in [`docs/secrets/`](docs/secrets/) describes
+  where each platform expects secrets to live (Vercel env vars,
+  Google Secret Manager, AWS Secrets Manager, Azure Key Vault).
+
+**Limit that no template can fix:** once an API key is in
+`os.environ` inside the container, an agent process can read it,
+log it, or send it to an attacker-controlled endpoint. The only
+architectural mitigation against that failure mode is the
+["key behind a proxy" pattern](docs/secrets/azure-foundry-apim-gemini-cosmos.md)
+— the agent calls a gateway it has identity-only access to, and
+the gateway substitutes the upstream key. We document the Azure
+Foundry → APIM → Gemini → Cosmos version of this pattern in
+detail; equivalent patterns exist on AWS (API Gateway / Lambda)
+and GCP (Apigee / API Gateway).
```

`README.ja.md`: same content, translated.

## What we explicitly do **not** do in this PR

- **Don't bake `gitleaks` into `base/`.** Behavior change at commit
  time → must be opt-in.
- **Don't make `--stack secrets` modify `.gitignore`.** The `.gitignore`
  baseline ships in default scaffold and is not changed by stack
  composition. This avoids surprising users on `sunaba rebuild --add
  secrets`.
- **Don't ship full prompt/response logging in the APIM policy
  template.** Default is metadata; payload logging is documented as
  an opt-in path with a checklist.
- **Don't recommend APIM subscription keys** for the agent path.
  Static shared secret. Use Entra tokens (with the Function shim
  fallback if Foundry can't bind one directly).
- **Don't rewrite agent files via `sunaba sync` in a destructive
  way.** The Secrets section appends to existing templates; users
  who have customized `AGENTS.md` will need a manual diff. We document
  this in the release notes.

## Rebuild consistency

> Added 2026-05-09 in response to: *"are inconsistencies on
> `sunaba rebuild` considered?"*
> The original proposal kept `.gitignore` out of the
> `rebuild`-managed file set and noted that `--stack secrets` does
> not modify `.gitignore`. That was correct as far as it went, but
> two cases were under-specified: (a) what does `--add secrets` /
> `--remove secrets` actually do for the secrets stack's own files,
> and (b) how does an existing project upgrade its `.gitignore` to
> the new baseline?

### `rebuild --remove secrets` leaves orphans

Same shape as the harness PR's orphan problem:
`.pre-commit-config.yaml`, `.gitleaks.toml`,
`.github/workflows/gitleaks.yml`, and `docs/secrets/*` remain on
disk after `rebuild --remove secrets`.

**Decision: same as harness — don't auto-delete; report and
instruct.** This relies on the orphan-reporting machinery that
lands with the harness PR. The secrets PR adds:

- `.pre-commit-config.yaml`
- `.gitleaks.toml`
- `.github/workflows/gitleaks.yml`
- `docs/secrets/`

…to the set of paths the orphan scan understands.

There's one wrinkle specific to this PR: the
`pre-commit install` hook installed by `_bootstrap` writes to
`.git/hooks/pre-commit`. Removing the stack does **not** uninstall
that hook (we never run `pre-commit uninstall`). The orphan-report
text needs to call this out:

```
Stack 'secrets' was removed.
The pre-commit hook is still wired in .git/hooks/pre-commit.
Run:  pre-commit uninstall
to disconnect it, or restore the stack with:
      sunaba rebuild myapp --add secrets
```

### `.gitignore` upgrade path for existing projects

This is the gap the original proposal didn't close.

The expanded `.gitignore` ships in `_default_gitignore()` and is
written by `sunaba new`. **An existing project that runs
`sunaba upgrade` (the CLI itself) and then `sunaba rebuild` does
not get the new `.gitignore` baseline** — by design, because
`rebuild` must not clobber a file the user almost certainly edited.

But that means a user can adopt the secrets posture *and never see
the new ignore patterns*, which silently undercuts the whole
proposal.

**Decision: add a dedicated `sunaba sync-gitignore` command (or
`sync` subcommand) for opt-in `.gitignore` upgrade.** Behavior:

- Reads the project's current `.gitignore`.
- Computes the union of (current contents) and
  `_default_gitignore()` output.
- Preserves user-specific entries.
- Shows a diff before writing.
- Refuses to run on a `.gitignore` outside a known sunaba project
  (registry check), unless `--force`.

Sketch:

```bash
sunaba sync-gitignore myapp           # diff + confirm
sunaba sync-gitignore myapp --dry-run # diff only
sunaba sync-gitignore --all           # walk every registered project
```

This gives users one explicit path to bring legacy projects up to
the new baseline without surprises.

### Implementation order

This PR depends on the harness PR's `_files` mechanism and on its
orphan-reporting infrastructure. Land **after** harness. The
`sync-gitignore` command added here is independent of the
stack-aware-agent-files PR, so the order between this and that PR
doesn't matter.

## Follow-ups to track

1. **Non-Azure equivalents** for the key-behind-proxy doc:
   - **AWS**: API Gateway in front of Lambda, with Lambda fetching
     the key from Secrets Manager.
   - **GCP**: Apigee or API Gateway with Workload Identity Federation;
     the upstream key in Secret Manager.
   - **Cloudflare**: Workers KV / Workers Secrets in front of any
     model API.
2. **MCP-config leak surface.** GitGuardian's 2026 finding — 24k
   secrets in `.mcp.json` files on GitHub — argues for an explicit
   "MCP config is a leak surface" advisory in `SECURITY.md`. Add
   once the harness PR has stabilized.
3. **`sunaba doctor` command.** A read-only command that scans an
   existing project for known leak patterns (committed `.env`,
   service-account JSON, API keys in source). Out of scope for this
   PR.

## Sources

- [TurboGeek — AI coding tools and 29M leaked secrets (2026)](https://www.turbogeek.co.uk/ai-coding-tools-secrets-leaked-2026/)
- [linou518 — Complete 2026 secrets management guide](https://dev.to/linou518/is-your-api-key-still-running-naked-the-complete-2026-secrets-management-guide-4m7n)
- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks)
- [GitHub — push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection)
- [Vercel — environment variables](https://vercel.com/docs/environment-variables)
- [Vercel — sensitive environment variables](https://vercel.com/docs/environment-variables/sensitive-environment-variables)
- [Firebase — secret params (Functions v2)](https://firebase.google.com/docs/functions/config-env)
- [AWS Secrets Manager](https://aws.amazon.com/documentation-overview/secrets-manager/)
- [AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Google Cloud Secret Manager — best practices](https://docs.cloud.google.com/secret-manager/docs/best-practices)
- [Google Cloud Workload Identity Federation — best practices](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation)
- [Gemini API — `x-goog-api-key`](https://ai.google.dev/gemini-api/docs/api-key)
- [Azure APIM — named values + Key Vault references](https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-properties)
- [Azure APIM — `validate-azure-ad-token` policy](https://learn.microsoft.com/en-us/azure/api-management/validate-azure-ad-token-policy)
- [Azure APIM — language-model API import (OpenAI-compatible Gemini)](https://learn.microsoft.com/en-us/azure/api-management/openai-compatible-google-gemini-api)
- [Azure APIM — Event Hubs logging](https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-log-event-hubs)
- [Azure Cosmos DB — Foundry Agent Service integration](https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/azure-agent-service)
- [Badr Kacimi — APIM as AI Gateway for Foundry (Apr 2026)](https://medium.com/@badrkacimi/azure-api-management-as-an-ai-gateway-for-microsoft-foundry-enterprise-model-governance-at-scale-64953cbf3da0)
- [Journey of the Geek — Foundry BYO AI Gateway pt 2 (Mar 2026)](https://journeyofthegeek.com/2026/03/09/microsoft-foundry-apim-and-model-gateway-connections-part-2/)
