# 05 — Proposal

> Synthesized from research notes and the two independent reviews
> ([`04a-gemini-review.md`](04a-gemini-review.md),
> [`04b-codex-review.md`](04b-codex-review.md)).
> Status: **draft for PR review**. Not implemented yet.

## TL;DR

We adopt **Strategy D with a thin "Strategy A"** root:

- Root `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` become **stack-aware
  indexes** — short, scannable, ≤60 lines even with 5+ stacks.
  Stacks contribute one or two summary lines that link to the
  canonical detail page.
- Canonical per-stack detail lives in **`docs/agents/<stack>.md`**.
  This file is the single source of truth for stack guidance.
- For Claude specifically, the same detail is also rendered to
  **`.claude/skills/sunaba-<stack>/SKILL.md`** with YAML frontmatter,
  enabling progressive disclosure. Codex / Gemini find it via
  `docs/agents/<stack>.md`.
- **`skills.md`** (the tool catalog) is stack-composed too — base
  tools at the top, stack tools appended in the user's `--stack`
  order.
- **`SECURITY.md`** is **not** stack-composed.

Where Codex and Gemini disagreed, we split the difference:

- **Where Markdown lives.** Codex wins. Per-stack `.md` fragments
  under `templates/agents/fragments/<stack>/` — **not** strings
  embedded in `stacks/*.json`. `compose.py` stays JSON-only.
- **How root files are composed.** Gemini wins. **Delimiter-based
  injection** — `<!-- SUNABA STACKS START -->` / `<!-- ... END -->`
  — between which the composer concatenates each stack's
  `summary.md` fragment.
