# 04a — Reviewer notes: Gemini 3.1 Pro Preview

> Independent review of the proposal in `03-llm-consultation-brief.md`.
> Model: `gemini-3.1-pro-preview` (Google Gemini CLI MCP).
> Date: 2026-05-09.
>
> Lightly edited for formatting only — no changes to the substance.

## A. Maturity scoring (1–5)

- **System prompt — 2.** `AGENTS.md` / `CLAUDE.md` are static and thin (~10
  generic lines). Lacks the **ratchet pattern** (Osmani) and fails to provide
  **feedforward guides** (Fowler) specific to the chosen stacks.
- **Tools — 3.** Good MCP baseline, but over-relies on always-on MCPs rather
  than prioritizing purpose-built **CLIs over MCP** for speed and reliability
  (HumanLayer). No custom bundled skills.
- **Context — 2.** `files.exclude` helps filter noise. No structural
  isolation or **context firewall** (HumanLayer).
- **Sub-agents — 1.** Entirely absent. Missing **planner / evaluator
  separation** (Osmani).
- **Feedback sensors — 1.** Missing. Agents are not receiving computational,
  **success-silent / failure-verbose** feedback (Fowler / HumanLayer).
- **Permissions — 2.** Container boundaries exist, but no application-level
  permission defaults → high approval fatigue.
- **Evals — 1.** Missing. No regression tests for the harness itself
  (Red Hat: "harness as code").
- **Observability — 1.** Missing.

## B. Concrete additions

### MUST — Stack-composable system prompts (the ratchet pattern)

- **What.** Extend stack JSONs to include an `_agents_md` array. During
  `sunaba new` / `sunaba sync`, dynamically construct `AGENTS.md` by
  combining the base prompt with stack-specific rules (e.g. the Python stack
  injects "Use `uv add`, not `pip install`").
- **Why.** Osmani's **ratchet pattern** — every rule traceable to a past
  agent failure. Generic `AGENTS.md` wastes tokens; tailored prompts give
  high-density **feedforward guidance** (Fowler).
- **How it composes.** Handled by the deep-merge composer in `compose.py`.
  `cli.py` takes the composed `_agents_md` list and writes it out.
- **Compatibility risk.** Low. `sunaba sync` starts writing generated files
  rather than copying static templates, but additive.

### MUST — Feedback sensors via silent hooks

- **What.** Generate a `.claude/settings.local.json` containing tool
  configurations that wrap linters / test runners so they only emit on
  failure:
  ```json
  {
    "customCommands": [
      { "name": "lint",
        "command": "uv run ruff check . > /dev/null || uv run ruff check ." }
    ]
  }
  ```
- **Why.** Fowler defines **feedback sensors** as computational checks.
  HumanLayer specifically advises **success-silent / failure-verbose** so the
  agent doesn't burn context reading "0 errors found."
- **How it composes.** Add `_claude_settings` to `base/devcontainer.json`
  (or a separate `base/claude.json`). Deep-merge lets stacks append their
  own hooks (e.g. `npm run lint`).
- **Compatibility risk.** Zero — new file, doesn't break container builds.

### SHOULD — Base permission defaults (anti-fatigue)

- **What.** `.claude/settings.local.json` `allowed_commands` array
  pre-approves safe computational commands inside the sandbox: `ls`, `cat`,
  `uv run pytest`, `npm test`, `git status`, etc.
- **Why.** In an agent-first world (OpenAI), user attention is the
  bottleneck. Prompting to approve `git diff` inside a disposable container
  defeats the sandbox.
- **How it composes.** Same `.claude/settings.local.json` via deep-merge.
- **Compatibility risk.** Zero.

### SHOULD — Sub-agent planner template

- **What.** Ship `templates/agents/planner.md` (or `.claude/agents/planner.md`)
  instructing the LLM to write a purely text-based architectural plan before
  modifying code.
- **Why.** Osmani's **planner / evaluator separation**. HumanLayer's
  **context firewall** — the planner holds requirements while the coder
  stays focused on the file.
- **How it composes.** Copied wholesale during `sunaba new`.
- **Compatibility risk.** Zero.

