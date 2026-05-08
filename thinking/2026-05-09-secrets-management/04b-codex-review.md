# 04 — Codex review: secrets management

> `03-llm-consultation-brief.md` に対する独立レビュー。
> Date: 2026-05-09.
> Scope: runtime ではなく、`sunaba` が生成するテンプレートの秘密情報管理。

## 結論

実装は **2 層** に分ける。

1. 拡張 `.gitignore` は default scaffold、つまり実質 `base` に入れる。
2. `pre-commit` / `gitleaks` と長めの秘密情報ドキュメントは、新しい opt-in の
   **`--stack secrets`** に入れる。

`harness` には畳み込まない。`harness` は agent の作業品質を上げるための実行・検証面、
`secrets` は秘密情報の漏洩防止面であり、併用は自然だが責務は別でよい。

```bash
sunaba new app --stack python --stack agents --stack harness --stack secrets
```

互換性の線引きは明確にする。ignore pattern は低リスクな予防策なので default、
commit を止める hook は挙動変更なので opt-in。

## A. Maturity score

| Axis | Score | 現状 |
|---|---:|---|
| `.gitignore` coverage | 2/5 | `.env` と `.env.local` は対象だが、cloud key / service account / agent-local state が抜けている。 |
| Agent rule clarity | 2/5 | README は runtime env の限界を正直に書いているが、`AGENTS.md` / `CLAUDE.md` に秘密情報配置ルールがない。 |
| Pre-commit detection | 1/5 | 生成物に `pre-commit` / `gitleaks` 設定がない。 |
| Per-cloud documentation | 1/5 | Vercel / Firebase / Azure / AWS / GCP の secret store guidance がない。 |
| Key-behind-proxy docs | 1/5 | 本番 agent workload で最も効く proxy pattern が未文書化。 |

## B. Concrete additions

### MUST 1 — 拡張 `.gitignore`

**What:** `src/sunaba_cli/cli.py::new()` の hard-coded `gitignore` 文字列を
`_default_gitignore()` のような helper に切り出し、以下を含める。

```gitignore
# Environment files
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

# Build/cache
.venv/
node_modules/
__pycache__/
*.pyc
.DS_Store
```

**Why:** Firebase Admin SDK JSON、service account key、SSH key、direnv export、
agent の local state などが index に入る前に止まる。

**Where it lives:** default scaffold。現コードでは `templates/base/` ではなく
`new()` が直接 `.gitignore` を書くため、実装上は `_default_gitignore()` を呼ぶ形でよい。

**Compatibility risk:** `sunaba new` には低リスク。既存 project の `.gitignore` を
`rebuild` で上書きしないこと。merge/append 仕様がないまま `_build_config_files()` に
`.gitignore` を入れるのは避ける。

### MUST 2 — agent instruction の secrets rule

**What:** `src/sunaba_cli/templates/agents/AGENTS.md` と `CLAUDE.md` に短い
`Secrets` セクションを追加する。`GEMINI.md` にも同じ内容を入れるとよい。

```md
## Secrets
- Local development uses exactly one `.env` file at the repository root.
- Do not create `web/.env`, `api/.env`, nested `.env.local`, or copied key files.
- Never write API keys, tokens, private keys, Firebase admin SDK JSON, or cloud credential files into source-controlled paths.
- Production, preview, and CI secrets must come from the platform secret store.
- Runtime env vars inside this container are readable by local processes and agents; do not treat them as isolation.
```

**Why:** agent は悪意よりも分散配置で漏らす。root の `.env` は ignore されていても、
`web/.env` や `api/.env.local` が後から commit される事故を防ぐ。

**Where it lives:** base agent templates。agent が毎回読む面なので効果が高い。

**Compatibility risk:** 実行挙動は変わらない。ただし `sunaba sync` は agent files を
上書きするため、release note で明示する。

### MUST 3 — 新しい `--stack secrets`

**What:** `src/sunaba_cli/templates/stacks/secrets.json` を追加する。`harness` 提案と同じ
`_files` mechanism を使い、devcontainer merge とは別に任意ファイルを生成できるようにする。

