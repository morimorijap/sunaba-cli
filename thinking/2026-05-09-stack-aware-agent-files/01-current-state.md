# 01 — Current state

## What sunaba ships in each agent file today

All four files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `skills.md`)
ship as static templates from
[`templates/agents/`](../../src/sunaba_cli/templates/agents/) and are
copied verbatim by `copy_agent_files()` in
[`sync.py:61`](../../src/sunaba_cli/sync.py).

### `AGENTS.md` (~12 lines)

```md
# Agents

## Build & Test
- `uv sync` to install dependencies
- `uv run pytest` to run tests
- `npm run build` for frontend builds
- `npm test` for frontend tests

## Project Structure
<!-- Update this section per project -->

## Coding Standards
- Follow existing code style
- Write tests for new features
- Use type hints (Python) / TypeScript strict mode

## MCP Servers
- Claude Code, Codex, Gemini CLI are available in this sandbox
- Use MCP for cross-agent communication
```

Notice what's wrong:

- It assumes both Python (`uv sync`, `uv run pytest`) **and** Node
  (`npm run build`, `npm test`) regardless of which stacks the user
  actually picked. A pure Python project gets npm advice it can't
  use; a pure Next.js project gets `uv` advice it can't use.
- "Project Structure" is a literal `<!-- Update this section per project -->`
  comment. The agent reads that as "no information."
- "Use type hints (Python) / TypeScript strict mode" is two
  language-specific rules glued together regardless of language choice.

### `CLAUDE.md` (~26 lines)

Mostly generic ("check `git status`", "feature branches") plus a useful
note about calling Gemini via MCP with `gemini-3.1-pro-preview`. None
of it is stack-aware.

### `GEMINI.md` (~10 lines)

The thinnest of the three. Generic rules.

### `skills.md` (~17 lines)

A flat tool catalog:

```md
- **uv**: Python package management and virtual environments
- **npm/node**: JavaScript/TypeScript toolchain
- **gh**: GitHub CLI for PR/issue management
- **docker**: Container management (via docker-outside-of-docker)
- **claude**: Claude Code AI assistant
- **codex**: OpenAI Codex agent
- **gemini**: Google Gemini CLI agent (...)
```

Same problem: every project gets the union, not the intersection. A
pure Python sandbox still tells the agent about `npm`. A
no-`--stack docker` project still tells the agent about Docker.

## What stacks contribute today (devcontainer side, not agent side)

Each stack's JSON only affects the devcontainer composition (features,
mounts, postStart commands, bootstrap snippets). None of it reaches
the agent files. There is no `_agents_md` or `_claude_md` mechanism on
stack JSON.

This is the structural gap.

## Why sync makes it worse

`sunaba sync` always copies the four files verbatim from
`templates/agents/`. So even if a user manually edited their root
`AGENTS.md` to record their stack choices, the next `sync` blows it
away. (The harness-engineering proposal already flagged that
`sync` should not be in the path for `--stack harness` content for
this exact reason.)

## What changes downstream when we make agent files stack-aware

If stack `X` contributes per-agent content, `cli.py` needs to know:

1. Which stacks were chosen.
2. Where their per-agent content lives.
3. How to assemble it into the four output files.
4. How to keep `sunaba sync` from clobbering it.
5. How to surface this to the deep-merge composer (or, more likely,
   keep it out of the composer entirely — agent files are Markdown,
   not JSON, and merging Markdown well is a notoriously ugly problem).

The proposal in `05-proposal.md` answers all five.

## What stays the same

Whatever we pick, these stay non-negotiable:

- The generated `AGENTS.md` ratchet body (from the harness PR) stays
  ≤60 lines. Stack contributions count against that budget.
- `SECURITY.md` is **not** stack-composed. Per-cloud content lives in
  `docs/secrets/<cloud>.md` as established in
  [`2026-05-09-secrets-management/05-proposal.md`](../2026-05-09-secrets-management/05-proposal.md).
- The cross-cutting rules (single root `.env`, never write keys to
  source-controlled paths) stay in the base agent templates regardless
  of stacks.
