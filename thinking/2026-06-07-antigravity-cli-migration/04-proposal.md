# 04 — Proposal: migrate sunaba-cli Gemini integration → Antigravity CLI (`agy`)

Synthesizes [01-current-state](01-current-state.md), the consultation brief
([02](02-consultation-brief.md)), and the two independent reviews
([codex/gpt-5.5](03b-codex-review.raw.txt), [gemini-3-flash](03a-gemini-review.raw.txt)).

## Decisions (both reviewers concurred unless noted)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Stop generating `GEMINI.md`**; do not auto-delete users' existing copies. Delete the template. | agy reads `AGENTS.md` (already generated). GEMINI.md is dead weight. Sync simply stops managing it. |
| D2 | **Keep `"gemini"` as the internal canonical token** (rule targets, `agent_kind` enum, volume names). Update only human-facing labels → "Antigravity CLI (agy)". | Renaming the token breaks existing state files / schemas. Lesser evil. |
| D3 | **Claude → agy delegation via headless Bash `agy -p "..." --model ...`.** Remove the `gemini-cli` MCP server. | agy is not an MCP server (no `mcp-server` subcommand). `mcp_config.json` is the *consume* direction, wrong for this. agy is a real binary (`command -v agy` works), not just an alias. |
| D4 | **bootstrap.sh**: replace `npm i -g @google/gemini-cli` with the official installer `curl -fsSL https://antigravity.google/cli/install.sh \| bash`, guarded by `command -v agy`, PATH-safe. | Authoritative Google source. Avoid the unverified `gemini-antigravity-cli` npm package (supply-chain caution per repo's SECURITY.md). |
| D5 | **Keep `~/.gemini` volume + `GEMINI_API_KEY`** (agy nests state under `~/.gemini/antigravity-cli/`). Relabel purpose; flag the key as legacy. | No rename → no orphaned Docker volume. Key kept for compat; agy is OAuth-first so it's belt-and-suspenders. |
| D6 | **Rewrite the autopilot doc** as *status & caveats*, rename `gemini-autopilot-limitations.md` → `antigravity-autopilot.md`. agy HAS hooks (`hooks.json`, stop hooks), subagents, plugins. | Conservative per codex: don't claim "limitations gone" — hook event semantics unverified in headless mode. |
| D7 | **Update tests** that assert GEMINI.md / the old doc name / the gemini host-tool. Leave Azure-Foundry "Gemini *model*" secrets docs untouched. | The Foundry doc is about the Gemini model, not the CLI — out of scope. |

## Extra risks flagged & mitigations

- **OAuth hang in bootstrap** (gemini): bootstrap only *installs*; auth happens at first interactive
  use, so no build-time hang. Keep `GEMINI_API_KEY` as fallback.
- **`curl | bash` user/home/PATH** (codex): run as the container user; repo bootstrap already puts
  `~/.local/bin` on PATH; guard with `command -v agy` so reruns are idempotent.
- **MCP config collision** (gemini): we are *not* generating `~/.gemini/config/mcp_config.json`;
  project `.mcp.json` stays Claude's. No collision. (Generating agy's mcp_config is a future enhancement.)
- **Stale model ids**: replace `gemini-3.1-pro-preview` everywhere with agy display ids
  (e.g. `Gemini 3.1 Pro (High)`, `Gemini 3.5 Flash (High)`).

## Edit inventory (exhaustive)

Code:
- `sync.py:15` — drop `GEMINI.md` from `AGENT_FILES`.
- `cli.py:265` — drop `GEMINI.md` from the agent-file generation tuple.
- `cli.py:764` — drop `GEMINI.md` from the skip set.
- `cli.py:612` — host req `("gemini","Google Gemini CLI")` → `("agy","Antigravity CLI")`.
- `cli.py:613` — npx note: drop `gemini-cli` from MCP list.
- `cli.py:798` — next-steps hint `claude / codex / gemini` → `claude / codex / agy`.
- `cli.py:237,402-404,565,578-580` — comments mentioning GEMINI.md / gemini-cli MCP.

Templates:
- DELETE `agents/base/GEMINI.md`.
- `agents/base/AGENTS.md:3,50` — copy → "Antigravity CLI"; refresh MCP-servers paragraph.
- `agents/base/CLAUDE.md:33-46` — replace "Calling Gemini via MCP" → "Delegating to agy (headless)".
- `agents/base/skills.md:8-9` — gemini entry → agy entry w/ current model ids.
- `harness/AGENTS.md:3` — copy → "Antigravity CLI".
- `agents/fragments/agents/{tools,guidance}.md` — note `~/.gemini` = agy state; key = legacy.
- `agents/fragments/multi-agent/guidance.md:20` — drop GEMINI.md from injected-files list.
- `base/bootstrap.sh:74-77` — agy installer block.
- `base/mcp.json` — remove `gemini-cli` server.
- `base/SECURITY.md:37` — upstream out-of-scope list → Antigravity CLI.
- `stacks/agents.json` — `_description` wording (keep volume + key).
- `stacks/autopilot.json:2,18` — description + rename doc mapping.
- `autopilot/docs/gemini-autopilot-limitations.md` → rename `antigravity-autopilot.md`, rewrite.
- `multi-agent/docs/orchestration.md:4` — agent list copy.
- `multi-agent/state/README.md:48` — GEMINI.md → AGENTS.md.

Tests:
- `test_e2e.py:72` — GEMINI.md should NOT exist (assert absence; AGENTS.md present).
- `test_e2e.py:469` — autopilot doc renamed.
- `test_stack_aware.py:94,148` — drop GEMINI from iterated agent files.
- `test_smoke.py:367` — host cmds: expect `agy`, not `gemini` (keep volume tests at 80-86,133).
- `test_rules_and_autopilot.py:171` — autopilot doc renamed (keep rule-target `gemini` at 69,76).

Untouched (intentionally): `agent_kind` enum + schema (`"gemini"` token), rule `targets:` lists,
`~/.gemini` volume + `gemini-config` mount + `GEMINI_API_KEY`, Azure-Foundry Gemini-model docs,
`.gemini/` gitignore entry (agy's dir family).

## Validation plan

1. `pip install -e . && pytest -q` — full suite green.
2. `sunaba new /tmp/agytest --stack agents,autopilot,multi-agent --no-devcontainer` (or devcontainer)
   → confirm no `GEMINI.md`, `AGENTS.md` present, `docs/agents/antigravity-autopilot.md` present,
   `.mcp.json` has no gemini-cli server, bootstrap installs agy.
3. `grep -rn "gemini-cli\|GEMINI.md\|gemini-3.1-pro-preview"` over templates/src → only intentional
   residue (volume name, model-provider keys).
