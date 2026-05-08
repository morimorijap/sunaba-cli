"""End-to-end tests that exercise the CLI via subprocess.

These tests invoke `python -m sunaba_cli.cli` rather than calling internal
helpers directly, so they catch wiring bugs that pure structural tests miss
(e.g. argument parsing, file write order, project registration interaction).

Docker / devcontainer build is intentionally NOT exercised — that would
require Docker on the test runner. We use `--no-devcontainer` to focus the
E2E on the CLI's file-emission path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Invoke the CLI as a subprocess and return the completed process.

    Uses `python -m sunaba_cli.cli` so we exercise the same entry point a
    `uv tool install` would expose, without depending on the script being
    on PATH.
    """
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "sunaba_cli.cli", *args],
        cwd=str(cwd),
        env=base_env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Redirect the sunaba registry into tmp_path so tests don't share state."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # On macOS, ~/.config is what sunaba writes to; HOME redirect is enough.
    return home


def test_sunaba_new_python_no_devcontainer(tmp_path, isolated_registry):
    """`sunaba new` with --stack python --no-devcontainer emits the host-only file set."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        ["new", "myapp", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    project = workspace / "myapp"
    # Devcontainer files must be absent
    assert not (project / ".devcontainer").exists()
    # Host-portable files must be present
    assert (project / ".mcp.json").exists()
    assert (project / ".vscode" / "settings.json").exists()
    assert (project / "AGENTS.md").exists()
    assert (project / "CLAUDE.md").exists()
    assert (project / "GEMINI.md").exists()
    assert (project / "skills.md").exists()
    assert (project / ".gitignore").exists()


def test_sunaba_new_with_harness_emits_claude_directory(tmp_path, isolated_registry):
    """--stack harness adds .claude/, claudedocs/, and a stronger AGENTS.md."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        [
            "new",
            "harnessapp",
            "--stack",
            "python",
            "--stack",
            "harness",
            "--no-devcontainer",
            "--no-prompt",
        ],
        cwd=workspace,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    project = workspace / "harnessapp"

    # Harness `_files` contributions
    settings_path = project / ".claude" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    assert "permissions" in settings
    assert "hooks" in settings

    assert (project / ".claude" / "hooks" / "verify.sh").exists()
    assert (project / ".claude" / "skills" / "impact-map" / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "verify-change" / "SKILL.md").exists()
    assert (project / ".claude" / "agents" / "planner.md").exists()
    assert (project / ".claude" / "agents" / "reviewer.md").exists()
    assert (project / ".claude" / "agents" / "verifier.md").exists()
    assert (project / "claudedocs" / "README.md").exists()
    assert (project / "claudedocs" / "traces" / ".gitkeep").exists()

    # AGENTS.md should be the harness ratchet version, not the generic seed.
    agents_md = (project / "AGENTS.md").read_text()
    assert "Ratchet log" in agents_md
    assert len(agents_md.splitlines()) <= 60


def test_sunaba_new_default_stack_does_not_emit_harness_files(tmp_path, isolated_registry):
    """A project without --stack harness must not contain .claude/settings.json."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        ["new", "plain", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    project = workspace / "plain"
    assert not (project / ".claude").exists()
    assert not (project / "claudedocs").exists()


def test_sunaba_rebuild_add_harness_emits_claude(tmp_path, isolated_registry):
    """`sunaba rebuild --add harness` on an existing project emits the harness files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # First create without harness.
    r1 = _run(
        ["new", "lift", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr

    project = workspace / "lift"
    assert not (project / ".claude").exists()

    # Now add harness.
    r2 = _run(
        ["rebuild", "lift", "--add", "harness", "--yes"],
        cwd=workspace,
    )
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"

    assert (project / ".claude" / "settings.json").exists()
    assert (project / ".claude" / "hooks" / "verify.sh").exists()


def test_sunaba_rebuild_remove_harness_reports_orphans(tmp_path, isolated_registry):
    """`sunaba rebuild --remove harness` reports the orphan files but does NOT delete."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create with harness.
    r1 = _run(
        [
            "new",
            "drop",
            "--stack",
            "python",
            "--stack",
            "harness",
            "--no-devcontainer",
            "--no-prompt",
        ],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr

    project = workspace / "drop"
    settings_before = (project / ".claude" / "settings.json").read_text()

    # Remove the harness.
    r2 = _run(
        ["rebuild", "drop", "--remove", "harness", "--yes"],
        cwd=workspace,
    )
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"

    # Output must mention orphans + the file paths.
    combined = r2.stdout + r2.stderr
    assert "orphan" in combined.lower() or "left in place" in combined.lower()
    assert ".claude/settings.json" in combined

    # The harness files MUST still be on disk (no auto-delete).
    assert (project / ".claude" / "settings.json").exists()
    assert (project / ".claude" / "settings.json").read_text() == settings_before
    assert (project / "AGENTS.md").exists()


def test_sunaba_idempotent_rebuild_same_stacks_makes_no_changes(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    r1 = _run(
        [
            "new",
            "idem",
            "--stack",
            "python",
            "--stack",
            "harness",
            "--no-devcontainer",
            "--no-prompt",
        ],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr

    r2 = _run(
        [
            "rebuild",
            "idem",
            "--stack",
            "python",
            "--stack",
            "harness",
            "--dry-run",
        ],
        cwd=workspace,
    )
    assert r2.returncode == 0, f"stderr: {r2.stderr}"
    # If everything is unchanged, the rebuild reports nothing-to-change or all '=' markers.
    combined = r2.stdout
    assert "unchanged" in combined or "Nothing to change" in combined


def test_sunaba_new_existing_directory_errors(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "exists").mkdir()

    result = _run(
        ["new", "exists", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode != 0
    assert "already exists" in result.stderr or "already exists" in result.stdout


def test_sunaba_stacks_lists_harness():
    """`sunaba stacks` output includes the harness stack."""
    result = _run(["stacks"], cwd=Path.cwd())
    assert result.returncode == 0
    assert "harness" in result.stdout
