"""Smoke tests: compose, path safety, stack enumeration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunaba_cli.cli import (
    _build_config_files,
    _build_dependabot_simple,
    _missing_host_commands,
    _safe_target,
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