- **`sunaba sync` posture.** Codex wins on safety. Registry-recorded
  mode (`agent_files: "static" | "stack-aware"`); legacy projects
  keep static copy by default; explicit opt-in migration. Inside the
  delimited region, replacement is preservative — anything outside
  the delimiters is left alone (Gemini's contribution).

## Maturity score (consensus)

| Axis | Score | Notes |
|---|---:|---|
| Stack signal in root agent files | 1/5 | Static templates, irrelevant advice for off-stack projects. |
| `skills.md` accuracy | 1/5 | Union of every tool, regardless of selection. |
| Cross-agent fairness | 2/5 | Three files exist, but content is identical-and-generic. |
| Length discipline | 3/5 | Short today, but "short *and useless*" doesn't count. |
| Sync safety | 2/5 | Verbatim copy clobbers user edits silently. |

## Where the reviewers disagreed

We had three substantive disagreements. Recording our position so
future contributors can re-open if facts change.

### Disagreement 1 — Where does per-stack Markdown live?

- **Gemini.** String arrays inside `stacks/<name>.json`
  (`_agents_md: ["- ...", "- ..."]`). Composer machinery already
  deduplicates lists.
- **Codex.** Separate `.md` files under
  `templates/agents/fragments/<stack>/`. `compose.py` is a
  JSON-only deep-merge composer; pollute it with Markdown bodies
  and reviewability and escaping both suffer.

**Decision: Codex's separate fragments.**

Three reasons:

1. **PR review.** A 6-line bullet list in JSON-escaped form
   (`"- **Python**: Use `uv run pytest`...\n- **uv add** instead of pip install\n..."`)
   is nearly unreadable in a diff. The same content as raw Markdown
   in `fragments/python/summary.md` is reviewed in seconds.
2. **Editor support.** Markdown linters, spell-checkers, and
   syntax highlighters work on `.md` files. They do not work on
   string-escaped Markdown inside JSON.
3. **Composability remains the same.** We can still concatenate
   fragments in stack order; we just read them from disk instead of
   from JSON keys. The composer logic is comparable.

The cost: one new directory layer. We accept it.

### Disagreement 2 — How much detail in the root file?

- **Gemini.** Inject the full per-stack body into the root
  `AGENTS.md` between delimiters.
- **Codex.** Root is a thin **index** — one summary line per
  stack, linking to `docs/agents/<stack>.md`.

**Decision: Codex's thin index.**

Why:

1. **The 60-line budget.** With five stacks contributing 6 lines
   each, Gemini's approach hits 30 lines of stack content alone,
   leaving 30 for everything else (header, general rules, ratchet
   log from the harness PR). It works, but it's tight.
2. **Reading economy.** A short index that the agent always loads,
   plus a deeper page the agent reads only when relevant, is a
   *better* progressive-disclosure shape than "everything inline."
3. **The single-source-of-truth claim is real.** `docs/agents/
   <stack>.md` reads the same as a docs page for a human as it does
   for an agent. That's a dual-use property worth keeping.

We still use Gemini's **delimiter-based injection** for the root —
just for a much smaller payload (the index lines).

### Disagreement 3 — `sunaba sync` posture

- **Gemini.** Move sync to delimiter-preserving replacement
  unconditionally. Existing files get partial rewrites on the next
  `sync`.
- **Codex.** Add a registry mode flag (`agent_files:
  "static"` | `"stack-aware"`). Legacy projects keep static copy.
  Explicit opt-in migration command.

**Decision: Codex's mode flag, with Gemini's delimiter machinery
inside the stack-aware mode.**

Why:

1. **Predictability for existing users.** A user who has been
   running `sunaba sync` for months should not see their `AGENTS.md`
   suddenly grow new sections because they upgraded `sunaba-cli`.
   Codex's gate keeps the upgrade silent.
2. **Migration path.** `sunaba sync --agent-files stack-aware
   <name>` migrates a project once. The next regular `sync` follows
   the new mode automatically.
3. **Composability.** Once a project is in stack-aware mode, the
   delimiter-preserving replacement Gemini described kicks in. User
   edits *outside* the delimited region are preserved across syncs.

## What we add

### 1. Fragment layout under `templates/agents/`

```
src/sunaba_cli/templates/agents/
├── base/
│   ├── AGENTS.md
│   ├── CLAUDE.md
│   ├── GEMINI.md
│   └── skills.md
└── fragments/
    ├── python/
    │   ├── summary.md     # 1–3 lines for the root index
    │   ├── tools.md       # 1–3 lines for skills.md
    │   └── guidance.md    # full body for docs/agents and skills mirror
    ├── nextjs/
    ├── aws/
    ├── azure/
    ├── gcp/
    ├── neon/
    ├── agents/
    ├── docker/
    └── playwright/
```

Each stack contributes three small files. Stacks without meaningful
content for a slot ship an empty file (or omit it; the composer skips
missing files).

### 2. Base templates with delimiters

`templates/agents/base/AGENTS.md`:

```md
# AGENTS.md

This sandbox was generated by sunaba. The rules below apply to any
agent (Claude Code, Codex, Gemini CLI) operating in this repository.

## Sandbox

Disposable devcontainer for AI agent development. If something
breaks, rebuild the container.

## Selected stacks

<!-- SUNABA STACKS START -->
<!-- SUNABA STACKS END -->

## General rules

- Prefer existing project commands over inventing new ones.
- Add or update tests for changed behavior.
- One `.env` at the repository root for local dev. Nowhere else.
- Never commit API keys, tokens, private keys, or cloud credential
  files.
- Cloud secret managers and `.gitignore` do not protect runtime env
  vars from agents in the container.

<!-- SUNABA USER START -->
<!-- Edit freely below this marker. sunaba sync will preserve it. -->
<!-- SUNABA USER END -->
```

`CLAUDE.md` and `GEMINI.md` mirror this shape — same delimiters,
agent-specific tone tweaks. The `## General rules` section can carry
the harness-PR's ratchet log entries verbatim.

### 3. Example fragment

`templates/agents/fragments/python/summary.md`:

```md
- **python**: `uv` for dependencies, `uv run pytest -q` for tests,
  `uv run ruff check` for lint. Detail in `docs/agents/python.md`.
```

`templates/agents/fragments/python/tools.md`:

```md
- **uv** — Python package manager + virtualenv (use this; do not
  install with `pip install` directly).
- **ruff** — formatter + linter (`uv run ruff check` /
  `uv run ruff format`).
- **pytest** — test runner (`uv run pytest -q`).
```

`templates/agents/fragments/python/guidance.md`:

```md
# Python stack

This sandbox uses Python 3.14 with `uv`. The following commands are
expected to be available.

## Day-to-day

```sh
uv sync                  # install/update deps from pyproject.toml
uv run pytest -q         # run tests
uv run ruff check        # lint
uv run ruff format       # format
```

## Conventions

- Edit `pyproject.toml` directly to add deps; let `uv sync` resolve.
  Don't write to `requirements.txt`.
- Type-hint new code. The project does not require 100% coverage,
  but new functions should annotate args and return types.
- Tests live under `tests/`. Match the source path structure.

## What not to do

- Don't run `pip install` against the project's `.venv`.
- Don't commit the `.venv/` (already in `.gitignore`).
- Don't generate fixtures with real-looking secrets.
```

The same `guidance.md` body is copied verbatim to
`docs/agents/python.md`, and is also wrapped with frontmatter to
produce `.claude/skills/sunaba-python/SKILL.md`.

### 4. Generator: `_build_agent_files()`

New helper in `cli.py`:

```python
def _build_agent_files(
    name: str,
    stacks: list[str],
    *,
    no_devcontainer: bool = False,
) -> dict[str, str]:
    """Produce the stack-aware agent-file outputs.

    Returns {relpath: content} for:
      AGENTS.md, CLAUDE.md, GEMINI.md, skills.md,
      docs/agents/<stack>.md (per stack with guidance.md),
      .claude/skills/sunaba-<stack>/SKILL.md (per stack with guidance.md).
    """
    files: dict[str, str] = {}

    # 1. Compose root indexes via delimiter injection.
    for base_name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        base = (TEMPLATES_DIR / "agents" / "base" / base_name).read_text()
        body = "\n".join(
            _read_fragment(s, "summary.md") for s in stacks
            if _fragment_exists(s, "summary.md")
        )
        files[base_name] = _inject_between_delimiters(
            base,
            "<!-- SUNABA STACKS START -->",
            "<!-- SUNABA STACKS END -->",
            body,
        )

    # 2. Compose skills.md from base + per-stack tools fragments.
    skills_base = (TEMPLATES_DIR / "agents" / "base" / "skills.md").read_text()
    skills_body = "\n".join(
        _read_fragment(s, "tools.md") for s in stacks
        if _fragment_exists(s, "tools.md")
    )
    files["skills.md"] = _inject_between_delimiters(
        skills_base,
        "<!-- SUNABA STACKS START -->",
        "<!-- SUNABA STACKS END -->",
        skills_body,
    )

    # 3. Per-stack docs and Claude skills mirror.
    for s in stacks:
        if not _fragment_exists(s, "guidance.md"):
            continue
        guidance = _read_fragment(s, "guidance.md")

        files[f"docs/agents/{s}.md"] = guidance

        skill_frontmatter = (
            "---\n"
            f"name: sunaba-{s}\n"
            f"description: Use when working on {s} parts of this project, "
            f"generated by sunaba --stack {s}.\n"
            "---\n\n"
        )
        files[f".claude/skills/sunaba-{s}/SKILL.md"] = skill_frontmatter + guidance

    if no_devcontainer:
        # Switch wording to host-only where applicable.
        files = {k: _strip_devcontainer_assumptions(v) for k, v in files.items()}

    return files
```

`_inject_between_delimiters` is a tight function — find the
delimiters, replace what's between them, leave everything else
untouched. No regex magic outside that scope.

`_strip_devcontainer_assumptions` is a small tag-based scrubber that
removes any blocks marked `<!-- DEVCONTAINER ONLY -->...<!-- END -->`
when the project is host-only.

### 5. Wire into `_build_config_files()`

```python
def _build_config_files(
    name: str, stacks: list[str], *, no_devcontainer: bool = False
) -> dict[str, str]:
    files: dict[str, str] = {}
    # ...existing devcontainer/dependabot/mcp/vscode logic...
    files.update(_build_agent_files(name, stacks, no_devcontainer=no_devcontainer))
    return files
```

This promotes Markdown to a first-class generated asset (Gemini's
contribution): `--dry-run`, diffing, and path-safety apply uniformly.

### 6. Registry mode flag and `sync`

`sunaba new` records `agent_files: "stack-aware"` for new projects.
Legacy projects (entry without that key) default to `"static"`.

`sync` switch:

```python
def sync_project(name: str) -> tuple[Path | None, list[str]]:
    entry = get_project(name)
    if entry is None:
        return None, []

    project_path = Path(entry["path"])
    mode = entry.get("agent_files", "static")
    stacks = entry.get("stacks") or []

    if mode == "static" or not stacks:
        return project_path, copy_agent_files(project_path)

    # stack-aware: regenerate via _build_agent_files,
    # write only inside the SUNABA STACKS delimiter regions
    # for AGENTS.md / CLAUDE.md / GEMINI.md / skills.md.
    # Leave the post-USER-START region untouched.
    return project_path, _sync_stack_aware(project_path, stacks)
```

Migration is explicit:

```bash
sunaba sync --agent-files stack-aware myapp
```

This flips the registry mode and runs one stack-aware sync. From
that point on, `sunaba sync myapp` follows the new mode
automatically.

### 7. `SECURITY.md`

Stays a single, repo-level document. The only conditional change is
that when `--stack secrets` is selected (per the secrets-management
proposal), a fixed reference line is appended pointing at
`docs/secrets/`.

```diff
+## Secrets
+
+See [`docs/secrets/`](docs/secrets/) for per-cloud guidance and the
+[Azure Foundry → APIM → Gemini → Cosmos](docs/secrets/azure-foundry-apim-gemini-cosmos.md)
+key-behind-a-proxy pattern.
```

That's the entire conditional surface in `SECURITY.md`. We don't
inject AWS / GCP / Azure body content into the root.

## Tests

Structural, not behavioral.

```python
def test_python_only_has_uv_no_npm():
    files = _build_config_files("p", ["python"])
    assert "uv run pytest" in files["AGENTS.md"]
    assert "npm test" not in files["AGENTS.md"]

def test_nextjs_only_has_npm_no_uv():
    files = _build_config_files("p", ["nextjs"])
    assert "npm" in files["AGENTS.md"]
    assert "uv run pytest" not in files["AGENTS.md"]

def test_per_stack_docs_generated():
    files = _build_config_files("p", ["python", "azure"])
    assert "docs/agents/python.md" in files
    assert "docs/agents/azure.md" in files

def test_claude_skill_has_frontmatter():
    files = _build_config_files("p", ["python"])
    skill = files[".claude/skills/sunaba-python/SKILL.md"]
    assert skill.startswith("---\nname: sunaba-python\n")
    assert "description:" in skill

def test_skills_md_contains_only_selected_tools():
    files = _build_config_files("p", ["python"])
    assert "uv" in files["skills.md"]
    assert "vercel" not in files["skills.md"]
    assert "neonctl" not in files["skills.md"]

def test_agents_md_under_60_lines_for_realistic_combos():
    for stacks in [
        ["python", "agents"],
        ["nextjs", "agents"],
        ["python", "nextjs", "azure", "agents"],
        ["python", "nextjs", "aws", "gcp", "azure", "agents"],
    ]:
        files = _build_config_files("p", stacks)
        for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            assert len(files[name].splitlines()) <= 60, (stacks, name)

def test_idempotent_regeneration():
    a = _build_config_files("p", ["python", "nextjs"])
    b = _build_config_files("p", ["python", "nextjs"])
    assert a == b

def test_stack_order_preserved():
    files = _build_config_files("p", ["nextjs", "python"])
    text = files["AGENTS.md"]
    assert text.index("nextjs") < text.index("python")

def test_no_devcontainer_strips_devcontainer_assumptions():
    files = _build_config_files("p", ["python"], no_devcontainer=True)
    body = files["AGENTS.md"] + files["skills.md"]
    assert "devcontainer feature" not in body.lower()
    assert "host-only" in body.lower()

def test_sync_static_mode_unchanged(tmp_path, monkeypatch):
    # Legacy project (no agent_files key in registry) → copy_agent_files path.
    ...

def test_sync_stack_aware_preserves_user_region(tmp_path, monkeypatch):
    # Append text below SUNABA USER START in AGENTS.md, run stack-aware sync,
    # assert the appended text survives.
    ...

def test_sync_stack_aware_requires_known_stacks(tmp_path):
    # Project registered without stacks → error when stack-aware sync requested.
    ...
```

## What we explicitly do **not** do in this PR

- **Don't put Markdown bodies inside `stacks/*.json`.** Codex was
  right; PR review and editor support both suffer.
- **Don't structurally merge Markdown.** Concatenate at delimiters.
  No AST work.
- **Don't rely on `@include` directives.** Generated files have to
  make sense as static text.
- **Don't ship Claude skills before the equivalent
  `docs/agents/<stack>.md` exists.** Cross-agent fairness — Codex /
  Gemini have to be able to find the same content.
- **Don't make subdirectory `AGENTS.md` automatic.** sunaba does
  not dictate project layout. If we add a `--layout` flag later,
  this becomes a follow-up.
- **Don't change `sunaba sync` for existing projects without an
  explicit migration command.** Predictability beats elegance.
- **Don't compose `SECURITY.md` per-stack.** Single allowed
  conditional change is the `--stack secrets` reference line.

## Rebuild consistency

> Added 2026-05-09 in response to: *"are inconsistencies on
> `sunaba rebuild` considered?"*
> The original proposal defined how `sunaba sync` behaves for
> stack-aware mode (preservative delimiter replacement) but did not
> specify how `sunaba rebuild` behaves on the same projects, did not
> define orphan handling for removed stacks, and did not address
> the `dry-run` diff inconsistency.

### `rebuild` must use the same write path as `sync` for stack-aware projects

The original proposal contains a contradiction:
`_sync_stack_aware()` writes only **inside** the
`<!-- SUNABA STACKS START/END -->` region, but `rebuild` calls
`_write_files()` which is a blind overwrite. So
`sunaba rebuild myapp --add azure` on a stack-aware project would
*destroy* the user's region below `<!-- SUNABA USER START -->`.

**Decision: `rebuild` consults the registry mode and dispatches.**

```python
def _write_agent_files(project_dir: Path, files: dict, mode: str) -> list[str]:
    if mode == "stack-aware":
        return _write_preservative(project_dir, files)
    return _write_files(project_dir, files)  # legacy path
```

`_write_preservative()` is the same function `sync` uses. For the
four root files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `skills.md`)
it replaces only the delimited region. For everything else
(`docs/agents/<stack>.md`, `.claude/skills/sunaba-<stack>/SKILL.md`)
it overwrites whole-file because those are pure render targets and
are not expected to carry user edits.

