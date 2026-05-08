# 02 — Research notes

Compact reference. The proposal in `05-proposal.md` builds on these.

## The three formats we have to feed

| File | Read by | Spec | Length budget |
|---|---|---|---|
| `AGENTS.md` | Codex, Cursor, OpenCode, others | [agents.md](https://agents.md/) (cross-vendor spec) | ≤60 lines (HumanLayer) |
| `CLAUDE.md` | Claude Code | [Claude Code docs](https://code.claude.com/docs) | ≤60 lines (HumanLayer) |
| `GEMINI.md` | Gemini CLI | Google docs | similar discipline applies |

Plus the optional **Claude Skills** surface, which is Claude-only:

- `.claude/skills/<name>/SKILL.md` — progressive disclosure, three
  levels (frontmatter → body → linked files).

## What the AGENTS.md spec says about hierarchy

> **The closest AGENTS.md to the edited file wins.**
> Place another AGENTS.md inside each package.

This matters because it gives us a free hierarchy primitive: if a
stack genuinely owns a subdirectory (Next.js → `web/`, Python +
Next.js often → `api/` + `web/`), we can drop a stack-flavored
AGENTS.md inside that directory. Codex, Cursor, and other AGENTS.md
consumers will prefer it over the root file when the agent is
working in that subtree.

But sunaba doesn't *know* whether the user is going to organize the
project as a monorepo. We can't assume `web/` exists.

Source: [agents.md](https://agents.md/),
[Cursor — `.cursorrules` vs `CLAUDE.md` vs `AGENTS.md` (2026)](https://thepromptshelf.dev/blog/cursorrules-vs-claude-md/).

## Claude Skills: the three-level disclosure model

Claude Skills load in stages:

1. **Level 1 — frontmatter.** Always loaded. Just enough for Claude to
   *know the skill exists* and when to invoke it.
2. **Level 2 — body.** Loaded when Claude decides this skill is
   relevant to the current task.
3. **Level 3 — linked files.** Loaded only when the skill body
   references them.

This is the canonical answer to "how do I keep AGENTS.md short while
still shipping a lot of stack guidance?" *for Claude specifically*.

A `.claude/skills/python/SKILL.md` with frontmatter like

```md
---
name: python
description: Python conventions for this project (uv, pytest, ruff)
when: when working in *.py files or running Python tests
---
```

never shows up in Claude's context unless the agent is actually about
to do Python work. Frontmatter cost: ~10 tokens.

Codex and Gemini CLI **don't load Claude skills**. Whatever stack
guidance we put under `.claude/skills/` is invisible to them.

Source:
[Claude Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview),
[Claude Skills authoring best practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices),
[Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).

## Why "compose Markdown" is ugly

`sunaba`'s existing composer (`compose.py`) deep-merges JSON. Lists
concatenate, dicts recurse, scalars overwrite. That works for
`devcontainer.json` because JSON has unambiguous structure.

Markdown does not. Deep-merging Markdown means deciding:

- Where in the parent file the new content goes (after which
  heading?).
- Whether duplicate sections should merge or stack.
- Whether stack ordering matters (it does — Python before Next.js
  reads differently than Next.js before Python).
- How comments / code fences / list items combine.

Every project that has tried "merge Markdown like JSON" has produced
files that look like a robot wrote them. We should not.

The pragmatic alternative: **concatenate** stack-contributed
Markdown sections in stack order, between fixed delimiters in the
template. Each stack contributes one fenced block; the composer just
joins them. No structural merging.

## What other tools do for monorepo / multi-stack contexts

- **Cursor** uses `.cursorrules` (single file) **plus** `.cursor/rules/`
  with file-glob-scoped `.mdc` rules. Per-rule `globs:` field decides
  which files trigger which rules.
- **OpenCode** uses `AGENTS.md` (root) plus optional
  `.opencode/rules.md`.
- **HumanLayer** recommends a 60-line root `CLAUDE.md` and aggressive
  use of skills.
- **Cursor community plugins (in 2026)** are pushing toward
  "**agent plugins**": isolated bundles of sub-agents, skills, hooks,
  and rules. Not formalized yet.

There is no established convention for "stack-flavored AGENTS.md."
That makes it our problem to design *and* worth designing carefully —
sunaba is a small enough surface that we can pick a convention and
let it drive whichever community standard eventually wins.

## On `SECURITY.md`

Should `SECURITY.md` be stack-composed? Our position is **no**:

1. `SECURITY.md` describes the project's security posture and
   reporting policy. Those don't change per stack.
2. The previous proposal (secrets-management) already routes
   per-cloud guidance to `docs/secrets/<cloud>.md` and links them
   from the root `SECURITY.md`. That's the right shape: short
   posture statement at the root, deep cloud-specific content
   one click away.
3. Composing `SECURITY.md` per-stack would create the same
   ugly-Markdown-merge problem AGENTS.md has, with worse
   consequences (security docs that read like a robot wrote them
   make users distrust them).

We will revisit if the reviewers push back hard.

## Summary of the constraints

- **Don't merge Markdown structurally.** Concatenate at fixed
  delimiters.
- **Three output files per project**, one per agent. We cannot
  consolidate.
- **Per-Claude bonus surface (skills) is real and worth using**, but
  not as a substitute for a coherent `AGENTS.md`.
- **HumanLayer's ratchet budget is per-file.** Stack contributions
  share that budget.
- **`sync` must respect stack composition.** It cannot copy verbatim
  from `templates/agents/` once stack content is in play.
