# 03 — LLM consultation brief (stack-aware agent files)

> Self-contained brief sent to external reviewers (Codex / Gemini Pro
> Preview). They have **not** seen the conversations that led here.

---

## You are reviewing

A small open-source CLI called **`sunaba-cli`**
(<https://github.com/morimorijap/sunaba-cli>). It scaffolds disposable
devcontainer sandboxes for AI coding agents (Claude Code, OpenAI Codex
CLI, Google Gemini CLI). It is a **template generator** — it writes
files, then gets out of the way.

Composable stacks: `python` `nextjs` `aws` `azure` `gcp` `neon`
`agents` (injects API keys) `docker` `playwright`. Two more proposals
in flight: `--stack harness` (harness-engineering scaffold,
`.claude/...`) and `--stack secrets` (gitleaks + per-cloud docs).

A user can run something like:

```bash
sunaba new myapp --stack python --stack nextjs --stack azure --stack agents
```

## The problem

The four agent-instruction files sunaba generates today —
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `skills.md` — are static
templates copied verbatim regardless of which stacks were chosen.
That means:

- A pure-Python project gets `npm test` advice it can't use.
- A pure-Next.js project gets `uv run pytest` advice it can't use.
- The "tools" catalog in `skills.md` is the union, not the
  intersection.
- Nothing in any of the four files acknowledges the user picked
  Azure / AWS / GCP / Neon.

We want generated agent files to **reflect the chosen stacks**
without:

- blowing past HumanLayer's 60-line ratchet budget on `AGENTS.md`
  (each `AGENTS.md` ≤ 60 lines is a discipline we want to keep —
  see HumanLayer's "Skill Issue: Harness Engineering for Coding
  Agents"),
- duplicating the same content across three files (`AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`),
- structurally merging Markdown (which always produces
  robot-looking files),
- and breaking the existing JSON-only deep-merge composer in
  `compose.py`.

## Five candidate strategies

### A. Composed single file (per agent)

Each stack JSON gets new keys:

```json
{
  "_agents_md":  "## Python\n- uv sync\n- uv run pytest -q\n- ...",
  "_claude_md":  "## Python\n- Run ruff before pytest.\n- ...",
  "_gemini_md":  "## Python\n- Use uv as the package manager.\n- ..."
}
```

`cli.py` concatenates these between fixed delimiters in the base
template:

```md
# AGENTS.md (base header)
...base content...
<!-- BEGIN: stack sections -->
## Python
- uv sync
- uv run pytest -q

## Next.js
- npm ci --ignore-scripts
- npm test
<!-- END: stack sections -->
```

### B. Multiple files at root

Generate `AGENTS.md` (base, short) plus `AGENTS.python.md`,
`AGENTS.nextjs.md`, `AGENTS.azure.md`. The base file `@`-includes them.

Pro: each file is small.
Con: tools may not all support `@`-include; spec-conformant agents
read whichever AGENTS.md is closest to the file they're editing.

### C. Skills + minimal root (Claude-only progressive disclosure)

Root `AGENTS.md` stays at ≤60 lines. Detailed per-stack guidance
moves to `.claude/skills/<stack>/SKILL.md` so Claude only loads it
when relevant. Codex / Gemini get a slightly richer composed file
because they don't load skills.

This is canonical for Claude. It does nothing for Codex / Gemini.

### D. Hybrid

- Minimal root `AGENTS.md` with one-line per-stack pointers.
- Deep guidance in `.claude/skills/<stack>/SKILL.md` (Claude).
- Mirror the same content as `docs/agents/<stack>.md` so non-Claude
  agents can be told to read it when relevant.

### E. Subdirectory AGENTS.md

When a stack genuinely owns a subdirectory (Next.js → `web/`), drop
an additional AGENTS.md *inside that subdirectory*. The
[agents.md](https://agents.md/) spec says the closest AGENTS.md to
the edited file wins. This is free hierarchy, but assumes the
subdirectory exists — and `sunaba` doesn't dictate project layout.

## On `SECURITY.md`

Our current position is that `SECURITY.md` should **not** be
stack-composed; per-cloud content already lives in
`docs/secrets/<cloud>.md` per the secrets-management proposal.

We want you to confirm or push back on that.

## Constraints

- **Templates only** — sunaba is a generator.
- **No backwards-incompatible churn** for `sunaba new` /
  `sunaba rebuild` / `sunaba sync` users.
- **Opt-in for material change.** Stack-composing existing agent
  files is a behavior change for `sunaba sync`, which currently
  copies verbatim.
- **Don't structurally merge Markdown.** Concatenation between
  fixed delimiters is the most we will accept.
- **Cross-agent fairness.** Whatever we ship has to give Codex /
  Gemini equivalent (not identical) signal to Claude. We are not
  optimizing the project around Claude.
- **HumanLayer 60-line discipline** stays per-file.

## What we want back

### A. Pick a strategy

Argue for one of A–E (or a combination), or propose a different
one. Address:

- Cross-agent fairness — does this give Codex / Gemini comparable
  signal?
- Length / context budget — does the chosen approach respect the
  60-line discipline?
- The structural-merge problem — how does your approach avoid
  ugly Markdown?
- `sunaba sync` interaction — what does sync do once stacks
  contribute content?

### B. The composer / generator design

Concrete:

- Where does the per-stack content live? (`stacks/<name>.json`
  with new `_agents_md` / `_claude_md` / `_gemini_md` keys?
  Sibling `.md` files in `templates/agent-fragments/<stack>/`?)
- How does `cli.py` assemble the final files?
- Stack ordering — does it matter? Pin the order to the user's
  `--stack` flags, or sort?
- Idempotent regeneration — running twice with the same flags
  must produce byte-identical output.
- Behavior with `--no-devcontainer`.

### C. `skills.md` (the tool catalog)

Should it be stack-composed? Right now it's the union of every
possible tool. Proposed direction: each stack contributes a few
lines, just like AGENTS.md.

### D. `SECURITY.md`

Should it be stack-composed? We say no — argue if you disagree.

### E. Test strategy

`sunaba` uses `pytest`. Propose **structural** tests for the new
generator: per-stack content present, idempotency, length
constraints, ordering.

### F. Top-3 picks

If we can only land three things in this PR, which three move the
posture the most?

### G. Push-back

Anything in the hypothesized framing you'd reject? Drop bad ideas
now.

---

## Length and format

Long-form welcome. Public design doc. Markdown. Code/file snippets
in fenced blocks. Cite sources for opinions that come from external
references.
