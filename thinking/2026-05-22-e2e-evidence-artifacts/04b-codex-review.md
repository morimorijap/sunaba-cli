# 04b — Codex CLI review

> Reviewer: **Codex CLI**, model `gpt-5.5`, `model_reasoning_effort=high`.
> Invoked non-interactively (`codex exec`, read-only sandbox, web search
> enabled) against [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md)
> on 2026-05-22. Output reproduced verbatim below; sunaba maintainers'
> synthesis lives in [`05-proposal.md`](05-proposal.md).

---

**A. Maturity Scoring**

| Area | Score | Review |
| --- | ---: | --- |
| Evidence durability | 1/5 | Today, a browser verification can happen through Playwright MCP, Chrome DevTools MCP, or an ad hoc Playwright script, but sunaba does not scaffold a durable run report. Screenshots may exist only in MCP output, temp files, Playwright's normal ignored artifacts, or chat transcript. That is not durable evidence. |
| Reviewability | 1/5 | A reviewer can read an agent's claim, but cannot reliably inspect the proof behind "verified in browser." Playwright itself has strong artifact support, but `test-results/` and `playwright-report/` are runner artifacts, not committed review artifacts. Playwright documents `test-results` as the normal output directory for screenshots/videos/traces and `playwright-report` as the default HTML report folder. [Playwright test config](https://playwright.dev/docs/test-configuration), [Playwright reporters](https://playwright.dev/docs/test-reporters). |
| Agent guidance | 1/5 | The generated agent files do not currently teach an E2E evidence convention. The `playwright` stack has no `templates/agents/fragments/playwright/{summary,tools,guidance}.md`, so selecting the stack installs environment support but not behavioral guidance. |
| Cross-agent parity | 4/5 | The tool wiring is fairly agent-neutral: the brief says all three agents get the browser MCP servers, and current templates generate `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`. It is not 5/5 because Claude gets extra skill affordances from the fragment system, and MCP client behavior still varies by agent. But the missing evidence convention is missing equally. |

**B. Directory + Naming Contract**

Use lowercase root-level `e2e/`.

Do not use uppercase `E2E/`. The acronym reads well in prose, but lowercase is the better filesystem contract: it matches common repository directories such as `tests/`, `docs/`, `src/`, and avoids case-only ambiguity on case-insensitive filesystems. The folder is a convention, not a product brand. Use `E2E` in headings and documentation, but `e2e/` on disk.

The run directory should be:

```text
e2e/YYYY-MM-DD-HHMMSS-slug/
├── README.md
└── *.png
```

Example:

```text
e2e/2026-05-22-143012-login-form/
├── README.md
├── 01-login-page.png
└── 02-error-state.png
```

The `xxxxx` suffix should be `HHMMSS-slug`.

Reasons:

- `YYYY-MM-DD-HHMMSS` sorts lexically and chronologically.
- It disambiguates two runs on the same day without a global counter.
- It is human-readable in reviews.
- A slug carries intent better than a random id.
- A zero-padded sequence requires coordination and is easy for agents to race or miscount.
- A short random id avoids collisions but loses useful context.

The folder should live at repo root, not under `docs/`, `tests/`, or `claudedocs/`.

Root `e2e/` is the right contract because this is neither documentation prose nor test source. It is committed verification evidence. Putting it under `docs/e2e/` makes it look like authored documentation. Putting it under `tests/e2e/runs/` makes it look like Playwright test inputs or outputs. Putting it under `claudedocs/` violates cross-agent fairness.

Use one folder per run, not per feature. A browser verification session has a specific environment, commit, branch, URL, browser, and result. Grouping by feature first makes append-only evidence harder to reason about and easier to accidentally mutate.

**C. `README.md` Run-Report Schema**

Use YAML frontmatter. It gives reviewers a normal Markdown report and gives future tools something parseable without scraping prose.

Full template:

```markdown
---
schema_version: 1
run_id: 2026-05-22-143012-login-form
date: 2026-05-22
time: "14:30:12"
timezone: Asia/Tokyo
status: pass # pass | fail | partial
agent: codex-cli # claude-code | codex-cli | gemini-cli | other
driver: playwright-mcp # playwright-mcp | chrome-devtools-mcp | playwright-script | other
branch: feature/login-form
commit: abc1234
url: http://localhost:3000/login
browser: chromium
viewport: 1280x720
---

# E2E Run: login-form

## Scope

Verify that the login form renders, validates invalid credentials, and keeps the user on the login page without exposing a stack trace.

## Environment

- URL: `http://localhost:3000/login`
- Branch: `feature/login-form`
- Commit: `abc1234`
- Browser: Chromium
- Viewport: `1280x720`
- Driver: Playwright MCP
- Agent: Codex CLI