### COULD — Modular skill definitions

- **What.** Generate a `.claude/skills/` directory with markdown files for
  complex API tasks (e.g. `.claude/skills/aws-s3-sync/SKILL.md`).
- **Why.** "Equipping over telling" (HumanLayer). CLIs over MCP where
  possible.
- **How it composes.** Base generator loops over a `_skills` array defined
  in stacks and copies corresponding files.
- **Compatibility risk.** Low.

## C. `--stack harness` — counter-proposal

> "I strongly argue against introducing a separate `--stack harness`."

Harness engineering is the **core value proposition** of an AI devcontainer.
If a user runs `sunaba new my-app --stack python`, they expect an environment
optimized for AI agents. Hiding harness behind an optional flag creates a
false dichotomy where the default path is just "a Docker wrapper."

**Recommendation:** bake harness principles directly into `base/` and the
deep-merge compiler. If user-facing exposure is needed, reframe as
`--harness-mode=strict` (extreme linters / agent-driven PR review) vs the
default.

Suggested README entry (when integrated into `base/`):

> "Sunaba implements **harness as code** (Red Hat). Every environment
> automatically generates silent-on-success feedback sensors, stack-tailored
> agent instructions (the ratchet pattern), and pre-configured context
> firewalls."

## D. Test strategy

Behavioral tests (Docker spin-ups in CI) are slow and flaky. Test the
**harness structure** with `pytest`:

1. **Template schema validation.** Assert no stack JSON has un-prefixed
   top-level keys that aren't valid devcontainer properties (i.e. enforce
   harness config lives under `_claude_settings`, etc.).
2. **JSON shape composition tests.** Assert
   `compose(["python", "nextjs"])` produces a `devcontainer.json` and
   `.claude/settings.local.json` that correctly deduplicates arrays
   (`allowed_commands`) and deep-merges nested dicts (VS Code
   `files.exclude`).
3. **Idempotent regeneration.** Run `sunaba new test-app`, capture state,
   run `sunaba rebuild test-app --stack python`, assert `_diff_files`
   reports zero changes.
4. **Harness snapshots.** Keep expected snapshots of generated `AGENTS.md`
   and `.claude/settings.json` so PRs can't silently drop critical
   feedforward rules.

## E. Top-3 picks

1. **Stack-composable system prompts.** Python/Next.js projects need very
   different feedforward rules than a raw GCP project.
2. **Feedback sensors (silent hooks).** Drastically reduces token usage and
   context pollution.
3. **Base permission defaults.** Cures approval fatigue, which otherwise
   trains users to click "always allow."

## F. Push-back / drop

- **Drop: always-on MCPs.** Currently `.mcp.json` loads Playwright, Chrome
  DevTools, and NotebookLM unconditionally. Wastes context on irrelevant
  tool descriptions. Move MCP entries out of `base/mcp.json` and into the
  stacks that actually need them (`playwright.json` ships Playwright,
  `nextjs.json` ships Chrome DevTools).
- **Drop: heavy evals / observability in the scaffold.** Do not add a
  `claudedocs/` eval suite or telemetry tracing to the *generated* project.
  Sunaba is for **disposable** sandboxes. Eval frameworks belong in the
  user's host repo, not the disposable harness.
- **Drop: hard-coded `AGENTS.md ≤60 lines` rule.** While conciseness is key,
  hardcoding a length limit in the generator is brittle. Focus on
  *relevance* via composition rather than arbitrary line counts.

## Notable disagreements with our hypothesized gaps

- We hypothesized `--stack harness` as a likely addition; Gemini says **no**
  and argues harness should be in `base/`. This is a substantive design
  call we need to take a position on in `04-proposal.md`.
- We hypothesized the always-on MCP list was OK to keep but flagged the
  context cost; Gemini says **move them into stacks**, which is more
  aggressive and aligns with HumanLayer's "every irrelevant tool description
  is an instruction the agent has to process."
- We hypothesized adding `claudedocs/` eval scaffolding; Gemini says **no**,
  it violates the "disposable sandbox" framing.

These three are exactly the questions where a second independent reviewer
(Codex with high reasoning) earns its keep.
