# 05 — Proposal

> Synthesized from the research notes and the two independent reviews
> ([`04a-gemini-review.md`](04a-gemini-review.md),
> [`04b-codex-review.md`](04b-codex-review.md)).
> Status: **draft for PR review**. Not implemented yet.

## TL;DR

1. Introduce **`--stack harness`** as a new opt-in stack.
2. Extend stack JSONs with a `_files` mechanism so a stack can emit
   arbitrary files (outside the existing devcontainer deep-merge).
3. Ship Claude-Code-shaped harness scaffolding under that stack:
   `.claude/settings.json` (permissions + Stop hook),
   `.claude/hooks/verify.sh` (silent-success / verbose-failure),
   `.claude/skills/{impact-map,verify-change}/SKILL.md`,
   `.claude/agents/{planner,reviewer,verifier}.md`,
   a 60-line ratchet `AGENTS.md`,
   and a `claudedocs/` trace directory.
4. **Defer** MCP-always-on slimming to a separate PR with a deprecation
   cycle.
5. **Defer** runtime telemetry / evals — sunaba is a generator, not a
   runtime.

## Maturity score (consensus across both reviewers)

| Axis | Score | Notes |
|---|---:|---|
| System prompt | 2/5 | Generic. No ratchet content. No per-stack rules. |
| Tools | 3/5 | MCP wired; no tool budget; always-on. |
| Context | 2/5 | `skills.md` is flat, not progressive-disclosure. |
| Sub-agents | 1/5 | No operational templates. |
| Feedback sensors | 1/5 | No hooks in the generated project. |
| Permissions | 1/5 | No allow / deny defaults → approval fatigue. |
| Evals | 1/5 | No structural harness regression tests. |
| Observability | 1/5 | No `claudedocs/`, no trace location. |

Both reviewers landed within ±1 on every axis. The picture is consistent:
the **sandbox** layer is solid, the **harness** layer is empty.

## Where the reviewers disagreed

We had two genuine disagreements. Recording our position so future
contributors can re-open the question if facts change.

### Disagreement 1 — `--stack harness` or bake into `base/`?

- **Codex:** introduce `--stack harness`. Cleanest fit with the project's
  stated "opt-in, templates only, no backwards-incompatible churn"
  constraints.
- **Gemini:** bake harness into `base/`. Argues the harness *is* the
  product; opt-in creates "a false dichotomy where the default path is
  merely a Docker wrapper."

**Decision: stack.** Three reasons:

1. **Honest constraints win.** The project README explicitly promises no
   surprises on `sunaba sync` / `sunaba rebuild`. Baking changes into
   `base/` would change behavior for every existing user on next sync.
2. **Hooks change agent semantics.** A Claude Code Stop hook isn't free
   context — it changes how every session ends. That has to be opt-in.
3. **The composability argument cuts both ways.** Once `_files` is in
   place, **the harness stack is the canonical example** of how to write
   an editable, PR-reviewable templated artifact. We can move pieces into
   `base/` later if data shows users always opt in.

### Disagreement 2 — slim MCP now, or later?

- **Codex:** slim MCP later, separate PR, with deprecation cycle. Bundling
  it with the first harness PR risks angry users.
- **Gemini:** slim MCP now — move Playwright/Chrome DevTools/NotebookLM
  out of `base/mcp.json` and into the stacks that need them.

**Decision: later.** Both reviewers want the same end state. We do it as
a follow-up PR so harness can land without a "you broke my Playwright"
support thread. We track the deprecation in the harness PR's "follow-ups"
section.

### Disagreement 3 — `claudedocs/` in scaffold or skip?

- **Codex:** include `claudedocs/README.md` + `claudedocs/traces/.gitkeep`.
  It is the trace location; without it, ratchet rules can't be earned.
- **Gemini:** skip. Sunaba is for *disposable* sandboxes. Eval scaffolding
  belongs in the user's host repo.

**Decision: include the directory, but only as a stub.** A README and a
`.gitkeep`. No eval framework, no telemetry. This is the minimum
necessary to make the ratchet pattern executable: a place to drop a note
when the agent fails. Gemini's concern is about **bloat**, and a stub
README + empty directory does not bloat.

