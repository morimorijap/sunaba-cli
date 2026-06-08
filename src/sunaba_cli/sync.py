"""Agent instruction file sync and project registry."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TypedDict

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
AGENTS_DIR = TEMPLATES_DIR / "agents" / "base"
CONFIG_DIR = Path.home() / ".config" / "sunaba-cli"
REGISTRY_PATH = CONFIG_DIR / "registry.json"

AGENT_FILES = ["AGENTS.md", "CLAUDE.md", "skills.md"]


class ProjectEntry(TypedDict, total=False):
    path: str
    stacks: list[str]
    agent_files: str  # "static" | "stack-aware"


def _load_raw_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def _normalize_entry(value) -> ProjectEntry:
    """Normalize a registry entry. Supports legacy string format (path only).

    Legacy entries (without `agent_files`) default to "static" so existing
    projects keep the verbatim-copy sync semantics they were created with.
    """
    if isinstance(value, str):
        return {"path": value, "stacks": [], "agent_files": "static"}
    return {
        "path": value.get("path", ""),
        "stacks": value.get("stacks", []),
        "agent_files": value.get("agent_files", "static"),
    }


def load_registry() -> dict[str, ProjectEntry]:
    """Load registry and normalize all entries to the new format."""
    raw = _load_raw_registry()
    return {name: _normalize_entry(val) for name, val in raw.items()}


def _save_registry(reg: dict[str, ProjectEntry]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))


def register_project(
    name: str,
    path: Path,
    stacks: list[str],
    *,
    agent_files: str = "stack-aware",
) -> None:
    """Register or update a project in the registry.

    `agent_files` defaults to "stack-aware" so newly created projects
    pick up regenerated `AGENTS.md` etc. on `sunaba sync`. Existing
    entries preserve whichever mode they were created with — they
    don't silently flip to stack-aware on a re-register call.
    """
    reg = load_registry()
    existing = reg.get(name) or {}
    reg[name] = {
        "path": str(path.resolve()),
        "stacks": list(stacks),
        "agent_files": existing.get("agent_files", agent_files),
    }
    _save_registry(reg)


def get_project(name: str) -> ProjectEntry | None:
    return load_registry().get(name)


def list_projects() -> dict[str, ProjectEntry]:
    return load_registry()


def _stacks_emit_path(stacks: list[str], relpath: str) -> bool:
    """True if any of `stacks` declares `relpath` in its `_files` map.

    Used by sync to avoid clobbering files that are owned by a stack
    template (e.g. `--stack harness` ships its own AGENTS.md).
    """
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if not stack_path.exists():
            continue
        data = json.loads(stack_path.read_text())
        if relpath in (data.get("_files") or {}):
            return True
    return False


def copy_agent_files(
    target_dir: Path, *, skip: set[str] | None = None
) -> list[str]:
    """Copy agent instruction files to target directory. Returns list of copied files.

    Validates that the target directory is real (not a symlink) and that
    each destination file does not escape the target via symlinks.

    `skip` is a set of basenames to leave alone. Used so sync does not
    clobber files that a selected stack owns via its `_files` map.
    """
    skip = skip or set()
    resolved_target = target_dir.resolve()
    copied = []
    for fname in AGENT_FILES:
        if fname in skip:
            continue
        src = AGENTS_DIR / fname
        if not src.exists():
            continue
        dest = target_dir / fname
        # Reject if destination is a symlink pointing outside target_dir
        if dest.exists() and dest.is_symlink():
            continue
        # Verify resolved path stays within target directory
        if dest.exists() and not dest.resolve().is_relative_to(resolved_target):
            continue
        shutil.copy2(src, dest)
        copied.append(fname)
    return copied


def _skip_for_stacks(stacks: list[str]) -> set[str]:
    """Return the set of agent-file basenames a stack list claims via `_files`."""
    return {fname for fname in AGENT_FILES if _stacks_emit_path(stacks, fname)}


def _stack_aware_sync(project_path: Path, stacks: list[str]) -> list[str]:
    """Regenerate stack-aware agent files for a project, preserving the
    `<!-- SUNABA USER START/END -->` region of any pre-existing file.

    Lazy-imports the cli module to avoid circular import (cli imports sync).
    """
    from . import cli as cli_module

    skip = _skip_for_stacks(stacks)
    files = cli_module._build_agent_files(stacks)
    copied: list[str] = []
    for relpath, content in files.items():
        # Don't regenerate files that a stack `_files` map owns —
        # those are written directly by `sunaba new` / `sunaba rebuild`.
        # (Skip is keyed by basename; agent files live at root.)
        basename = Path(relpath).name
        if basename in skip and "/" not in relpath:
            continue

        target = project_path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not target.is_symlink():
            existing = target.read_text()
            content = cli_module._splice_user_region(content, existing)
        target.write_text(content)
        copied.append(relpath)
    return copied


def sync_project(name: str) -> tuple[Path | None, list[str]]:
    """Sync agent files for a registered project. Returns (project_path, copied_files).

    - Static-mode projects: copy `templates/agents/base/*.md` verbatim
      (skipping basenames any selected stack owns via `_files`). This is
      the legacy behavior pre-Phase-2.
    - Stack-aware projects: regenerate via the cli's
      `_build_agent_files()` and write each output preservatively (the
      file's `<!-- SUNABA USER START/END -->` region survives across
      regenerations).
    """
    entry = get_project(name)
    if entry is None:
        return None, []
    project_path = Path(entry["path"])
    if not project_path.exists():
        return None, []

    stacks = entry.get("stacks") or []
    mode = entry.get("agent_files", "static")

    if mode == "stack-aware" and stacks:
        return project_path, _stack_aware_sync(project_path, stacks)

    skip = _skip_for_stacks(stacks)
    copied = copy_agent_files(project_path, skip=skip)
    return project_path, copied


def sync_all() -> list[tuple[str, Path, list[str]]]:
    """Sync agent files for all registered projects."""
    results = []
    for name, entry in load_registry().items():
        project_path = Path(entry["path"])
        if not project_path.exists():
            continue
        stacks = entry.get("stacks") or []
        mode = entry.get("agent_files", "static")
        if mode == "stack-aware" and stacks:
            copied = _stack_aware_sync(project_path, stacks)
        else:
            skip = _skip_for_stacks(stacks)
            copied = copy_agent_files(project_path, skip=skip)
        results.append((name, project_path, copied))
    return results