If the registry mode is `static`, `rebuild` behaves exactly as
today.

### `rebuild --remove <stack>` leaves orphan render targets

When a project drops a stack in stack-aware mode, the per-stack
render targets become orphans:

- `docs/agents/<stack>.md`
- `.claude/skills/sunaba-<stack>/SKILL.md`

The root `AGENTS.md` re-composes correctly (the removed stack's
summary line just isn't there anymore), but the orphan files lurk
on disk.

**Decision: same as the harness PR's orphan policy.** Don't
auto-delete; report and instruct. The harness PR introduces the
shared orphan-scan code path; this PR registers two more path
patterns into it:

```python
ORPHAN_PATTERNS_PER_REMOVED_STACK = {
    "stack-aware": [
        "docs/agents/{stack}.md",
        ".claude/skills/sunaba-{stack}/SKILL.md",
    ],
}
```

The user-facing report on `rebuild --remove python`:

```
Stack 'python' was removed. The following stack-aware render targets
are no longer regenerated and were left in place:
  docs/agents/python.md
  .claude/skills/sunaba-python/SKILL.md
Delete them with:  rm docs/agents/python.md .claude/skills/sunaba-python/SKILL.md
```

We do **not** delete `docs/agents/` or `.claude/skills/` themselves
even when empty — those directories may have other content the user
added.

### `rebuild --dry-run` diff is misleading for delimited files

Today `_diff_files()` reports `modified` if the file's full content
differs. For `AGENTS.md` in stack-aware mode, every regeneration
produces a new "in-region" body — but if the user has edits
*outside* the delimiters, those survive intact and shouldn't be
reported as user-affecting changes.

Conversely, if the user edited the delimited region by hand, that's
about to be overwritten — and they need to see it loud and clear.

**Decision: `_diff_files()` learns the delimiter convention.**

For paths in `_DELIMITED_PATHS = {"AGENTS.md", "CLAUDE.md",
"GEMINI.md", "skills.md"}`, the diff:

1. Extracts the existing in-region body and compares to the new
   in-region body. This is the "stack contribution" diff. Reported
   as `modified (managed region)`.
2. Extracts the existing out-of-region body. If it does not match
   the base template's out-of-region body **and** the new
   composition is also using the base template (i.e., we're about
   to clobber user edits inside what should be a managed region),
   warn loudly:

   ```
     ! AGENTS.md (managed region modified, user edits in managed region detected)
   ```

Whole-file targets (`docs/agents/<stack>.md`,
`.claude/skills/...`) keep the existing whole-file diff.

Snapshot test:

```python
def test_rebuild_dry_run_does_not_flag_user_region_edits(tmp_path):
    # Generate a stack-aware project, append text below
    # <!-- SUNABA USER START -->, then run rebuild --dry-run with
    # the same stacks. Assert AGENTS.md is reported as 'unchanged'.
    ...

def test_rebuild_dry_run_warns_on_managed_region_edits(tmp_path):
    # Append text inside the delimited region by hand. Then rebuild
    # --dry-run. Assert the warning fires.
    ...
```

### Implementation order

This PR depends on:

1. **The harness PR's `_files` mechanism** — needed for emitting
   the per-stack render targets.
2. **The harness PR's orphan-scan path** — this PR plugs in two
   path patterns.

It does **not** depend on the secrets PR; the two are
interchangeable in landing order once harness is in.

## Follow-ups to track

1. **Layout-aware nested `AGENTS.md`.** When/if we add an explicit
   `--layout nextjs:web` flag, the generator can emit
   `web/AGENTS.md` per the [agents.md](https://agents.md/) spec.
2. **Codex / Gemini-native skill formats.** Today, the
   stack-specific detail page has two render targets
   (`docs/agents/<stack>.md` and `.claude/skills/sunaba-<stack>/`).
   When Codex CLI or Gemini CLI ship their own equivalent of
   "discoverable skills," add the corresponding render target.
3. **Stack content quality.** Each stack's `summary.md`, `tools.md`,
   and `guidance.md` are seed templates. Ratchet rules earn their
   place; iterate them as agent failures expose specifics.

## Sources

- [agents.md spec](https://agents.md/) — root + nested AGENTS.md
  hierarchy.
- [HumanLayer — *Skill Issue: Harness Engineering for Coding
  Agents*](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents)
  — keep `AGENTS.md` ≤60 lines, ratchet pattern.
- [HumanLayer — *Writing a good CLAUDE.md*](https://www.humanlayer.dev/blog/writing-a-good-claude-md).
- [Anthropic — Equipping agents for the real world with Agent
  Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).
- [Claude Code Skills docs](https://docs.claude.com/en/docs/claude-code/skills)
  — three-level progressive disclosure.
- [`.cursorrules` vs `CLAUDE.md` vs `AGENTS.md` (2026)](https://thepromptshelf.dev/blog/cursorrules-vs-claude-md/).
- Prior internal docs:
  [`2026-05-09-harness-engineering/05-proposal.md`](../2026-05-09-harness-engineering/05-proposal.md),
  [`2026-05-09-secrets-management/05-proposal.md`](../2026-05-09-secrets-management/05-proposal.md).
