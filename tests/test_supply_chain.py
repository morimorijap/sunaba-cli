"""Every GitHub Action a workflow uses — in generated projects and in this
repository's own CI — must be pinned to a full commit SHA.

Adapted from the SHA-pin audit (and the probe that proves the audit can
fail) in northraystudio/maruda (MIT):
https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/tests/run.sh#L248-L264
See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sunaba_cli.cli import _build_config_files
from sunaba_cli.compose import available_stacks

REPO_ROOT = Path(__file__).resolve().parent.parent

_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")
# owner/repo[/path]@<40-hex> # vX[.Y[.Z]]
_PINNED = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"^\s+# v\d+(?:\.\d+){0,2}\s*$")


def _unpinned(text: str) -> list[str]:
    """Return every `uses:` line not pinned to a SHA with a version comment.
    Local (`./`) and `docker://` references are not GitHub Actions refs."""
    bad = []
    for line in text.splitlines():
        m = _USES.match(line)
        if not m:
            continue
        ref, rest = m.groups()
        if ref.startswith(("./", "docker://")):
            continue
        if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest)):
            bad.append(line.strip())
    return bad


def _generated_workflows() -> dict[str, str]:
    out = {}
    for stack in available_stacks():
        for path, text in _build_config_files("p", [stack]).items():
            if path.startswith(".github/workflows/"):
                out[f"--stack {stack}: {path}"] = text
    return out


def test_audit_rejects_mutable_refs():
    """Guard the guard: the detector must flag tags, branches, short SHAs,
    and SHA pins that lack the `# vX.Y.Z` comment Dependabot maintains."""
    for line in [
        "      - uses: actions/checkout@v4",
        "      - uses: actions/checkout@main",
        "      - uses: actions/checkout@3d3c42e",
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "        uses: gitleaks/gitleaks-action@v2",
    ]:
        assert _unpinned(line) == [line.strip()], line


def test_audit_accepts_sha_pins():
    ok = "\n".join([
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "        uses: github/codeql-action/init@0123456789abcdef0123456789abcdef01234567 # v3",
        "      - uses: ./.github/actions/local",
        "      - uses: docker://alpine:3.20",
    ])
    assert _unpinned(ok) == []


def test_some_stack_generates_a_workflow():
    """If no stack emitted a workflow, the parametrized audit would pass
    vacuously."""
    assert _generated_workflows()


_WORKFLOWS = _generated_workflows()


@pytest.mark.parametrize("name", sorted(_WORKFLOWS))
def test_generated_workflows_pin_actions_to_sha(name):
    assert _unpinned(_WORKFLOWS[name]) == [], name


@pytest.mark.parametrize(
    "path", sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml")), ids=lambda p: p.name
)
def test_own_workflows_pin_actions_to_sha(path):
    assert _unpinned(path.read_text()) == [], path.name


def test_own_ci_installs_the_same_gitleaks_as_the_template():
    """sunaba's CI runs the binary-backed secrets tests with its own copy of
    the install step; it must stay on the release the template ships."""
    template = _build_config_files("p", ["secrets"])[".github/workflows/gitleaks.yml"]
    own = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for key in ("GITLEAKS_VERSION", "GITLEAKS_SHA256"):
        pattern = rf"{key}: (\S+)"
        assert re.search(pattern, own).group(1) == re.search(pattern, template).group(1), key


_IMAGE = re.compile(r"^\s*image:\s*(\S+)\s*$", re.M)


@pytest.mark.parametrize("name", sorted(_WORKFLOWS))
def test_generated_workflow_container_images_are_digest_pinned(name):
    """Tags on a registry are as mutable as action tags; Trivy's March 2026
    compromise pushed malicious images under existing version tags, and
    images referenced by digest were unaffected (GHSA-69fq-xp46-6x23)."""
    for image in _IMAGE.findall(_WORKFLOWS[name]):
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), (name, image)


def test_own_ci_installs_the_same_trivy_as_the_template():
    template = _build_config_files("p", ["security-ci"])[".github/workflows/security-scan.yml"]
    own = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for key in ("TRIVY_VERSION", "TRIVY_SHA256"):
        pattern = rf"{key}: (\S+)"
        assert re.search(pattern, own).group(1) == re.search(pattern, template).group(1), key
