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
