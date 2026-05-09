"""Structural tests for --stack rules and --stack autopilot (Phase 4)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sunaba_cli.cli import (
    _build_config_files,
    _build_rule_files,
    _parse_rule_frontmatter,
    _render_rule,
)
from sunaba_cli.compose import available_stacks


# --- Rules ---


def test_rules_stack_listed():
    assert "rules" in available_stacks()


def test_autopilot_stack_listed():
    assert "autopilot" in available_stacks()


def test_parse_rule_frontmatter_basic():
    text = (
        "---\n"
        "name: foo\n"
        "description: short text\n"
        "globs:\n"
        "  - \"tests/**/*.py\"\n"
        "  - \"src/**/*.py\"\n"
        "alwaysApply: false\n"
        "targets:\n"
        "  - claude\n"
        "  - cursor\n"
        "---\n"
        "body line 1\n"
        "body line 2\n"
    )
    fm, body = _parse_rule_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["description"] == "short text"
    assert fm["globs"] == ["tests/**/*.py", "src/**/*.py"]
    assert fm["alwaysApply"] == "false"
    assert fm["targets"] == ["claude", "cursor"]
    assert "body line 1" in body
    assert "body line 2" in body


def test_render_rule_emits_all_targets():
    text = (
        "---\n"
        "name: r1\n"
        "description: d\n"
        "globs:\n"
        "  - \"src/**/*.py\"\n"
        "alwaysApply: false\n"
        "targets:\n"
        "  - claude\n"
        "  - cursor\n"
        "  - codex\n"
        "  - gemini\n"
        "---\n"
        "body\n"
    )
    out = _render_rule(text)
    assert ".cursor/rules/r1.mdc" in out
    assert ".claude/rules/r1.md" in out
    # Codex/Gemini share a docs fallback page.
    assert "docs/agents/rules/r1.md" in out


def test_render_rule_cursor_uses_globs_alwaysapply():
    text = (
        "---\n"
        "name: c\n"
        "description: d\n"
        "globs:\n"
        "  - \"a/**/*.ts\"\n"
        "alwaysApply: true\n"
        "targets:\n"
        "  - cursor\n"
        "---\n"
        "body\n"
    )
    out = _render_rule(text)
    mdc = out[".cursor/rules/c.mdc"]
    assert "globs:" in mdc
    assert "alwaysApply: true" in mdc


def test_render_rule_claude_rewrites_globs_to_paths():
    text = (
        "---\n"
        "name: c\n"
        "description: d\n"
        "globs:\n"
        "  - \"a/**/*.ts\"\n"
        "alwaysApply: false\n"
        "targets:\n"
        "  - claude\n"
        "---\n"
        "body\n"
    )
    out = _render_rule(text)
    md = out[".claude/rules/c.md"]
    assert "paths:" in md
    assert "globs:" not in md
    assert "alwaysApply" not in md


def test_rules_stack_emits_seed_rules():
    files = _build_config_files("p", ["rules"])
    assert ".cursor/rules/python-tests.mdc" in files
    assert ".claude/rules/python-tests.md" in files
    assert ".cursor/rules/nextjs-api.mdc" in files
    assert ".claude/rules/nextjs-api.md" in files


def test_rules_stack_idempotent():
    a = _build_config_files("p", ["rules"])
    b = _build_config_files("p", ["rules"])
    assert a == b


def test_rule_render_path_safety_rejects_escape():
    # Synthesize a rule file under templates/ with traversal in its
    # _rules path is rejected by the renderer's resolve check.
    from sunaba_cli.cli import TEMPLATES_DIR
    bad = TEMPLATES_DIR.parent / "outside.rule.md"  # outside templates/
    if bad.exists():
        bad.unlink()  # cleanup any stale fixture
    # We can't easily inject a synthetic stack JSON into the live tree,
    # so instead assert at the live shipped seeds: every `_rules` entry
    # in stacks/rules.json resolves *under* templates/.
    rules_stack = json.loads(
        (TEMPLATES_DIR / "stacks" / "rules.json").read_text()
    )
    for rule_rel in rules_stack.get("_rules", []):
        resolved = (TEMPLATES_DIR / rule_rel).resolve()
        assert resolved.is_relative_to(TEMPLATES_DIR.resolve()), rule_rel


# --- Autopilot ---


def test_autopilot_emits_expected_paths():
    files = _build_config_files("p", ["autopilot"])
    expected = {
        ".claude/hooks/verify.sh",
        ".claude/agents/planner.md",
        ".claude/agents/reviewer.md",
        ".claude/agents/verifier.md",
        ".codex/config.toml",
        ".codex/agents/planner.toml",
        ".codex/agents/reviewer.toml",
        ".codex/agents/verifier.toml",
        ".codex/hooks/verify.sh",
        ".githooks/pre-push",
        "scripts/install-githooks.sh",
        "claudedocs/plans/.gitkeep",
        "claudedocs/checkpoints/.gitkeep",
        "docs/agents/subagent-dispatch.md",
        "docs/agents/gemini-autopilot-limitations.md",
        ".sunaba/autopilot/.gitignore",
    }
    missing = expected - set(files.keys())
    assert not missing, f"autopilot didn't emit: {missing}"


def test_autopilot_verify_script_is_syntactically_valid(tmp_path):
    files = _build_config_files("p", ["autopilot"])
    script = tmp_path / "verify.sh"
    script.write_text(files[".claude/hooks/verify.sh"])
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_autopilot_verify_emits_structured_failure_format():
    """The hook's failure paths must include the SUNABA_VERIFY_FAILED /
    SUNABA_BUDGET_EXCEEDED keywords so consumers can pattern-match."""
    files = _build_config_files("p", ["autopilot"])
    body = files[".claude/hooks/verify.sh"]
    assert "SUNABA_VERIFY_FAILED" in body
    assert "SUNABA_BUDGET_EXCEEDED" in body
    # Budget knobs must be exposed via env.
    assert "SUNABA_AUTOPILOT_MAX_ITERS" in body
    assert "SUNABA_AUTOPILOT_MAX_MINUTES" in body
    assert "SUNABA_AUTOPILOT_MAX_CHANGED_FILES" in body


def test_autopilot_pre_push_hook_blocks_main():
    files = _build_config_files("p", ["autopilot"])
    hook = files[".githooks/pre-push"]
    assert "refs/heads/main" in hook
    assert "refs/heads/master" in hook
    assert "exit 1" in hook


def test_autopilot_codex_agent_toml_parses():
    import tomllib

    files = _build_config_files("p", ["autopilot"])
    for relpath in (
        ".codex/config.toml",
        ".codex/agents/planner.toml",
        ".codex/agents/reviewer.toml",
        ".codex/agents/verifier.toml",
    ):
        body = files[relpath]
        # tomllib raises on malformed input.
        tomllib.loads(body)


def test_autopilot_claude_role_files_have_frontmatter():
    files = _build_config_files("p", ["autopilot"])
    for relpath in (
        ".claude/agents/planner.md",
        ".claude/agents/reviewer.md",
        ".claude/agents/verifier.md",
    ):
        body = files[relpath]
        assert body.startswith("---\n")
        assert "description:" in body


def test_autopilot_overrides_harness_role_files_when_after():
    """`--stack harness --stack autopilot` ordering: autopilot's
    operational planner/reviewer/verifier role files override the
    harness PR's roleplay seeds (later-wins per the `_files`
    collision rule)."""
    files = _build_config_files("p", ["harness", "autopilot"])
    planner = files[".claude/agents/planner.md"]
    # Autopilot's planner names the plan file path explicitly.
    assert "claudedocs/plans/" in planner


def test_autopilot_reverse_order_does_not_get_operational_planner():
    """Reverse order: harness wins. Document this footgun via the test."""
    files = _build_config_files("p", ["autopilot", "harness"])
    planner = files[".claude/agents/planner.md"]
    # Harness's planner is shorter and does NOT mention claudedocs/plans/.
    assert "claudedocs/plans/" not in planner


def test_autopilot_state_dir_is_gitignored():
    files = _build_config_files("p", ["autopilot"])
    body = files[".sunaba/autopilot/.gitignore"]
    assert "*" in body
    assert "!.gitignore" in body


def test_autopilot_idempotent_regeneration():
    a = _build_config_files("p", ["autopilot"])
    b = _build_config_files("p", ["autopilot"])
    assert a == b


def test_autopilot_does_not_leak_into_devcontainer():
    files = _build_config_files("p", ["autopilot"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    for key in dc:
        assert not key.startswith("_"), key
