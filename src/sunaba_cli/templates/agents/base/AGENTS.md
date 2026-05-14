# AGENTS.md

These rules apply to any agent (Claude Code, Codex, Gemini CLI) operating
in this repository.

## General rules

- Read the task, `git status`, and the smallest relevant files before
  proposing changes.
- Prefer existing project commands over inventing new ones.
- Add or update tests for changed behavior.
- Keep changes scoped to what was requested. No drive-by refactors.

## Recommended folder layout

Layered, feature-first split under the stack's source root (`src/`, `lib/`, package root):

- `app/` — top-level wiring (routes, providers, entry points, themes)
- `core/` — shared utilities, components, constants
- `features/<name>/` — `data/` (I/O), `domain/` (models), presentation (`ui/`, `handlers/`)
- `services/` — cross-cutting (notifications, SDK adapters)
- `config/` — environment wiring (no secrets)

Top-level folders are plural; feature names are singular (`features/auth/`).
Isolate external SDK/API access in `data/` or `services/` so the rest stays decoupled.
Treat this as a default — follow the stack's idiomatic layout when one already exists.

## Selected stacks

<!-- SUNABA STACKS START -->
<!-- SUNABA STACKS END -->

## Secrets

- Local development uses **exactly one** `.env` file at the repository
  root. Do not create `web/.env`, `api/.env`, nested `.env.local`, or
  copies of key files.
- Never write API keys, tokens, private keys, Firebase admin SDK
  JSON, or cloud credential files into source-controlled paths.
- Production, preview, and CI secrets must come from the platform's
  secret store: Vercel Environment Variables, Google Secret Manager,
  AWS Secrets Manager, Azure Key Vault. See `docs/secrets/` (when
  `--stack secrets` is selected) for per-cloud guidance.
- Runtime env vars inside this container are readable by every local
  process and agent. Cloud secret managers and `.gitignore` do not
  change that.

## MCP servers

Claude Code, Codex, and Gemini CLI are available in this sandbox. Use
MCP for cross-agent delegation when one agent's specialty fits the task
better.

<!-- SUNABA USER START -->
<!-- Edit freely below. `sunaba sync` preserves anything between the USER markers. -->
<!-- SUNABA USER END -->
