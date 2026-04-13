"""Smoke tests: compose, path safety, stack enumeration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sunaba_cli.cli import _safe_target, _build_config_files
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
