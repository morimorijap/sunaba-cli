# Phase 4b — `rebuild` keeps local edits

> Part of [`2026-11-21-maruda-followup/`](README.md). Phase 4 of the
> [maruda adoption](../2026-09-24-maruda-adoption/README.md) listed
> "`.new` proposal files instead of overwrites, `settings.json` merge"
> (maruda `setup.sh:183-198`, `248-256`).

## Problem

`sunaba rebuild` wrote every generated file that differed from the disk,
after one "Apply these changes?" prompt that listed paths, not
contents. Anything a user had tuned was lost:

- `.claude/settings.json` permissions and hooks, which matters more now
  that Phase 4a adds a PreToolUse hook there;
- `verify.sh`, workflows, `devcontainer.json`;
- the `<!-- SUNABA USER START/END -->` region of `AGENTS.md`. `sunaba
  sync` preserves it, but `rebuild` did not. Reproduced on `main`: a line
  added there disappeared after `sunaba rebuild p --add secrets --yes`.

## Why maruda's approach needs a record here

maruda writes `<file>.new` whenever the target exists and differs. That
is fine for a one-shot installer. sunaba's `rebuild` is routine (add a
stack, pick up a template fix), so "differs" must separate *sunaba's
older output* (update it) from *the user's edit* (keep it). Only a
record of what sunaba wrote can tell them apart.

## Design

- **Record.** `sunaba new` and every `rebuild` write
  `.sunaba/generated.json`: per generated path, the sha256 of what sunaba
  generated, with the USER-region body left out. It is committed with the
  project, so the whole team's rebuilds agree.
- **Plan per file** (`regen.plan`):

  | On disk | Action |
  |---|---|
  | missing | create |
  | equal to the regenerated file (USER region carried over) | unchanged |
  | fingerprint equals the record | update |
  | `--overwrite` | update (the old behavior) |
  | `.claude/settings.json`, valid JSON | merge |
  | otherwise (edited, or not in the record) | keep; write `<path>.new` |

- **USER region.** Carried over into every regenerated agent file and
  excluded from the fingerprint, so editing it never triggers a proposal.
  This fixes the `AGENTS.md` loss above.
- **Settings merge** (`regen.merge_claude_settings`), three-way with the
  previously generated JSON (stored in the record) as the base:
  - an item in the template but not the base is new: append it;
  - an item in the base that the user lacks was removed on purpose: keep
    it removed;
  - nothing the user has is changed or removed;
  - without a base (projects from before the record), anything the user
    lacks counts as new **except `permissions.allow`**: adding an allow
    rule widens what runs unprompted, so it needs proof the user did not
    remove it. `deny`, `ask` and hooks only tighten.
  - unexpected shapes or invalid JSON fall back to a `.new` proposal.
- **Projects without a record** are treated as all-edited: every differing
  file gets a `.new`, with a message pointing at `--overwrite`. The record
  is written after that run, so later rebuilds update in place.
- `.new` files are written through `_safe_target` like any other write
  (no symlinks, no escape), are not made executable, and are not
  rewritten when already up to date. The record keeps the sha256 of each
  `.new` sunaba wrote; a `.new` that no longer matches it is the user's
  work in progress and is left alone.
- **A proposed file keeps its previous record.** The user's copy still
  descends from the old output, and for the settings merge the old base
  is what marks template entries as new. Advancing it would make the next
  rebuild treat a proposed-but-never-merged deny rule as already known.
- A file whose fingerprint matches but whose USER region the regenerated
  file has no place for (a stack template without the markers, such as
  `harness/AGENTS.md`) is proposed, not updated.
- A settings base that is not a JSON object counts as no base.

## Review

Codex (`codex exec --sandbox read-only`) reviewed the first version and
found four defects, each now covered by a test that fails without the fix:
the USER region dropped by a template without markers; an edited `.new`
overwritten; a damaged base (`"[]"`) re-adding allow rules; and a proposed
settings file advancing the base so a new deny rule was never merged.

## Rejected

- **Hash in the user-level registry** (`~/.config/sunaba-cli`): per
  machine, so a teammate's rebuild would see every file as edited.
- **Union merge of settings without a base** (maruda's jq merge): re-adds
  allow rules a user deliberately removed.
- **Interactive per-file prompts**: breaks `-y` and scripted use; `.new`
  plus `git diff` is reviewable.

## Tests

`tests/test_rebuild_keeps_edits.py`: the record matches the files; untouched
files update; an edited file is kept with a `.new` beside it; proposals are
idempotent; `--overwrite`; `--dry-run` writes nothing; a project without a
record; the `AGENTS.md` USER region survives (the regression); the settings
merge adds a newly introduced deny and keeps a user's removal and addition;
invalid settings get a proposal; the base is not advanced while settings
are proposed; an edited `.new` is left alone and a stale one refreshed; a
template without USER markers does not drop the region; merge unit tests
(no allow widening without a base or with a damaged one, base-aware
additions, idempotence, shape checks).
