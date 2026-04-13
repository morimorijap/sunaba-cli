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