```json
{
  "_description": "Secret hygiene scaffold: gitleaks pre-commit config and per-cloud secret-store docs",
  "_files": {
    ".pre-commit-config.yaml": "secrets/pre-commit-config.yaml",
    ".gitleaks.toml": "secrets/gitleaks.toml",
    "docs/secrets/README.md": "secrets/docs/README.md",
    "docs/secrets/azure-foundry-apim-gemini-cosmos.md": "secrets/docs/azure-foundry-apim-gemini-cosmos.md",
    "docs/secrets/vercel.md": "secrets/docs/vercel.md",
    "docs/secrets/firebase.md": "secrets/docs/firebase.md",
    "docs/secrets/aws.md": "secrets/docs/aws.md",
    "docs/secrets/gcp.md": "secrets/docs/gcp.md"
  },
  "_bootstrap": [
    "# --- secrets ---",
    "if ! command -v pre-commit >/dev/null 2>&1; then pip install --user --quiet pre-commit; fi",
    "if [ -f .pre-commit-config.yaml ] && [ -d .git ]; then pre-commit install >/dev/null 2>&1 || true; fi"
  ]
}
```

`templates/secrets/pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
```

`templates/secrets/gitleaks.toml`:

```toml
title = "sunaba generated gitleaks config"

[allowlist]
description = "Allow committed templates, never real local secrets"
paths = [
  '''^\.env\.example$''',
  '''^\.env\..*\.example$''',
]
```

実装時点で `rev` は最新安定版に pin する。pattern 数は version で変わるため、
生成 docs では「Gitleaks の maintained default rules」と書き、固定の数を強調しない。

**Why:** `.gitignore` は未追跡ファイルにしか効かない。`gitleaks` は追跡済みファイルへ
貼られた key や、ignore 漏れを commit 前に検出する。

**Where it lives:** 新規 `secrets` stack。base ではない。`harness` でもない。
commit block は明確な挙動変更であり、security 専用 stack として opt-in にする。

**Compatibility risk:** stack 未選択ならなし。`--stack secrets` 選択時は、疑似陽性を含め
commit が止まる可能性がある。escape hatch は `SKIP=gitleaks git commit ...` とし、
false positive のレビュー済み例外に限定して案内する。

### SHOULD — repo-level docs

**What:** source repo に `docs/secrets/` を作り、`SECURITY.md` からリンクする。
生成 project には `--stack secrets` で同じ内容の subset をコピーする。

**Why:** generated project は disposable だが、`sunaba-cli` 自体には public な canonical stance が必要。

**Where it lives:** source repo `docs/secrets/`、generated copy は `secrets` stack。

**Compatibility risk:** CLI 挙動にはなし。

### COULD — GitHub Actions scan

**What:** `--stack secrets` で `.github/workflows/gitleaks.yml` を生成する。

```yaml
name: gitleaks
on: [pull_request, push, workflow_dispatch]
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

**Why:** local hook は全員が install するとは限らない。CI は最後の検出層になる。

**Where it lives:** `--stack secrets`。CI 挙動を増やすため base にはしない。

**Compatibility risk:** opt-in だが PR/check が fail する可能性あり。初回 PR から外してもよい。

## Placement decisions

| Question | Position |
|---|---|
| Expanded `.gitignore`: base or stack? | **Base/default scaffold。** 低リスクな予防策。`rebuild` で既存 `.gitignore` を上書きしない。 |
| `pre-commit` + `gitleaks`: base or harness? | **どちらでもなく `--stack secrets`。** commit block は明示 opt-in。 |
| New `secrets` stack or fold into `harness`? | **New `secrets` stack。** `harness` と併用できるが責務は分ける。 |

## C. Azure Foundry -> APIM -> Gemini -> Cosmos

生成 docs としては `docs/secrets/azure-foundry-apim-gemini-cosmos.md` に置く。

### Goal

agent は Gemini を呼べるが、`GEMINI_API_KEY` は一度も agent に渡さない。
real key は Key Vault に置き、APIM が outbound request にだけ注入する。

```text
Foundry agent
     |
     | Managed Identity / Entra token
     v
Azure API Management
     | set-header x-goog-api-key from Key Vault named value
     v
Google Generative Language API

Azure Cosmos DB
     stores Foundry threads/state and optional sanitized audit records
