# Claude Code Instructions

## Environment

Running inside a sunaba devcontainer sandbox.

## Rules

- Always check `git status` before starting work.
- Use feature branches; never commit directly to main.
- Run tests before marking a task complete.
- Use absolute paths for file operations when crossing directories.

## Recommended folder layout

Layered, feature-first layout under the source root (`src/`/`lib/`/`app/`):

- `app/` — routes, theme, providers
- `core/` — shared utilities, components, constants
- `features/<name>/` — `data/` (API/repo), `domain/` (models), `presentation/` (UI)
- `services/` — cross-cutting (notifications, SDKs)
- `config/` — environment wiring (no secrets)

Plural folder names. New work goes under `features/<name>/`, not `core/`.
Route SDK calls through `data/` or `services/` so UI stays decoupled.

## Selected stacks

<!-- SUNABA STACKS START -->
<!-- SUNABA STACKS END -->

## Calling Gemini via MCP

When delegating to the `gemini-cli` MCP server, prefer the latest
preview model by passing the `model` parameter explicitly:

```
mcp__gemini-cli__chat({
  "prompt": "...",
  "model": "gemini-3.1-pro-preview"
})
```

Fallbacks if `gemini-3.1-pro-preview` is unavailable on your account:
`gemini-3-pro-preview` → `gemini-2.5-pro` (default).

<!-- SUNABA USER START -->
<!-- Edit freely below. `sunaba sync` preserves anything between the USER markers. -->
<!-- SUNABA USER END -->
