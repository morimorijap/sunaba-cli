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
    """A project without --stack harness must not contain harness-specific paths.

    Note: stack-aware composition (since Phase 2) does emit
    `.claude/skills/sunaba-<stack>/SKILL.md` for stacks with a
    guidance.md fragment. Those are *not* harness-specific.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        ["new", "plain", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    project = workspace / "plain"
    # Harness-specific paths must not exist.
    assert not (project / ".claude" / "settings.json").exists()
    assert not (project / ".claude" / "hooks").exists()
    assert not (project / ".claude" / "agents").exists()
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
    # Harness-specific paths must not yet exist.
    assert not (project / ".claude" / "settings.json").exists()

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


# --- Stack-aware (Phase 2) E2E ---


def test_stack_aware_agents_md_reflects_python_stack(tmp_path, isolated_registry):
    """`sunaba new --stack python` produces an AGENTS.md with python-specific guidance."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        ["new", "py", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode == 0, result.stderr

    project = workspace / "py"
    agents = (project / "AGENTS.md").read_text()
    assert "uv run pytest" in agents
    # The nextjs *summary fragment* should NOT be present. Match on a
    # fragment-specific phrase rather than a generic word like "vercel"
    # which can legitimately appear in the base Secrets section.
    assert "Node 22" not in agents
    assert "NEXT_PUBLIC_*" not in agents


def test_stack_aware_emits_per_stack_docs(tmp_path, isolated_registry):
    """Stacks with a guidance.md fragment produce docs/agents/<stack>.md."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        [
            "new",
            "twostack",
            "--stack",
            "python",
            "--stack",
            "nextjs",
            "--no-devcontainer",
            "--no-prompt",
        ],
        cwd=workspace,
    )
    assert result.returncode == 0, result.stderr

    project = workspace / "twostack"
    assert (project / "docs" / "agents" / "python.md").exists()
    assert (project / "docs" / "agents" / "nextjs.md").exists()


def test_stack_aware_emits_claude_skill_with_frontmatter(tmp_path, isolated_registry):
    """A `--stack python` project ships .claude/skills/sunaba-python/SKILL.md
    with YAML frontmatter for Claude's progressive disclosure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run(
        ["new", "skl", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert result.returncode == 0, result.stderr

    skill = (
        workspace / "skl" / ".claude" / "skills" / "sunaba-python" / "SKILL.md"
    )
    assert skill.exists()
    body = skill.read_text()
    assert body.startswith("---\n")
    assert "name: sunaba-python" in body


def test_stack_aware_user_region_preserved_across_sync(tmp_path, isolated_registry):
    """Editing the SUNABA USER region survives a subsequent `sunaba sync`."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    r1 = _run(
        ["new", "edits", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr

    project = workspace / "edits"
    agents_path = project / "AGENTS.md"
    original = agents_path.read_text()
    # Insert a sentinel inside the user region.
    edited = original.replace(
        "<!-- SUNABA USER START -->",
        "<!-- SUNABA USER START -->\nSENTINEL_42_PRESERVE_ME",
        1,
    )
    agents_path.write_text(edited)

    # Run sync. For stack-aware projects, sync regenerates everything but
    # splices the existing USER region back in.
    r2 = _run(["sync", "edits"], cwd=workspace)
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"

    final = agents_path.read_text()
    assert "SENTINEL_42_PRESERVE_ME" in final


# --- Multi-agent (Phase 5) E2E ---


def test_sunaba_new_with_multi_agent_emits_full_structure(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "ma", "--stack", "python", "--stack", "multi-agent",
         "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    project = workspace / "ma"
    # Coordination state
    assert (project / ".agents" / "multi-agent" / "tasks.yaml").exists()
    assert (project / ".agents" / "multi-agent" / "schema.json").exists()
    assert (project / ".agents" / "multi-agent" / "README.md").exists()
    # Helper script
    assert (project / "scripts" / "agent-task.py").exists()
    # Docs
    assert (project / "docs" / "multi-agent" / "orchestration.md").exists()
    assert (project / "docs" / "multi-agent" / "sharding.md").exists()
    assert (
        project / "docs" / "multi-agent" / "subagent-prompt-template.md"
    ).exists()
    # Stack-aware fragment landed in root AGENTS.md.
    agents = (project / "AGENTS.md").read_text()
    assert "multi-agent" in agents
    assert "tasks.yaml" in agents


def test_agent_task_help_runs(tmp_path, isolated_registry):
    """The generated helper script must at least respond to --help.
    Pure-function tests cover the rest; this one catches argparse
    wiring regressions."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "ah", "--stack", "multi-agent",
         "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    script = workspace / "ah" / "scripts" / "agent-task.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=str(workspace / "ah"),
    )
    assert proc.returncode == 0, proc.stderr
    assert "claim" in proc.stdout
    assert "check-owns" in proc.stdout
    assert "overlap" in proc.stdout