```

### Resources to create

1. **Azure Key Vault**
   - Secret: `gemini-api-key`
   - APIM managed identity に `Key Vault Secrets User`、または `get/list` 相当を付与する。

2. **Azure API Management**
   - system-assigned managed identity を有効化する。
   - named value `gemini-api-key` を type **Key vault** で作り、version なしの Key Vault secret URI を参照する。
   - Gemini API を OpenAI-compatible language model API または passthrough HTTP API として公開する。
   - caller auth は APIM subscription key より Entra token validation を優先する。

3. **Microsoft Foundry project / agent**
   - hosted agent か agent tool runtime に Managed Identity を持たせる。
   - tool/action config には APIM URL だけを書く。Gemini key は書かない。

4. **Azure Cosmos DB for NoSQL**
   - Foundry standard/BYO storage で thread state / agent state を保持する。
   - 必要なら sanitized audit record を Event Hubs + Function 経由で Cosmos に書く。

5. **Optional Event Hubs + Function**
   - APIM `log-to-eventhub` で metadata を流す。
   - Function で redaction/truncation して Cosmos に audit record を保存する。

### APIM policy

前提 named values:

- `aad-tenant-id`: Entra tenant ID
- `foundry-managed-identity-client-id`: APIM 呼び出しを許可する managed identity / shim app の client ID
- `gemini-api-key`: Key Vault-backed named value

Minimal inbound policy:

```xml
<policies>
  <inbound>
    <base />

    <validate-azure-ad-token tenant-id="{{aad-tenant-id}}">
      <client-application-ids>
        <application-id>{{foundry-managed-identity-client-id}}</application-id>
      </client-application-ids>
    </validate-azure-ad-token>

    <set-header name="x-goog-api-key" exists-action="override">
      <value>{{gemini-api-key}}</value>
    </set-header>

    <set-header name="Authorization" exists-action="delete" />
    <set-header name="Ocp-Apim-Subscription-Key" exists-action="delete" />

    <set-backend-service base-url="https://generativelanguage.googleapis.com" />
  </inbound>

  <backend>
    <forward-request />
  </backend>

  <outbound>
    <base />
  </outbound>

  <on-error>
    <base />
  </on-error>
