"""Structural tests for the secrets stack and `.gitignore` baseline (Phase 3)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
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
        "docs/secrets/THIRD_PARTY_NOTICES.md",
    }
    missing = expected - set(files.keys())
    assert not missing, f"secrets stack didn't emit: {missing}"


def _frozen_gitleaks_rev(text: str) -> tuple[str, str]:
    """Return (commit_sha, version) from `rev: <sha>  # frozen: vX.Y.Z`."""
    m = re.search(r"^\s*rev: ([0-9a-f]{40})\s+# frozen: v(\d+\.\d+\.\d+)\s*$", text, re.M)
    assert m, "pre-commit gitleaks rev must be a 40-hex commit with a `# frozen: vX.Y.Z` comment"
    return m.group(1), m.group(2)


def test_pre_commit_freezes_gitleaks_to_a_commit():
    text = _build_config_files("p", ["secrets"])[".pre-commit-config.yaml"]
    assert "gitleaks/gitleaks" in text
    assert "id: gitleaks" in text
    # A tag can be moved; a commit SHA cannot.
    _frozen_gitleaks_rev(text)


def test_gitleaks_toml_extends_default_rules():
    """Regression: a custom .gitleaks.toml without `[extend] useDefault = true`
    replaces gitleaks' default rule set and detects nothing."""
    text = _build_config_files("p", ["secrets"])[".gitleaks.toml"]
    parsed = tomllib.loads(text)
    assert parsed.get("extend", {}).get("useDefault") is True


def test_gitleaks_workflow_is_hardened():
    text = _build_config_files("p", ["secrets"])[".github/workflows/gitleaks.yml"]
    # gitleaks-action needs a GITLEAKS_LICENSE key on organization repos.
    assert "gitleaks/gitleaks-action" not in text
    assert "pull_request_target" not in text
    assert "permissions:\n  contents: read" in text
    assert "fetch-depth: 0" in text
    assert "persist-credentials: false" in text
    assert "timeout-minutes:" in text
    assert "sudo" not in text
    # The downloaded archive is checksum-verified before it runs.
    assert re.search(r"GITLEAKS_SHA256: [0-9a-f]{64}\n", text)
    assert "sha256sum -c -" in text
    # Matches never reach the (possibly public) Actions log, inline
    # `gitleaks:allow` cannot suppress a finding, and repo-configured diff
    # helpers cannot rewrite what gitleaks reads.
    assert "gitleaks git --redact" in text
    assert "--ignore-gitleaks-allow" in text
    assert "--no-ext-diff --no-textconv" in text


def test_gitleaks_ci_and_pre_commit_pin_the_same_release():
    files = _build_config_files("p", ["secrets"])
    _, frozen = _frozen_gitleaks_rev(files[".pre-commit-config.yaml"])
    m = re.search(r"GITLEAKS_VERSION: (\S+)", files[".github/workflows/gitleaks.yml"])
    assert m and m.group(1) == frozen


def test_gitleaks_toml_allowlists_no_paths():
    """Path allowlists are a scan bypass: a real key pasted into
    .env.example must still be caught."""
    parsed = tomllib.loads(_build_config_files("p", ["secrets"])[".gitleaks.toml"])
    for allowlist in [parsed.get("allowlist", {}), *parsed.get("allowlists", [])]:
        assert not allowlist.get("paths"), allowlist


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


# --- Tests that run the real gitleaks binary -------------------------------
# Skipped when `gitleaks` is not on PATH, unless SUNABA_REQUIRE_GITLEAKS=1
# (set by the `gitleaks` CI job, which installs the pinned binary).

_GITLEAKS = shutil.which("gitleaks")
_needs_gitleaks = pytest.mark.skipif(
    _GITLEAKS is None and os.environ.get("SUNABA_REQUIRE_GITLEAKS") != "1",
    reason="gitleaks binary not on PATH",
)

# Built at runtime so this file never contains a literal that gitleaks
# (scanning this repository) would flag.
_FAKE_AWS_KEY_ID = "AKIA" + "QYLPMN5HHHFPZAM2"


_ENV_EXAMPLE_PLACEHOLDERS = """\
# Copy to .env and fill in. Never commit .env.
OPENAI_API_KEY=
ANTHROPIC_API_KEY=your-anthropic-api-key
GEMINI_API_KEY=<your-gemini-key>
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
NEON_API_KEY=changeme
VERCEL_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=postgres://user:password@localhost:5432/app
SECRET_KEY=replace-me-with-a-long-random-string
"""


def _scan_repo(root: Path, files: dict[str, str], report: Path) -> tuple[int, set[str]]:
    """Commit `files` plus the generated .gitleaks.toml into a fresh repo and
    run `gitleaks git` there, relying on its auto-loading of the config."""
    assert _GITLEAKS, "SUNABA_REQUIRE_GITLEAKS=1 but gitleaks is not on PATH"
    root.mkdir()
    (root / ".gitleaks.toml").write_text(
        _build_config_files("p", ["secrets"])[".gitleaks.toml"]
    )
    for name, text in files.items():
        (root / name).write_text(text)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-qm", "seed"], cwd=root, check=True)
    proc = subprocess.run(
        [_GITLEAKS, "git", "--redact", "--no-banner", "--report-path", str(report), "."],
        cwd=root,
        capture_output=True,
        text=True,
    )
    findings = json.loads(report.read_text() or "[]")
    return proc.returncode, {f["File"] for f in findings}


