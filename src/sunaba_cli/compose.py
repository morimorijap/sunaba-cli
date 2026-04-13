"""Stack composition: deep-merge devcontainer JSON fragments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def load_base() -> dict[str, Any]:
    return json.loads((TEMPLATES_DIR / "base" / "devcontainer.json").read_text())


def load_stack(name: str) -> dict[str, Any]:
    path = TEMPLATES_DIR / "stacks" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Stack not found: {name}")
    return json.loads(path.read_text())


def available_stacks() -> list[str]:
    return sorted(p.stem for p in (TEMPLATES_DIR / "stacks").glob("*.json"))


def stack_description(name: str) -> str:
    try:
        data = load_stack(name)
    except FileNotFoundError:
        return ""
    return data.get("_description", "")


def deep_merge(base: dict, overlay: dict) -> dict:
    """Merge overlay into base. Lists concatenate (deduplicated), dicts recurse, scalars overwrite."""
    result = dict(base)
    for key, val in overlay.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = deep_merge(result[key], val)
            elif isinstance(result[key], list) and isinstance(val, list):
                # Deduplicate while preserving order
                seen = set()
                merged = []
                for item in result[key] + val:
                    s = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                    if s not in seen:
                        seen.add(s)
                        merged.append(item)
                result[key] = merged
            else:
                result[key] = val
        else:
            result[key] = val
    return result


def compose(stacks: list[str]) -> dict[str, Any]:
    """Compose base + selected stacks into a single devcontainer.json dict."""
    result = load_base()
    for name in stacks:
        overlay = load_stack(name)
        result = deep_merge(result, overlay)
    return result