## Steps

1. Opened `/login`.
2. Confirmed the email and password fields were visible.
3. Submitted invalid credentials.
4. Checked that the inline error message appeared.
5. Confirmed the URL remained `/login`.

## Evidence

Initial page:

![Login page](./01-login-page.png)

Invalid credential state:

![Invalid credential state](./02-invalid-credentials.png)

## Result

Status: **pass**

The login page rendered correctly, invalid credentials produced an inline error, and no unexpected navigation or browser console error was observed.

## Bugs / Follow-Ups

- None.

## Notes

- No secrets or real user data were entered.
- Screenshots were downscaled before commit.
```

Mandatory fields should be:

- `schema_version`
- `run_id`
- `date`
- `status`
- `agent`
- `driver`
- `branch`
- `commit`
- `url`
- `browser`
- `viewport`

Mandatory sections should be:

- `Scope`
- `Environment`
- `Steps`
- `Evidence`
- `Result`
- `Bugs / Follow-Ups`

The status vocabulary should be exactly `pass`, `fail`, or `partial`.

**D. Where It Plugs Into sunaba**

Do not add a new `--stack e2e`. Fold this into the existing `playwright` stack.

The existing `playwright` stack already means "browser automation environment." Adding a second stack named `e2e` would create a confusing split: users would ask whether they need `--stack playwright`, `--stack e2e`, or both. The evidence convention should ship when users opt into browser automation.

Do not make this an always-on scaffold. It would add repository policy to projects that may never do browser verification, and it creates binary-bloat expectations for every generated project.

Recommended files:

```text
src/sunaba_cli/templates/agents/fragments/playwright/summary.md
src/sunaba_cli/templates/agents/fragments/playwright/tools.md
src/sunaba_cli/templates/agents/fragments/playwright/guidance.md
src/sunaba_cli/templates/playwright/e2e/TEMPLATE.md
```

Then add an `_files` entry to `src/sunaba_cli/templates/stacks/playwright.json`:

```json
{
  "_files": {
    "e2e/TEMPLATE.md": "playwright/e2e/TEMPLATE.md"
  }
}
```

The root agent summary should be short, for example:

```markdown
- **playwright**: Browser automation is available. When browser verification supports a user-facing claim, create a committed `e2e/YYYY-MM-DD-HHMMSS-slug/README.md` run report with curated screenshots. See `docs/agents/playwright.md`.
```

The tools fragment should mention both MCP servers and Playwright scripts:

```markdown
- **Playwright MCP**: Drive and inspect browser flows through accessibility snapshots; use screenshots for visual evidence.
- **Chrome DevTools MCP**: Inspect Chrome, console output, network requests, performance traces, and screenshots.
- **Playwright scripts**: Use project-local Playwright tests or one-off scripts when repeatability matters.
```

`guidance.md` should say, concretely:

````markdown
# Playwright stack

Use browser automation to verify user-visible behavior when code changes affect UI, routing, forms, auth flows, rendering, or browser-only integrations.

## E2E evidence convention

When browser verification supports your final claim, create one run folder:

```text
e2e/YYYY-MM-DD-HHMMSS-slug/
├── README.md
└── *.png
```

The run folder is human-curated evidence. It is different from Playwright's generated `test-results/` and `playwright-report/` folders.

The `README.md` must include:

- Scope / goal
- Environment: URL, branch, commit, browser, viewport, agent, driver
- Steps performed
- Result: `pass`, `fail`, or `partial`
- Inline screenshot references
- Bugs or follow-ups found

Use only curated screenshots. Do not commit raw dumps, videos, traces, or repeated near-duplicate captures. Prefer 1-3 screenshots per run. Downscale or crop large screenshots before committing. Do not include secrets, tokens, production personal data, or private customer data.

Use `e2e/TEMPLATE.md` as the starting point.
````

Yes, wire Playwright MCP `--output-dir`, but wire it to scratch, not to `e2e/`.

Recommended `.mcp.json` change:

```json
"playwright": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "@playwright/mcp@latest",
    "--browser",
    "chromium",
    "--output-dir",
    ".sunaba/e2e-scratch"
  ],
  "env": {}
}
```

Playwright MCP officially supports `--output-dir` / `PLAYWRIGHT_MCP_OUTPUT_DIR` for output files. [Playwright MCP configuration](https://github.com/microsoft/playwright-mcp). The scratch directory should be a landing pad. Agents should copy or move only curated evidence into the run folder.

Do not set `--save-session` by default. It increases output volume and risks committing irrelevant or sensitive session state.

Recommended `.gitignore` baseline additions:

```gitignore
# Playwright generated artifacts
test-results/
playwright-report/
blob-report/