## What we add

### 1. Stack file-emission mechanism (`_files`)

`stacks/<name>.json` may declare a `_files` map of
**destination → source-relative-to-templates/**:

```json
{
  "_files": {
    ".claude/settings.json": "harness/claude/settings.json",
    "claudedocs/README.md":  "harness/claudedocs/README.md"
  }
}
```

Implemented in `cli.py::_build_config_files()`. After the devcontainer
deep-merge, walk the chosen stacks' `_files` (in stack order; later wins
on collision), and for each pair:

- Resolve the source under `TEMPLATES_DIR / <source>`.
- Resolve the destination via the existing `_safe_target(...)` path-safety
  helper (rejects `..`, absolute paths, symlinks).
- Add `{relpath: source.read_text()}` to the `files` dict so the existing
  write/diff machinery handles it uniformly.

This stays inside the project's existing path-safety contract. No new
attack surface.

### 2. New stack: `harness`

`templates/stacks/harness.json`:

```json
{
  "_description": "Claude Code-oriented harness: permissions, hooks, skills, sub-agent roles, ratchet AGENTS.md, and a claudedocs trace directory. Opt-in because it changes agent behavior.",
  "_files": {
    ".claude/settings.json":                       "harness/claude/settings.json",
    ".claude/hooks/verify.sh":                     "harness/claude/hooks/verify.sh",
    ".claude/skills/impact-map/SKILL.md":          "harness/claude/skills/impact-map/SKILL.md",
    ".claude/skills/verify-change/SKILL.md":       "harness/claude/skills/verify-change/SKILL.md",
    ".claude/agents/planner.md":                   "harness/claude/agents/planner.md",
    ".claude/agents/reviewer.md":                  "harness/claude/agents/reviewer.md",
    ".claude/agents/verifier.md":                  "harness/claude/agents/verifier.md",
    "AGENTS.md":                                   "harness/AGENTS.md",
    "claudedocs/README.md":                        "harness/claudedocs/README.md",
    "claudedocs/traces/.gitkeep":                  "harness/claudedocs/traces/.gitkeep"
  }
}
```

The `harness` stack contributes nothing to the devcontainer JSON. It only
emits files. (`compose()` returns `base + harness` unchanged because the
overlay has no devcontainer keys to merge.)

### 3. Templates under `templates/harness/`

Drop the actual scaffolds here. Snippets below are the contents to ship —
with the explicit understanding that **users will edit them**. They are
seed templates, not commandments.

#### `templates/harness/claude/settings.json`

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git branch:*)",
      "Bash(rg:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(uv run pytest:*)",
      "Bash(uv run ruff:*)",
      "Bash(npm test:*)",
      "Bash(npm run lint:*)",
      "Bash(npm run typecheck:*)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)",
      "Bash(sudo:*)"
    ]
  },
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/verify.sh" }
        ]
      }
    ]
  }
}
```

#### `templates/harness/claude/hooks/verify.sh`

```bash
#!/usr/bin/env bash
# Silent on success, verbose on failure. Exit 2 to re-engage the agent.
set -euo pipefail

fail=0
out="$(mktemp)"
trap 'rm -f "$out"' EXIT

check() {
  local label="$1"; shift
  if ! "$@" >"$out" 2>&1; then
    echo "❌ $label" >&2
    cat "$out" >&2
    fail=1
  fi
}

if [ -f pyproject.toml ]; then
  command -v uv >/dev/null && check "uv pytest" uv run pytest -q
fi

if [ -f package.json ]; then
  npm run lint --if-present >/dev/null 2>&1 || \
    check "npm run lint" npm run lint --if-present
  npm run typecheck --if-present >/dev/null 2>&1 || \
    check "npm run typecheck" npm run typecheck --if-present
  npm test --if-present >/dev/null 2>&1 || \
    check "npm test" npm test --if-present
fi

[ "$fail" -eq 0 ] || exit 2
```

(Yes, the double-call pattern wastes one run on success. The point is
*output* discipline — the agent only sees text on failure. If we want to
optimize later, we can buffer stdout and only emit on non-zero.)

#### `templates/harness/AGENTS.md`

```md
# AGENTS.md

These rules apply to any agent (Claude Code, Codex, Gemini CLI) operating
inside this repository. Keep this file under 60 lines.

## Operating rules

- Read the task, `git status`, and the smallest relevant files before
  proposing changes.
- Prefer repo-local scripts and existing CLIs over ad-hoc shell pipelines.
- Do not add a new dependency unless the task requires it and the
  trade-off is recorded.
- When a check fails, fix the cause or record the blocker in
  `claudedocs/traces/`. Do not mark work complete with failing checks.
- Keep changes scoped to the requested behavior.

## Ratchet log

Every rule below traces to a specific past failure or hard external
constraint. If a rule no longer earns its place, delete it.

- Do not overwrite generated secrets, `.env`, or user-local auth state.
  *Reason:* sunaba sandboxes mount persistent CLI credentials in named
  volumes; clobbering them logs the user out of every IDE session.
- Do not edit unrelated files while regenerating harness artifacts.
  *Reason:* `sunaba rebuild` users may have local modifications.
- When a Stop hook reports failure, treat the failure verbatim — do not
  paraphrase it or mark the task done.
  *Reason:* the hook's whole point is to be the source of truth.
```

(Three rules to start. We add new entries when an agent failure earns
them.)

#### `templates/harness/claude/skills/impact-map/SKILL.md`

```md
# impact-map

Use **before implementation** when the requested change touches code you
have not edited in this session.

## Output

- Files likely to change.
- Existing symbols / scripts to reuse.
- Risks and unknowns.
- A short checkpoint for human review.

Do not edit files in this skill. Return only the map.
```

#### `templates/harness/claude/skills/verify-change/SKILL.md`

```md
# verify-change

Use **after implementation, before final response.**

## Steps

1. Inspect `git diff --stat` and `git diff`.
2. Run the smallest relevant checks (typecheck, lint, the touched test
   file).
3. Report failures with exact command output, not paraphrased.
4. Record unresolved risk in `claudedocs/traces/<short-name>.md` only
   when it is genuinely useful for future sessions.
```

#### `templates/harness/claude/agents/planner.md`

```md
# planner

You produce repository-grounded plans only.

- Read code before proposing files.
- Return an impact map, assumptions, and acceptance criteria.
- Do not edit files.
- Keep output short. Cite paths in `path:line` form.
```

#### `templates/harness/claude/agents/reviewer.md`

```md
# reviewer

You review diffs for bugs, regressions, missing tests, and harness drift.

- Findings first, ordered by severity.
- Cite file paths and line numbers.
- Do not rewrite the implementation unless explicitly asked.
```

#### `templates/harness/claude/agents/verifier.md`

```md
# verifier

You run checks and summarize evidence.

- Prefer existing project commands.
- Success: concise.
- Failure: include the exact failing command and an actionable next step.
```

#### `templates/harness/claudedocs/README.md`

```md
# claudedocs

Repository-local notes that the agent can see.

- `decisions/` — durable design decisions (one per file, dated).
- `traces/` — short failure notes. When a rule earns its way into
  `AGENTS.md`'s ratchet log, the trace can be deleted or kept as
  history.

This directory is part of the harness — review changes here in PRs.
```

#### `templates/harness/claudedocs/traces/.gitkeep`

Empty file. Preserves the directory in git.

## What sunaba's main code has to change

- `cli.py::_build_config_files()` — read each chosen stack's `_files`
  map; resolve sources and destinations; add to the `files` dict.
- `compose.py::deep_merge` — unchanged.
- `_clean_devcontainer()` — already strips keys starting with `_`, so
  `_files` won't leak into the emitted `devcontainer.json`.
- `sync.py::copy_agent_files` — unchanged for now. We do not include the
  harness stack's files in `sync` until the design has shipped at least
  once and we know what users keep editing locally.
- `tests/test_smoke.py` — add the structural tests in section D.

## Tests (structural, not behavioral)

```python
def test_harness_stack_listed():
    assert "harness" in available_stacks()

def test_harness_does_not_leak_into_devcontainer():
    files = _build_config_files("p", ["harness"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    assert "_files" not in dc

def test_harness_emits_expected_paths():
    files = _build_config_files("p", ["harness"])
    expected = {
        ".claude/settings.json",
        ".claude/hooks/verify.sh",
        ".claude/skills/impact-map/SKILL.md",
        ".claude/skills/verify-change/SKILL.md",
        ".claude/agents/planner.md",
        ".claude/agents/reviewer.md",
        ".claude/agents/verifier.md",
        "AGENTS.md",
        "claudedocs/README.md",
        "claudedocs/traces/.gitkeep",
    }
    assert expected.issubset(files.keys())

def test_harness_settings_json_is_valid():
    files = _build_config_files("p", ["harness"])
    settings = json.loads(files[".claude/settings.json"])
    assert "permissions" in settings
    assert "allow" in settings["permissions"]
    assert "deny" in settings["permissions"]
    assert "hooks" in settings

def test_harness_agents_md_is_short():
    files = _build_config_files("p", ["harness"])
    assert len(files["AGENTS.md"].splitlines()) <= 60

def test_harness_verify_script_is_syntactically_valid(tmp_path):
    files = _build_config_files("p", ["harness"])
    script = tmp_path / "verify.sh"
    script.write_text(files[".claude/hooks/verify.sh"])
    subprocess.run(["bash", "-n", str(script)], check=True)

def test_harness_idempotent_regeneration():
    a = _build_config_files("p", ["python", "harness"])
    b = _build_config_files("p", ["python", "harness"])
    assert a == b

def test_harness_files_path_safety(tmp_path):
    # _files cannot point outside the project root.
    bad = {".claude/../escape.txt": "harness/claude/settings.json"}
    with pytest.raises(ValueError):
        _safe_target(tmp_path, "../escape.txt")

def test_no_devcontainer_keeps_harness_files():
    files = _build_config_files(
        "p", ["python", "harness"], no_devcontainer=True
    )
    assert ".devcontainer/devcontainer.json" not in files
    assert ".claude/settings.json" in files
```

## README updates

`README.md`:

```diff
 | `playwright` | Chromium + Linux deps for Playwright / Chrome DevTools MCP (E2E browser automation) |
+| `harness`    | Claude Code-oriented harness: permissions, Stop hook, on-demand skills, sub-agent role files, a 60-line ratchet `AGENTS.md`, and a `claudedocs/` trace directory. **Opt-in because it changes agent behavior.** |
```

In the "What sunaba does NOT protect you from" section:

```diff
+- **`--stack harness`**: ships a Claude Code Stop hook that runs
+  `bash .claude/hooks/verify.sh` after every agent session. The hook is
+  a template — review it like code. It can run any local command. The
+  permissions list reduces approval prompts for routine tools, but it
+  is **not** a security boundary.
```

`README.ja.md`: same wording, translated.

## What we explicitly do **not** do in this PR

- **Don't slim `base/mcp.json`.** Track as a follow-up. Both reviewers
  agree this should happen, just not in the same PR.
- **Don't add `_agents_md` per-stack composition** (Gemini's idea). Good
  idea, but it requires deciding *what each existing stack contributes*,
  which is a content debate of its own. Defer.
- **Don't auto-generate `AGENTS.md` per-project.** HumanLayer's evidence:
  auto-generated agentfiles cost tokens and hurt agent performance. The
  shipped one is a *seed*, not a generator output.
- **Don't add runtime telemetry / evals / `evals/` directory.** Sunaba is
  a generator. The user can add evals in their own repo.
- **Don't change `sunaba sync`.** It still copies the four canonical
  agent files from `templates/agents/`. Harness files only land via
  `sunaba new --stack harness` or `sunaba rebuild --add harness`.

## Rebuild consistency

> Added 2026-05-09 in response to: *"are inconsistencies on
> `sunaba rebuild` considered?"*
> The original proposal addressed `rebuild --add harness` but did not
> address `--remove harness` or `_files` collisions across stacks.

### `rebuild --remove harness` leaves orphans

`_diff_files()` only inspects files in the *new* compose. Files that
were emitted by a previous stack selection are not detected, not
diffed, and not removed. So:

```bash
sunaba rebuild myapp --remove harness
```

leaves `.claude/settings.json`, `.claude/hooks/verify.sh`,
`.claude/skills/*`, `.claude/agents/*`, `claudedocs/` etc. **on disk**
even though they no longer correspond to any selected stack. The
project's `AGENTS.md` is also left untouched (because we said `sync`
doesn't compose), which is consistent but contributes to drift.

**Decision: don't auto-delete. Report and instruct.**

Three reasons:

1. **Users edit these files.** `.claude/settings.json` is exactly the
   thing the harness PR's "templates only — users own them" framing
   says we shouldn't auto-mutate.
2. **Removing files on `rebuild` is a new destructive operation.**
   `rebuild` today only writes; introducing deletes raises the blast
   radius materially.
3. **The harness PR's stated philosophy is "treat the harness as
   code."** Code that the user keeps owning, including across
   stack-list changes.

Concrete behavior on `rebuild --remove harness`:

- The command runs as today; agent files / mcp / devcontainer
  regenerate without harness contributions.
- After the rewrite, `cli.py` walks the now-orphan paths
  (`.claude/`, `claudedocs/` for the harness case) and lists them
  to the user with a clear message:

  ```
  Stack 'harness' was removed. The following files are no longer
  managed by any selected stack and were left in place:
    .claude/settings.json
    .claude/hooks/verify.sh
    .claude/skills/impact-map/SKILL.md
    ...
  Delete them with:  rm -r .claude claudedocs
  Or restore the stack with:  sunaba rebuild myapp --add harness
  ```

- A future `sunaba doctor` (already a follow-up) is the right place
  to formalize this scan.

### `_files` collision rules

If two stacks declare the same destination key in `_files`, the
behavior must be deterministic.

**Decision: stack ordering wins; later stack overwrites earlier.**

Rationale:

- `--stack` flag order is already the source of truth for
  ordering elsewhere (devcontainer composition, fragment
  concatenation in the stack-aware-agent-files PR).
- "Later wins" is the same convention as the deep-merge composer's
  scalar-overwrite rule.
- We add a structural test that exercises the rule:

  ```python
  def test_files_collision_later_stack_wins():
      # If two synthetic stacks declared the same _files target,
      # the second one in the --stack order must be the resulting
      # content.
      ...
  ```

  Today no two real stacks collide. We still want the rule pinned.

### Implementation order

This PR (`harness`) introduces the `_files` mechanism. The
secrets-management, stack-aware-agent-files, and rules-and-autonomy
PRs all depend on it. Land harness first; the other three are
interchangeable after that. The full canonical ordering across all
four proposals lives in
[`thinking/README.md`](../README.md#implementation-order).

## Follow-ups to track

1. MCP slimming: move Playwright / Chrome DevTools / NotebookLM out of
   `base/` and into the stacks that need them. Deprecation cycle: warn
   in next minor, slim in next major.
2. Per-stack `_agents_md` composition (Gemini's suggestion).
3. Once we have data on what users edit in their `harness` files, decide
   whether some pieces graduate into `base/`.
4. Gemini and Codex CLI both have their own home for skills /
   instructions. Today the harness stack is Claude-Code-shaped. Add
   parallel `templates/harness/codex/` and `templates/harness/gemini/`
   trees once the formats stabilize.

## Sources

- OpenAI — *Harness engineering: leveraging Codex in an agent-first world*
  — <https://openai.com/index/harness-engineering/>
- Martin Fowler — *Harness engineering for coding agent users* —
  <https://martinfowler.com/articles/harness-engineering.html>
- HumanLayer — *Skill Issue: Harness Engineering for Coding Agents* —
  <https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents>
- Addy Osmani — *Agent Harness Engineering* —
  <https://addyosmani.com/blog/agent-harness-engineering/>
- Red Hat — *Harness engineering: structured workflows for AI-assisted
  development* —
  <https://developers.redhat.com/articles/2026/04/07/harness-engineering-structured-workflows-ai-assisted-development>
- `ai-boost/awesome-harness-engineering` —
  <https://github.com/ai-boost/awesome-harness-engineering>
