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

APIM_URL   = os.environ["APIM_GEMINI_URL"]
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
