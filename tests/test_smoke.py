"""Smoke tests: compose, path safety, stack enumeration."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from click.testing import CliRunner

from sunaba_cli import cli as cli_module
from sunaba_cli.cli import (
    _build_config_files,
    _build_dependabot_simple,
    _missing_host_commands,
    _safe_target,
    main,
)
from sunaba_cli.compose import available_stacks, compose, deep_merge


def test_available_stacks_nonempty():
    stacks = available_stacks()
    assert len(stacks) >= 5
    assert "python" in stacks
    assert "agents" in stacks


def test_compose_python_has_feature():
    config = compose(["python"])
    features = config.get("features", {})
    assert any("python" in k for k in features)


def test_compose_agents_injects_env():
    config = compose(["agents"])
    env = config.get("remoteEnv", {})
    assert "OPENAI_API_KEY" in env
    assert "ANTHROPIC_API_KEY" in env


def test_base_has_no_secrets_by_default():
    config = compose([])
    assert config.get("remoteEnv", {}) == {}


def test_deep_merge_dedup_list():
    merged = deep_merge({"x": [1, 2]}, {"x": [2, 3]})
    assert merged["x"] == [1, 2, 3]


def test_build_config_files_clean():
    files = _build_config_files("testproj", ["python"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    # Internal keys must be stripped
    assert not any(k.startswith("_") for k in dc)
    assert dc["name"] == "sunaba-testproj"


def test_compose_playwright_adds_browser_cache_mount():
    config = compose(["playwright"])
    mounts = config.get("mounts", [])
    assert any("ms-playwright" in m for m in mounts), mounts
    # Base npm-cache mount must be preserved alongside the playwright cache.
    assert any("npm-cache" in m for m in mounts), mounts


def test_base_mounts_gh_config_volume():
    """gh-config volume is in base because github-cli feature is in base."""
    config = compose([])
    mounts = config.get("mounts", [])
    assert any(
        "source=gh-config" in m and "/.config/gh" in m for m in mounts
    ), mounts


def test_compose_agents_persists_claude_codex_gemini_volumes():
    config = compose(["agents"])
    mounts = config.get("mounts", [])
    targets = {m for m in mounts}
    assert any("source=claude-config" in m and "/.claude" in m for m in targets), mounts
    assert any("source=codex-config" in m and "/.codex" in m for m in targets), mounts
    assert any("source=gemini-config" in m and "/.gemini" in m for m in targets), mounts


def test_compose_aws_persists_aws_config_volume():
    config = compose(["aws"])
    mounts = config.get("mounts", [])
    assert any("source=aws-config" in m and "/.aws" in m for m in mounts), mounts


def test_compose_nextjs_persists_vercel_config_volume():
    config = compose(["nextjs"])
    mounts = config.get("mounts", [])
    assert any(
        "source=vercel-config" in m and "/.local/share/com.vercel.cli" in m
        for m in mounts
    ), mounts


def test_base_bootstrap_defines_helper_and_pre_creates_parent_dirs():
    """The chown helper must be defined before any stack snippet calls it,
    and parent dirs (.local/.config/.local/share) must be pre-created so a
    later child volume mount or `pip install --user` does not run into a
    root-owned parent.
    """
    files = _build_config_files("p", [])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    # Helper defined
    assert "sunaba_fix_config_dir() {" in bootstrap
    # Parent dirs pre-created AND owned by user (mkdir+chown, not install -d
    # which leaves existing root-owned parents alone).
    assert "sudo mkdir -p" in bootstrap
    assert 'sudo chown "$uid:$gid"' in bootstrap
    assert '"$HOME/.config"' in bootstrap
    assert '"$HOME/.local"' in bootstrap
    assert '"$HOME/.local/bin"' in bootstrap
    # gh-config (base mount) is fixed in base
    assert 'sunaba_fix_config_dir "$HOME/.config/gh"' in bootstrap


def test_agents_bootstrap_symlinks_claude_json_into_volume():
    """~/.claude.json (single-file MCP/trust state) is wiped on rebuild;
    must be moved into the persistent ~/.claude volume and symlinked back.
    """
    files = _build_config_files("p", ["agents"])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    assert 'sunaba_fix_config_dir "$HOME/.claude"' in bootstrap
    assert 'sunaba_fix_config_dir "$HOME/.codex"' in bootstrap
    assert 'sunaba_fix_config_dir "$HOME/.gemini"' in bootstrap
    # Symlink-or-move logic for ~/.claude.json
    assert '$HOME/.claude.json' in bootstrap
    assert '$HOME/.claude/claude.json' in bootstrap
    assert "ln -s" in bootstrap


def test_aws_bootstrap_calls_helper_for_aws_dir():
    files = _build_config_files("p", ["aws"])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    assert 'sunaba_fix_config_dir "$HOME/.aws"' in bootstrap


def test_nextjs_bootstrap_calls_helper_for_vercel_dir():
    files = _build_config_files("p", ["nextjs"])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    assert 'sunaba_fix_config_dir "$HOME/.local/share/com.vercel.cli"' in bootstrap


def test_helper_defined_before_stack_snippets():
    """Composition order matters: the helper must appear before any stack
    invocation so bash parses it before reaching the call site.
    """
    files = _build_config_files("p", ["agents", "aws", "nextjs"])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    helper_idx = bootstrap.index("sunaba_fix_config_dir() {")
    first_call_idx = bootstrap.index('sunaba_fix_config_dir "$HOME/.claude"')
    assert helper_idx < first_call_idx


# --- Behavior tests for ~/.claude.json move/symlink/backup ---------------------
#
# These run the relevant slice of agents.json `_bootstrap` against a temp HOME
# to confirm the four scenarios behave as intended:
#   1. only ~/.claude.json (not symlink), no volume copy → moved + symlinked
#   2. both files identical                              → root copy removed,
#                                                          symlink created
#   3. both files differ                                 → root copy backed up
#                                                          as claude.json.import.<ts>.bak,
#                                                          symlink to volume copy
#   4. ~/.claude.json already a valid symlink            → unchanged

def _agents_symlink_snippet() -> str:
    """Extract just the ~/.claude.json move/symlink block from agents.json
    so we can run it without invoking sudo-requiring chown/chmod lines.
    """
    repo_root = Path(__file__).resolve().parent.parent
    data = json.loads(
        (repo_root / "src/sunaba_cli/templates/stacks/agents.json").read_text()
    )
    lines = data["_bootstrap"]
    for i, line in enumerate(lines):
        if 'if [ -f "$HOME/.claude.json"' in line:
            return "set -e\n" + "\n".join(lines[i:])
    raise AssertionError("symlink snippet marker not found in agents.json")


def _run_snippet(home: Path) -> None:
    snippet = _agents_symlink_snippet()
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    subprocess.run(
        ["bash", "-c", snippet], env=env, check=True, capture_output=True
    )


def test_claude_json_moved_into_volume_and_symlinked(tmp_path):
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude.json").write_text("orig")

    _run_snippet(home)

    assert (home / ".claude" / "claude.json").read_text() == "orig"
    link = home / ".claude.json"
    assert link.is_symlink()
    assert link.resolve() == (home / ".claude" / "claude.json").resolve()


def test_claude_json_dedup_when_identical(tmp_path):
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude.json").write_text("same")
    (home / ".claude" / "claude.json").write_text("same")

    _run_snippet(home)

    link = home / ".claude.json"
    assert link.is_symlink()
    assert (home / ".claude" / "claude.json").read_text() == "same"
    # No backup file on identical path
    assert not list((home / ".claude").glob("claude.json.import.*.bak"))


def test_claude_json_conflict_creates_backup(tmp_path):
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude.json").write_text("from-dotfiles")
    (home / ".claude" / "claude.json").write_text("from-volume")

    _run_snippet(home)

    backups = sorted((home / ".claude").glob("claude.json.import.*.bak"))
    assert len(backups) == 1, list((home / ".claude").iterdir())
    assert backups[0].read_text() == "from-dotfiles"
    # Volume version preserved unchanged
    assert (home / ".claude" / "claude.json").read_text() == "from-volume"
    link = home / ".claude.json"
    assert link.is_symlink()
    assert link.resolve() == (home / ".claude" / "claude.json").resolve()


def test_claude_json_existing_symlink_is_left_alone(tmp_path):
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude" / "claude.json").write_text("vol")
    (home / ".claude.json").symlink_to(home / ".claude" / "claude.json")

    _run_snippet(home)

    link = home / ".claude.json"
    assert link.is_symlink()
    assert (home / ".claude" / "claude.json").read_text() == "vol"
    assert not list((home / ".claude").glob("claude.json.import.*.bak"))


def test_composed_bootstrap_passes_bash_syntax_check(tmp_path):
    """All-stacks composition must produce a syntactically valid script."""
    files = _build_config_files(
        "p", ["agents", "aws", "nextjs", "playwright", "python", "docker"]
    )
    script_path = tmp_path / "bootstrap.sh"
    script_path.write_text(files[".devcontainer/bootstrap.sh"])
    result = subprocess.run(
        ["bash", "-n", str(script_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_compose_playwright_bootstrap_installs_chromium_with_deps():
    files = _build_config_files("e2eproj", ["playwright"])
    bootstrap = files[".devcontainer/bootstrap.sh"]
    assert "playwright" in bootstrap
    assert "--with-deps chromium" in bootstrap


def test_mcp_json_playwright_pins_bundled_chromium():
    """Regression: the Playwright MCP server must explicitly pass
    --browser chromium so it uses Playwright's bundled Chromium instead of
    looking for a system Google Chrome install (which devcontainers don't
    have).
    """
    files = _build_config_files("p", ["python"])
    mcp = json.loads(files[".mcp.json"])
    pw_args = mcp["mcpServers"]["playwright"]["args"]
    assert "--browser" in pw_args
    assert pw_args[pw_args.index("--browser") + 1] == "chromium"


def test_safe_target_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        _safe_target(tmp_path, "../escape.txt")


def test_safe_target_rejects_absolute(tmp_path):
    with pytest.raises(ValueError):
        _safe_target(tmp_path, "/etc/passwd")


def test_safe_target_rejects_symlink(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x")
    link = tmp_path / "devcontainer.json"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        _safe_target(tmp_path, "devcontainer.json")


def test_safe_target_allows_normal_relative(tmp_path):
    target = _safe_target(tmp_path, ".devcontainer/devcontainer.json")
    assert target == tmp_path / ".devcontainer" / "devcontainer.json"


def test_no_devcontainer_skips_devcontainer_files():
    files = _build_config_files("hostproj", ["python"], no_devcontainer=True)
    assert ".devcontainer/devcontainer.json" not in files
    assert ".devcontainer/bootstrap.sh" not in files


def test_no_devcontainer_keeps_host_agnostic_files():
    files = _build_config_files("hostproj", ["python"], no_devcontainer=True)
    assert ".mcp.json" in files
    assert ".github/dependabot.yml" in files
    # python stack contributes vscode settings via base file-watcher excludes
    assert ".vscode/settings.json" in files


def test_no_devcontainer_dependabot_drops_devcontainer_ecosystems():
    text = _build_dependabot_simple(["python"], no_devcontainer=True)
    assert "devcontainers" not in text
    assert 'package-ecosystem: "docker"' not in text
    assert "github-actions" in text
    # Stack-specific extras should still flow in
    assert 'package-ecosystem: "uv"' in text


def test_default_dependabot_keeps_devcontainer_ecosystems():
    text = _build_dependabot_simple(["python"])
    assert "devcontainers" in text
    assert "docker" in text


def test_missing_host_commands_reports_only_missing():
    # Stub `which` so only `claude` and `aws` are present; everything else missing.
    present = {"claude", "aws"}
    missing = _missing_host_commands(
        ["aws", "python", "agents"], which=lambda cmd: cmd if cmd in present else None
    )
    cmds = [c for c, _ in missing]
    # Present ones are filtered out
    assert "claude" not in cmds
    assert "aws" not in cmds
    # Missing base agent CLIs and MCP runtime show up
    assert "codex" in cmds
    assert "gemini" in cmds
    assert "npx" in cmds
    assert "uvx" in cmds
    # Missing stack-specific tool shows up (uv for python)
    assert "uv" in cmds
    # `agents` stack has no host requirement of its own
    assert all(c != "az" for c in cmds)


def test_missing_host_commands_empty_when_all_present():
    missing = _missing_host_commands(["python"], which=lambda cmd: f"/usr/bin/{cmd}")
    assert missing == []


def test_upgrade_invokes_uv_binary_with_reinstall(monkeypatch):
    """Regression: `sunaba upgrade` must call the `uv` binary on PATH (not
    `python -m uv`) and use `tool install --reinstall <git-url>` form, since
    `uv tool upgrade` does not accept git URLs.
    """

    class _Result:
        returncode = 0
        stdout = "Installed sunaba-cli"
        stderr = ""

    captured: dict = {}

    def fake_run(cmd, capture_output, text):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(cli_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(main, ["upgrade"])
    assert result.exit_code == 0, result.output

    cmd = captured["cmd"]
    assert cmd[0] == "/usr/bin/uv"
    assert cmd[1:4] == ["tool", "install", "--reinstall"]
    assert cmd[-1].startswith("git+https://github.com/morimorijap/sunaba-cli")


def test_upgrade_errors_when_uv_missing(monkeypatch):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: None)
    runner = CliRunner()
    result = runner.invoke(main, ["upgrade"])
    assert result.exit_code != 0
    assert "uv" in result.output


def test_upgrade_repo_override_normalizes_to_git_prefix(monkeypatch):
    captured: dict = {}

    class _Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(
        cli_module.subprocess,
        "run",
        lambda cmd, **kw: (captured.setdefault("cmd", cmd), _Result())[1],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["upgrade", "--repo", "https://example.com/x"])
    assert result.exit_code == 0, result.output
    assert captured["cmd"][-1] == "git+https://example.com/x"
