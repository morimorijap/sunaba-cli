# Agents stack

The `agents` stack injects host API keys into the container and persists
CLI auth state in named volumes.

## What you get

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` pulled from the
  host's environment (must be set on the host before container start).
- `~/.claude/`, `~/.codex/`, `~/.gemini/` are named-volume mounts so OAuth
  and session state survive a container rebuild.

## Honest limits

- Once the keys are injected, **any** process in the container — every
  AI agent included — can read them via environment variables. There is
  no isolation between an agent's tool runtime and your `OPENAI_API_KEY`.
- The container is the trust boundary against the host. It is **not** a
  trust boundary against the agents you run inside it.

## Conventions

- Never paste real API keys into source files. The host env vars + the
  persistent CLI auth volumes are sufficient.
- If you need a "key behind a proxy" pattern (so the agent never sees
  the upstream key directly), see the upcoming `--stack secrets` and
  the Azure Foundry → APIM → Gemini → Cosmos pattern.
