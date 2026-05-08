# 05 — Proposal

> Synthesized from research notes and the two independent reviews
> ([`04a-gemini-review.md`](04a-gemini-review.md),
> [`04b-codex-review.md`](04b-codex-review.md)).
> Status: **draft for PR review**. Not implemented yet.

## TL;DR

We adopt **two stacks** with **multi-target rule rendering** and a
**structured Ralph Loop**:

1. **`--stack rules`** — low-risk context improvement. Ships the
   canonical `templates/rules/<name>.rule.md` source, the renderer,
   and seed rule files. No behavior change at runtime.
2. **`--stack autopilot`** — opt-in autonomous environment.
   Recommends (but doesn't force) `rules` and `harness` together.
   Ships the structured verify hook, budget cap, branch protection,
   subagent dispatch protocol, checkpoint primitives.

A canonical rule format under `templates/rules/<name>.rule.md`
renders to **four targets**:

- `.cursor/rules/<name>.mdc` (Cursor — `globs` / `alwaysApply`).
- `.claude/rules/<name>.md` (Claude Code — `paths:`).
- Hierarchical `AGENTS.md` (Codex CLI — closest-wins).
- Hierarchical `GEMINI.md` (Gemini CLI — closest-wins; honest gap
  on glob scoping).

Subagents get **first-class templates for both Claude and Codex**.
Gemini remains the honest gap, documented but not simulated.

## Maturity score (consensus)

| Axis | Score | Notes |
|---|---:|---|
| Rules | 2/5 | No glob scoping today; `AGENTS.md` is flat. |
| Subagents | 2–3/5 | Role files exist; no operational dispatch protocol. Codex CLI's native subagent surface is unused. |
| Autonomous loop | 2/5 | Stop hook returns non-zero; re-engage / budget undefined. |
| Branch / repo protection | 2/5 | `permissions.deny --force` only. |
| Cross-agent fairness | 2–3/5 | Claude and (correction) Codex CLI are both reachable; Gemini honest gap. |

## Where the reviewers disagreed

Three substantive disagreements. Recording our position so future
contributors can re-open.

### Disagreement 1 — One stack or two?

- **Gemini.** One — `--stack autopilot` covers rules + autonomy.
  *"Rules without an autonomous loop are just hints; an
  autonomous loop without scoped rules is a loose cannon."*
- **Codex.** Two — `--stack rules` and `--stack autopilot`.
  Different opt-in boundaries: rules is low-risk context
  improvement; autopilot changes runtime behavior.

**Decision: two stacks, with a documented "you usually want both."**

Reasons:

1. **Opt-in boundary fidelity.** A user who wants better in-context
   guidance should not have to also accept Stop-hook re-engage and
   budget caps as the same opt-in.
2. **Composability.** The user who pairs them gets both. The
   README's recommended invocation:
   `--stack harness --stack rules --stack autopilot`.
3. **Replaceability.** If the rule format converges to a single
   industry standard later, swapping `rules` is easier than
   carving it out of a combined `autopilot`.

### Disagreement 2 — Cross-agent fairness for autonomy

- **Gemini.** Drop the pretense. *"Stop pretending we can make
  Gemini and Codex CLI do Auto Mode right now. Ship as
  Claude-Code-and-Cursor first."*
- **Codex.** Factual correction — Codex CLI as of May 2026
  ships native `.codex/agents/*.toml` subagents, hooks, rules,
  and `codex exec --sandbox workspace-write`. Codex CLI deserves
  **first-class** templates. Gemini is the only honest gap.

**Decision: Codex's correction is right.** We verified the citations
([Codex subagents](https://developers.openai.com/codex/subagents),
[Codex hooks](https://developers.openai.com/codex/hooks),
[Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md)).

The autopilot stack ships first-class templates for Claude **and**
Codex CLI. Gemini gets:

- Hierarchical `GEMINI.md` for rule mirroring (where the glob can
  map cleanly to a directory).
- `docs/agents/gemini-autopilot-limitations.md` documenting why no
  Stop-loop / no glob-scoped rules / no native subagents.
- A clearly labeled "manual protocol" path.

### Disagreement 3 — Verifier as bash or LLM?

- **Gemini.** *"The verifier MUST be a deterministic bash script.
  Using an LLM to verify an LLM's code is an ouroboros of
  hallucination."*
- **Codex.** Doesn't take a strong position; describes the
  verifier as "runs checks **and compares against the plan's
  acceptance criteria**" — implying both bash and judgment.

**Decision: deterministic at the bottom, LLM-shaped at the top.**

The bottom layer (`verify.sh`) is a deterministic bash script —
typecheck, lint, tests, exit code. Period. The verifier *role
file* (`.claude/agents/verifier.md`) describes how to interpret
that exit code, where to read the failure log, and how to compare
against `claudedocs/plans/<slug>.md`. The role file is *not* what
decides "did the code pass" — `verify.sh` decides that. The role
file decides *what to do next*.

This satisfies Gemini's "no ouroboros" and Codex's "compare against
acceptance criteria" simultaneously.

### Other consensus

- **Multi-target rule render.** Both agree.
- **Structured failure output.** Both agree (we use Codex's
  format — it's more concrete).
- **Budget cap.** Both want one. Gemini argues for iteration count
  only; Codex wants iteration *and* wall-clock. We take both
  (cheap to implement, more robust).
- **Branch protection via git hook + permission deny.** Both
  agree.
- **Drop "fairness shim" for Gemini autonomy.** Both agree —
  manual protocol, no simulated subagents.

## What we add

### 1. New stack: `--stack rules`

`templates/stacks/rules.json`:

```json
{
  "_description": "Path-scoped rule files rendered to .cursor/rules, .claude/rules, AGENTS.md hierarchy, GEMINI.md hierarchy. Low-risk context improvement; no runtime behavior change.",
  "_files": {},
  "_rules": [
    "templates/rules/python-tests.rule.md",
    "templates/rules/nextjs-api.rule.md",
    "templates/rules/agent-handoff.rule.md"
  ]
}
```

The `_rules` key is new — it lists the rule sources that the
renderer should process. The harness PR's `_files` mechanism is
not enough on its own because each rule produces multiple output
files.

### 2. Canonical rule format

`templates/rules/python-tests.rule.md`:

```md
---
name: python-tests
description: Python tests use pytest fixtures, not unittest classes.
globs:
  - "tests/**/*.py"
alwaysApply: false
targets:
  - claude
  - cursor
  - codex
  - gemini
---

# Python test rules

- Use pytest fixtures.
- Do not introduce `unittest.TestCase`.
- Prefer `uv run pytest -q`.
- Test files mirror source: `src/foo/bar.py` → `tests/foo/test_bar.py`.
```

### 3. Renderer

New helper `_render_rules(rules: list[Path]) -> dict[str, str]`
in `cli.py`. Logic:

1. For each rule source: parse YAML frontmatter + body.
2. **Claude target.** Output to `.claude/rules/<name>.md` with
   frontmatter rewritten to use `paths:` instead of `globs:`.
3. **Cursor target.** Output to `.cursor/rules/<name>.mdc` with
   frontmatter intact (`globs:`, `alwaysApply:`).
4. **Codex target.** Try to map globs to a single directory
   prefix. If clean, append a stable section to that directory's
   `AGENTS.md` between markers:
   ```md
   <!-- SUNABA RULE: python-tests START -->
   ...body...
   <!-- SUNABA RULE: python-tests END -->
   ```
   If not clean (e.g. globs span multiple directories), write
   `docs/agents/rules/<name>.md` and append a one-line index to
   the root `AGENTS.md`'s rule index.
5. **Gemini target.** Same as Codex but writes to `GEMINI.md` /
   `docs/agents/rules/`. Only the directory mapping case
   produces a hierarchy file — Gemini has no glob support.

Idempotent. Marker-based replacement so re-runs don't duplicate.
Path-safety via the harness PR's `_safe_target()`.

### 4. New stack: `--stack autopilot`

`templates/stacks/autopilot.json`:

```json
{
  "_description": "Opt-in autonomous environment: structured Stop-hook re-engage with budget caps, branch protection, subagent dispatch protocol, checkpoints. Recommends --stack harness and --stack rules.",
  "_files": {
    ".claude/hooks/verify.sh":                    "autopilot/claude/hooks/verify.sh",
    ".claude/agents/planner.md":                  "autopilot/claude/agents/planner.md",
    ".claude/agents/reviewer.md":                 "autopilot/claude/agents/reviewer.md",
    ".claude/agents/verifier.md":                 "autopilot/claude/agents/verifier.md",
    ".codex/config.toml":                         "autopilot/codex/config.toml",
    ".codex/agents/planner.toml":                 "autopilot/codex/agents/planner.toml",
    ".codex/agents/reviewer.toml":                "autopilot/codex/agents/reviewer.toml",
    ".codex/agents/verifier.toml":                "autopilot/codex/agents/verifier.toml",
    ".codex/hooks/verify.sh":                     "autopilot/codex/hooks/verify.sh",
    ".githooks/pre-push":                         "autopilot/githooks/pre-push",
    "scripts/install-githooks.sh":                "autopilot/scripts/install-githooks.sh",
    "claudedocs/plans/.gitkeep":                  "autopilot/claudedocs/plans/.gitkeep",
    "claudedocs/checkpoints/.gitkeep":            "autopilot/claudedocs/checkpoints/.gitkeep",
    "docs/agents/subagent-dispatch.md":           "autopilot/docs/subagent-dispatch.md",
    "docs/agents/gemini-autopilot-limitations.md":"autopilot/docs/gemini-autopilot-limitations.md",
    ".sunaba/autopilot/.gitignore":               "autopilot/state/.gitignore"
  },
  "_bootstrap": [
    "# --- autopilot ---",
    "# Wire up the pre-push hook (idempotent).",
    "if [ -f scripts/install-githooks.sh ]; then bash scripts/install-githooks.sh || true; fi"
  ]
}
```

Note that the harness PR overrides
`.claude/agents/{planner,reviewer,verifier}.md`. Stack ordering
("later wins" per the harness PR's collision rule) means the
**user must declare `--stack harness --stack autopilot` in that
order** — the autopilot versions overwrite the harness role files
because they carry the operational protocol the harness role
templates didn't have.

We document this ordering requirement explicitly in the autopilot
README entry.

### 5. Structured `verify.sh`

`templates/autopilot/claude/hooks/verify.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail

STATE=".sunaba/autopilot"
mkdir -p "$STATE"

# Budget defaults (overridable via env)
: "${SUNABA_AUTOPILOT_MAX_ITERS:=5}"
: "${SUNABA_AUTOPILOT_MAX_MINUTES:=30}"
: "${SUNABA_AUTOPILOT_MAX_CHANGED_FILES:=25}"

ITER_FILE="$STATE/iteration"
START_FILE="$STATE/run-start"
LOG="$STATE/last-failure.log"
: > "$LOG"

# Initialize on first iteration
if [ ! -f "$ITER_FILE" ]; then
  echo 0 > "$ITER_FILE"
  date +%s > "$START_FILE"
fi

iter=$(cat "$ITER_FILE")
iter=$((iter + 1))
echo "$iter" > "$ITER_FILE"

start=$(cat "$START_FILE")
now=$(date +%s)
elapsed_min=$(( (now - start) / 60 ))

run() {
  local label="$1"; shift
  local out
  if ! out=$("$@" 2>&1); then
    {
      echo "------ $label ------"
      echo "$out"
    } >> "$LOG"
    return 1
  fi
  return 0
}

failed=0

# File-based stack detection — silent skip on missing files
if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
  run "uv run pytest -q" uv run pytest -q || failed=1
fi
if [ -f package.json ]; then
  run "npm run lint" sh -c 'npm run lint --if-present 2>&1' || failed=1
  run "npm run typecheck" sh -c 'npm run typecheck --if-present 2>&1' || failed=1
  run "npm test" sh -c 'npm test --if-present 2>&1' || failed=1
fi

# Changed-file budget
if command -v git >/dev/null 2>&1 && git rev-parse HEAD >/dev/null 2>&1; then
  changed=$(git diff --name-only HEAD | wc -l | tr -d ' ')
  if [ "$changed" -gt "$SUNABA_AUTOPILOT_MAX_CHANGED_FILES" ]; then
    cat <<EOF >&2
SUNABA_BUDGET_EXCEEDED kind=changed-files iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES changed_files=$changed/$SUNABA_AUTOPILOT_MAX_CHANGED_FILES next_action=Stop autonomous loop. Human review required for the size of this change.
EOF
    rm -f "$ITER_FILE" "$START_FILE"
    exit 1
  fi
fi

if [ "$failed" -eq 0 ]; then
  rm -f "$ITER_FILE" "$START_FILE"
  exit 0
fi

# Failure path: structured stderr
if [ "$iter" -ge "$SUNABA_AUTOPILOT_MAX_ITERS" ] \
   || [ "$elapsed_min" -ge "$SUNABA_AUTOPILOT_MAX_MINUTES" ]; then
  cat <<EOF >&2
SUNABA_BUDGET_EXCEEDED kind=iteration-or-time iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES failure_log=$LOG next_action=Stop autonomous loop. Human review required.
EOF
  rm -f "$ITER_FILE" "$START_FILE"
  exit 1
fi

cat <<EOF >&2
SUNABA_VERIFY_FAILED iteration=$iter/$SUNABA_AUTOPILOT_MAX_ITERS elapsed_minutes=$elapsed_min/$SUNABA_AUTOPILOT_MAX_MINUTES failure_log=$LOG next_action=Read $LOG, propose a fix that addresses the failing checks specifically. Do not summarize.
EOF
exit 2
```

The Codex hook (`.codex/hooks/verify.sh`) is identical except for
where it reads the iteration file — Codex hooks have their own
spec for state passing, so the file paths under `.sunaba/` are
shared but the entry points are separate.

### 6. Subagent role files (operational, not roleplay)

`templates/autopilot/claude/agents/planner.md`:

```md
---
name: planner
description: Repository-grounded planner. Dispatched when the orchestrator detects a task touching 3+ files, unknown code, schema/API/auth/secrets/infra changes, or when the user explicitly asks for a plan.
---

# planner

Read the task, the smallest relevant files, `git status`, and any
existing `claudedocs/plans/` entries that look related.

Write a plan to `claudedocs/plans/<YYYY-MM-DD>-<slug>.md` with:

- **Goal.** One sentence.
- **Scope.** Files to touch (paths). Files NOT to touch (paths).
- **Acceptance criteria.** Concrete shell commands the verifier
  will run, with expected outcomes.
- **Risks.** Things that could go wrong; how to roll back.

Do not edit code in this dispatch. Return the plan path.
```

`templates/autopilot/claude/agents/reviewer.md`:

```md
---
name: reviewer
description: Diff reviewer. Dispatched after the implementer finishes a slice and BEFORE the verifier runs. Reads the diff for taste, regressions, missing tests, and plan adherence. Cites paths and lines.
---

# reviewer

Read `git diff`. Compare against the most recent
`claudedocs/plans/<...>.md`.

Report findings ordered by severity:

- 🛑 *Blocker* — likely regression, missing test, plan deviation
  the user did not authorize.
- ⚠ *Concern* — taste / maintainability / scope creep.
- ✅ *Note* — non-blocking observations.

Cite paths in `path:line` form. Do not rewrite the
implementation.
```

`templates/autopilot/claude/agents/verifier.md`:

```md
---
name: verifier
description: Mechanical verifier. Invokes `.claude/hooks/verify.sh` and parses its structured output. Compares against the plan's Acceptance Criteria. Does NOT review for taste.
---

# verifier

Invoke `.claude/hooks/verify.sh`. Read its exit code and the
structured stderr.

- **Exit 0.** All checks passed. Compare against the plan's
  Acceptance Criteria. If criteria match, signal done. If not,
  request a clarification.
- **Exit 2 (`SUNABA_VERIFY_FAILED`).** Read
  `.sunaba/autopilot/last-failure.log`. Surface the specific
  failing command. Do NOT propose a fix here — the orchestrator
  will dispatch the implementer.
- **Exit 1 (`SUNABA_BUDGET_EXCEEDED`).** Stop. Hand off to
  human review.
```

The Codex versions live under `.codex/agents/*.toml` with
equivalent semantics. The TOML format is set by Codex CLI:

```toml
# templates/autopilot/codex/agents/verifier.toml
name = "verifier"
description = "Invokes .codex/hooks/verify.sh and parses structured output. Compares against the plan's Acceptance Criteria."

instructions = """
Invoke .codex/hooks/verify.sh. Read its exit code and stderr.

- Exit 0: all checks passed; compare against plan acceptance criteria.
- Exit 2 (SUNABA_VERIFY_FAILED): read .sunaba/autopilot/last-failure.log; surface the failing command.
- Exit 1 (SUNABA_BUDGET_EXCEEDED): stop; hand off to human review.
"""
```

### 7. Subagent dispatch protocol document

`templates/autopilot/docs/subagent-dispatch.md` is the canonical
operational doc. The agent files reference it; the orchestrator
follows it. (Excerpt — full content in template.)

```md
# Subagent dispatch protocol

The orchestrator decides when to dispatch subagents based on this
flowchart.

## Planner

Dispatch IF any of:
- Task touches >= 3 files.
- Task involves unknown code (the orchestrator hasn't read it yet).
- Task changes a schema / API surface / auth / secrets / infra.
- The user asks for a plan explicitly.

Skip planner for:
- Single-file bug fixes where the failing test already names the
  fix.
- Documentation-only edits.

## Implementer

The orchestrator (or a dedicated subagent) does the edits. Updates
checkpoint after every coherent slice (see "Checkpoints" below).

## Reviewer → Verifier

After the implementer completes a slice:

1. Reviewer reads the diff. If it returns a 🛑 Blocker, hand back
   to the implementer.
2. Verifier runs `verify.sh`. Acts on exit code per the role file.

## Checkpoints

Write to `claudedocs/checkpoints/<slug>.md`:
- after a plan is accepted,
- before a broad edit,
- after each failed verification pass,
- before the final response.
```

### 8. Branch protection

`templates/autopilot/githooks/pre-push`:

```sh
#!/usr/bin/env sh
set -e

protected="refs/heads/main refs/heads/master"

while read -r local_ref local_sha remote_ref remote_sha; do
  for ref in $protected; do
    if [ "$remote_ref" = "$ref" ]; then
      echo "sunaba autopilot: refusing push to $remote_ref" >&2
      echo "Push to a feature branch instead. Override with --no-verify if you really mean it." >&2
      exit 1
    fi
  done
done
```

`templates/autopilot/scripts/install-githooks.sh`:

```sh
#!/usr/bin/env sh
# Wire .githooks/* into Git's hook directory. Idempotent.
set -e
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
```

The `_bootstrap` snippet runs `install-githooks.sh` once after
container creation. Belt-and-braces: also append to the harness
PR's `permissions.deny`:

```diff
 "deny": [
   "Bash(rm -rf:*)",
   "Bash(git push --force:*)",
   "Bash(git push -f:*)",
   "Bash(git reset --hard:*)",
+  "Bash(git push origin main:*)",
+  "Bash(git push origin master:*)",
+  "Bash(git checkout main:*)",
+  "Bash(git checkout master:*)",
   "Bash(sudo:*)"
 ]
```

### 9. Gemini honest-gap doc

`templates/autopilot/docs/gemini-autopilot-limitations.md`:

```md
# Gemini CLI and the autopilot stack

`--stack autopilot` is built around a Stop-hook re-engage loop and
a structured failure protocol. Gemini CLI as of May 2026 does not
provide a Stop hook, glob-scoped path rules, or native subagent
dispatch with separate context windows.

## What works for Gemini in this stack

- Hierarchical `GEMINI.md` files (closest-to-edited-file wins) for
  rules whose globs map cleanly to a directory.
- The structured `verify.sh` script can be invoked manually
  (`bash .claude/hooks/verify.sh`) — Gemini just won't auto
  re-engage on exit 2.
- The pre-push branch protection hook works (it's git-level, not
  agent-level).

## What does not work

- Native autonomous loop. There is no Gemini equivalent of Stop
  exit 2 → re-prompt.
- Glob-scoped rules that don't map to a directory. Those are
  rendered to `docs/agents/rules/<name>.md` for human reference;
  Gemini will read them only if its context happens to find them.
- Sub-agent dispatch with isolated context windows.

## Manual protocol

Treat Gemini as a single-shot agent. Plan, implement, verify, and
review by hand. The role files in `.claude/agents/` and
`.codex/agents/` document the discipline; you can adopt that
discipline on Gemini even though the runtime won't enforce it.
```

## Tests (structural)

```python
def test_rules_stack_listed():
    assert "rules" in available_stacks()
    assert "autopilot" in available_stacks()

def test_canonical_rule_frontmatter_parses():
    src = (TEMPLATES_DIR / "rules" / "python-tests.rule.md").read_text()
    fm, body = _split_frontmatter(src)
    assert fm["name"] == "python-tests"
    assert "tests/**/*.py" in fm["globs"]
    assert "claude" in fm["targets"]

def test_rule_renders_to_all_targets():
    files = _build_config_files("p", ["rules"])
    assert ".claude/rules/python-tests.md" in files
    assert ".cursor/rules/python-tests.mdc" in files
    # Codex/Gemini render either to a hierarchy file or to the docs fallback;
    # either is acceptable but at least one must exist.
    assert any(
        k.endswith("/AGENTS.md") or k == "docs/agents/rules/python-tests.md"
        for k in files
    )

def test_cursor_render_keeps_globs_and_alwaysApply():
    files = _build_config_files("p", ["rules"])
    mdc = files[".cursor/rules/python-tests.mdc"]
    assert "globs:" in mdc
    assert "alwaysApply:" in mdc

def test_claude_render_uses_paths_key():
    files = _build_config_files("p", ["rules"])
    md = files[".claude/rules/python-tests.md"]
    assert "paths:" in md
    assert "globs:" not in md  # rewritten

def test_autopilot_emits_expected_paths():
    files = _build_config_files("p", ["autopilot"])
    expected = {
        ".claude/hooks/verify.sh",
        ".claude/agents/planner.md",
        ".claude/agents/verifier.md",
        ".codex/agents/planner.toml",
        ".codex/agents/verifier.toml",
        ".githooks/pre-push",
        "claudedocs/plans/.gitkeep",
        "claudedocs/checkpoints/.gitkeep",
        "docs/agents/subagent-dispatch.md",
        "docs/agents/gemini-autopilot-limitations.md",
    }
    assert expected.issubset(files.keys())

def test_codex_agent_toml_parses():
    import tomllib
    files = _build_config_files("p", ["autopilot"])
    for k in files:
        if k.startswith(".codex/agents/") and k.endswith(".toml"):
            tomllib.loads(files[k])  # raises on malformed TOML

def test_verify_script_exits_2_on_failure_within_budget(tmp_path):
    # Simulate a failing test command, run verify.sh once, assert exit 2.
    ...

def test_verify_script_exits_1_when_iteration_budget_exceeded(tmp_path):
    # Pre-write iteration file at MAX_ITERS, run verify.sh, assert exit 1
    # and SUNABA_BUDGET_EXCEEDED in stderr.
    ...

def test_verify_script_exits_1_when_changed_files_exceed_budget(tmp_path):
    ...

def test_pre_push_hook_blocks_main(tmp_path):
    # git init in tmp_path, install hook, simulate push to main, assert refusal.
    ...

def test_autopilot_overwrites_harness_role_files_when_after():
    files = _build_config_files("p", ["harness", "autopilot"])
    assert "claudedocs/plans/<YYYY-MM-DD>" in files[".claude/agents/planner.md"]

def test_autopilot_first_does_not_get_operational_planner(tmp_path):
    # Reverse order: harness wins. Document this footgun.
    files = _build_config_files("p", ["autopilot", "harness"])
    assert "claudedocs/plans/<YYYY-MM-DD>" not in files[".claude/agents/planner.md"]

def test_rebuild_remove_autopilot_reports_orphans(tmp_path):
    # Per the rebuild-consistency addendum.
    ...
```

## README + SECURITY updates

`README.md` stack table:

```diff
 | `secrets`    | Secret hygiene scaffold ... |
+| `rules`      | Multi-target path-scoped rule files (Cursor `.mdc`, Claude `.md`, hierarchical `AGENTS.md` / `GEMINI.md`). Low-risk context improvement. |
+| `autopilot`  | Opt-in autonomous environment: structured Stop-hook re-engage with budget caps, branch protection, subagent dispatch protocol, checkpoints. **Changes agent runtime behavior.** Recommends `--stack harness --stack rules --stack autopilot` together, in that order. |
```

`SECURITY.md` — extend the "what sunaba does NOT protect you from"
list:

```diff
+- **`--stack autopilot` is autonomous.** The Stop hook re-engages
+  the agent on verify failure, up to a configured iteration /
+  wall-clock / changed-file budget. The budget caps are *defaults*
+  — the user can lift them by setting `SUNABA_AUTOPILOT_MAX_*`
+  env vars, in which case real money may be spent before a human
+  intervenes. Branch protection (pre-push hook) prevents pushes
+  to `main` / `master`; it does not prevent `git push` to a
+  feature branch on a public remote. Treat the autopilot stack
+  as production-affecting if the project's remote is public.
```

`README.ja.md`: same content, translated.

## What we explicitly do **not** do in this PR

- **Don't fold rules into autopilot** (Gemini's preference).
  Different opt-in boundaries.
- **Don't simulate Gemini autonomy.** No brittle bash loops trying
  to fake what the runtime doesn't provide. Honest gap doc.
- **Don't ship an LLM verifier as the bottom layer.** Bash is
  deterministic; the role file interprets the bash output.
- **Don't overwrite harness role files silently.** The
  `--stack harness --stack autopilot` ordering requirement is
  documented; reversing it produces a less operational planner /
  reviewer / verifier (and a structural test catches both cases).
- **Don't ship a runtime budget enforcer.** sunaba is a generator.
  The budget cap lives in `verify.sh` because that's the surface
  the agent already calls — not in a daemon process we'd have to
  install.
- **Don't auto-commit checkpoints.** The agent writes
  `claudedocs/checkpoints/*.md`; whether the user commits them is
  a per-project choice.

## Rebuild consistency

Same rules as the prior three proposals — see each PR's
"Rebuild consistency" section. Specifically for this PR:

- **`rebuild --remove rules`** orphans:
  `.cursor/rules/*.mdc`, `.claude/rules/*.md`,
  the appended sections inside hierarchical `AGENTS.md` /
  `GEMINI.md`, and `docs/agents/rules/*`.
  Resolution: report, don't auto-delete. The hierarchical
  `AGENTS.md` sections are bracketed by
  `<!-- SUNABA RULE: <name> START/END -->` markers — the
  orphan-scan path can detect and offer to remove them
  surgically, but doesn't do so automatically.
- **`rebuild --remove autopilot`** orphans: every file under
  `.claude/hooks/`, `.codex/`, `.githooks/`, `claudedocs/plans/`,
  `claudedocs/checkpoints/`, `docs/agents/subagent-dispatch.md`,
  `docs/agents/gemini-autopilot-limitations.md`, `.sunaba/`.
  Plus `core.hooksPath` is left set in `.git/config` — the
  orphan-report calls this out explicitly with the
  `git config --unset core.hooksPath` command.

## Implementation order (revised)

The full sequence is now:

1. **harness-engineering** — `_files`, harness stack, orphan
   reporting code path, `_files` collision rule.
2. **stack-aware-agent-files** — `_build_agent_files()`, fragment
   layout, registry mode.
3. **secrets-management** — `--stack secrets`, `sync-gitignore`.
4. **rules-and-autonomy** (this PR) — `--stack rules`,
   `--stack autopilot`, the rule renderer, the structured Stop
   hook.

Steps 2, 3, and 4 are mostly independent of each other once
step 1 lands. Step 4 has soft dependencies on 2 (uses fragment
ideas) and 3 (the rule for `.gitignore` of the autopilot state
directory) but neither is blocking.

## Sources

- [Anthropic — Auto Mode (May 2026)](https://claude.com/blog/auto-mode)
- [InfoQ — Inside Claude Code Auto Mode (May 2026)](https://www.infoq.com/news/2026/05/anthropic-claude-code-auto-mode/)
- [Claude Code — memory / rules](https://code.claude.com/docs/en/memory)
- [Claude Code — hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code subagents (2026 guide)](https://skillsplayground.com/guides/claude-code-agents/)
- [Codex CLI — subagents](https://developers.openai.com/codex/subagents)
- [Codex CLI — hooks](https://developers.openai.com/codex/hooks)
- [Codex CLI — AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Codex CLI — non-interactive (`exec`)](https://developers.openai.com/codex/noninteractive)
- [Gemini CLI — `GEMINI.md`](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html)
- [Cursor — Rules `.mdc` complete guide (2026)](https://www.vibecodingacademy.ai/blog/cursor-rules-complete-guide)
- [`awesome-cursor-rules-mdc`](https://github.com/sanjeed5/awesome-cursor-rules-mdc)
- [Knightli — Ralph Loop (Apr 2026)](https://www.knightli.com/en/2026/04/27/ralph-autonomous-agent-loop-claude-code-amp/)
- [Pasquale Pillitteri — Claude Code Harness 2026 Guide](https://pasqualepillitteri.it/en/news/1892/claude-code-harness-runtime-architecture-2026-guide)
- Prior internal docs:
  [`2026-05-09-harness-engineering/05-proposal.md`](../2026-05-09-harness-engineering/05-proposal.md),
  [`2026-05-09-stack-aware-agent-files/05-proposal.md`](../2026-05-09-stack-aware-agent-files/05-proposal.md),
  [`2026-05-09-secrets-management/05-proposal.md`](../2026-05-09-secrets-management/05-proposal.md).
