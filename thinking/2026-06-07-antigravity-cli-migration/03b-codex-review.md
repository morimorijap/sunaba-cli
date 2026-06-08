1. **Q1: Delete `GEMINI.md`?**  
   Yes for new generated scaffolds. `agy` reads `AGENTS.md`, so continuing to generate `GEMINI.md` implies first-class Gemini CLI support you are intentionally removing.

   Do **not** auto-delete a user’s existing `GEMINI.md` during sync/migration unless it is clearly sunaba-owned. Best path: stop generating/updating it, remove it from managed agent-file lists, and mention the migration in release notes. A transition-window pointer is low value and creates ambiguity.

2. **Q2: Keep `"gemini"` or rename to `"agy"`?**  
   Keep `"gemini"` as the internal canonical token for now. It is the lesser evil because it avoids breaking rule targets, state files, schemas, and existing automation.

   But accept `"agy"` / `"antigravity"` as input aliases where practical, normalize to `"gemini"`, and update all human-facing labels to `Antigravity CLI (agy)`. Treat a real rename as a later schema-versioned migration, not part of this cutover.

3. **Q3: Claude → agy delegation path?**  
   Bash/headless invocation is the right near-term replacement: `agy -p ... --model ...`, assuming auth is already configured.

   `mcp_config.json` is the wrong direction for Claude delegating to agy: that lets **agy consume MCP servers**, not expose agy as one. ACP/plugins are also not a clean replacement unless Google exposes a stable server/protocol surface. A custom wrapper MCP around `agy -p` is possible, but it reintroduces maintenance and should not block this migration.

   One concrete risk: if `agy` is only a shell alias, Claude’s non-interactive Bash may not see it. Prefer verifying `command -v agy`; otherwise document/use the real `antigravity` binary.

4. **Q4: What you are missing / likely landing risks**  
   Biggest issue: deleting `GEMINI.md` means any Gemini-specific instructions previously injected there must either move into shared `AGENTS.md` or be intentionally dropped. Check `agents/fragments/multi-agent/guidance.md`, `agents/base/skills.md`, and any per-agent composition comments.

   Install risk: `curl | bash` in a devcontainer may install under the wrong user/home or update shell startup files that non-login shells do not read. Verify PATH for the runtime user after bootstrap, not just install success.

   Auth risk: keeping `GEMINI_API_KEY` is compatibility, not safety. If `agy` is OAuth/token-profile based, forwarding an unused secret broadens exposure. Keep it only as deprecated/legacy until verified, and update `SECURITY.md`.

   MCP config path risk: public docs/snippets are inconsistent about the exact Antigravity MCP config location. Since sunaba may document or generate this later, verify with `agy` 1.0.6 before baking paths. Your supplied fact says `~/.gemini/config/mcp_config.json`; official migration docs confirm Antigravity uses a distinct `mcp_config.json`, but path details deserve one last check.

   Autopilot risk: “agy has hooks/subagents” does not prove it has the same Stop-hook loop semantics sunaba relied on. Rewrite the limitations doc as “status and caveats,” not “limitations gone,” until hook event names and headless behavior are tested.

   Also update `base/SECURITY.md`, host-tool checks to look for `agy`/`antigravity`, stale model examples, `base/mcp.json` JSON shape after removing the entry, and tests listed in the inventory. Leave Azure Foundry Gemini model docs alone.

Sources checked: Google Antigravity install docs and Gemini CLI migration docs: https://antigravity.google/docs/cli-install, https://www.antigravity.google/docs/gcli-migration
