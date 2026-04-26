# Claude Code Instructions

## Environment
- Running inside a devcontainer sandbox
- uv for Python dependency management
- Node.js available for frontend tasks

## Rules
- Always check `git status` before starting work
- Use feature branches, never commit to main
- Run tests before marking tasks complete
- Use absolute paths for file operations

## Calling Gemini via MCP
When delegating to the `gemini-cli` MCP server, prefer the latest preview model
by passing the `model` parameter explicitly:

```
mcp__gemini-cli__chat({
  "prompt": "...",
  "model": "gemini-3.1-pro-preview"
})
```

Fallbacks if `gemini-3.1-pro-preview` is unavailable on your account:
`gemini-3-pro-preview` → `gemini-2.5-pro` (default).
