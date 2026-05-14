# sunaba-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> 日本語版は [README.ja.md](README.ja.md) にあります。

**One-command devcontainer sandboxes for AI agent development.**

`sunaba` (Japanese for "sandbox") scaffolds isolated, disposable devcontainer
environments pre-wired for [Claude Code](https://claude.com/claude-code),
[OpenAI Codex CLI](https://github.com/openai/codex), and
[Google Gemini CLI](https://github.com/google-gemini/gemini-cli) — plus MCP
servers, cloud SDKs, and project scaffolding. Break it, throw it away, make
another one.

---

## Why

AI coding agents are powerful but messy: they install global packages, fetch
random scripts, and mutate your machine in surprising ways. `sunaba-cli` gives
you a **fresh, isolated Linux container per project** with all three major
agents pre-installed and pre-configured to talk to each other via MCP.

- 🧪 **Disposable** — if an agent breaks something, rebuild the container
- 🔌 **Composable** — mix and match stacks (`python`, `nextjs`, `aws`, `gcp`, …)
- 🤖 **Agents talk to each other** — Claude Code can call Codex and Gemini as MCP sub-agents
- 🔐 **Opt-in secrets** — API keys only injected when you ask for them (`--stack agents`)
- 📦 **Self-contained** — `uv tool install` gives you a global `sunaba` command

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/morimorijap/sunaba-cli
```

You now have a `sunaba` command on your PATH.

### Upgrade

```bash
sunaba upgrade
```

## Quick start

```bash
# Interactive stack picker
sunaba new myapp

# Explicit stacks
sunaba new myapp --stack python --stack agents

cd myapp
code .
# VS Code: Cmd+Shift+P → "Dev Containers: Reopen in Container"
```

The first container start takes a few minutes while base images and agent
CLIs install. Subsequent starts are fast (cached).

### Host-only mode (`--no-devcontainer`)

If you'd rather run the agents directly on your host machine instead of
inside a container, pass `--no-devcontainer`:

```bash
sunaba new local --stack python --no-devcontainer
```

This skips `.devcontainer/devcontainer.json` and `bootstrap.sh` and emits
only the host-portable pieces: `.mcp.json`, `.vscode/settings.json`, agent
instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `skills.md`), a
filtered `dependabot.yml` (no `devcontainers` / `docker` ecosystems), and
`.gitignore`.

After creation, `sunaba` checks your `PATH` and warns about any required
host commands that are missing — agent CLIs (`claude`, `codex`, `gemini`),
the MCP runtime (`npx`, `uvx`), and stack-specific tools (e.g. `uv`, `aws`,
`gcloud`, `az`, `neonctl`, `vercel`). Install whatever is reported missing.

## Commands

| Command | Description |
|---|---|
| `sunaba new <name>` | Scaffold a new sandbox project |
| `sunaba rebuild <name\|path>` | Change stacks on an existing project |
| `sunaba register <path> --stack ...` | Add an existing project to the registry |
| `sunaba list` | List registered projects |
| `sunaba stacks` | Show available stacks |
| `sunaba sync [<name>\|--all]` | Re-sync agent instruction files |
| `sunaba upgrade` | Update `sunaba-cli` itself |

## Stacks

| Stack | Contents |
|---|---|
| `python` | Python 3.14 + `uv` (installed via pip, no `curl \| sh`) |
| `nextjs` | Vercel CLI + ESLint / Tailwind VS Code extensions (Node.js is in base) |
| `aws` | `aws-cli` (devcontainer feature) + AWS env vars |
| `azure` | `az` CLI + Azure env vars |
| `gcp` | `gcloud` CLI + GCP env vars |
| `neon` | `neonctl` (Neon Postgres CLI) + PostgreSQL server (`postgresql` apt package, includes `psql`) + `NEON_API_KEY` |
| `agents` | Injects `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` from host |
| `docker` | `docker-outside-of-docker` (access host Docker daemon) |
| `playwright` | Chromium + Linux deps for Playwright / Chrome DevTools MCP (E2E browser automation) |
| `harness` | Claude Code-oriented harness templates: `.claude/settings.json` (permissions + Stop hook), a silent-on-success `verify.sh`, on-demand skills, planner / reviewer / verifier sub-agent role files, a 60-line ratchet `AGENTS.md`, and a `claudedocs/` trace directory. **Opt-in because it changes agent behavior at session boundaries.** |
| `secrets` | Secret hygiene scaffold: `.pre-commit-config.yaml` with `gitleaks` (pinned tag), a `.gitleaks.toml` allowlist, a CI scan workflow, and per-cloud docs in `docs/secrets/` (Vercel · Firebase · AWS · GCP · Azure Foundry → APIM → Gemini → Cosmos). **Opt-in because it changes commit-time behavior** (`git commit` is blocked when a secret is detected). |
| `rules` | Multi-target path-scoped rule files. One canonical source under `templates/rules/` renders to `.cursor/rules/<name>.mdc` (Cursor `globs:` / `alwaysApply:`), `.claude/rules/<name>.md` (Claude `paths:`), and `docs/agents/rules/<name>.md` (Codex / Gemini fallback). Low-risk context improvement; no runtime behavior change. |
| `autopilot` | Opt-in autonomous environment for Claude Code and Codex CLI: structured Stop-hook re-engage with budget caps (`SUNABA_AUTOPILOT_MAX_ITERS` / `_MINUTES` / `_CHANGED_FILES`), branch protection via `.githooks/pre-push`, operational planner / reviewer / verifier role files (Claude `.claude/agents/*.md` + Codex `.codex/agents/*.toml`), a subagent dispatch protocol document, `claudedocs/{plans,checkpoints}/`. **Changes agent runtime behavior** (Stop hook re-engages on verifier failure). Recommended invocation: `--stack harness --stack rules --stack autopilot` in that order so autopilot's operational role files override harness's seeds. Gemini CLI is documented as an honest gap — see `docs/agents/gemini-autopilot-limitations.md`. |
| `multi-agent` | Cooperative parallel-agent orchestration: shared YAML task list at `.agents/multi-agent/tasks.yaml` validated by `schema.json`, `owns:`-based hybrid conflict avoidance (overlapping `owns:` → orchestrator serializes), default cohort cap 4 via `SUNABA_MULTI_AGENT_MAX`, sharding flowchart in `docs/multi-agent/sharding.md`, `flock`-protected helper script (`scripts/agent-task.py`) with `claim` / `start` / `complete` / `fail` / `block` / `check-owns` / `overlap` subcommands, scoped subagent prompt template. Templates only — coordination is **cooperative, not enforced** (the helper makes the right thing easy; defense-in-depth is `git worktree` per shard + autopilot's branch protection + reviewer subagent). Recommended together with `--stack autopilot`. |

List them at runtime:

```bash
sunaba stacks
```

## Examples

```bash
# Python microservice
sunaba new api --stack python --stack agents

# Full-stack Next.js + Neon Postgres
sunaba new apps --stack nextjs --stack neon --stack agents

# Multi-cloud infra work
sunaba new infra --stack python --stack aws --stack gcp --stack azure

# Everything
sunaba new playground --stack python --stack nextjs --stack aws \
  --stack gcp --stack azure --stack neon --stack agents --stack docker

# Host-only (no devcontainer) — just MCP + agent files on the host
sunaba new local --stack python --no-devcontainer
```

## Rebuild: change stacks after the fact

```bash
# Replace the stack list
sunaba rebuild myapp --stack python --stack aws

# Add a stack
sunaba rebuild myapp --add nextjs

# Remove a stack
sunaba rebuild myapp --remove docker

# Preview without writing
sunaba rebuild myapp --add gcp --dry-run

# Skip confirmation
sunaba rebuild myapp --add neon -y
```

Output:

```
Project: myapp (/Users/me/projects/myapp)
  Current stacks: python
  New stacks:     python, nextjs

Changes:
  ~ .devcontainer/devcontainer.json (modified)
  ~ .devcontainer/bootstrap.sh (modified)
  ~ .github/dependabot.yml (modified)
  = .vscode/settings.json (unchanged)

Apply these changes? [y/N]:
```

## What gets generated

`sunaba new myapp --stack python` produces:

```
myapp/
├── .devcontainer/
│   ├── devcontainer.json      # Composed devcontainer config
│   └── bootstrap.sh           # Installs AI agents + stack tools
├── .github/
│   └── dependabot.yml         # Dependency update automation
├── .vscode/
│   └── settings.json          # File-watcher exclusions (prevents agent runaway)
├── .mcp.json                  # MCP server config for Claude Code
├── .gitignore
├── AGENTS.md                  # Shared agent instructions
├── CLAUDE.md                  # Claude-specific instructions
├── GEMINI.md                  # Gemini-specific instructions
└── skills.md                  # Tool catalog for agents
```

## MCP servers

Generated projects ship with a `.mcp.json` that lets Claude Code call:

| Server | Purpose |
|---|---|
| `codex` | OpenAI Codex CLI (sub-agent) |
| `gemini-cli` | Google Gemini CLI (sub-agent) |
| `playwright` | Browser automation / E2E tests |
| `chrome-devtools` | Chrome DevTools protocol |
| `notebooklm` | NotebookLM CLI |

All run via `npx` or `uvx`, so no extra installation is required beyond the
Node.js and `uv` already provided by the base image and `python` stack.

> ⚠️ Note: `npx ...@latest` and `uvx` fetch third-party packages on first use.
> This is a supply-chain surface. If you need deterministic builds, fork and
> pin the entries in `templates/base/mcp.json`.

## Base image contents

Every generated project starts from:

- Ubuntu 22.04 (Jammy) — `mcr.microsoft.com/devcontainers/base:jammy`
- **GitHub CLI** (`gh`)
- **Node.js 22** (powers `npx` + MCP servers)
- **Claude Code** (`claude`) — `@latest`
- **OpenAI Codex** (`codex`) — `@latest`
- **Gemini CLI** (`gemini`) — `@latest`
- VS Code extensions: Claude Code, ChatGPT, Markdown Preview Enhanced, Rainbow CSV
- VS Code file-watcher exclusions (`node_modules`, `.venv`, `__pycache__`, …)

## Security notes

This section is intentionally honest rather than marketing-flavored. Read it
before using `sunaba-cli` on sensitive work.

### What `sunaba-cli` does to protect you

- **Path-traversal hardening** — project names containing `/`, `\`, or `..`
  are rejected. Generated file paths are resolved against the project root
  before writing.
- **Symlink fail-closed on write** — `sunaba rebuild` refuses to write through
  a symlink or to any resolved path outside the project directory.
- **Secrets are opt-in** — no API keys are injected unless you pass
  `--stack agents`, `--stack aws`, etc. The base container starts with
  `remoteEnv: {}`.
- **Docker-in-docker is opt-in** — host Docker socket is only mounted when
  you pass `--stack docker`.
- **Fail-closed dependency install** — `npm ci --ignore-scripts` only runs
  when a `package-lock.json` exists. `uv sync --frozen` only runs when a
  `pyproject.toml` exists. No silent fallbacks to unpinned installs.
- **`uv` is installed via `pip`** — avoids piping a remote shell script.

### What `sunaba-cli` does NOT protect you from

- **`@latest` agent CLIs**: Claude Code, Codex, and Gemini CLI are installed
  with `@latest` on every first container start. This is an intentional
  tradeoff — the alternative is stale agents. If upstream is compromised, so
  is your sandbox. Fork and pin if you need deterministic builds.
- **MCP server supply chain**: `playwright`, `chrome-devtools-mcp`, and
  `notebooklm-mcp-cli` are fetched via `npx`/`uvx` on first use.
- **Secret visibility inside the container**: once you pass `--stack agents`,
  *any* process in the container — including any AI agent — can read your
  API keys via environment variables. Use sandbox boundaries accordingly.
- **Host Docker socket**: `--stack docker` gives the container full control
  of your host's Docker daemon. Only use with code you trust.
- **Your own prompts**: `sunaba-cli` does not sandbox the AI agents
  themselves. An agent can still `rm -rf` files inside the container, commit
  and push secrets, etc. The sandbox protects your host, not your repo.
- **`--stack harness`**: ships a Claude Code Stop hook that runs
  `bash .claude/hooks/verify.sh` after every agent session. The hook is a
  template — review it like code. It can run any local command. The
  permissions list reduces approval prompts for routine tools, but it is
  **not** a security boundary.

Report vulnerabilities via GitHub Security Advisories or an issue — see
[SECURITY.md](SECURITY.md).

## GitHub SSH from inside the container

`sunaba-cli` does **not** copy your SSH keys into the container. Instead, it
relies on VS Code Dev Containers' built-in **SSH agent forwarding**: your
host's `ssh-agent` socket is bind-mounted into the container as
`$SSH_AUTH_SOCK`, so `git push` over SSH works without the private key
ever leaving the host.

### One-time host setup (macOS)

```bash
# Load your GitHub key into the macOS keychain (persists across reboots)
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# Make sure ~/.ssh/config tells ssh to use the keychain
cat >> ~/.ssh/config <<'EOF'
Host *
  UseKeychain yes
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_ed25519
EOF

# Verify
ssh-add -l   # should list your key
```

On Linux hosts, just running `eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519`
in your shell rc file is enough.

### Verify from inside the container

After reopening the project in the container:

```bash
echo "$SSH_AUTH_SOCK"      # should print a path, e.g. /tmp/vscode-ssh-auth-sock-...
ssh -T git@github.com       # should greet you by username
git push                    # works over SSH
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| `$SSH_AUTH_SOCK` is empty | Run `ssh-add -l` on the host; if "no identities", run `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` and rebuild the container |
| `Permission denied (publickey)` | Host key not loaded in agent — `ssh-add -l` on host |
| `fatal: detected dubious ownership` | Already handled by bootstrap (`safe.directory`); rebuild the container if you hit it on an old project |

> ⚠️ The forwarded agent is reachable by **any process inside the container**,
> including AI agents. It cannot export your private key, but it can sign
> authentication challenges while the container is running. Treat it as a
> live credential and don't run untrusted code in the same sandbox as
> sensitive SSH access.

## Requirements

- macOS or Linux (devcontainers run Linux containers)
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker-compatible runtime (Docker Desktop, Colima, Rancher Desktop, …)
- VS Code with the **Dev Containers** extension

### Colima users

Colima does not create `/var/run/docker.sock`. Set `DOCKER_HOST`:

```bash
echo 'export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"' >> ~/.zshrc
source ~/.zshrc
colima start
```

## Design notes / roadmap

Larger design changes are worked through in the open under
[`thinking/`](thinking/) before they land as code. Each entry is a
self-contained set of notes (current state → research → independent
LLM reviews → synthesized proposal) covering one area of the project.

Drafts in flight as of 2026-05:

- [`thinking/2026-05-09-harness-engineering/`](thinking/2026-05-09-harness-engineering/) —
  applying harness-engineering principles (OpenAI / Martin Fowler /
  HumanLayer / Addy Osmani / Red Hat) to the generated agent
  scaffolding. Introduces `--stack harness` and the `_files`
  template-emission mechanism that subsequent proposals build on.
- [`thinking/2026-05-09-stack-aware-agent-files/`](thinking/2026-05-09-stack-aware-agent-files/) —
  making the generated `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` /
  `skills.md` reflect the stacks the user actually selected, with
  per-stack fragments and a registry-flagged sync mode.
- [`thinking/2026-05-09-secrets-management/`](thinking/2026-05-09-secrets-management/) —
  expanded `.gitignore` baseline, opt-in `--stack secrets` (gitleaks
  pre-commit + per-cloud docs), and the Azure
  Foundry → APIM → Gemini → Cosmos "key behind a proxy" pattern.
- [`thinking/2026-05-09-rules-and-autonomy/`](thinking/2026-05-09-rules-and-autonomy/) —
  multi-target path-scoped rules (`--stack rules`) and an opt-in
  autonomous environment (`--stack autopilot`) with structured
  Stop-hook re-engage, budget caps, and a subagent dispatch protocol.

These are **drafts under review**, not shipped features. The shape
is intentional: docs land first so the design can be argued with
before implementation. See [`thinking/README.md`](thinking/README.md)
for the implementation order and how the proposals interact.

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
