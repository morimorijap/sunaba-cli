"""Structural tests for the secrets stack and `.gitignore` baseline (Phase 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sunaba_cli.cli import (
    _build_config_files,
    _default_gitignore,
    _merge_gitignore,
)
from sunaba_cli.compose import available_stacks


def test_secrets_stack_listed():
    assert "secrets" in available_stacks()


def test_default_gitignore_covers_secret_file_family():
    text = _default_gitignore()
    expected = [
        ".env",
        ".env.*",
        "!.env.example",
        "*.pem",
        "*.key",
        "*.p12",
        "id_rsa*",
        "id_ed25519*",
        "**/serviceAccount*.json",
        "**/*-firebase-adminsdk-*.json",
        "credentials.json",
        ".claude/settings.local.json",
        ".envrc",
        ".aws/",
        ".azure/",
        ".gcloud/",
    ]
    for pattern in expected:
        assert pattern in text, f"missing {pattern!r} from baseline gitignore"


def test_secrets_stack_emits_expected_paths():
    files = _build_config_files("p", ["secrets"])
    expected = {
        ".pre-commit-config.yaml",
        ".gitleaks.toml",
        ".github/workflows/gitleaks.yml",
        "docs/secrets/README.md",
        "docs/secrets/vercel.md",
        "docs/secrets/firebase.md",
        "docs/secrets/aws.md",
        "docs/secrets/gcp.md",
        "docs/secrets/azure-foundry-apim-gemini-cosmos.md",
    }
    missing = expected - set(files.keys())
    assert not missing, f"secrets stack didn't emit: {missing}"


def test_pre_commit_pins_gitleaks_to_a_tag():
    text = _build_config_files("p", ["secrets"])[".pre-commit-config.yaml"]
    assert "gitleaks/gitleaks" in text
    assert "id: gitleaks" in text
    assert "rev: v" in text
    # Must not pin to a moving target.
    assert "rev: main" not in text
    assert "rev: HEAD" not in text


def test_gitleaks_toml_has_env_example_allowlist():
    text = _build_config_files("p", ["secrets"])[".gitleaks.toml"]
    assert "[allowlist]" in text
    # The path patterns are regex-escaped (`\.env\.example`); look for
    # the un-escaped form in a flattened view.
    flat = text.replace("\\", "")
    assert ".env.example" in flat


def test_azure_apim_doc_present_with_key_phrases():
    doc = _build_config_files("p", ["secrets"])[
        "docs/secrets/azure-foundry-apim-gemini-cosmos.md"
    ]
    # The doc must explain the four core moving parts.
    assert "Key Vault" in doc
    assert "API Management" in doc or "APIM" in doc
    assert "Gemini" in doc
    assert "Cosmos" in doc
    assert "Managed Identity" in doc
    # And include the actual policy snippet shape (not just prose).
    assert "validate-azure-ad-token" in doc
    assert "x-goog-api-key" in doc


def test_secrets_stack_idempotent():
    a = _build_config_files("p", ["secrets"])
    b = _build_config_files("p", ["secrets"])
    assert a == b


def test_secrets_section_in_base_agents_md():
    """The Phase 3 Secrets section must be present in the base AGENTS.md
    so every project's composed AGENTS.md inherits it."""
    files = _build_config_files("p", ["python"])
    agents = files["AGENTS.md"]
    assert "## Secrets" in agents
    assert "exactly one" in agents
    # Match across possible line wrapping — the phrase "repository root"
    # is likely split when the section is rendered as Markdown bullets.
    flat = " ".join(agents.split())
    assert "repository root" in flat


def test_merge_gitignore_preserves_user_lines():
    baseline = "# Environment files\n.env\n.env.*\n*.pem\n"
    existing = "# my project\n.env\nweb/build/\nmy-secret-thing/\n"
    merged, extras = _merge_gitignore(existing, baseline)
    # Baseline content survives.
    assert ".env" in merged
    assert "*.pem" in merged
    # User-only lines preserved.
    assert "web/build/" in merged
    assert "my-secret-thing/" in merged
    assert len(extras) == 2


def test_merge_gitignore_no_extras_when_baseline_covers_all():
    baseline = ".env\n*.pem\n"
    existing = ".env\n*.pem\n"
    merged, extras = _merge_gitignore(existing, baseline)
    assert extras == []


def test_secrets_stack_does_not_emit_into_devcontainer():
    """The `_files` map must not leak into devcontainer.json."""
    import json
    files = _build_config_files("p", ["secrets"])
    dc = json.loads(files[".devcontainer/devcontainer.json"])
    for key in dc:
        assert not key.startswith("_"), key


def test_rebuild_does_not_include_gitignore_in_diff_set():
    """`.gitignore` must not be regenerated on `rebuild`. We assert at
    the `_build_config_files` level — `.gitignore` is written only by
    `sunaba new`."""
    files = _build_config_files("p", ["python", "secrets"])
    assert ".gitignore" not in files