# MCP/browser scratch output
.sunaba/e2e-scratch/
```

Do not gitignore `e2e/`. The entire point is that curated run reports are commit candidates.

**E. The Binary-Bloat Decision**

Pick policy 1: commit a curated handful of PNGs per run plus a retention cap.

The convention is pointless if the proof never reaches the PR. Gitignoring `e2e/` entirely gives you local notes, not review evidence. Committing only `README.md` preserves the narrative but loses the visual proof. For UI work, the screenshot is often the artifact the reviewer actually needs.

Primary policy:

- Commit `README.md`.
- Commit only curated screenshots referenced by `README.md`.
- Prefer 1-3 screenshots per run.
- Hard cap 5 screenshots per run.
- Downscale wide screenshots to at most 1440 px width unless the extra pixels are material.
- Prefer viewport or element screenshots over full-page screenshots.
- Do not commit videos, traces, raw MCP dumps, Playwright reports, or repeated near-duplicates.
- Keep the latest 5 run folders in `e2e/` per active branch or PR.

The retention cap should be `N = 5`.

Five is enough to preserve a useful review trail across a normal PR: initial verification, one or two failed/partial runs, fix verification, and final verification. More than five usually becomes noise. This cap controls checkout size and review clutter, but be honest: deleting old PNGs later does not remove them from Git history. GitHub warns that repository health is affected by size and contents, and files over 50 MiB trigger warnings while files over 100 MiB are blocked. [GitHub large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

Git LFS is not worth making part of this feature.

Git LFS stores pointer files in Git while the large content lives elsewhere. [GitHub LFS docs](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage). That is useful for projects that intentionally version large binaries, but it is overkill for a disposable sandbox generator. It adds setup, hosting, quota, and collaboration complexity to generated projects. For sunaba's target use, disciplined curation beats LFS.

**F. Cross-Agent Matrix**

| Agent | Drive Playwright MCP? | Follow folder + README convention? | Read prior run folders as memory? | Honest gaps |
| --- | --- | --- | --- | --- |
| Claude Code | Yes. Playwright MCP documents Claude Code setup directly. [Playwright MCP](https://playwright.dev/docs/getting-started-mcp). Chrome DevTools MCP also documents Claude Code setup. [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp). | Yes, likely strongest because sunaba can emit `CLAUDE.md` plus a Claude skill from the `playwright` fragment. Still cooperative, not enforceable. | Yes, if the files are committed or present in workspace. Claude can read `e2e/*/README.md` like normal repo context. | Claude-specific skills create a slight guidance advantage unless root `CLAUDE.md` is kept equally clear. |
| Codex CLI | Yes. Playwright MCP documents Codex setup, and Chrome DevTools MCP documents Codex setup. | Yes. Codex follows `AGENTS.md` conventions well when they are concrete. It can create folders, write Markdown, and reference screenshots, subject to local permissions. | Yes. Prior run folders are normal files and can be searched/read. | No automatic guarantee that a final answer claiming verification has a matching run folder unless instructed or tested socially in review. |
| Gemini CLI | Yes. Playwright MCP says Gemini CLI can use the standard MCP config; Chrome DevTools MCP documents Gemini CLI setup. | Yes, if `GEMINI.md` includes the same convention. Keep the guidance root-visible, not Claude-only. | Yes. A committed run folder is agent-neutral memory. | Gemini's project-instruction and extension behavior may differ by installation; do not rely on Claude skills or Codex-specific conventions for parity. |

The cross-agent principle is simple: the durable artifact must be plain files in the repo. Anything stored in one agent's transcript, local memory, skill state, or MCP session is not cross-agent evidence.

**G. Tests**

Add structural tests, not browser tests.

Recommended tests:

```python
def test_playwright_stack_emits_e2e_template():
    files = _build_config_files("p", ["playwright"])
    assert "e2e/TEMPLATE.md" in files
    body = files["e2e/TEMPLATE.md"]
    assert "schema_version:" in body
    assert "status: pass # pass | fail | partial" in body
    assert "## Steps" in body
    assert "## Evidence" in body
    assert "## Result" in body
```

```python
def test_playwright_fragment_composed_into_agent_files():
    files = _build_config_files("p", ["playwright"])
    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        body = files[fname]
        assert "e2e/YYYY-MM-DD-HHMMSS-slug" in body
        assert "docs/agents/playwright.md" in body
```

```python
def test_playwright_guidance_doc_and_claude_skill_generated():
    files = _build_config_files("p", ["playwright"])
    assert "docs/agents/playwright.md" in files
    assert ".claude/skills/sunaba-playwright/SKILL.md" in files
    assert files[".claude/skills/sunaba-playwright/SKILL.md"].startswith("---\n")
```

```python
def test_mcp_json_sets_playwright_output_dir():
    files = _build_config_files("p", ["playwright"])
    mcp = json.loads(files[".mcp.json"])
    args = mcp["mcpServers"]["playwright"]["args"]
    assert "--output-dir" in args
    assert ".sunaba/e2e-scratch" in args
```

```python
def test_default_gitignore_keeps_curated_e2e_but_ignores_scratch_and_playwright_reports():
    text = _default_gitignore()
    assert ".sunaba/e2e-scratch/" in text
    assert "test-results/" in text
    assert "playwright-report/" in text
    assert "blob-report/" in text
    assert "e2e/" not in text
    assert "*.png" not in text
```

```python
def test_e2e_template_frontmatter_has_required_keys():
    files = _build_config_files("p", ["playwright"])
    text = files["e2e/TEMPLATE.md"]
    fm, _ = _parse_rule_frontmatter(text)  # or add a tiny generic frontmatter parser
    for key in [
        "schema_version",
        "run_id",
        "date",
        "status",
        "agent",
        "driver",
        "branch",
        "commit",
        "url",
        "browser",
        "viewport",
    ]:
        assert key in fm
```

Also preserve the existing line-count test for root agent files. The summary fragment must stay short enough that `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` remain usable.

**H. Top-3 Picks**

If only three things land, ship these:

1. Add the `playwright` agent fragment with explicit `e2e/YYYY-MM-DD-HHMMSS-slug/README.md` guidance.
2. Add `e2e/TEMPLATE.md` through the `playwright` stack.
3. Add `.sunaba/e2e-scratch/`, `test-results/`, `playwright-report/`, and `blob-report/` to `.gitignore`, and wire Playwright MCP `--output-dir` to `.sunaba/e2e-scratch`.

Those three create the convention, make it discoverable by all agents, and keep raw browser output out of Git.

**I. Push-Back**

The framing is mostly right, but the design must stay honest: this is review evidence, not test enforcement.

Do not claim that sunaba can make agents produce evidence. It can only scaffold instructions and templates. The convention is cooperative.

Do not replace this with Playwright's HTML report. The HTML report is useful for test-run debugging, but it is generated output. Playwright documents the default report folder as `playwright-report`, and the test output directory as `test-results`; those belong in `.gitignore` for this project's lifecycle. [Playwright reporters](https://playwright.dev/docs/test-reporters), [Playwright test config](https://playwright.dev/docs/test-configuration). The proposed `e2e/` folder is a curated, committed review artifact.

Do not move this entirely to CI. CI is the right place for repeatable regression tests, videos, traces, and uploaded artifacts. This proposal is about agent-driven browser verification during implementation: "I changed the UI and checked it in a browser; here is what I saw." That belongs close to the PR when the evidence is small and curated.

Do not gitignore all screenshots. That dodges the bloat problem by destroying the review value. The better policy is strict curation: few screenshots, downscaled, retained only while useful.

`e2e/` does not meaningfully collide with `tests/test_e2e.py`. One is evidence; one is automated test code. The README template should state that executable tests still belong under `tests/` or the project's normal test directory.
