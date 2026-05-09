# thinking/

Public design notes for `sunaba-cli`.

This folder is where we work in the open: research summaries, design
explorations, and consultation briefs that drive non-trivial changes to the
project. We treat these documents as **harness-as-code**: they go through PR
review like any other artifact, they cite sources, and they record *why* a
design decision was made — not just *what* changed.

The bar for landing a doc here:

- **Self-contained.** A reader who has not seen the conversation can follow it.
- **Sourced.** External claims link to the original article or repo.
- **Decision-oriented.** Every doc ends with a concrete proposal or a
  documented "we considered this and rejected it because…".

## Index

- [`2026-05-09-harness-engineering/`](2026-05-09-harness-engineering/) —
  applying harness-engineering principles (OpenAI, Martin Fowler, HumanLayer,
  Addy Osmani, Red Hat) to sunaba's generated agent scaffolding.
- [`2026-05-09-secrets-management/`](2026-05-09-secrets-management/) —
  expanding the generated `.gitignore`, adding a `pre-commit` /
  `gitleaks` opt-in stack, and documenting the per-cloud "key behind a
  proxy" pattern (Vercel, Firebase, AWS, GCP, plus the
  Azure Foundry → APIM → Gemini → Cosmos flow in detail).
- [`2026-05-09-stack-aware-agent-files/`](2026-05-09-stack-aware-agent-files/) —
  making the generated `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` /
  `skills.md` reflect the stacks the user actually selected, instead
  of shipping a static union of every possible tool. Lands per-stack
  fragments, a `docs/agents/<stack>.md` canonical detail page, an
  optional Claude skills mirror, and a registry-flagged `sync` mode.
- [`2026-05-09-rules-and-autonomy/`](2026-05-09-rules-and-autonomy/) —
  adding two new opt-in stacks: `--stack rules` (multi-target
  path-scoped rule files for Claude / Cursor / Codex / Gemini) and
  `--stack autopilot` (structured Stop-hook re-engage with budget
  caps, branch protection, subagent dispatch protocol, checkpoints).
  Codex CLI gets first-class subagent / hook templates alongside
  Claude; Gemini is the honest gap.
- [`2026-05-09-multi-agent-orchestration/`](2026-05-09-multi-agent-orchestration/) —
  cooperative parallel-agent coordination: shared YAML task list at
  `.agents/multi-agent/tasks.yaml`, hybrid `owns:`-based conflict
  avoidance, default cohort cap = 4, `flock`-protected helper script
  for atomic claims, sharding flowchart that defaults to serial.
  Templates only — coordination is cooperative, not enforced.

## Implementation order

The four proposals interlock. Recommended landing order:

1. **harness-engineering** — introduces the `_files` mechanism, the
   `--stack harness` itself, and the rebuild-orphan reporting code
   path. Everything else depends on this.
2. **stack-aware-agent-files** — adds `_build_agent_files()` and
   per-stack Markdown fragments. Uses `_files` ideas; introduces the
   registry `agent_files` mode.
3. **secrets-management** — adds `--stack secrets` (gitleaks +
   per-cloud docs) and a new `sunaba sync-gitignore` subcommand.
4. **rules-and-autonomy** — adds `--stack rules` (multi-target rule
   renderer with a new `_rules` key) and `--stack autopilot`
   (structured Stop-hook loop, branch protection, subagent dispatch).

Steps 2, 3, and 4 are mostly independent of each other once step 1
lands. Step 4 uses ideas from step 2 (fragment-style templates) but
doesn't strictly require it.

The recommended user invocation once everything has shipped:

```bash
sunaba new myapp \
  --stack python --stack agents \
  --stack harness --stack rules --stack autopilot \
  --stack secrets
```

(Stack order matters: `harness` before `autopilot` so the autopilot
PR's operational planner / reviewer / verifier role files override
the harness PR's roleplay seeds. The harness PR's `_files`
collision rule is "later wins.")

## How `sunaba sync` evolves across these proposals

Three independent modifications, none in conflict:

- **harness PR** — `sync` is **not** changed. Harness files only
  land via `sunaba new --stack harness` or `sunaba rebuild --add
  harness`.
- **stack-aware-agent-files PR** — `sync` learns a registry mode
  (`agent_files: "static" | "stack-aware"`). Legacy projects keep
  the static-copy path; new projects (and projects opted-in via
  `sync --agent-files stack-aware`) get delimiter-preserving
  regeneration.
- **secrets PR** — adds a sibling subcommand
  `sunaba sync-gitignore` for one-shot, opt-in `.gitignore`
  baseline upgrades on existing projects.

In aggregate: existing users see no surprises on `sunaba sync`;
each new behavior is opt-in via either a new flag, a registry
field, or a new subcommand.