@_needs_gitleaks
def test_gitleaks_binary_detects_with_generated_config(tmp_path):
    """Regression: the generated .gitleaks.toml must keep gitleaks' default
    rules active. With the pre-fix config this scan exited 0."""
    code, flagged = _scan_repo(
        tmp_path / "repo",
        {"app.py": f'aws_access_key_id = "{_FAKE_AWS_KEY_ID}"\n'},
        tmp_path / "report.json",
    )
    assert code == 1, "gitleaks found nothing: the config disabled detection"
    assert flagged == {"app.py"}


@_needs_gitleaks
def test_gitleaks_binary_catches_real_key_in_env_example(tmp_path):
    code, flagged = _scan_repo(
        tmp_path / "repo",
        {".env.example": f"AWS_ACCESS_KEY_ID={_FAKE_AWS_KEY_ID}\n"},
        tmp_path / "report.json",
    )
    assert code == 1
    assert flagged == {".env.example"}


@_needs_gitleaks
def test_gitleaks_binary_ignores_env_example_placeholders(tmp_path):
    code, flagged = _scan_repo(
        tmp_path / "repo",
        {".env.example": _ENV_EXAMPLE_PLACEHOLDERS},
        tmp_path / "report.json",
    )
    assert (code, flagged) == (0, set())


def _workflow_scan_script() -> str:
    """The `run:` block of the generated workflow's Scan step, dedented."""
    lines = _build_config_files("p", ["secrets"])[".github/workflows/gitleaks.yml"].splitlines()
    start = lines.index("      - name: Scan")
    run = next(i for i in range(start, len(lines)) if lines[i] == "        run: |")
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    for name, text in files.items():
        (repo / name).write_text(text)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", message], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run_workflow_scan(repo: Path, tmp_path: Path, event: str, **env: str):
    assert _GITLEAKS, "SUNABA_REQUIRE_GITLEAKS=1 but gitleaks is not on PATH"
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", "-c", _workflow_scan_script()],
        cwd=repo,
        capture_output=True,
        text=True,
        env={
            "PATH": f"{Path(_GITLEAKS).parent}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path),
            "GITHUB_EVENT_NAME": event,
            "RUNNER_TEMP": str(runner_temp),
            "BASE_SHA": "",
            "HEAD_SHA": "",
            **env,
        },
    )


def _assert_found_leak(r: subprocess.CompletedProcess) -> None:
    """Failed because gitleaks found a leak, not because git errored."""
    assert r.returncode != 0
    assert "leaks found:" in r.stdout, r.stdout
    assert "did not complete" not in r.stdout, r.stdout


def _new_repo(root: Path) -> Path:
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _commit(root, {".gitleaks.toml": _build_config_files("p", ["secrets"])[".gitleaks.toml"]}, "init")
    return root


@_needs_gitleaks
def test_workflow_scan_push_fails_on_leak_and_passes_clean(tmp_path):
    clean = _new_repo(tmp_path / "clean")
    _commit(clean, {"app.py": "print(1)\n"}, "clean")
    assert _run_workflow_scan(clean, tmp_path, "push").returncode == 0

    leaky = _new_repo(tmp_path / "leaky")
    _commit(leaky, {"app.py": f'key = "{_FAKE_AWS_KEY_ID}"\n'}, "leak")
    _assert_found_leak(_run_workflow_scan(leaky, tmp_path, "push"))


@_needs_gitleaks
def test_workflow_scan_pr_covers_only_the_pr_range(tmp_path):
    repo = _new_repo(tmp_path / "repo")
    base = _commit(repo, {"old.py": f'key = "{_FAKE_AWS_KEY_ID}"\n'}, "old leak")
    head = _commit(repo, {"new.py": "print(1)\n"}, "clean PR commit")
    r = _run_workflow_scan(repo, tmp_path, "pull_request", BASE_SHA=base, HEAD_SHA=head)
    assert r.returncode == 0, r.stdout

    head = _commit(repo, {"leak.py": f'k = "{_FAKE_AWS_KEY_ID}"\n'}, "PR adds a leak")
    _assert_found_leak(
        _run_workflow_scan(repo, tmp_path, "pull_request", BASE_SHA=base, HEAD_SHA=head)
    )


@_needs_gitleaks
def test_workflow_scan_ignores_inline_gitleaks_allow(tmp_path):
    repo = _new_repo(tmp_path / "repo")
    _commit(repo, {"app.py": f'key = "{_FAKE_AWS_KEY_ID}"  # gitleaks:allow\n'}, "suppressed")
    _assert_found_leak(_run_workflow_scan(repo, tmp_path, "push"))


@_needs_gitleaks
def test_workflow_scan_is_not_fooled_by_a_textconv_driver(tmp_path):
    """A diff driver that writes to stderr makes plain `gitleaks git` scan
    nothing and exit 0 (gitleaks/gitleaks#2129)."""
    repo = _new_repo(tmp_path / "repo")
    subprocess.run(
        ["git", "config", "diff.noisy.textconv", "sh -c 'echo noise >&2; cat \"$1\"' --"],
        cwd=repo,
        check=True,
    )
    _commit(
        repo,
        {".gitattributes": "*.txt diff=noisy\n", "leak.txt": f'k = "{_FAKE_AWS_KEY_ID}"\n'},
        "leak behind textconv",
    )
    _assert_found_leak(_run_workflow_scan(repo, tmp_path, "push"))


@_needs_gitleaks
def test_workflow_scan_fails_closed_when_git_errors(tmp_path):
    repo = _new_repo(tmp_path / "repo")
    head = _commit(repo, {"app.py": "print(1)\n"}, "clean")
    r = _run_workflow_scan(
        repo, tmp_path, "pull_request", BASE_SHA="0" * 40, HEAD_SHA=head
    )
    assert r.returncode != 0
    assert "gitleaks did not complete" in r.stdout
