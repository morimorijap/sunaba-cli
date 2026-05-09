"""Structural tests for stack-aware agent file composition (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sunaba_cli.cli import (
    _build_agent_files,
    _build_config_files,
    _inject_between_delimiters,
    _splice_user_region,
    _STACKS_DELIMITER_END,
    _STACKS_DELIMITER_START,
    _USER_DELIMITER_END,
    _USER_DELIMITER_START,
)


def test_inject_between_delimiters_replaces_body():
    text = "before\n<!-- A -->\nold body\n<!-- B -->\nafter\n"
    out = _inject_between_delimiters(text, "<!-- A -->", "<!-- B -->", "new body")
    assert "old body" not in out
    assert "new body" in out
    assert out.startswith("before\n")
    assert out.endswith("after\n")


def test_inject_between_delimiters_no_markers_returns_unchanged():
    text = "no markers here"
    out = _inject_between_delimiters(text, "<!-- A -->", "<!-- B -->", "x")
    assert out == text


def test_python_only_emits_uv_advice_no_npm():
    files = _build_config_files("p", ["python"])
    agents = files["AGENTS.md"]
    assert "uv" in agents.lower()
    assert "uv run pytest" in agents
    # The Python summary fragment doesn't mention npm test.
    assert "npm test" not in agents
    assert "npm run build" not in agents


def test_nextjs_only_emits_npm_no_uv_pytest():
    files = _build_config_files("p", ["nextjs"])
    agents = files["AGENTS.md"]
    assert "npm" in agents.lower()
    assert "uv run pytest" not in agents


def test_python_plus_nextjs_has_both_sections():
    files = _build_config_files("p", ["python", "nextjs"])
    agents = files["AGENTS.md"]
    assert "uv run pytest" in agents
    assert "npm" in agents


def test_per_stack_docs_generated_when_guidance_exists():
    files = _build_config_files("p", ["python", "nextjs"])
    assert "docs/agents/python.md" in files
    assert "docs/agents/nextjs.md" in files
    # Stacks without a guidance.md fragment should NOT produce a doc page.
    files_aws = _build_config_files("p", ["aws"])
    assert "docs/agents/aws.md" not in files_aws


def test_claude_skill_has_frontmatter():
    files = _build_config_files("p", ["python"])
    skill = files[".claude/skills/sunaba-python/SKILL.md"]
    assert skill.startswith("---\n")
    assert "name: sunaba-python" in skill
    assert "description:" in skill


def test_skills_md_contains_only_selected_tools():
    files = _build_config_files("p", ["python"])
    sk = files["skills.md"]
    assert "uv" in sk
    # Don't include nextjs tooling when nextjs not selected.
    assert "vercel" not in sk.lower()


def test_agents_md_under_60_lines_for_realistic_combos():
    for stacks in [
        ["python"],
        ["nextjs"],
        ["python", "nextjs"],
        ["python", "agents"],
        ["python", "nextjs", "agents", "azure"],
    ]:
        files = _build_config_files("p", stacks)
        for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            line_count = len(files[fname].splitlines())
            assert line_count <= 60, f"{fname} has {line_count} lines for {stacks}"


def test_stack_aware_idempotent_regeneration():
    a = _build_config_files("p", ["python", "nextjs"])
    b = _build_config_files("p", ["python", "nextjs"])
    assert a == b


def test_stack_order_preserved_in_root_files():
    files = _build_config_files("p", ["nextjs", "python"])
    text = files["AGENTS.md"]
    # `nextjs` summary line appears before `python` summary line because
    # we passed nextjs first.
    nextjs_idx = text.lower().index("nextjs")
    python_idx = text.lower().index("python")
    assert nextjs_idx < python_idx


def test_user_region_splice_preserves_existing_content():
    new = (
        "header\n"
        f"{_USER_DELIMITER_START}\n"
        "regenerated body\n"
        f"{_USER_DELIMITER_END}\n"
        "footer\n"
    )
    existing = (
        "old header\n"
        f"{_USER_DELIMITER_START}\n"
        "MY CUSTOM EDITS\n"
        f"{_USER_DELIMITER_END}\n"
        "old footer\n"
    )
    out = _splice_user_region(new, existing)
    assert "MY CUSTOM EDITS" in out
    assert "regenerated body" not in out
    assert out.startswith("header\n")
    assert out.endswith("footer\n")


def test_user_region_splice_no_markers_passthrough():
    new = "no markers here"
    existing = "also no markers"
    assert _splice_user_region(new, existing) == new


def test_stacks_delimiter_present_in_base_files():
    """Base templates must carry the SUNABA STACKS delimiters or the
    composer cannot inject."""
    from sunaba_cli.cli import _AGENT_FILES_BASE_DIR

    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "skills.md"):
        body = (_AGENT_FILES_BASE_DIR / fname).read_text()
        assert _STACKS_DELIMITER_START in body, fname
        assert _STACKS_DELIMITER_END in body, fname


def test_harness_overrides_stack_aware_agents_md():
    """When --stack harness comes after stack-aware-composed AGENTS.md,
    the harness `_files` map wins."""
    files = _build_config_files("p", ["python", "harness"])
    agents = files["AGENTS.md"]
    # Harness AGENTS.md has a "Ratchet log" section the stack-aware base
    # doesn't ship.
    assert "Ratchet log" in agents


def test_stack_without_fragments_is_silent():
    """Selecting a stack with no fragments (e.g. azure today) shouldn't
    crash or emit broken docs/.claude paths for that stack."""
    files = _build_config_files("p", ["azure"])
    assert "docs/agents/azure.md" not in files
    assert ".claude/skills/sunaba-azure/SKILL.md" not in files
    # The base AGENTS.md still exists (with empty SUNABA STACKS section).
    assert "AGENTS.md" in files
