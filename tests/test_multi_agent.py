"""Structural tests for the multi-agent stack and the agent-task.py helper.

The helper script lives under templates/ (it is a generated artifact).
We import its pure functions by loading the file directly so we can
unit-test the sharding heuristics, owns/path matching, and overlap
detection without running it via subprocess.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from sunaba_cli.cli import _build_config_files
from sunaba_cli.compose import available_stacks


# --- helper: load templates/multi-agent/scripts/agent-task.py as a module ---


def _load_agent_task_module():
    """Import the bundled agent-task.py for pure-function testing.

    Avoids requiring PyYAML at sunaba-cli's test time by stubbing it
    out — the helper's pure functions don't actually call yaml.
    """
    if "yaml" not in sys.modules:
        # Minimal stub. The pure-function tests we run here never call
        # yaml.safe_load / safe_dump.
        import types as _types
        stub = _types.ModuleType("yaml")
        stub.safe_load = lambda *a, **kw: {}    # type: ignore[attr-defined]
        stub.safe_dump = lambda *a, **kw: ""    # type: ignore[attr-defined]
        sys.modules["yaml"] = stub

    from sunaba_cli import cli as _cli
    script_path = (
        _cli.TEMPLATES_DIR
        / "multi-agent"
        / "scripts"
        / "agent-task.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_agent_task_test_module", script_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# --- stack listing + emitted paths ---


def test_multi_agent_stack_listed():
    assert "multi-agent" in available_stacks()


def test_multi_agent_emits_expected_paths():
    files = _build_config_files("p", ["multi-agent"])
    expected = {
        ".agents/multi-agent/tasks.yaml",
        ".agents/multi-agent/schema.json",
        ".agents/multi-agent/README.md",
        "scripts/agent-task.py",
        "docs/multi-agent/orchestration.md",
        "docs/multi-agent/sharding.md",
        "docs/multi-agent/subagent-prompt-template.md",
    }
    missing = expected - set(files.keys())
    assert not missing, f"multi-agent stack didn't emit: {missing}"


def test_multi_agent_does_not_leak_into_devcontainer():
    files = _build_config_files("p", ["multi-agent"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    for k in dc:
        assert not k.startswith("_"), k


def test_multi_agent_idempotent_regeneration():
    a = _build_config_files("p", ["multi-agent"])
    b = _build_config_files("p", ["multi-agent"])
    assert a == b


# --- tasks.yaml + schema.json content ---


def test_tasks_yaml_carries_required_top_level_fields():
    text = _build_config_files("p", ["multi-agent"])[
        ".agents/multi-agent/tasks.yaml"
    ]
    assert "version: 1" in text
    assert "cohort:" in text
    assert "tasks:" in text
    assert "max_agents_env: SUNABA_MULTI_AGENT_MAX" in text
    assert "default_max_agents: 4" in text


def test_schema_json_parses_and_describes_task_status_enum():
    schema_text = _build_config_files("p", ["multi-agent"])[
        ".agents/multi-agent/schema.json"
    ]
    schema = json.loads(schema_text)
    assert schema["type"] == "object"
    task_props = schema["properties"]["tasks"]["items"]["properties"]
    expected_statuses = {
        "pending", "claimed", "in_progress",
        "blocked", "review", "completed", "failed",
    }
    assert set(task_props["status"]["enum"]) == expected_statuses
    # Cohort cap upper-bound is in the schema (2026 industry consensus
    # is 4-8 worktrees per developer).
    cohort = schema["properties"]["cohort"]["properties"]
    assert cohort["default_max_agents"]["maximum"] >= 8


# --- agent-task.py: helper script discipline ---


def test_agent_task_script_is_syntactically_valid():
    """`python -m py_compile` the bundled helper to catch syntax slips."""
    import py_compile
    files = _build_config_files("p", ["multi-agent"])
    # Materialize to a temp file because py_compile wants a path.
    import tempfile
    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w"
    ) as f:
        f.write(files["scripts/agent-task.py"])
        tmp = f.name
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_agent_task_script_documents_exit_codes():
    text = _build_config_files("p", ["multi-agent"])[
        "scripts/agent-task.py"
    ]
    assert "EXIT_OVERLAP" in text
    assert "EXIT_NOT_FOUND" in text
    assert "EXIT_SCHEMA" in text


# --- pure-function tests for the helper ---


def test_recommend_agents_serial_for_one_file():
    m = _load_agent_task_module()
    assert m.recommend_agents(
        files=1, components=1, has_schema_change=False
    ) == 1


def test_recommend_agents_serial_for_schema_change():
    m = _load_agent_task_module()
    assert m.recommend_agents(
        files=20, components=8, has_schema_change=True
    ) == 1


def test_recommend_agents_serial_for_shared_file():
    m = _load_agent_task_module()
    assert m.recommend_agents(
        files=20, components=4, has_schema_change=False, has_shared_file=True
    ) == 1


def test_recommend_agents_two_for_modest_split():
    m = _load_agent_task_module()
    assert m.recommend_agents(
        files=5, components=3, has_schema_change=False
    ) == 2


def test_recommend_agents_caps_at_4_by_default():
    m = _load_agent_task_module()
    # Big task should not exceed default cap.
    assert m.recommend_agents(
        files=80, components=20, has_schema_change=False
    ) == 4


def test_recommend_agents_respects_explicit_cap():
    m = _load_agent_task_module()
    assert m.recommend_agents(
        files=80, components=20, has_schema_change=False, max_cap=2
    ) == 2


def test_has_overlap_detects_glob_vs_concrete():
    m = _load_agent_task_module()
    assert m.has_overlap(["src/auth/**"], ["src/auth/login.ts"])


def test_has_overlap_distinct_modules_no_overlap():
    m = _load_agent_task_module()
    assert not m.has_overlap(["src/auth/**"], ["src/billing/index.ts"])


def test_has_overlap_identical_globs():
    m = _load_agent_task_module()
    assert m.has_overlap(["src/parser/**"], ["src/parser/**"])


def test_path_matches_owns_simple_glob():
    m = _load_agent_task_module()
    assert m.path_matches_owns("src/parser/foo.py", ["src/parser/**"])
    assert not m.path_matches_owns("src/billing/foo.py", ["src/parser/**"])


# --- stack-aware integration ---


def test_multi_agent_summary_appears_in_root_agents_md():
    files = _build_config_files("p", ["python", "multi-agent"])
    agents = files["AGENTS.md"]
    assert "multi-agent" in agents
    assert "tasks.yaml" in agents


def test_multi_agent_guidance_emits_per_stack_doc():
    files = _build_config_files("p", ["multi-agent"])
    assert "docs/agents/multi-agent.md" in files
    body = files["docs/agents/multi-agent.md"]
    assert "cooperative" in body.lower()
    assert "owns:" in body
