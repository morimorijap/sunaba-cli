# 05 — Proposal: the E2E evidence-artifact convention

> Status: **draft / in review**. Synthesises
> [`04a-gemini-review.md`](04a-gemini-review.md) (Gemini
> `gemini-3-flash-preview`) and [`04b-codex-review.md`](04b-codex-review.md)
> (Codex CLI `gpt-5.5`, high reasoning) against the
> [consultation brief](03-llm-consultation-brief.md).

## TL;DR — the decisions

1. **Directory.** When an agent verifies behaviour in a browser, it
   writes one folder per session:

   ```text
   evidence/e2e/YYYY-MM-DD-<slug>/
   ├── README.md          ← the run report (what / how / result)
   └── NN-<name>.png      ← curated screenshots, referenced inline
   ```

   Lowercase, repo-root, **`evidence/e2e/`** — not the user's literal
   `E2E/`. Both reviewers independently rejected uppercase `E2E/`;
   see [§8](#8-alternatives-considered-and-rejected) for why we took
   Gemini's `evidence/` prefix over Codex's bare `e2e/`.

2. **Run report.** `README.md` carries YAML frontmatter
   (machine-parseable) plus six mandatory sections. A
   `evidence/e2e/TEMPLATE.md` ships as the starting point. Result
   vocabulary is exactly `pass` / `fail` / `partial`.

3. **Where it ships.** Folded into the **existing `playwright`
   stack** — *not* a new `--stack e2e`, *not* an always-on scaffold.
   Selecting `playwright` already means "browser automation"; the
   evidence convention rides along with it.

4. **New artifacts.** A `playwright` agent fragment (the gap noted in
   [`01-current-state.md`](01-current-state.md)), the `TEMPLATE.md`,
   a `.gitignore` policy, and a Playwright-MCP `--output-dir` wired
   to a gitignored scratch path.

5. **Binary bloat.** Commit a *curated* handful of PNGs per run
   (1–3 typical, 5 hard cap), downscaled; keep the last **5** run
   folders; gitignore raw browser output. No Git LFS.

6. **Honest limit.** sunaba is a template generator. It *cannot*
   force an agent to write the folder. This is a **cooperative
   convention** — same posture as the `multi-agent` stack.

## Why this matters

Today an agent can drive a browser through the Playwright MCP, take
screenshots, declare "login verified," and end the turn — and the
proof lands in a temp dir, the narrative lives only in an
uncommitted transcript, and the next agent re-explores from zero.
Both reviewers scored sunaba **1/5** on evidence durability,
reviewability, and agent guidance. This proposal closes that gap
with a committed, reviewable, cross-agent-readable artifact.

---

## 1. The directory contract

```text
evidence/
└── e2e/
    ├── TEMPLATE.md                       ← shipped by sunaba; copy this
    ├── 2026-05-22-login-validation/
    │   ├── README.md
    │   ├── 01-login-page.png
    │   └── 02-invalid-credentials.png
    └── 2026-05-23-checkout-flow/
        ├── README.md
        └── 01-cart-summary.png
```

**`evidence/e2e/`, lowercase, repo root.**

- *Lowercase* — matches `src/`, `tests/`, `docs/`; avoids case-only
  ambiguity on case-insensitive filesystems. Both reviewers agreed.
- *`evidence/` prefix* — separates test **artifacts** from test
  **code**. The repo already has `tests/test_e2e.py`, and a project
  may also keep Playwright scripts under `tests/e2e/`. A bare root
  `e2e/` blurs "is this code or output?"; `evidence/e2e/` does not.
- *Repo root, not `docs/` or `claudedocs/`* — it is neither authored
  documentation nor a Claude-only directory. Routing evidence under
  `claudedocs/` would break cross-agent fairness.

**Naming: `YYYY-MM-DD-<slug>`.**

- ISO date prefix sorts chronologically *and* lexically.
- `<slug>` is a short kebab-case intent tag (`login-validation`,
  `checkout-flow`) — a human scanning the tree finds the run without
  opening five `README.md` files. This is the user's `xxxxx`.
- **Same-day collision rule:** if `YYYY-MM-DD-<slug>/` already
  exists, append `-HHMMSS` (the run's start time):
  `2026-05-22-login-validation-143012/`. Deterministic, sortable, no
  global counter to race. (Codex argued for *always* including
  `HHMMSS`; we make it collision-only to keep the common-case name
  readable.)

**One folder per run**, not per feature. Each browser session has a
distinct commit, branch, URL, and result; per-run folders keep the
evidence append-only and immutable (the ADR discipline from
[`02-research-notes.md`](02-research-notes.md)).

**Screenshot naming:** `NN-<name>.png`, zero-padded ordinal so the
files sort in capture order and read in narrative order.

---

## 2. The run-report schema (`README.md`)

Every run folder contains a `README.md`. It has **YAML frontmatter**
(so a future `sunaba` indexer or a reviewer's script can parse runs
without scraping prose) followed by six mandatory sections.

`evidence/e2e/TEMPLATE.md` ships this verbatim as the starting point:

````markdown
---
schema_version: 1
run_id: 2026-05-22-login-validation
date: 2026-05-22
status: pass            # pass | fail | partial
agent: claude-code      # claude-code | codex-cli | gemini-cli | other
driver: playwright-mcp  # playwright-mcp | chrome-devtools-mcp | playwright-script
branch: feat/login-fix
commit: a1b2c3d
url: http://localhost:3000/login
browser: chromium
viewport: 1280x720
---

# E2E run: login-validation

## Scope
What this browser session set out to verify, in one or two sentences.

## Environment
- URL: `http://localhost:3000/login`
- Branch / commit: `feat/login-fix` @ `a1b2c3d`
- Browser / viewport: Chromium, 1280x720
- Driver: Playwright MCP
- Agent: Claude Code

## Steps
1. Opened `/login`.
2. Submitted invalid credentials.
3. Confirmed the inline error appeared — `01-invalid-credentials.png`.
4. Submitted valid credentials.
5. Confirmed redirect to `/dashboard` — `02-dashboard.png`.

## Evidence
![Invalid credentials show an inline error](./01-invalid-credentials.png)

![Valid login redirects to the dashboard](./02-dashboard.png)

## Result
**pass** — invalid credentials produced an inline error with no
navigation; valid credentials redirected to `/dashboard`. No browser
console errors observed.

## Follow-ups
- Error toast is misaligned by ~2px (cosmetic). Filed as #42.
````

**Mandatory frontmatter:** `schema_version`, `run_id`, `date`,
`status`, `agent`, `driver`, `branch`, `commit`, `url`, `browser`,
`viewport`.

**Mandatory sections:** `Scope`, `Environment`, `Steps`, `Evidence`,
`Result`, `Follow-ups`.

**`status` is exactly `pass` / `fail` / `partial`** — lowercase, for
clean machine parsing. A `fail` or `partial` run is *still
committed*: a failed verification is evidence too, and the next
agent should see it.

We keep section headings plain (no emoji) to match the repo's
existing Markdown style; Gemini's emoji variant was dropped on that
basis only.

---

## 3. Where it plugs into sunaba

Both reviewers agreed: **fold into the existing `playwright` stack**,
do not add `--stack e2e`, do not make it always-on. A second stack
would force users to wonder "do I need `playwright`, `e2e`, or
both?", and an always-on scaffold would push browser-evidence policy
onto projects that never touch a browser.

### 3.1 New files

```text
src/sunaba_cli/templates/agents/fragments/playwright/summary.md
src/sunaba_cli/templates/agents/fragments/playwright/tools.md
src/sunaba_cli/templates/agents/fragments/playwright/guidance.md
src/sunaba_cli/templates/playwright/evidence/TEMPLATE.md
```

The `playwright` **agent fragment** is the missing piece from
[`01-current-state.md`](01-current-state.md) — `playwright` is the
only browser stack with no `fragments/` entry today. Adding it makes
the convention show up in the generated `AGENTS.md` / `CLAUDE.md` /
`GEMINI.md`, and (via the stack-aware machinery) in
`docs/agents/playwright.md` and `.claude/skills/sunaba-playwright/`.

- **`summary.md`** — one bullet for the root agent files (keep it
  short; the existing `AGENTS.md` line-count test must still pass):

  > **playwright** — browser automation is available. When a browser
  > check backs a user-facing claim, record it as a committed
  > `evidence/e2e/YYYY-MM-DD-<slug>/README.md` run report with
  > curated screenshots. See `docs/agents/playwright.md`.

- **`tools.md`** — names the two MCP servers + script option:

  > - **Playwright MCP** — drive/inspect browser flows; screenshots
  >   for visual evidence.
  > - **Chrome DevTools MCP** — console, network, performance,
  >   screenshots.
  > - **Playwright scripts** — project-local tests when
  >   repeatability matters.

- **`guidance.md`** — the full convention: when to produce a run
  folder, the directory contract (§1), the README schema (§2), the
  curation rules (§4), and the scratch-dir workflow (§3.3). Ends by
  pointing at `evidence/e2e/TEMPLATE.md`.

### 3.2 Stack wiring

`templates/stacks/playwright.json` gains an `_files` entry so the
template lands at project root:

```json
{
  "_files": {
    "evidence/e2e/TEMPLATE.md": "playwright/evidence/TEMPLATE.md"
  }
}
```

`TEMPLATE.md` doubles as the `.gitkeep` for `evidence/e2e/` — the
directory is born non-empty and self-documenting.

### 3.3 Playwright MCP `--output-dir` → scratch

Point the Playwright MCP server at a **gitignored scratch directory**
so raw screenshots land predictably; the agent then *curates* chosen
images into the run folder. In `templates/base/mcp.json` (or a
playwright-stack overlay):

```json
"playwright": {
  "type": "stdio",
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--browser", "chromium",
           "--output-dir", ".sunaba/e2e-scratch"],
  "env": {}
}
```

`--output-dir` is a documented Playwright-MCP flag
([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)).
The workflow becomes: **MCP dumps to `.sunaba/e2e-scratch/` →
agent picks the keepers → agent copies them into
`evidence/e2e/<run>/` and writes `README.md`.** Curation is a
deliberate step, not an afterthought. We do *not* enable
`--save-session` / trace saving by default — too much volume, and a
session blob can carry sensitive state.

### 3.4 `.gitignore` additions

```gitignore
# Playwright / browser generated artifacts (regenerated each run)
test-results/
playwright-report/
blob-report/
playwright/.cache/

# Browser-MCP scratch output — agents curate into evidence/e2e/
.sunaba/e2e-scratch/
```

**`evidence/` is deliberately *not* ignored** — committed curated run
reports are the entire point. This keeps Playwright's own
machine-lifecycle artifacts (`test-results/`, `playwright-report/`)
out of git while letting the human-lifecycle `evidence/e2e/` in.

---

## 4. Binary-bloat policy

Both reviewers picked the same policy: **commit curated PNGs +
retention cap.** Gitignoring `evidence/` (option 2) yields local
notes, not review evidence; committing only the README (option 3)
drops the proof a UI reviewer actually needs.

**Curation rules** (in `guidance.md`):

- Commit `README.md` + only the screenshots it references inline.
- 1–3 screenshots per run is typical; **5 is the hard cap.**
- Prefer **viewport or element** screenshots over full-page.
- Downscale to ≤ 1440px wide unless the extra pixels are material.
- Never commit videos, traces, raw MCP dumps, `playwright-report/`,
  or near-duplicate frames.
- Never capture secrets, tokens, or real user/customer data.

**Retention: keep the last `N = 5` run folders.** Five spans a
normal PR's trail — initial check, a fail/partial, the fix
verification, the final pass. Older folders are pruned in the same
commit that adds a new one.

**Honest caveat:** pruning the working tree does **not** shrink git
history — every committed PNG is permanent
([GitHub large-file guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)).
The cap controls *checkout size and review clutter*, not history
size. Strict curation is what actually keeps history sane.

**Git LFS: rejected.** It adds setup, hosting, quota, and
collaboration friction — overkill for a disposable-sandbox
generator. Disciplined curation beats LFS here.

**Optional helper (`could`-tier).** A `scripts/prune-evidence.py`
(modelled on the `multi-agent` stack's `scripts/agent-task.py`)
could enforce the `N=5` cap and validate run folders against the
schema. Not required for the first PR.

---

## 5. Cross-agent matrix

All three agents receive the Playwright + Chrome DevTools MCP servers
from the base `.mcp.json`, so all three *can* produce evidence. The
durable artifact is **plain files in the repo** — anything in an
agent's transcript, private memory, or MCP session is not
cross-agent evidence.

| Capability | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| Drive Playwright MCP | Yes | Yes | Yes |
| Follow folder + README convention | Yes — strongest (root `CLAUDE.md` + a `sunaba-playwright` skill) | Yes — reliable when `AGENTS.md` guidance is concrete | Yes — when `GEMINI.md` carries the same guidance |
| Read prior run folders as memory | Yes | Yes | Yes |

**Honest gaps.** Claude gets a slight edge from the generated skill;
the mitigation is to keep the convention fully spelled out in the
root agent files, not Claude-only. Codex tends to skip "boring"
documentation steps unless the instruction is forceful — so
`guidance.md` states the run report as a *requirement* of a browser
verification, not an optional extra. No template can *guarantee* a
final "verified" claim is backed by a run folder; that gap is closed
socially, in PR review (and, optionally, by the helper script).

---

## 6. Tests

`sunaba` uses `pytest` (structural + subprocess-E2E). Browser tests
are out of scope; everything here is **structural**:

```python
def test_playwright_stack_emits_e2e_template():
    files = _build_config_files("p", ["playwright"])
    assert "evidence/e2e/TEMPLATE.md" in files
    body = files["evidence/e2e/TEMPLATE.md"]
    assert "schema_version:" in body
    assert "status: pass" in body
    for section in ("## Scope", "## Steps", "## Evidence", "## Result"):
        assert section in body


def test_playwright_fragment_composed_into_agent_files():
    files = _build_config_files("p", ["playwright"])
    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        body = files[fname]
        assert "evidence/e2e/YYYY-MM-DD-" in body
        assert "docs/agents/playwright.md" in body


def test_playwright_guidance_doc_and_claude_skill_generated():
    files = _build_config_files("p", ["playwright"])
    assert "docs/agents/playwright.md" in files
    skill = files[".claude/skills/sunaba-playwright/SKILL.md"]
    assert skill.startswith("---\n")


def test_mcp_json_sets_playwright_output_dir():
    files = _build_config_files("p", ["playwright"])
    mcp = json.loads(files[".mcp.json"])
    args = mcp["mcpServers"]["playwright"]["args"]
    assert "--output-dir" in args and ".sunaba/e2e-scratch" in args


def test_gitignore_keeps_evidence_but_ignores_scratch_and_reports():
    text = _default_gitignore()  # or the playwright-stack gitignore
    for pat in ("test-results/", "playwright-report/",
                "blob-report/", ".sunaba/e2e-scratch/"):
        assert pat in text
    assert "evidence/" not in text
    assert "*.png" not in text


def test_e2e_template_frontmatter_has_required_keys():
    files = _build_config_files("p", ["playwright"])
    fm, _ = _parse_frontmatter(files["evidence/e2e/TEMPLATE.md"])
    for key in ("schema_version", "run_id", "date", "status", "agent",
                "driver", "branch", "commit", "url", "browser", "viewport"):
        assert key in fm
```

The existing root-agent-file line-count test must keep passing —
`summary.md` stays short.

---

## 7. What ships — must / should / could

**Must (the top-3 — this PR is worthless without them):**

1. The **`playwright` agent fragment**
   (`summary` / `tools` / `guidance.md`) with the explicit
   `evidence/e2e/YYYY-MM-DD-<slug>/README.md` convention — makes it
   discoverable to all three agents.
2. **`evidence/e2e/TEMPLATE.md`** shipped via the `playwright`
   stack's `_files` — gives agents one schema to copy instead of
   improvising five report styles.
3. The **`.gitignore` policy + Playwright-MCP `--output-dir`** wired
   to `.sunaba/e2e-scratch/` — keeps raw browser output out of git
   and makes curation a real step.

**Should:**

- `docs/agents/playwright.md` canonical detail page (falls out of
  the stack-aware fragment machinery automatically).
- The curation + `N=5` retention rules written into `guidance.md`.

**Could:**

- `scripts/prune-evidence.py` — enforce `N=5`, validate frontmatter.
- A `sunaba` indexer that reads `evidence/e2e/*/README.md`
  frontmatter into a summary table.

## 8. Alternatives considered and rejected

- **Uppercase `E2E/` (the user's literal spelling).** Both reviewers
  rejected it: case-only ambiguity on case-insensitive filesystems,
  and it doesn't match `src/` / `tests/` / `docs/`. Use `E2E` in
  prose, `evidence/e2e/` on disk.
- **Bare root `e2e/` (Codex's pick).** Reasonable, and Codex argued
  the `tests/test_e2e.py` collision is "not meaningful." We took
  Gemini's `evidence/e2e/` instead: a project may legitimately keep
  Playwright *scripts* under `tests/e2e/`, and `evidence/` makes the
  code-vs-artifact split unambiguous at a glance. Low-stakes
  disagreement; either works.
- **A new `--stack e2e`.** Rejected by both — redundant with
  `playwright`, forces a "which stack do I pick" decision.
- **Always-on scaffold (like `SECURITY.md`).** Rejected — pushes
  browser-evidence policy onto non-browser projects.
- **Gitignore all screenshots / commit only the README.** Rejected —
  destroys the review value; for UI work the screenshot *is* the
  evidence.
- **Git LFS.** Rejected — operational overhead unjustified for a
  sandbox generator.
- **"Just use Playwright's HTML report" / "do it in CI."** Rejected —
  `playwright-report/` and `test-results/` are machine-lifecycle,
  regenerated, gitignored. CI is for repeatable regression. This
  convention is for *development-time, agent-driven* verification
  that travels with the PR.

## 9. Honest limits

- **Cooperative, not enforced.** sunaba writes templates and
  guidance; it cannot make an agent take a screenshot or write a
  README. Same honest posture as the `multi-agent` stack.
- **History is forever.** The `N=5` cap trims the working tree, not
  git history. Curation discipline is the real control.
- **`status` is self-reported.** An agent writing `pass` is a claim,
  not a proof gate — the screenshots and steps are what a reviewer
  actually checks.
