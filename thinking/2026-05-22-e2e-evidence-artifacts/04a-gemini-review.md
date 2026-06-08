# 04a — Gemini CLI review

> Reviewer: **Gemini CLI**, model `gemini-3-flash-preview`. Invoked
> non-interactively (`gemini -p`, plan/read-only approval mode) against
> [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) on
> 2026-05-22. The first two attempts failed (`gemini-3-flash-preview`
> capacity / quota exhaustion — itself a small data point on Gemini
> availability); the third attempt succeeded. Output reproduced
> verbatim below; maintainers' synthesis lives in
> [`05-proposal.md`](05-proposal.md).

---

# E2E Evidence Artifacts: Design Review & Proposal

## A. Maturity Scoring (1–5)

*   **Evidence durability: 1/5** — Currently, browser interactions are ephemeral. Screenshots taken by MCP servers live in transient temp directories or the agent's internal memory. Once the session ends, the visual proof is lost.
*   **Reviewability: 1/5** — A reviewer can see "I ran the test" in a chat log if shared, but there is no side-by-side artifact in the PR to verify UI state, layout, or specific error states.
*   **Agent guidance: 1/5** — There is no `playwright` fragment in `sunaba-cli`. Agents have no "house rules" on where to put screenshots or how to report findings beyond the standard tool output.
*   **Cross-agent parity: 3/5** — All three agents share the same MCP infrastructure (`@playwright/mcp`), providing a level playing field, but they lack a unified protocol for persisting that output.

## B. Directory + Naming Contract

**Position: Use `evidence/e2e/YYYY-MM-DD-slug/`**

1.  **Lower-case `evidence/` over `E2E/`:** `E2E` is often a directory for *code* (test scripts). `evidence/` semantically separates *test results/artifacts* from *test logic*. Lowercase follows the project's convention (`src/`, `tests/`, `docs/`).
2.  **Naming:** `YYYY-MM-DD-slug` (e.g., `2026-05-22-login-validation`).
    *   **Why slug?** A random ID or `HHMMSS` is hard for humans to scan in a file tree. A slug allows a developer to find the "login fix" evidence without opening five `README.md` files.
    *   **Sortability:** Leading ISO date ensures chronological sorting.
3.  **Location:** **Root-level `evidence/`**. Placing it under `docs/` implies it is static documentation; placing it under `tests/` implies it is code. Root-level signals this is a primary lifecycle artifact of the repository.

## C. The `README.md` Run-Report Schema

Every run folder must contain a `README.md`. It should use YAML frontmatter to allow for future automation/indexing.

```markdown
---
date: 2026-05-22
status: PASS | FAIL | PARTIAL
agent: Claude-3.5-Sonnet
commit: a1b2c3d
feature: User Authentication
---

# E2E Run: [Brief Slug]

## 🎯 Goal
Identify the primary objective of this browser session.

## 🛠 Environment
- **URL:** `http://localhost:3000`
- **Browser:** Chromium (Playwright MCP)
- **Branch:** `feat/login-fix`

## 📑 Execution Steps
1. Navigate to `/login`.
2. Enter invalid credentials.
3. [Screenshot 1] Verify error message appearance.
4. Enter valid credentials.
5. [Screenshot 2] Verify redirect to `/dashboard`.

## 🖼 Evidence
![Error State](./error-message.png)
*Figure 1: The red toast notification appears as expected.*

![Success State](./dashboard-load.png)
*Figure 2: User successfully landed on the dashboard.*

