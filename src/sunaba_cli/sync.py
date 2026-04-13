"""Agent instruction file sync and project registry."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TypedDict

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
AGENTS_DIR = TEMPLATES_DIR / "agents"
CONFIG_DIR = Path.home() / ".config" / "sunaba-cli"
REGISTRY_PATH = CONFIG_DIR / "registry.json"

AGENT_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "skills.md"]


class ProjectEntry(TypedDict):
    path: str
    stacks: list[str]


def _load_raw_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}


def _normalize_entry(value) -> ProjectEntry:
    """Normalize a registry entry. Supports legacy string format (path only)."""
    if isinstance(value, str):
        return {"path": value, "stacks": []}
    return {"path": value.get("path", ""), "stacks": value.get("stacks", [])}


def load_registry() -> dict[str, ProjectEntry]:
    """Load registry and normalize all entries to the new format."""
    raw = _load_raw_registry()
    return {name: _normalize_entry(val) for name, val in raw.items()}


def _save_registry(reg: dict[str, ProjectEntry]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))


def register_project(name: str, path: Path, stacks: list[str]) -> None:
    reg = load_registry()
    reg[name] = {"path": str(path.resolve()), "stacks": list(stacks)}
    _save_registry(reg)


def get_project(name: str) -> ProjectEntry | None:
    return load_registry().get(name)


def list_projects() -> dict[str, ProjectEntry]:
    return load_registry()


def copy_agent_files(target_dir: Path) -> list[str]:
    """Copy agent instruction files to target directory. Returns list of copied files.

    Validates that the target directory is real (not a symlink) and that
    each destination file does not escape the target via symlinks.
    """
    resolved_target = target_dir.resolve()
    copied = []
    for fname in AGENT_FILES:
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


def sync_project(name: str) -> tuple[Path | None, list[str]]:
    """Sync agent files for a registered project. Returns (project_path, copied_files)."""
    entry = get_project(name)
    if entry is None:
        return None, []
    project_path = Path(entry["path"])
    if not project_path.exists():
        return None, []
    copied = copy_agent_files(project_path)
    return project_path, copied


def sync_all() -> list[tuple[str, Path, list[str]]]:
    """Sync agent files for all registered projects."""
    results = []
    for name, entry in load_registry().items():
        project_path = Path(entry["path"])
        if project_path.exists():
            copied = copy_agent_files(project_path)
            results.append((name, project_path, copied))
    return results
