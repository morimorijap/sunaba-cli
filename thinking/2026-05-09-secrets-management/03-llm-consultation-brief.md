# 03 — LLM consultation brief (secrets management)

> Self-contained brief sent to external reviewers (Codex / Gemini Pro
> Preview). They have **not** seen the conversation that led here.

---

## You are reviewing

A small open-source CLI called **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>). It scaffolds disposable
devcontainer sandboxes for AI coding agents (Claude Code, OpenAI Codex
CLI, Google Gemini CLI). It is a **template generator** — it writes
files, then gets out of the way. It is not a runtime.

For each project the CLI emits a `.devcontainer/`, `.mcp.json`,
`AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `skills.md`, a
`.gitignore`, etc. Available stacks (composable):
`python` `nextjs` `aws` `azure` `gcp` `neon` `agents` (injects API
keys into the container) `docker` `playwright`.

## The problem

API keys for AI providers are leaking to public GitHub repos at high
rates (81% YoY surge in AI-credential leaks; 24k+ secrets found in
MCP config files specifically). Coding agents make this worse — they
write `.env` files, copy keys between locations, and occasionally
commit `*-firebase-adminsdk-*.json` etc.

Today `sunaba` does:

- Inject secrets only when the user asks for them
  (`--stack agents` / `aws` / `neon` / `nextjs`), via
  `${localEnv:...}` in `remoteEnv`. The base container starts with
  `remoteEnv: {}`.
- Generate a thin `.gitignore` covering only `.env` and `.env.local`.
- Document in the README that "any process in the container can read
  the keys" once `--stack agents` is set.

What `sunaba` does **not** do today:

1. Cover the rest of the secret-leak file family in `.gitignore`
   (`.env.*`, `*.pem`, `*.key`, `*.p12`, `id_rsa*`, `id_ed25519*`,
   `**/serviceAccount*.json`, `**/*-firebase-adminsdk-*.json`,
   `credentials.json`, `.claude/settings.local.json`, `.envrc`,
   `.aws/`, `.azure/`, `.gcloud/`).
2. State a "single `.env` at repo root, nowhere else" rule in
   `AGENTS.md` / `CLAUDE.md`.
3. Ship a pre-commit secret-scanner config (`gitleaks` is the
   industry default in 2026, 160+ patterns).
4. Document **per-cloud** secret-store guidance for Vercel, Firebase,
   Azure, AWS, GCP.
5. Document the **"key behind a proxy"** pattern. Specifically, the
   user wants the Azure pattern called out in detail:
   ```
   Foundry agent
        │  (Managed Identity, no upstream key)
        ▼
   Azure API Management
        │  (subscription-key-from-Key-Vault policy)
        │  (real Gemini key, never seen by client)
        ▼
   Google Generative Language API
        │
        ▼
   Cosmos DB  (logs, agent threads, request/response audit)
   ```
   This is the highest-leverage posture move for any user actually
   deploying agent workloads.

## Constraints

- **Templates only.** `sunaba` writes files the user owns. We don't
  ship runtime tooling.
- **Opt-in.** The harness PR (separate, in flight) is introducing
  `--stack harness`. This new work could either (a) live as a peer
  `--stack secrets`, (b) fold into the existing `harness` stack, or
  (c) ship partly in `base/` (the `.gitignore` expansion is a strong
  candidate for `base/`).
- **No backwards-incompatible churn.** Existing
  `sunaba new` / `sunaba rebuild` users must not see surprises.
- **Honest about limits.** Cloud-managed secrets do **not** protect
  against an agent inside the container reading runtime env vars.
  Whatever we ship has to keep saying that out loud.

## What we want from you

### A. Maturity score (1–5) on each axis

`.gitignore` coverage · agent rule clarity · pre-commit detection ·
per-cloud documentation · "key behind a proxy" pattern docs.

### B. Concrete additions, prioritized must / should / could

For each:
- **What** — exact file path, content sketch or full snippet.
- **Why** — the specific leak pattern this prevents.
- **Where it lives** — `base/`, the existing `harness` stack, or a
  new `secrets` stack. Argue for the placement.
- **Compatibility risk** — does this change behavior for anyone
  running `sunaba new` / `sunaba rebuild` / `sunaba sync` today?

Reviewers must take a position on:

- Should the expanded `.gitignore` go into `base/` (so every project
  gets it) or under a stack? We lean toward `base/` because a
  conservative `.gitignore` is not a behavior change in any
  meaningful sense, but argue if you disagree.
- Should `pre-commit` + `gitleaks` be in `base/` or under the
  harness stack? It's a runtime behavior change (commits get
  blocked).
- Should this be a **new `secrets` stack** or fold into the
  existing `harness` stack? Pick one.

### C. The Azure Foundry → APIM → Gemini → Cosmos doc

Write the page you'd want to read as someone deploying this for the
first time. Include:

- Resources to create (Key Vault, APIM instance, Foundry project,
  Cosmos DB account).
- The APIM policy snippet that injects the Gemini key from Key Vault.
- How the Foundry agent authenticates to APIM (Managed Identity, not
  a static subscription key, where possible).
- What gets logged to Cosmos vs. what stays in APIM analytics.
- The smallest end-to-end demo that proves the agent can call Gemini
  *without ever seeing the Gemini key*.
- Cost / performance / observability trade-offs.

This is the user's primary ask. Don't gloss it.

### D. Per-cloud pages — Vercel, Firebase, AWS, GCP

For each: where the secret should live, how the local dev experience
maps to it, the one-line agent rule that prevents the most common
leak on that platform.

### E. Test strategy

`sunaba` is tested with `pytest`. Propose **structural** tests for
whatever we ship: `.gitignore` contents, `pre-commit-config.yaml`
shape, presence of expected docs.

### F. Top-3 picks

If we can only land three things, which three move the secrets
posture the most?

### G. Push-back

If anything in the hypothesized gaps is wrong, say so. We'd rather
drop a bad idea now than implement it.

---

## Length and format

Long-form is welcome. We're going to land this as a public design
doc. Markdown. Code/file snippets in fenced blocks. Cite sources for
opinions that come from external references.
