# 01 — Current state: Gemini CLI → Antigravity CLI (`agy`) migration

Date: 2026-06-07
Context: Google is transitioning `gemini-cli` into **Antigravity CLI** (binary `antigravity`,
invoked as `agy`). Gemini CLI stops serving free/paid Google AI users on **2026-06-18**.
Source: https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/

sunaba-cli scaffolds devcontainer + agent files for sandboxed AI-agent development. It currently
treats Gemini CLI as a first-class agent alongside Claude Code and Codex. This doc records what
the migration must touch.

## Facts established about `agy` (antigravity-cli 1.0.6)

Verified by inspecting the installed binary (`agy --help`, `agy changelog`, `agy models`,
and `strings` over `/opt/homebrew/Caskroom/antigravity-cli/1.0.6/antigravity`).

1. **Context/customization file is `AGENTS.md`, NOT `GEMINI.md`.**
   Binary strings:
   - "Global Rules: ... append to `AGENTS.md` in the Global Customizations Root."
   - "Project-Scoped Rules: ... append to `AGENTS.md` in the Workspace Customizations Root."
   Customizations = **Skills** + **Rules**. Skills under `skills/<name>/`, auto-discovered in
   standard customization roots; `skills.json` only needed for non-standard locations.
   ⇒ `GEMINI.md` is obsolete for agy. The repo already generates `AGENTS.md`.

2. **Config/state directory is still `~/.gemini`** (the "GeminiDir").
   Binary strings: "using hardcoded .gemini", `~/.gemini/antigravity-cli/cache/projects.json`,
   `~/.gemini/jetski/...`. Antigravity CLI nests its data under `~/.gemini/antigravity-cli/`.
   ⇒ The existing `~/.gemini` named volume in `agents.json` stays valid; no rename required,
   though the *purpose* changes.

3. **MCP config file is `config/mcp_config.json`** (relative to customization root), supports
   stdio servers and a `url` field. NOT `.mcp.json`. (`.mcp.json` is Claude Code's convention.)

4. **Install path is Homebrew cask `antigravity-cli`**, not npm `@google/gemini-cli`.
   Binary name `antigravity`, CLI alias `agy`. There is an `agy install` subcommand that
   configures PATH and shell aliases.

5. **Models** (`agy models`): Gemini 3.5 Flash (Low/Medium/High), Gemini 3.1 Pro (Low/High),
   Claude Sonnet 4.6 (Thinking), Claude Opus 4.6 (Thinking), GPT-OSS 120B (Medium).
   ⇒ The `gemini-3.1-pro-preview` model id referenced in CLAUDE.md is stale.

6. **Subcommands**: `agy plugin` (extensions are now "plugins"), `models`, `changelog`,
   `install`, `update`. Headless: `agy -p "<prompt>"` / `--model`.

7. Features preserved per blog: Agent Skills, Hooks, Subagents, Extensions (→ plugins).

## Where Gemini is referenced in the repo (scope of change)

Code:
- `src/sunaba_cli/sync.py:15` — `AGENT_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "skills.md"]`
- `src/sunaba_cli/cli.py:185` — `.gitignore` body includes `.gemini/`
- `src/sunaba_cli/cli.py:237,265` — help text + per-file marker injection over GEMINI.md
- `src/sunaba_cli/cli.py:377,402,404` — rule compilation targets `["claude","cursor","codex","gemini"]`
- `src/sunaba_cli/cli.py:565,578,589` — mcp.json + agent file composition comments
- `src/sunaba_cli/cli.py:612-613` — host tool checks: `("gemini","Google Gemini CLI")`, npx note
- `src/sunaba_cli/cli.py:764,798` — agent file skip set + host-run hint mentions gemini

Templates:
- `agents/base/GEMINI.md` — the obsolete context file
- `agents/base/CLAUDE.md:33-46` — "Calling Gemini via MCP" block w/ stale `gemini-3.1-pro-preview`
- `agents/base/AGENTS.md:3,50` / `harness/AGENTS.md:3` — "Claude Code, Codex, Gemini CLI" copy
- `agents/base/skills.md:8-9` — gemini skill entry w/ stale model id
- `agents/fragments/agents/{tools,guidance,summary}.md` — env keys, `~/.gemini` volume, key copy
- `agents/fragments/multi-agent/guidance.md:20` — injects into GEMINI.md
- `base/bootstrap.sh:74-77` — `npm install -g @google/gemini-cli@latest`
- `base/mcp.json:9-14` — `gemini-cli` MCP server (npx mcp-gemini-cli)
- `base/SECURITY.md:31,37` — `.gemini/` path, `@google/gemini-cli` package
- `stacks/agents.json` — `GEMINI_API_KEY`, `~/.gemini` volume mount + chmod, `sunaba_fix_config_dir`
- `stacks/autopilot.json:2,18` — description + gemini-autopilot-limitations doc mapping
- `autopilot/docs/gemini-autopilot-limitations.md` — Gemini autopilot gap doc (hierarchical GEMINI.md)
- `multi-agent/docs/orchestration.md`, `multi-agent/state/{schema.json,README.md}`,
  `multi-agent/scripts/agent-task.py:492` — `agent_kind` enum includes "gemini"
- `rules/{nextjs-api,python-tests}.rule.md` — `targets:` include `gemini`
- `stacks/secrets.json` + `secrets/docs/azure-foundry-apim-gemini-cosmos.md` — Gemini = the Google
  *model* (Azure Foundry), NOT the CLI. **Out of scope — do not touch.**

Tests asserting current behaviour (will need updates):
- `tests/test_e2e.py:72` — asserts `GEMINI.md` exists
- `tests/test_stack_aware.py:94,148` — iterates `(AGENTS, CLAUDE, GEMINI)`
- `tests/test_smoke.py:80-86,133,367` — gemini volume mounts, host tool list
- `tests/test_rules_and_autopilot.py:69,76,171` — rule targets, gemini-autopilot doc
- `tests/test_secrets.py` — azure-foundry doc (model, out of scope)

## Key open questions (for codex / gemini consultation)

1. **Drop vs. keep `GEMINI.md`.** Since agy reads `AGENTS.md`, is GEMINI.md pure dead weight?
   Options: (a) delete entirely, (b) keep as a thin pointer/symlink to AGENTS.md for back-compat
   with old gemini-cli during the transition window (until 2026-06-18).
2. **Backward compatibility window.** Gemini CLI still works until 2026-06-18. Should the
   scaffold support BOTH during transition, or cut over cleanly to agy now?
3. **Naming taxonomy.** Internal identifier: keep `"gemini"` in agent-kind enums / rule targets,
   or rename to `"agy"` / `"antigravity"`? (rename = breaking change to existing user state files.)
4. **Install method.** bootstrap.sh runs in a Linux devcontainer. Homebrew cask is macOS-only.
   How is agy installed on Linux? (download script? npm successor? need to verify.)
5. **MCP story.** Does agy still expose an MCP server for Claude to call (replacing
   `mcp-gemini-cli`)? Or does the MCP integration go away entirely?
6. **Config volume.** Keep `~/.gemini` mount (agy nests under it) — confirm no second dir needed.