</policies>
```

friendly path を公開する場合は operation policy で rewrite する。

```xml
<rewrite-uri template="/v1beta/models/gemini-2.5-flash:generateContent" />
```

Observability は metadata first にする。

```xml
<log-to-eventhub logger-id="sunaba-ai-audit">
@{
  return new JObject(
    new JProperty("time", DateTime.UtcNow.ToString("o")),
    new JProperty("requestId", context.RequestId),
    new JProperty("operation", context.Operation.Name),
    new JProperty("callerIp", context.Request.IpAddress),
    new JProperty("status", context.Response?.StatusCode)
  ).ToString();
}
</log-to-eventhub>
```

`x-goog-api-key`、`Authorization`、full prompt、full response は default で log しない。
payload audit が必要なら、sampling / redaction / retention を決めてから追加する。

### Foundry agent が APIM に認証する方法

推奨:

1. APIM-protected API 用の Entra application ID URI / audience を用意する。
2. Foundry hosted agent または tool runtime が Managed Identity で token を取得する。
3. request に `Authorization: Bearer <token>` を付ける。
4. APIM が `validate-azure-ad-token` で検証し、Key Vault named value から `x-goog-api-key` を注入する。

注意点: Foundry の declarative action surface が常に managed-identity bearer token を直接付けられるとは限らない。
直接できない場合でも Gemini key を agent に渡さない。Azure Function / Logic App の薄い shim を置き、
shim に Managed Identity を持たせて APIM を呼ばせる。

APIM subscription key は routine path では推奨しない。Gemini key を隠す意味では一段よくなるが、
結局は static shared secret であり、target posture は Entra token / Managed Identity。

### 何をどこに保存するか

| Data | Location |
|---|---|
| Gemini API key | Key Vault secret。APIM named value が参照する。 |
| APIM caller identity | Entra token / Managed Identity を APIM policy で検証する。 |
| Agent thread state | Foundry standard/BYO storage の Cosmos DB。 |
| Request/response audit | Event Hubs -> Function -> Cosmos の sanitized record を推奨。 |
| APIM platform metrics | APIM analytics / Azure Monitor / Application Insights。 |
| Raw provider key | Foundry instructions、tool config、repo、`.env`、Cosmos、logs のどこにも置かない。 |

### Smallest end-to-end demo

1. agent/tool environment に upstream key がないことを確認する。

   ```bash
   printenv | rg 'GEMINI|GOOGLE_API_KEY' && exit 1 || true
   ```

2. managed-identity-enabled shim または hosted tool runtime から APIM を呼ぶ。

   ```python
   import os
   import requests
   from azure.identity import DefaultAzureCredential

   APIM_URL = os.environ["APIM_GEMINI_URL"]
   APIM_SCOPE = os.environ["APIM_APP_ID_URI"] + "/.default"

   token = DefaultAzureCredential().get_token(APIM_SCOPE).token
   response = requests.post(
       APIM_URL,
       headers={
           "Authorization": f"Bearer {token}",
           "Content-Type": "application/json",
       },
       json={
           "contents": [
               {"parts": [{"text": "Reply with only: apim-ok"}]}
           ]
       },
       timeout=30,
   )
   response.raise_for_status()
   print(response.json())
   ```

3. negative controls:
   - bearer token を外すと APIM が 401 を返す。
   - generated project と tool env を検索しても Gemini key がない。
   - Key Vault access logs では APIM identity が secret reader になっている。
   - APIM / Event Hubs / Cosmos の audit record に `x-goog-api-key` がない。

これで agent が Gemini key を見ずに Gemini を呼べることを示せる。

### Cost / performance / observability trade-offs

- **Cost:** 小規模 hobby project では APIM が相対的に高い。prototype は consumption/basic で始め、
  production の private networking / gateway policy / throughput 要件で tier を見直す。
- **Latency:** APIM は network hop と policy execution を追加する。token validation と Key Vault-backed named value は通常許容範囲だが、測定する。
- **Rotation:** Key Vault secret 更新は APIM named value に反映されるが即時ではない。rotation window を設ける。
- **Observability:** APIM は gateway metrics、Cosmos は agent state / optional audit。役割を混同しない。
- **Security:** この pattern は upstream Gemini key を agent から隠す。prompt/response 自体は機微データになり得るので別途 retention と redaction が必要。

## D. Per-cloud pages

### Vercel

**Where secrets live:** Vercel Project/Team Environment Variables。Preview / Production は sensitive を使う。
`NEXT_PUBLIC_*` は browser に出るため秘密情報ではない。

**Local mapping:** `vercel env pull .env.local` は local mirror。ignore された local dev 用ファイルとして扱う。
`sunaba` の基本ルールは root の single `.env` だが、Vercel workflow で `.env.local` を使う場合も source of truth ではないと明記する。

**Agent rule:** `NEXT_PUBLIC_*` に secret value を入れない。server-only secret は Vercel env vars、local mirror は commit しない。

### Firebase

**Where secrets live:** Functions v2 は Cloud Secret Manager-backed secret params
（`defineSecret` / `SecretParam`）。Firebase Admin SDK JSON は ADC / workload identity が使えるなら作らない。

**Local mapping:** emulator-only config は local に閉じ、commit しない。
`*-firebase-adminsdk-*.json` と `serviceAccount*.json` は repo に置かない。

**Agent rule:** Firebase admin SDK JSON を repo に生成しない。Secret Manager と local ADC / emulator config を使う。

### AWS

**Where secrets live:** rotation が必要なものは AWS Secrets Manager。単純な static config は SSM Parameter Store `SecureString`。
compute では static access key より IAM role / STS を優先する。

**Local mapping:** host の `~/.aws` profile / SSO / short-lived STS を使う。
project tree の `.aws/` は ignore し、home の mounted `~/.aws` volume と混同しない。

**Agent rule:** `aws_access_key_id` / `aws_secret_access_key` を project tree に書かない。host profiles、SSO、managed roles を使う。

### GCP

**Where secrets live:** Google Secret Manager。外部 compute は Workload Identity Federation、local dev は ADC を優先する。
service-account JSON key は last resort。

**Local mapping:** `gcloud auth application-default login` を使う。JSON key が unavoidable なら repo 外に保存し、env var で参照する。

**Agent rule:** service-account JSON を repo に作らない。ADC、Workload Identity Federation、Secret Manager を使う。

## E. Test strategy

cloud call は不要。構造テストでよい。

```python
def test_default_gitignore_covers_secret_file_family():
    text = cli_module._default_gitignore()
    for pattern in [
        ".env.*",
        "!.env.example",
        "*.pem",
        "*.key",
        "id_rsa*",
        "id_ed25519*",
        "**/serviceAccount*.json",
        "**/*-firebase-adminsdk-*.json",
        "credentials.json",
        ".claude/settings.local.json",
        ".envrc",
        ".aws/",
        ".azure/",
        ".gcloud/",
    ]:
        assert pattern in text