## 📈 Result & Follow-ups
- **Result:** PASS
- **Notes:** CSS alignment on the error toast is slightly off (2px), but functional.
- **Issues Found:** Created issue #42 for the alignment bug.
```

## D. Integration into sunaba

1.  **Stack Update:** Fold this into the existing `playwright` stack. A separate `--stack e2e` is overkill; if you have Playwright, you want evidence.
2.  **New File Paths:**
    *   `templates/agents/fragments/playwright/guidance.md`:
        > "When performing E2E verification:
        > 1. Create a directory: `evidence/e2e/YYYY-MM-DD-short-slug/`.
        > 2. Save all relevant screenshots to this folder.
        > 3. Write a `README.md` using the project template explaining your steps and findings.
        > 4. Reference screenshots inline in the README."
    *   `templates/agents/fragments/playwright/summary.md`:
        > "Uses Playwright MCP for browser-based verification and produces durable evidence artifacts in `evidence/e2e/`."
3.  **MCP Wiring:** Update `templates/base/mcp.json` (or the playwright specific version) to pass an environment variable or flag to the MCP server if it supports a default download path, but primarily, the **Agent Guidance** must instruct the agent to move files from the MCP's default temp path to the `evidence/` path.
4.  **`.gitignore` additions:**
    ```
    # Playwright internals
    test-results/
    playwright-report/
    blob-report/
    playwright/.cache/

    # Evidence (Policy: keep the README, curate the images)
    # See section E for the specific strategy
    ```

## E. The Binary-Bloat Decision

**Policy: Commit Curated PNGs + Hard Retention Cap (N=5)**

Git LFS is overkill for a "disposable sandbox" project. The "Commit only README" (Option 3) defeats the purpose of "Evidence."

*   **The Rule:** Agents are instructed to only keep "Milestone Screenshots."
*   **Retention:** `sunaba sync` or a provided helper script should flag or automatically delete `evidence/e2e/` folders older than the 5 most recent runs.
*   **Optimization:** Guidance should suggest saving as `.webp` if the MCP/Agent supports it, or ensure screenshots are focused on the viewport rather than full-page unless necessary.

## F. Cross-Agent Matrix

| Feature | Claude Code | Codex CLI | Gemini CLI |
| :--- | :--- | :--- | :--- |
| **Drive Playwright MCP** | High | High | Medium (Reliant on system-wide MCP) |
| **Follow Folder Convention** | High | Medium | High |
| **Read Prior Evidence** | High | High | Medium |

*   **Claude Code:** Best-in-class at following multi-step file creation/movement workflows.
*   **Codex CLI:** Strong, but often requires a more forceful "System Prompt" to not skip the "boring" documentation step.
*   **Gemini CLI:** Excellent at summarizing existing `evidence/` to provide context for the *next* run.

## G. Tests (`pytest`)

1.  **Scaffold Test:** Verify that `sunaba new --stack playwright` creates the `evidence/e2e/` directory and a `.gitkeep`.
2.  **Fragment Test:** Verify that `AGENTS.md` contains the string "Create a directory: `evidence/e2e/`" when the playwright stack is active.
3.  **Template Test:** Verify that a `templates/playwright/E2E_TEMPLATE.md` exists and is valid Markdown.
4.  **Ignore Test:** Verify `.gitignore` contains `test-results/` but *allows* `evidence/`.

## H. Top-3 Picks

1.  **The `playwright` Agent Fragment:** Specifically the `guidance.md` that defines the "capture and document" loop.
2.  **The `evidence/e2e/` Directory + `.gitkeep`:** Establishes the physical "home" for artifacts.
3.  **The `README.md` Template:** Provides the structure so agents don't hallucinate different reporting styles.

## I. Push-back

*   **"Why not CI?"** CI evidence is for *regression*. Agent evidence is for *development-time verification*. They serve different masters. A dev wants to see why the agent *thought* it fixed the bug before they ever push to CI.
*   **Naming Collision:** Ensure the documentation clarifies that `tests/e2e/` is for Playwright **scripts** (code) and `evidence/e2e/` is for **results** (artifacts).
*   **Manual vs. Auto:** We must accept that sometimes agents will forget to write the README. This is a "Cooperative Convention," not a hard-coded binary gate. We should frame this as "Professionalism for Agents."
