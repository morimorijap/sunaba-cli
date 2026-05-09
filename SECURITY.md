# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability in `sunaba-cli`, please report it privately:

1. **Preferred**: Open a [GitHub Security Advisory](https://github.com/morimorijap/sunaba-cli/security/advisories/new) on this repository.
2. **Alternative**: Open a normal GitHub issue with a minimal reproduction — but **do not** include exploit details for unpatched vulnerabilities.

Please include:

- Affected version / commit
- Steps to reproduce
- Impact (what an attacker can do)
- Suggested fix, if you have one

We aim to acknowledge reports within 72 hours and to ship fixes for
high-severity issues within two weeks.

## Scope

`sunaba-cli` is a scaffolding tool. Its security surface is primarily:

- The CLI itself (path traversal, symlink handling, command injection)
- Generated files (`.devcontainer/`, `.github/`, `.mcp.json`, `.vscode/`)
- The bootstrap shell script run inside the devcontainer

### Out of scope

- Vulnerabilities in upstream AI agent CLIs (`@anthropic-ai/claude-code`,
  `@openai/codex`, `@google/gemini-cli`) — please report those to the
  respective projects.
- Vulnerabilities in MCP servers fetched via `npx` / `uvx`.
- Vulnerabilities in the base devcontainer image
  (`mcr.microsoft.com/devcontainers/base:jammy`) or in devcontainer features
  (`ghcr.io/devcontainers/features/*`).
- User code written inside a generated sandbox. A `sunaba` sandbox protects
  the **host** from the container, not the container from its own contents.

## Known trade-offs

By design, `sunaba-cli` installs certain tools at `@latest` on every first
container start:

- `@anthropic-ai/claude-code`
- `@openai/codex`
- `@google/gemini-cli`
- `vercel` (with `--stack nextjs`)
- `neonctl` (with `--stack neon`)

This is an intentional supply-chain / freshness trade-off. If an upstream
package is compromised, a fresh `sunaba` sandbox that starts after the
compromise will execute the malicious version. Users who need deterministic
builds should fork this repository and pin versions in
`src/sunaba_cli/templates/base/bootstrap.sh` and the relevant stack files.

See the `Security notes` section of [README.md](README.md) for the full list
of what `sunaba-cli` does and does not protect against.

## Secrets

`sunaba-cli` ships defense-in-depth for secret hygiene, but each
layer has clear limits:

- The default `.gitignore` excludes the common secret-file family
  (cloud credentials, SSH keys, Firebase admin SDK JSON, agent
  local state, the wider `.env.*` family). It only covers
  *untracked* files. Use `sunaba sync-gitignore <project>` to
  bring an existing project up to the current baseline without
  losing your own additions.
- `--stack secrets` adds `pre-commit` with `gitleaks`, a
  `.gitleaks.toml` allowlist, and a CI scan. This blocks commits
  with detected secrets; it does not protect already-tracked
  files.
- Per-cloud guidance in [`docs/secrets/`](docs/secrets/) (when
  `--stack secrets` is selected) describes where each platform
  expects secrets to live (Vercel env vars, Google Secret
  Manager, AWS Secrets Manager, Azure Key Vault).

**Limit that no template can fix:** once an API key is in
`os.environ` inside the container, an agent process can read it,
log it, or send it to an attacker-controlled endpoint. The only
architectural mitigation against that failure mode is the
"key behind a proxy" pattern — the agent calls a gateway it has
identity-only access to, and the gateway substitutes the upstream
key. We document the
[Azure Foundry → APIM → Gemini → Cosmos](https://github.com/morimorijap/sunaba-cli/blob/main/thinking/2026-05-09-secrets-management/05-proposal.md)
version of this pattern in detail; equivalent patterns exist on
AWS (API Gateway / Lambda) and GCP (Apigee / API Gateway).

## Autonomy

`--stack autopilot` is **autonomous**. The Stop hook re-engages the
agent on verify failure, up to a configured iteration / wall-clock /
changed-file budget:

- `SUNABA_AUTOPILOT_MAX_ITERS` (default 5)
- `SUNABA_AUTOPILOT_MAX_MINUTES` (default 30)
- `SUNABA_AUTOPILOT_MAX_CHANGED_FILES` (default 25)

Budget caps are *defaults* — the user can lift them by setting the
env vars, in which case real money may be spent before a human
intervenes. Branch protection (`.githooks/pre-push`) prevents pushes
to `main` / `master`; it does not prevent `git push` to a feature
branch on a public remote. Treat the autopilot stack as
production-affecting if the project's remote is public.

Gemini CLI does not have a Stop-hook re-engage equivalent as of
May 2026 — `--stack autopilot` is explicitly Claude- and
Codex-CLI-shaped. See `docs/agents/gemini-autopilot-limitations.md`
in any project that includes the stack.