```

```python
def test_secrets_stack_emits_gitleaks_and_docs():
    files = _build_config_files("p", ["secrets"])
    assert ".pre-commit-config.yaml" in files
    assert ".gitleaks.toml" in files
    assert "docs/secrets/azure-foundry-apim-gemini-cosmos.md" in files
```

```python
def test_pre_commit_config_uses_pinned_gitleaks():
    text = _build_config_files("p", ["secrets"])[".pre-commit-config.yaml"]
    assert "https://github.com/gitleaks/gitleaks" in text
    assert "id: gitleaks" in text
    assert "rev: v" in text
    assert "rev: main" not in text
```

```python
def test_agent_templates_include_single_root_env_rule():
    text = (TEMPLATES_DIR / "agents" / "AGENTS.md").read_text()
    assert "one `.env`" in text.lower() or "single `.env`" in text.lower()
    assert "repository root" in text.lower()
```

`_files` を導入するなら次も見る。

- `_files` destination の `..` を reject する。
- absolute destination を reject する。
- destination collision は「後勝ち」か「明示 fail」かを決めてテストする。
- `rebuild --dry-run --stack secrets` は docs/config を new として表示し、書き込まない。

この repo は PyYAML を依存に持たないため、YAML は parser 追加なしの構造 assertion で十分。

## F. Top-3 picks

3 つだけなら次。

1. **拡張 `.gitignore` を default scaffold に入れる。** 効果が広く、挙動変更が小さい。
2. **agent secret rules を追加する。** single root `.env` と key file copy 禁止は agent 特有の事故を直接減らす。
3. **`--stack secrets` + gitleaks pre-commit config。** ignore では防げない tracked-file への貼り付けを検出する。

Azure APIM doc は production posture として非常に重要だが、初手 3 件に限るなら、まず scaffold 全体の漏洩確率を下げる変更を優先する。

## G. Push-back

1. **cloud secret store は devcontainer 内 agent から runtime env var を守らない。**
   `remoteEnv` に入った時点で container 内 process は読める。これは引き続き明記する。

2. **"gitleaks has 160+ patterns" を固定文言にしない。**
   version で変わる。生成 docs では maintained default rules と書き、`rev` を pin する。

3. **APIM subscription key を推奨 caller auth にしない。**
   それも static shared secret。移行策としては可だが、目標は Entra token / Managed Identity。

4. **full prompt/response を default log しない。**
   prompt と response は user data、credential、proprietary context を含み得る。metadata first にする。

5. **`.gitleaks.toml` allowlist を広げすぎない。**
   `.env.example` の path allowlist は妥当だが、fake key regex の広い allowlist は本物の漏洩を隠す。

## Sources

- Gitleaks README: pre-commit hook and config precedence:
  <https://github.com/gitleaks/gitleaks>
- GitHub push protection:
  <https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection>
- Vercel environment variables:
  <https://vercel.com/docs/environment-variables>
- Vercel sensitive environment variables:
  <https://vercel.com/docs/environment-variables/sensitive-environment-variables>
- Firebase Functions secret params:
  <https://firebase.google.com/docs/functions/config-env>
- AWS Secrets Manager:
  <https://aws.amazon.com/documentation-overview/secrets-manager/>
- AWS SSM Parameter Store:
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html>
- Google Cloud Secret Manager best practices:
  <https://docs.cloud.google.com/secret-manager/docs/best-practices>
- Google Cloud Workload Identity Federation best practices:
  <https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation>
- Google workload identities and service-account key risk:
  <https://cloud.google.com/iam/docs/workload-identities>
- Gemini API key / `x-goog-api-key`:
  <https://ai.google.dev/gemini-api/docs/api-key>
- Gemini API reference:
  <https://ai.google.dev/api>
- Azure API Management named values and Key Vault references:
  <https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-properties>
- Azure API Management `set-header` policy:
  <https://learn.microsoft.com/en-ca/azure/api-management/set-header-policy>
- Azure API Management Entra token validation:
  <https://learn.microsoft.com/en-us/azure/api-management/validate-azure-ad-token-policy>
- Azure API Management language model API import:
  <https://learn.microsoft.com/en-us/azure/api-management/openai-compatible-llm-api>
- Azure API Management subscriptions:
  <https://learn.microsoft.com/en-us/azure/api-management/api-management-subscriptions>
- Azure API Management Event Hubs logging:
  <https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-log-event-hubs>
- Azure Cosmos DB integration with Foundry Agent Service:
  <https://learn.microsoft.com/en-us/azure/cosmos-db/gen-ai/azure-agent-service>