# --- Rules + Autopilot (Phase 4) E2E ---


def test_sunaba_new_with_rules_emits_multi_target_renders(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "rl", "--stack", "python", "--stack", "rules",
         "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    project = workspace / "rl"
    assert (project / ".cursor" / "rules" / "python-tests.mdc").exists()
    assert (project / ".claude" / "rules" / "python-tests.md").exists()
    assert (project / "docs" / "agents" / "rules" / "python-tests.md").exists()
    cursor = (project / ".cursor" / "rules" / "python-tests.mdc").read_text()
    claude = (project / ".claude" / "rules" / "python-tests.md").read_text()
    assert "globs:" in cursor
    assert "paths:" in claude


def test_sunaba_new_with_autopilot_emits_full_structure(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "ap",
         "--stack", "python",
         "--stack", "harness",
         "--stack", "autopilot",
         "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    project = workspace / "ap"
    assert (project / ".claude" / "hooks" / "verify.sh").exists()
    assert (project / ".claude" / "agents" / "planner.md").exists()
    assert (project / ".codex" / "agents" / "verifier.toml").exists()
    assert (project / ".codex" / "hooks" / "verify.sh").exists()
    assert (project / ".githooks" / "pre-push").exists()
    assert (project / "docs" / "agents" / "subagent-dispatch.md").exists()
    assert (project / "docs" / "agents" / "gemini-autopilot-limitations.md").exists()
    # Autopilot's planner overrides harness's because it comes later.
    planner = (project / ".claude" / "agents" / "planner.md").read_text()
    assert "claudedocs/plans/" in planner


def test_autopilot_pre_push_hook_blocks_main_in_real_repo(tmp_path, isolated_registry):
    """Wire the generated pre-push hook into a real `git` repo and verify
    that pushing to refs/heads/main is rejected."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "bp", "--stack", "python", "--stack", "autopilot",
         "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    project = workspace / "bp"

    subprocess.run(
        ["chmod", "+x", str(project / ".githooks" / "pre-push")], check=True
    )
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=str(project), check=True,
    )

    proc = subprocess.run(
        ["bash", str(project / ".githooks" / "pre-push")],
        input="refs/heads/main 0000 refs/heads/main 0000\n",
        capture_output=True,
        text=True,
        cwd=str(project),
    )
    assert proc.returncode != 0
    assert "main" in proc.stderr.lower()


# --- Secrets (Phase 3) E2E ---


def test_sunaba_new_writes_expanded_gitignore(tmp_path, isolated_registry):
    """`sunaba new` writes the expanded baseline `.gitignore` regardless of stack."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "gi", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    gi = (workspace / "gi" / ".gitignore").read_text()
    # New baseline patterns
    assert "*.pem" in gi
    assert "**/serviceAccount*.json" in gi
    assert ".claude/settings.local.json" in gi
    # Old baseline patterns still there
    assert ".env" in gi
    assert "node_modules/" in gi


def test_sunaba_new_with_secrets_stack_emits_docs_and_pre_commit(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        [
            "new", "sek",
            "--stack", "python",
            "--stack", "secrets",
            "--no-devcontainer", "--no-prompt",
        ],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    project = workspace / "sek"
    assert (project / ".pre-commit-config.yaml").exists()
    assert (project / ".gitleaks.toml").exists()
    assert (project / ".github" / "workflows" / "gitleaks.yml").exists()
    assert (project / "docs" / "secrets" / "README.md").exists()
    assert (project / "docs" / "secrets" / "azure-foundry-apim-gemini-cosmos.md").exists()


def test_sync_gitignore_dry_run_does_not_write(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r1 = _run(
        ["new", "ud", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr
    project = workspace / "ud"
    # Hand-edit the .gitignore down to a smaller subset (legacy shape).
    (project / ".gitignore").write_text(".env\nnode_modules/\n")
    # Snapshot before
    before = (project / ".gitignore").read_text()
    r2 = _run(["sync-gitignore", "ud", "--dry-run"], cwd=workspace)
    assert r2.returncode == 0, r2.stderr
    after = (project / ".gitignore").read_text()
    assert before == after  # not written
    assert "dry run" in (r2.stdout + r2.stderr).lower()


def test_sync_gitignore_writes_baseline_and_preserves_user_lines(tmp_path, isolated_registry):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r1 = _run(
        ["new", "uw", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr
    project = workspace / "uw"
    # Replace gitignore with a legacy + custom-line mix.
    (project / ".gitignore").write_text(
        ".env\nnode_modules/\nmy-custom-dir/\n# my comment\n"
    )
    r2 = _run(["sync-gitignore", "uw"], cwd=workspace)
    assert r2.returncode == 0, r2.stderr
    final = (project / ".gitignore").read_text()
    # Baseline patterns now present.
    assert "*.pem" in final
    assert "**/serviceAccount*.json" in final
    # User-specific line preserved.
    assert "my-custom-dir/" in final


def test_rebuild_does_not_overwrite_gitignore(tmp_path, isolated_registry):
    """User edits to `.gitignore` survive `sunaba rebuild`."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r1 = _run(
        ["new", "rb", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr
    project = workspace / "rb"
    # User edits .gitignore.
    (project / ".gitignore").write_text(".env\nMY_CUSTOM_GITIGNORE_LINE\n")
    r2 = _run(["rebuild", "rb", "--add", "secrets", "--yes"], cwd=workspace)
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"
    final = (project / ".gitignore").read_text()
    assert "MY_CUSTOM_GITIGNORE_LINE" in final


def test_sunaba_new_writes_security_md(tmp_path, isolated_registry):
    """`sunaba new` writes a SECURITY.md from the base template."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r = _run(
        ["new", "sec", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r.returncode == 0, r.stderr
    body = (workspace / "sec" / "SECURITY.md").read_text()
    assert "Reporting a Vulnerability" in body
    # The fixed template must not direct reporters to public Issues
    # nor mention stack-specific (autopilot/multi-agent) sections.
    assert "Open a normal GitHub issue" not in body
    assert "Autonomy (`--stack autopilot`)" not in body
    assert "Multi-agent (`--stack multi-agent`)" not in body


def test_rebuild_does_not_overwrite_security_md(tmp_path, isolated_registry):
    """User edits to `SECURITY.md` survive `sunaba rebuild` — the file is
    written by `new` only, not by `_build_config_files`.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    r1 = _run(
        ["new", "secrb", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr
    project = workspace / "secrb"
    (project / "SECURITY.md").write_text("# Custom security policy\nreport here\n")
    r2 = _run(["rebuild", "secrb", "--add", "secrets", "--yes"], cwd=workspace)
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"
    assert (project / "SECURITY.md").read_text() == (
        "# Custom security policy\nreport here\n"
    )


def test_legacy_static_mode_uses_verbatim_copy(tmp_path, isolated_registry):
    """Legacy projects without `agent_files` in registry default to static
    copy. We simulate this by manually rewriting the registry entry."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    r1 = _run(
        ["new", "leg", "--stack", "python", "--no-devcontainer", "--no-prompt"],
        cwd=workspace,
    )
    assert r1.returncode == 0, r1.stderr

    # Force the registry entry to legacy "static" mode.
    registry_path = (
        Path(os.environ.get("HOME", "")) / ".config" / "sunaba-cli" / "registry.json"
    )
    assert registry_path.exists(), f"registry not at expected path {registry_path}"
    reg = json.loads(registry_path.read_text())
    reg["leg"]["agent_files"] = "static"
    registry_path.write_text(json.dumps(reg, indent=2))

    # sync should now copy templates/agents/base/AGENTS.md verbatim
    # (no per-stack content injected — empty SUNABA STACKS section).
    r2 = _run(["sync", "leg"], cwd=workspace)
    assert r2.returncode == 0, f"stderr: {r2.stderr}\nstdout: {r2.stdout}"
    project = workspace / "leg"
    agents = (project / "AGENTS.md").read_text()
    # Static copy of base/AGENTS.md has the delimiters but NO injected content.
    assert "<!-- SUNABA STACKS START -->" in agents
    assert "uv run pytest" not in agents
