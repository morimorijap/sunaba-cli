# 02 — Research notes

Compact reference for the proposal.

## Cursor rules `.mdc` — the reference implementation for scoped rules

- Location: `.cursor/rules/*.mdc`. Cursor reads recursively.
- YAML frontmatter:
  ```yaml
  ---
  description: Use Tailwind for styling React components
  globs: ["src/**/*.tsx", "src/**/*.jsx"]
  alwaysApply: false
  ---
  ```
- `alwaysApply: true` means the rule is in context every turn.
- `alwaysApply: false` + `globs` means "load when the user is editing
  a matching file."
- Body is plain Markdown. Conventionally short — the rule is a
  *constraint*, not a tutorial.

Source:
[Cursor Rules — Complete .mdc Guide & 15 Templates (2026)](https://www.vibecodingacademy.ai/blog/cursor-rules-complete-guide),
[awesome-cursor-rules-mdc](https://github.com/sanjeed5/awesome-cursor-rules-mdc).

## Claude Code path-specific rules (early 2026)

Anthropic shipped path-specific rules natively, with a slightly
different shape: rules use a `paths:` key rather than `globs:`. Cursor
can also load Claude skills/plugins; imported rules are treated as
*agent-decided* (Cursor decides relevance from context rather than
matching globs).

Cross-tool conversion tools exist (e.g., `rule-porter` from the
Cursor community) that translate `.mdc` → `CLAUDE.md` /
`AGENTS.md` / Copilot Instructions.

Source:
[Claude Code Gets Path-Specific Rules (Cursor Had This First)](https://paddo.dev/blog/claude-rules-path-specific-native/),
[Cursor Forum — rule-porter](https://forum.cursor.com/t/rule-porter-convert-your-mdc-rules-to-claude-md-agents-md-or-copilot/153197).

## Claude Code subagents 2.0

- Defined in Markdown files with frontmatter under `.claude/agents/`
  (project) or `~/.claude/agents/` (user).
- Each subagent has **its own context window** and a configurable
  subset of tools — the parent's context isn't polluted by the
  subagent's intermediate steps.
- Spawned through the **Agent tool**. The subagent gets a single
  prompt, runs its own loop, and returns a single summary message.
- Three justified use cases (per Anthropic's own framing):
  - *Parallelizing independent work.*
  - *Isolating heavy research* so it doesn't saturate the main
    conversation.
  - *Specializing on a domain* (frontend, security, debugging).

Source:
[Claude Code Agents & Subagents — Complete Guide (2026)](https://skillsplayground.com/guides/claude-code-agents/),
[Anthropic — Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview).

## Auto Mode — Anthropic's safety gates for autonomous coding

InfoQ (May 2026) describes Auto Mode as "autonomous coding *with
human approval gates*." Three gate layers:

1. **Outbound check** at delegation. Validates the dispatched task
   against the user's stated intent before the subagent starts.
2. **Return check** at completion. Evaluates the subagent's full
   execution history for prompt-injection or in-loop manipulation
   before merging the result back.
3. **Permission boundaries** for the underlying tools, with
   explicit allow / deny lists.

The framing is the right one for sunaba's autopilot stack: *not* "no
human in the loop ever," but "human approves the *boundaries*, then
agents work inside them."

Source:
[InfoQ — Inside Claude Code Auto Mode (May 2026)](https://www.infoq.com/news/2026/05/anthropic-claude-code-auto-mode/).

## Ralph Loop — the canonical autonomous-development pattern

> "Run the same prompt repeatedly, with stronger context each time,
> until verification passes."

Mechanics:

- A driver script (or hook) re-invokes the agent with a fresh prompt
  each iteration.
- Each iteration ends in a verifier (typecheck / lint / tests).
- On failure, the next iteration receives the failure output as
  context.
- Termination: verifier passes, max-iterations reached, or wallclock
  exceeded.

This is operationally what `.claude/hooks/verify.sh` enables when it
exits with code 2 — the harness re-engages the agent. We don't need
to ship Ralph itself; we need to ship *something Ralph-shaped that
respects sunaba's constraints* (templates only, no runtime).

Source:
[Knightli — What Ralph Is (Apr 2026)](https://www.knightli.com/en/2026/04/27/ralph-autonomous-agent-loop-claude-code-amp/).

## AGENTS.md hierarchy (recap)

- `AGENTS.md` is the cross-tool baseline supported by Codex,
  Cursor, Copilot, Windsurf, OpenCode.
- The closest `AGENTS.md` to the file being edited wins — natural
  hierarchy for monorepos.
- The recommended structure: a single root `AGENTS.md` for shared
  rules, plus tool-specific files (`CLAUDE.md`, `.cursor/rules/`)
  for tool-specific behavior.

Source:
[deployhq — CLAUDE.md, AGENTS.md & Copilot Instructions](https://www.deployhq.com/blog/ai-coding-config-files-guide),
[AGENTS.md Guide (2026)](https://vibecoding.app/blog/agents-md-guide).

## Rule priority across systems

The 2026 convention across tools:

```
Team Rules → Project Rules → User Rules
Earlier sources win on conflict.
```

For sunaba this means:

- **Project-level** rules (what we ship) live in
  `.cursor/rules/*.mdc`, `.claude/rules/*.md`, and root /
  subdirectory `AGENTS.md`.
- **User-level** rules (what the developer adds at home) live in
  `~/.cursor/rules/`, `~/.claude/agents/` etc.
- We ship templates the user owns; we never write to user-level
  paths.

## Codex CLI / Gemini CLI — what's actually portable

Honest accounting of cross-agent autonomy support, May 2026:

| Capability | Claude Code 2.0 | Codex CLI | Gemini CLI |
|---|---|---|---|
| Subagents (separate context) | Native (`.claude/agents/`) | Limited (Task delegation via prompts; no separate context) | Not yet |
| Path-specific rules | Native | Hierarchical via subdirectory `AGENTS.md` | `GEMINI.md` only (no path scoping) |
| Stop hooks (re-engage) | Native | Not standardized | Not standardized |
| Permission allow/deny | Native | Sandbox flags (`-s`) | Ask-on-action |
| Auto Mode equivalent | Native | `codex exec` non-interactive | One-shot only |

Two implications:

1. **Cross-agent parity is currently impossible.** Anything with
   "subagent dispatch with auto-verify" lives in Claude Code first.
2. **We can still ship for all three.** Rules: AGENTS.md hierarchy
   handles Codex; `.claude/rules/` handles Claude;
   `.cursor/rules/*.mdc` covers Cursor users. Gemini gets the root
   `GEMINI.md` plus `docs/agents/<stack>.md` from the stack-aware
   PR. Subagents: ship Claude-native; document the Codex / Gemini
   limitations honestly. Autonomy: ship Claude-flavored hook
   wiring; mark the rest "Claude-only" until upstream catches up.

## What converges across the sources

If you strip away the marketing, every 2026 autonomous-coding source
agrees on these five points:

1. **Verification beats persuasion.** A failing typecheck is more
   reliable than "please run the typecheck." The Stop hook is
   the keystone.
2. **Scope rules to where they apply.** A rule that activates on
   every turn is a tax; a rule that activates on `*.tsx` is
   information.
3. **Subagents are a context firewall, not roleplay.** Use them to
   isolate heavy work, not to make the model "be a frontend
   engineer."
4. **Autonomy needs explicit gates.** Outbound check, return
   check, hard budget cap. No exceptions.
5. **Recovery is non-optional.** Branch protection +
   checkpoint/resume + clear rollback path. Without these, a long
   autonomous run that fails late costs the user real money.
