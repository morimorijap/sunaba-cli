"""Regenerating stack files without discarding local edits.

`sunaba new` records a fingerprint of every file it generates in
`.sunaba/generated.json`. `sunaba rebuild` compares each file on disk
with that record:

- unchanged since sunaba wrote it -> update it in place;
- edited locally, or never recorded -> leave it alone and write the
  regenerated version next to it as `<path>.new`;
- `.claude/settings.json` -> three-way merge (see `merge_claude_settings`).

The `<!-- SUNABA USER START/END -->` region of agent files is the user's
by design: it is carried over on every regeneration and left out of the
fingerprint, so editing it never turns a file into a `.new` proposal.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MANIFEST_PATH = ".sunaba/generated.json"
MANIFEST_VERSION = 1

# Files merged key by key instead of proposed as `.new`. The manifest keeps
# the generated JSON as the merge base for these.
JSON_MERGE_PATHS = frozenset({".claude/settings.json"})

USER_START = "<!-- SUNABA USER START -->"
USER_END = "<!-- SUNABA USER END -->"

PROPOSAL_SUFFIX = ".new"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(text: str) -> str:
    """sha256 of `text` with the body of the USER region removed."""
    s = text.find(USER_START)
    e = text.find(USER_END)
    if s != -1 and e != -1 and e > s:
        text = text[: s + len(USER_START)] + text[e:]
    return _sha256(text)


def _user_body(text: str) -> str:
    s = text.find(USER_START)
    e = text.find(USER_END)
    if s == -1 or e == -1 or e < s:
        return ""
    return text[s + len(USER_START): e].strip()


def load_manifest(project_dir: Path) -> dict[str, dict] | None:
    """The recorded files, or None when the project has no usable record
    (created before the manifest existed, or the file is damaged)."""
    path = project_dir / MANIFEST_PATH
    if not path.is_file() or path.is_symlink():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return None
    # An entry may hold only "proposal": a file sunaba never recorded as its
    # own output, for which it has written a `.new`.
    return {
        k: v for k, v in files.items()
        if isinstance(v, dict)
        and (isinstance(v.get("sha256"), str) or isinstance(v.get("proposal"), str))
    }


def _generated_entry(rel: str, text: str) -> dict:
    entry: dict = {"sha256": fingerprint(text)}
    if rel in JSON_MERGE_PATHS:
        entry["base"] = text
    return entry


def manifest_text(
    files: dict[str, str],
    steps: list[Step] | None = None,
    previous: dict[str, dict] | None = None,
) -> str:
    """The record after writing `files`, or after carrying out `steps`.

    A file left as a `.new` proposal keeps its previous entry: the user's
    copy still descends from what sunaba wrote before, and for the settings
    merge the old base is what tells new template entries from removed
    ones. Advancing it would make a later rebuild skip what was proposed.
    """
    previous = previous or {}
    by_path = {s.relpath: s for s in steps or []}
    entries: dict[str, dict] = {}
    for rel in sorted(files):
        step = by_path.get(rel)
        if step is not None and step.action == "propose":
            entry = dict(previous[rel]) if rel in previous else {}
            entry.pop("proposal", None)
            if step.proposal_sha:
                entry["proposal"] = step.proposal_sha
            if entry:
                entries[rel] = entry
            continue
        entries[rel] = _generated_entry(rel, files[rel])
    doc = {
        "_comment": "Written by sunaba. Fingerprints of the files sunaba last generated, "
        "so `sunaba rebuild` can tell your edits from its own. Commit this file.",
        "version": MANIFEST_VERSION,
        "files": entries,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --- .claude/settings.json ---------------------------------------------------


def _hook_keys(entries: list) -> set[tuple[str, str]]:
    keys = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks") or []:
            if isinstance(h, dict):
                keys.add((entry.get("matcher", ""), h.get("command", "")))
    return keys


def merge_claude_settings(user: dict, template: dict, base: dict | None) -> tuple[dict, list[str]]:
    """Add what the template newly introduced to the user's settings.

    `base` is the settings sunaba generated last time. An item that is in
    the template but not in `base` is new and gets added; an item in `base`
    that the user's file lacks was removed on purpose and stays removed.
    Nothing the user has is ever changed or removed.

    Without a base (a project from before the manifest), every template
    item the user lacks counts as new, except `permissions.allow`: adding
    an allow rule widens what runs without asking, so it is never done
    without knowing the user did not remove it.

    Raises ValueError when the user's file does not have the expected shape;
    the caller then proposes a `.new` file instead.
    """
    if not isinstance(user, dict):
        raise ValueError("settings is not a JSON object")
    merged = copy.deepcopy(user)
    added: list[str] = []
    # A base that is not an object (a damaged record) is no base: treating
    # it as known-and-empty would re-add allow rules the user removed.
    base_known = isinstance(base, dict)
    base = base if base_known else {}

    t_perms = template.get("permissions") or {}
    b_perms = base.get("permissions") or {}
    for key in ("deny", "ask", "allow"):
        if key == "allow" and not base_known:
            continue
        new_items = [
            item for item in t_perms.get(key) or []
            if not (base_known and item in (b_perms.get(key) or []))
        ]
        if not new_items:
            continue
        perms = merged.setdefault("permissions", {})
        if not isinstance(perms, dict) or not isinstance(perms.get(key, []), list):
            raise ValueError(f"permissions.{key} is not a list")
        current = perms.setdefault(key, [])
        for item in new_items:
            if item not in current:
                current.append(item)
                added.append(f"permissions.{key}: {item}")

    b_hooks = base.get("hooks") or {}
    for event, t_entries in (template.get("hooks") or {}).items():
        base_keys = _hook_keys(b_hooks.get(event) or []) if base_known else set()
        for t_entry in t_entries:
            for h in t_entry.get("hooks") or []:
                key = (t_entry.get("matcher", ""), h.get("command", ""))
                if key in base_keys:
                    continue
                hooks = merged.setdefault("hooks", {})
                if not isinstance(hooks, dict) or not isinstance(hooks.get(event, []), list):
                    raise ValueError(f"hooks.{event} is not a list")
                entries = hooks.setdefault(event, [])
                if key in _hook_keys(entries):
                    continue
                entries.append({"matcher": key[0], "hooks": [copy.deepcopy(h)]})
                added.append(f"hooks.{event}: {key[1]}")

    for k, v in template.items():
        if k in ("permissions", "hooks") or k in merged:
            continue
        if base_known and k in base:
            continue
        merged[k] = copy.deepcopy(v)
        added.append(k)

    return merged, added


# --- planning ----------------------------------------------------------------


@dataclass
class Step:
    relpath: str
    # create | update | unchanged | propose | merge
    action: str
    # Text to write, and where (relpath, or relpath + ".new"); None = no write.
    content: str | None = None
    dest: str | None = None
    detail: str = ""
    # For proposals: sha256 of the `.new` sunaba wrote, so a later rebuild
    # can tell its own stale proposal from one the user has edited.
    proposal_sha: str | None = None


def plan(
    project_dir: Path,
    files: dict[str, str],
    manifest: dict[str, dict] | None,
    *,
    overwrite: bool,
    safe_target: Callable[[Path, str], Path],
    splice_user_region: Callable[[str, str], str],
) -> list[Step]:
    recorded = manifest or {}
    steps: list[Step] = []
    for rel, generated in files.items():
        full = safe_target(project_dir, rel)
        if not full.exists() and not full.is_symlink():
            steps.append(Step(rel, "create", generated, rel))
            continue
        if full.is_symlink():
            # The write refuses it; surface it as a change so the user sees it.
            steps.append(Step(rel, "update", generated, rel))
            continue
        existing = full.read_text()
        candidate = splice_user_region(generated, existing)
        if existing == candidate:
            steps.append(Step(rel, "unchanged"))
            continue
        entry = recorded.get(rel)
        known = entry is not None and isinstance(entry.get("sha256"), str)
        untouched = known and entry["sha256"] == fingerprint(existing)
        # The fingerprint ignores the USER region, so it cannot see that the
        # regenerated file has no place for it (a stack template without
        # the markers). Updating would drop the user's region.
        body = _user_body(existing)
        region_lost = bool(body) and body not in candidate
        if overwrite or (untouched and not region_lost):
            steps.append(Step(rel, "update", candidate, rel))
            continue
        if rel in JSON_MERGE_PATHS:
            step = _plan_json_merge(rel, existing, generated, entry if known else None)
            if step is not None:
                steps.append(step)
                continue
        proposal = rel + PROPOSAL_SUFFIX
        prop_path = safe_target(project_dir, proposal)
        if region_lost and untouched:
            why = "the regenerated file has no SUNABA USER region to keep yours in"
        elif known:
            why = "edited locally"
        else:
            why = "not recorded as generated by sunaba"
        sha = _sha256(candidate)
        recorded_proposal = entry.get("proposal") if entry else None
        if prop_path.is_file() and not prop_path.is_symlink():
            current = prop_path.read_text()
            if current == candidate:
                steps.append(Step(rel, "propose", None, None,
                                  f"{why}; {proposal} is up to date", proposal_sha=sha))
                continue
            if _sha256(current) != recorded_proposal:
                # Not the proposal sunaba last wrote: the user is working in it.
                steps.append(Step(rel, "propose", None, None,
                                  f"{why}; {proposal} has your edits, left as is "
                                  f"(delete it for a fresh proposal)",
                                  proposal_sha=recorded_proposal))
                continue
        steps.append(Step(rel, "propose", candidate, proposal, f"{why} -> {proposal}",
                          proposal_sha=sha))
    return steps


def _plan_json_merge(rel: str, existing: str, generated: str, entry: dict | None) -> Step | None:
    try:
        user = json.loads(existing)
        template = json.loads(generated)
        base = json.loads(entry["base"]) if entry and isinstance(entry.get("base"), str) else None
        merged, added = merge_claude_settings(user, template, base)
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return None
    if not added:
        return Step(rel, "unchanged", detail="your edits kept; nothing new to add")
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    return Step(rel, "merge", text, rel, "added " + "; ".join(added))
