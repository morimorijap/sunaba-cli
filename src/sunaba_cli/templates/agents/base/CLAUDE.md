# Claude Code Instructions

## Environment

Running inside a sunaba devcontainer sandbox.

## Rules

- Always check `git status` before starting work.
- Use feature branches; never commit directly to main.
- Run tests before marking a task complete.
- Use absolute paths for file operations when crossing directories.

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
