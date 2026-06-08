1. **Delete `GEMINI.md`**. A clean break is safer. Since `agy` defaults to `AGENTS.md` (which you already generate), keeping `GEMINI.md` as a pointer only creates ambiguity for the agent and technical debt for you.

2. **Keep the `"gemini"` internal token**. Renaming the internal taxonomy to `"agy"` is a breaking change for existing user state/metadata. Map `"gemini"` to `"Antigravity (agy)"` in the UI/labels only.

3. **Bash `agy -p` is the right path**, but verify if Claude expects JSON-RPC (MCP) or if it can parse raw CLI output. If `agy` supports a `--json` or `--format` flag, use that to ensure Claude receives structured responses rather than just text.

4. **Missing / Risks**:
   * **Auth Bottleneck**: `agy` uses OAuth. Your `bootstrap.sh` is likely non-interactive; if `agy` cannot use a service-account key or `GEMINI_API_KEY` as a fallback, the devcontainer will hang waiting for a browser login.
   * **Nested Config Path**: `agy` expects state in `~/.gemini/antigravity-cli/`. Your volume mount in `agents.json` must ensure this subdirectory exists or is correctly mapped, otherwise `agy` will recreate config on every launch.
   * **Model IDs**: `gemini-3.1-pro-preview` is stale; you must map the new `3.5-flash-high` / `3.1-pro-high` IDs immediately to avoid "Model not found" errors on day one.

**Extra Risk**: `agy` consumes MCP servers via `~/.gemini/config/mcp_config.json`. If `sunaba-cli` also writes to this file or expects `base/mcp.json` to be the source of truth, you may have a config collision where `agy` ignores your project-specific MCP servers.
