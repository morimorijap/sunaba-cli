# 02 — Consultation brief for codex (gpt-5.5) + gemini-3-flash-preview

You are reviewing a migration plan for **sunaba-cli**, a Python CLI that scaffolds a devcontainer
sandbox + AI-agent instruction files for a repo. It currently treats three agent CLIs as
first-class: **Claude Code**, **Codex**, and **Gemini CLI**.

## The event

Google is transitioning `gemini-cli` → **Antigravity CLI** (binary `antigravity`, alias `agy`).
Gemini CLI stops serving free/paid Google AI users on **2026-06-18** (today is 2026-06-07).
We must migrate sunaba-cli's Gemini integration to Antigravity CLI.

## Verified facts about `agy` (antigravity-cli 1.0.6)

1. Context/customization file = **`AGENTS.md`** (NOT `GEMINI.md`). Customizations = Skills + Rules.
2. Config/state dir = **`~/.gemini`** (agy nests under `~/.gemini/antigravity-cli/`; OAuth token at
   `~/.gemini/antigravity-cli/antigravity-oauth-token`).
3. MCP servers CONSUMED via **`~/.gemini/config/mcp_config.json`** (stdio or `url`).
4. agy has **no `mcp-server` subcommand** — it does NOT expose itself as an MCP server. (Codex does:
   `codex mcp-server`. Claude previously called Gemini through the third-party `mcp-gemini-cli` npm
   wrapper.)
5. Install: Linux → `curl -fsSL https://antigravity.google/cli/install.sh | bash` or
   `npm install -g gemini-antigravity-cli`; macOS → Homebrew cask `antigravity-cli`.
6. Models: Gemini 3.5 Flash (Low/Med/High), Gemini 3.1 Pro (Low/High), Claude Sonnet/Opus 4.6
   (Thinking), GPT-OSS 120B. Headless: `agy -p "<prompt>" --model <name>`.
7. Preserved: Agent Skills, Hooks, Subagents, Extensions (→ "plugins", `agy plugin`).

## Current sunaba-cli integration (what changes)

- Generates `GEMINI.md` as one of the per-repo agent files (alongside AGENTS.md, CLAUDE.md, skills.md).
- `bootstrap.sh` installs `@google/gemini-cli@latest` via npm in a **Linux** devcontainer.
- `base/mcp.json` registers a `gemini-cli` MCP server (`npx mcp-gemini-cli`) for Claude to call.
- `CLAUDE.md` has a "Calling Gemini via MCP" block with stale model id `gemini-3.1-pro-preview`.
- `stacks/agents.json` mounts a `~/.gemini` named volume, forwards `GEMINI_API_KEY`.
- Internal taxonomy uses the literal `"gemini"` in: rule-target lists (`["claude","cursor","codex",
  "gemini"]`), multi-agent `agent_kind` enum (`[claude,codex,gemini,human]`), host-tool checks.
- An autopilot doc `gemini-autopilot-limitations.md` describes Gemini's lack of a Stop-hook loop.

## My proposed decisions (critique these — find what's wrong or risky)

D1. **Delete `GEMINI.md`** from generated agent files. agy reads `AGENTS.md`, which we already
    generate. GEMINI.md is dead weight. (Alternative considered: keep a thin pointer for the
    11-day gemini-cli transition window — I think not worth it.)

D2. **bootstrap.sh**: replace npm gemini-cli install with
    `curl -fsSL https://antigravity.google/cli/install.sh | bash` (Linux). Keep `@latest` spirit.

D3. **mcp.json**: remove the `gemini-cli` MCP server entry. Since agy is not an MCP server, Claude
    delegates to it via Bash (`agy -p "..."`) instead. Replace the CLAUDE.md "Calling Gemini via
    MCP" block with an "agy headless" usage note + corrected model ids.

D4. **agents.json**: keep the `~/.gemini` volume (agy still uses it) but relabel its purpose;
    drop `GEMINI_API_KEY` only if agy auth is OAuth-based (uncertain — keep it to be safe).

D5. **Taxonomy**: keep the internal literal `"gemini"` as the agent-kind / rule-target token to
    avoid breaking existing user state files; only update human-facing labels to "Antigravity
    (agy)". (Alternative: rename token to `"agy"` — breaking.)

D6. **autopilot limitations doc**: rewrite for agy. agy HAS hooks + subagents + a Stop-hook
    equivalent, so most of the old Gemini limitations no longer apply — verify and soften.

D7. **Tests**: update assertions that expect `GEMINI.md`, gemini volume labels, host-tool list.
    The Azure-Foundry "Gemini model" secrets doc is about the *model*, not the CLI → leave alone.

## Questions

Q1. Is deleting GEMINI.md correct, or is a transition-window pointer worth the safety?
Q2. Taxonomy: keep `"gemini"` token (back-compat) or rename to `"agy"`? Which is the lesser evil?
Q3. Is Bash `agy -p` the right Claude→agy delegation now that there's no MCP server? Any better path
    (e.g. agy as an `mcp_config.json` peer, ACP, plugins)?
Q4. What am I MISSING — any file, breaking change, or ordering risk that would make this <90%
    likely to land cleanly? Be specific and concrete.

Answer concisely with a numbered response to Q1–Q4 plus any extra risks. Do not write code.
