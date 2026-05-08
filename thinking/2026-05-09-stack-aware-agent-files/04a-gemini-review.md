# 04a — Reviewer notes: Gemini 3.1 Pro Preview

> Independent review of [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md).
> Model: `gemini-3.1-pro-preview` (Google Gemini CLI MCP).
> Date: 2026-05-09.
>
> Lightly reformatted. Substance unchanged.

## Headline position

> **Strategy A (composed single file) — refined with delimiter-based
> injection.**
>
> Reject Strategy E (subdirectory AGENTS.md) outright.
> Reject Strategy C (skills-only) as primary because Codex / Gemini
> don't load Claude skills.
> Reject structural Markdown merging.

This converges with our prior position on cross-agent fairness and on
"don't structurally merge Markdown."

## A. Strategy

**Refined Strategy A.** Each base template (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`) carries fixed delimiters:

```md
<!-- SUNABA STACKS START -->
<!-- SUNABA STACKS END -->
```

Each stack JSON contributes string arrays under hidden keys
(`_agents_md`, `_claude_md`, `_gemini_md`, `_skills_md`). The existing
deep-merge composer already concatenates and deduplicates lists, so
ordering and idempotency come for free.

### Why this clears the constraints

- **Cross-agent fairness.** Three files, three identical injection
  paths. Codex (`AGENTS.md`), Claude (`CLAUDE.md`), Gemini (`GEMINI.md`)
  receive equivalent stack signal.
- **Length / context budget.** Each stack contributes 1–2 bullets.
  Five stacks ≈ 10 lines of injected content. Well under the 60-line
  HumanLayer discipline.
- **Structural-merge problem avoided.** No AST parsing. HTML-comment
  delimiters are standard practice (Dependabot, `markdown-magic`),
  invisible in rendered Markdown, and universally understood.
- **`sunaba sync` interaction.** **This is the most important
  consequence.** `sync` evolves from "destructive clobber" to "scoped
  delimiter replacement." Anything the user appends *outside* the
  delimited region is preserved.

## B. Composer / generator design

### Where per-stack content lives

Inside the existing `templates/stacks/<name>.json`, using new hidden
keys. `_clean_devcontainer()` already strips keys starting with `_`,
so they don't leak into `devcontainer.json`.

```json
{
  "image": "mcr.microsoft.com/devcontainers/python:1-3.12-bullseye",
  "_agents_md": [
    "- **Python**: Use `uv run pytest` for testing and `uv add` for dependencies."
  ],
  "_skills_md": [
    "- `uv_add`: Resolves and adds Python packages to pyproject.toml."
  ]
}
```

### How `cli.py` assembles the final files

Move agent files **out of `copy_agent_files()` and into
`_build_config_files()`**. This is the second most important change.
It promotes `.md` files to first-class generated assets:

- Same `--dry-run` behavior as `devcontainer.json`.
- Same diff / write machinery.
- Same path-safety checks.
- Same idempotency guarantees.

Implementation sketch:

1. `compose(stacks)` returns the deep-merged dict; the `_agents_md`
   list is concatenated naturally.
2. `cli.py` reads `templates/base/AGENTS.md`.
3. `re.sub(r'(?<=<!-- SUNABA STACKS START -->\n).*?(?=<!-- SUNABA STACKS END -->)',
   joined_list, base_text, flags=re.DOTALL)`.
4. The generated string is added to the `files` dict from
   `_build_config_files()`.

### Stack ordering

Pin to the order of `--stack` flags. The deep-merge composer already
concatenates lists in stack order. `--stack python --stack nextjs`
puts Python rules above Next.js rules — that mirrors the user's
"primary vs. secondary" intent.

### Idempotent regeneration

Same input → byte-identical output, because:

- `compose.py` deduplicates list items while preserving order.
- Regex replacement between static delimiters is strictly
  deterministic.

### Behavior with `--no-devcontainer`

Mandate that stack JSON arrays are **environment-agnostic**. Commands
reference the host CLI tool (e.g. `uv run pytest`), which works the
same inside the devcontainer or directly on the host. The same
Markdown is injected either way.

## C. `skills.md`

**Yes, stack-compose it.**

> *"Providing a union of all possible tools drastically clutters
> context and leads to AI hallucinations (e.g. an agent trying to
> run a Node MCP tool in a pure-Python project)."*

Base `skills.md` carries only core capabilities (`read_file`,
`run_shell`). Stacks contribute through `_skills_md`. The catalog
becomes the intersection, not the union.

## D. `SECURITY.md`

**Strongly push back against composing it.**

> *"Security rules are systemic invariants. A rule like 'Never commit
> AWS keys' is critical even if the project hasn't scaffolded the
> `--stack aws` flag yet — an agent could easily write an AWS key
> into a Python script."*

Plus, per-cloud guidance already lives at `docs/secrets/<cloud>.md`
per the in-flight secrets-management proposal. `SECURITY.md` stays a
static, universal baseline that links to those docs. Stack-composing
it would *introduce* gaps in posture.

## E. Test strategy

```python
def test_agent_files_composed(stacks=("python", "nextjs")):
    files = _build_config_files("p", list(stacks))
    agents = files["AGENTS.md"]
    assert "uv" in agents
    assert "npm" in agents

def test_idempotency():
    a = _build_config_files("p", ["python", "nextjs"])
    b = _build_config_files("p", ["python", "nextjs"])
    assert a == b

def test_length_constraints():
    files = _build_config_files("p", ["python", "nextjs", "azure", "agents"])
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        assert len(files[name].splitlines()) <= 60

def test_sync_preserves_user_edits(tmp_path):
    # Append text below <!-- SUNABA STACKS END --> ...
    # Run sync ...
    # Assert the user-appended text still exists.
    ...

def test_ordering():
    files = _build_config_files("p", ["python", "nextjs"])
    agents = files["AGENTS.md"]
    assert agents.index("Python") < agents.index("Next.js")
```

## F. Top-3 picks

1. **Delimiter-based Markdown injection (Strategy A).** Solves the
   core "irrelevant advice" problem without AST parsing.
2. **Preservative `sunaba sync`.** Move from clobber to scoped
   replacement so users can safely customize their agent files
   between runs.
3. **Shift agent files into `_build_config_files()`.** Markdown
   becomes a first-class generated asset, gaining `--dry-run`,
   diffing, lifecycle management.

## G. Push-back

- **Drop Strategy E (subdirectory AGENTS.md).** Users rename `web/`
  to `frontend/`, `ui/`, `app/` constantly. The generator shouldn't
  guess. Keep instructions at the root.
- **Drop structural Markdown merging.** AST merging is brittle,
  overkill, produces robot-looking output. Delimiters are robust,
  invisible to rendered Markdown, universally supported.
- **Drop Strategy C (skills-only) as the primary surface.** Stashing
  stack guidance under `.claude/skills/` fragments cross-agent. Codex
  and Gemini don't auto-load those paths. A composed root file per
  agent equalizes capability across clients.

## What this leaves open for the synthesized proposal

Areas the second reviewer (Codex high reasoning) needs to weigh in on
before we lock the design:

- **Skills as a *complement* to root composition.** Gemini rejects
  Strategy C as the primary surface but didn't address whether it's
  worth shipping `.claude/skills/<stack>/SKILL.md` *in addition* to
  the composed root file. That additive case still has merit because
  Claude's progressive disclosure costs almost nothing in the base
  context.
- **The "stack ordering matters" claim.** Gemini takes the position
  that primary stack first is correct. That deserves a second
  opinion.
- **Whether `_skills_md` should also be a list.** The deep-merge
  composer concatenates lists with deduplication. Same machinery,
  same trade-offs. Worth confirming.
