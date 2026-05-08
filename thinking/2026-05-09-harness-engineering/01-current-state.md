# 01 — Current state

What `sunaba new` produces today, and where the harness is thin.

## What sunaba generates

For `sunaba new myapp --stack python --stack agents`:

```
myapp/
├── .devcontainer/
│   ├── devcontainer.json     # composed from base + stack overlays
│   └── bootstrap.sh          # installs claude / codex / gemini @latest
├── .github/dependabot.yml
├── .vscode/settings.json     # file-watcher exclusions
├── .mcp.json                 # codex / gemini-cli / playwright /
│                             # chrome-devtools / notebooklm
├── .gitignore
├── AGENTS.md                 # shared agent instructions
├── CLAUDE.md                 # Claude-specific
├── GEMINI.md                 # Gemini-specific
└── skills.md                 # tool catalog
```

Available stacks: `python` `nextjs` `aws` `azure` `gcp` `neon` `agents`
`docker` `playwright`.

## What sunaba does well today

**Infrastructure side, mostly solid:**

- Path-traversal hardening, symlink fail-closed on write.
- Secrets opt-in (`--stack agents`).
- `npm ci --ignore-scripts` and `uv sync --frozen` only when locks exist; no
  silent fallback to unpinned installs.
- `uv` installed via `pip --user` (no `curl | sh` RCE).
- SSH agent forwarded from host — keys never enter the container.
- Auth state for claude / codex / gemini persisted in named volumes so
  rebuilds don't log you out.
- `@latest` agent CLIs is a deliberate trade-off, documented in the README
  rather than hidden.

These cover the **sandbox**. They are not the **harness**.

## Where the harness is thin

Mapping the four pillars (system prompt / tools / context / sub-agents) plus
the cross-cutting concerns (sensors, permissions, evals/observability) onto
what we ship:

| Pillar / concern | Current state | Gap |
|---|---|---|
| **System prompt** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) | ~10 generic lines each | No ratchet rules, no per-stack guidance, no "things that have actually broken" |
| **Tools (MCP)** | 5 servers in `.mcp.json`, all on by default | No opt-in tiering; `playwright` / `chrome-devtools` / `notebooklm` always loaded even when the project will never use them |
| **Tools (CLI / skills)** | `skills.md` is a flat tool list | Not a `.claude/skills/` directory, no SKILL.md files, no progressive disclosure |
| **Context management** | None | No `CLAUDE.md` ratchet conventions, no `claudedocs/` directory, no compaction guidance |
| **Sub-agents** | None | No `.claude/agents/<role>.md` templates (planner / reviewer / verifier), no documented delegation pattern |
| **Hooks (sensors)** | None | No `.claude/settings.json` with PreToolUse / PostToolUse / Stop hooks. No silent-on-success typecheck/lint/test wiring per stack |
| **Permissions** | None | No `permissions.allow` / `permissions.deny` in `.claude/settings.json`. Users hit approval prompts for every shell call, or worse, run with permissions disabled |
| **Evals / observability** | None | No `claudedocs/` for trace logs or design notes, no `evals/` for harness regression tests |

## What this means in practice

A user running `sunaba new myapp --stack nextjs --stack agents` today gets:

- A clean container ✅
- Three coding agents installed ✅
- A `.mcp.json` that lets Claude call Codex and Gemini as sub-agents ✅
- Roughly **zero** project-specific guardrails for those agents ❌

The agent will:

- Re-discover the project structure on every fresh session.
- Hit permission prompts for routine shell calls, training the user to
  click "always allow" without reading.
- Have no automatic feedback loop ("did the typecheck pass?") — the user has
  to ask.
- Carry context for `playwright` / `chrome-devtools` / `notebooklm` MCP tool
  descriptions even on a backend-only project.

## Constraints on the fix

- **Don't break existing projects.** `sunaba sync` and `sunaba rebuild`
  must continue to behave predictably. Anything new lands as additive
  templates or behind new stack flags.
- **Don't smuggle in opinions.** The agent files are seed templates. Users
  are expected to edit them — the goal is to give them a *working starting
  point*, not a framework they have to opt out of.
- **Stay honest about supply chain.** Every new MCP server or auto-installed
  tool is supply-chain surface. Track it explicitly.
