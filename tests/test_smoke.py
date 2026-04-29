"""Smoke tests: compose, path safety, stack enumeration."""

from __future__ import annotations

import json
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
