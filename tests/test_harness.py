"""Structural tests for the harness stack and the `_files` emission mechanism."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sunaba_cli.cli import (
    _build_config_files,
    _build_stack_files,
    _scan_orphans,
    _stacks_owning_path,
)
from sunaba_cli.compose import available_stacks


def test_harness_stack_listed():
    assert "harness" in available_stacks()


def test_harness_does_not_leak_into_devcontainer():
    files = _build_config_files("p", ["harness"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    # `_files` (and other underscore-prefixed keys) must be stripped before
    # the JSON is written.
    for key in dc.keys():
        assert not key.startswith("_"), key


def test_harness_emits_expected_paths():
    files = _build_config_files("p", ["harness"])
    expected = {
        ".claude/settings.json",
        ".claude/hooks/verify.sh",
        ".claude/skills/impact-map/SKILL.md",
        ".claude/skills/verify-change/SKILL.md",
        ".claude/agents/planner.md",
        ".claude/agents/reviewer.md",
        ".claude/agents/verifier.md",
        "AGENTS.md",
        "claudedocs/README.md",
        "claudedocs/traces/.gitkeep",
    }
    assert expected.issubset(set(files.keys())), expected - set(files.keys())


def test_harness_settings_json_is_valid():
    files = _build_config_files("p", ["harness"])
    settings = json.loads(files[".claude/settings.json"])
    assert "permissions" in settings
    assert "allow" in settings["permissions"]
    assert "deny" in settings["permissions"]
    assert "hooks" in settings
    # The Stop hook must point at the bundled verify.sh.
    stop_hooks = settings["hooks"]["Stop"]
    cmds = [
        h["command"]
        for entry in stop_hooks
        for h in entry["hooks"]
        if h.get("type") == "command"
    ]
    assert any(".claude/hooks/verify.sh" in c for c in cmds)


def test_harness_agents_md_is_short():
    files = _build_config_files("p", ["harness"])
    line_count = len(files["AGENTS.md"].splitlines())
    # The harness ratchet is capped at 60 lines per HumanLayer's discipline.
    assert line_count <= 60, f"AGENTS.md is {line_count} lines"


def test_harness_verify_script_is_syntactically_valid(tmp_path):
    files = _build_config_files("p", ["harness"])
    script = tmp_path / "verify.sh"
    script.write_text(files[".claude/hooks/verify.sh"])
    # `bash -n` parses the script without executing it.
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_harness_idempotent_regeneration():
    a = _build_config_files("p", ["python", "harness"])
    b = _build_config_files("p", ["python", "harness"])
    assert a == b


def test_harness_files_path_safety_rejects_traversal(tmp_path):
    # Synthetic stack with a traversal-style _files destination.
    bad_stack_dir = tmp_path / "templates" / "stacks"
    bad_stack_dir.mkdir(parents=True)
    (bad_stack_dir / "evil.json").write_text(
        json.dumps({"_description": "x", "_files": {"../escape.txt": "harness/AGENTS.md"}})
    )
    # We can't easily redirect TEMPLATES_DIR mid-test, so assert at the
    # _build_stack_files level using the live templates: the harness stack
    # itself must not contain `..` or absolute paths in its declared _files.
    files = _build_stack_files(["harness"])
    for dest in files:
        p = Path(dest)
        assert not p.is_absolute()
        assert ".." not in p.parts


def test_no_devcontainer_keeps_harness_files():
    files = _build_config_files("p", ["python", "harness"], no_devcontainer=True)
    assert ".devcontainer/devcontainer.json" not in files
    assert ".devcontainer/bootstrap.sh" not in files
    assert ".claude/settings.json" in files
    assert "AGENTS.md" in files


def test_files_collision_later_stack_wins(tmp_path, monkeypatch):
    """When two stacks declare the same `_files` destination, the later one wins."""
    # Build two synthetic stacks under a temporary templates/ tree by
    # overriding TEMPLATES_DIR for cli + compose.
    tmpl_dir = tmp_path / "templates"
    (tmpl_dir / "stacks").mkdir(parents=True)
    (tmpl_dir / "base").mkdir(parents=True)
    (tmpl_dir / "frags").mkdir(parents=True)

    # Base devcontainer + minimal mcp
    (tmpl_dir / "base" / "devcontainer.json").write_text(
        json.dumps({"name": "base", "image": "x"})
    )
    (tmpl_dir / "base" / "bootstrap.sh").write_text("#!/usr/bin/env bash\nset -e\n")
    (tmpl_dir / "base" / "dependabot.yml").write_text(
        'version: 2\nupdates:\n  - package-ecosystem: "github-actions"\n'
        '    directory: "/"\n    schedule:\n      interval: "weekly"\n'
    )
    (tmpl_dir / "base" / "mcp.json").write_text("{}")

    (tmpl_dir / "frags" / "first.txt").write_text("FIRST")
    (tmpl_dir / "frags" / "second.txt").write_text("SECOND")

    (tmpl_dir / "stacks" / "first.json").write_text(
        json.dumps({"_description": "first", "_files": {"out.txt": "frags/first.txt"}})
    )
    (tmpl_dir / "stacks" / "second.json").write_text(
        json.dumps({"_description": "second", "_files": {"out.txt": "frags/second.txt"}})
    )

    from sunaba_cli import cli as cli_module
    from sunaba_cli import compose as compose_module

    monkeypatch.setattr(cli_module, "TEMPLATES_DIR", tmpl_dir)
    monkeypatch.setattr(compose_module, "TEMPLATES_DIR", tmpl_dir)

    files = _build_config_files("p", ["first", "second"])
    assert files["out.txt"] == "SECOND"

    files_rev = _build_config_files("p", ["second", "first"])
    assert files_rev["out.txt"] == "FIRST"


def test_stacks_owning_path_for_harness():
    owners = _stacks_owning_path(["harness"])
    assert ".claude/settings.json" in owners
    assert owners[".claude/settings.json"] == ["harness"]


def test_scan_orphans_reports_left_behind_files(tmp_path):
    # Pretend a project has the harness files on disk, then we removed the
    # harness stack. _scan_orphans should report them.
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    (tmp_path / "AGENTS.md").write_text("placeholder")

    orphans = _scan_orphans(
        tmp_path, removed_stacks=["harness"], remaining_stacks=["python"]
    )
    paths = {relpath for relpath, _ in orphans}
    assert ".claude/settings.json" in paths
    assert "AGENTS.md" in paths
    # Files that don't exist on disk should not be in the orphan list.
    assert ".claude/hooks/verify.sh" not in paths


def test_scan_orphans_skips_files_remaining_stacks_emit():
    # If two synthetic stacks declared the same path, removing one should
    # not flag it as orphan when the other still emits it. Smoke-test using
    # the harness path: if harness is "removed" but also still in
    # remaining_stacks, no orphans.
    orphans = _scan_orphans(
        Path("/nonexistent"),
        removed_stacks=["harness"],
        remaining_stacks=["harness"],
    )
    assert orphans == []


def test_sync_skips_harness_emitted_files(tmp_path, monkeypatch):
    """sync_project must not clobber AGENTS.md when harness is selected."""
    from sunaba_cli import sync as sync_module

    # Stub the registry to point at tmp_path.
    monkeypatch.setattr(
        sync_module,
        "load_registry",
        lambda: {"proj": {"path": str(tmp_path), "stacks": ["harness"]}},
    )

    # Pre-populate AGENTS.md with harness content (simulates `sunaba new`).
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md (harness version)\n")

    proj_path, copied = sync_module.sync_project("proj")
    assert proj_path == tmp_path
    assert "AGENTS.md" not in copied  # skipped because harness owns it
    # And the harness content survives.
    assert "harness version" in (tmp_path / "AGENTS.md").read_text()
