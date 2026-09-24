"""Tests for --stack security-ci: the security-scan workflow and
scripts/protect-branch.sh."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from sunaba_cli.cli import _build_config_files
from sunaba_cli.compose import available_stacks

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ".github/workflows/security-scan.yml"
SCRIPT = "scripts/protect-branch.sh"


def _files(*stacks: str) -> dict[str, str]:
    return _build_config_files("p", list(stacks or ["security-ci"]))


def _workflow() -> str:
    return _files()[WORKFLOW]


def _step_script(workflow: str, step_name: str) -> str:
    """The `run: |` block of the named step, dedented."""
    lines = workflow.splitlines()
    start = lines.index(f"      - name: {step_name}")
    run = next(i for i in range(start, len(lines)) if lines[i] == "        run: |")
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def _job_names(workflow: str) -> set[str]:
    return set(re.findall(r"^    name: (.+)$", workflow, re.M))


# --- stack shape -----------------------------------------------------------


def test_security_ci_stack_listed():
    assert "security-ci" in available_stacks()


def test_security_ci_emits_expected_paths():
    files = _files()
    expected = {
        WORKFLOW,
        SCRIPT,
        "docs/security/README.md",
        "docs/security/THIRD_PARTY_NOTICES.md",
        "docs/agents/security-ci.md",
    }
    assert expected <= set(files)
    assert "security-ci" in files["AGENTS.md"]


def test_security_ci_does_not_ship_user_owned_ignore_files():
    """`rebuild` overwrites stack files, and a .semgrepignore replaces
    Semgrep's default ignore list, so neither ignore file is generated."""
    files = _files()
    assert ".semgrepignore" not in files
    assert ".trivyignore" not in files


def test_security_ci_does_not_leak_into_devcontainer():
    dc = json.loads(_files()[".devcontainer/devcontainer.json"])
    assert not [k for k in dc if k.startswith("_")]


# --- workflow --------------------------------------------------------------


def test_semgrep_gate_actually_fails_on_findings():
    """Regression for maruda's gate: without --error, semgrep exits 0 on
    findings."""
    script = _step_script(_workflow(), "Scan")
    assert "semgrep scan --error --metrics=off" in script
    assert "p/security-audit" in script and "p/owasp-top-ten" in script
    assert "--config auto" not in script  # needs metrics; not reproducible


def test_semgrep_image_is_digest_pinned():
    m = re.search(r"image: semgrep/semgrep:(\S+)@sha256:([0-9a-f]{64})\n", _workflow())
    assert m, "Semgrep image must be pinned as <version>@sha256:<digest>"
    assert re.fullmatch(r"\d+\.\d+\.\d+", m.group(1))


def _without_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_workflow_can_back_required_checks():
    text = _without_comments(_workflow())
    # A skipped workflow leaves required checks "Pending" forever.
    assert "paths:" not in text and "paths-ignore:" not in text
    # A green-but-failed step would hide failures from the gate.
    assert "continue-on-error" not in text
    assert "pull_request_target" not in text
    assert "permissions:\n  contents: read" in text
    assert text.count("persist-credentials: false") == 2
    assert text.count("timeout-minutes:") == 2


def test_trivy_install_is_verified():
    text = _without_comments(_workflow())
    assert "aquasecurity/trivy-action" not in text
    assert "setup-trivy" not in text
    assert re.search(r"TRIVY_SHA256: [0-9a-f]{64}\n", text)
    assert re.search(r"TRIVY_VERSION: \d+\.\d+\.\d+\n", text)
    assert "sha256sum -c -" in text
    assert "sudo" not in text


def test_trivy_mode_lives_in_a_repository_variable():
    """`sunaba rebuild` overwrites the workflow; a mode stored in it would be
    silently reset to informational."""
    assert "TRIVY_BLOCKING: ${{ vars.SUNABA_TRIVY_BLOCKING || 'false' }}" in _workflow()


def test_workflow_supports_merge_queues_and_scoped_concurrency():
    text = _without_comments(_workflow())
    assert "merge_group:" in text
    # A branch push must not cancel the PR run for the same branch.
    assert "github.event_name }}-${{ github.event.pull_request.number || github.ref }}" in text


_FAKE_TRIVY = """#!/bin/sh
echo "trivy $*" >> "$FAKE_TRIVY_LOG"
case "$1" in
  convert) echo "(table)"; exit 0 ;;
  version) echo '{"Version":"0.74.0","VulnerabilityDB":{"UpdatedAt":"2026-09-24T00:00:00Z"}}'; exit 0 ;;
esac
out=""
prev=""
for arg in "$@"; do
  [ "$prev" = "--output" ] && out="$arg"
  prev="$arg"
done
case " $* " in
  *" --download-db-only "*)
    n=$(cat "$FAKE_TRIVY_DB_FAILS" 2>/dev/null || echo 0)
    if [ "$n" -gt 0 ]; then echo $((n - 1)) > "$FAKE_TRIVY_DB_FAILS"; exit 1; fi
    exit 0 ;;
esac
[ -n "$out" ] && printf '%s' "$FAKE_TRIVY_JSON" > "$out"
exit "$FAKE_TRIVY_EXIT"
"""

_ONE_FINDING = '{"Results":[{"Target":"package-lock.json","Vulnerabilities":[{"VulnerabilityID":"CVE-2021-44906"}]}]}'
_CLEAN = '{"Results":[{"Target":"package-lock.json"}]}'
_NO_TARGETS = '{"SchemaVersion":2}'


def _run_trivy_step(tmp_path: Path, step: str, trivy_exit: int = 0, blocking: str = "false",
                    report: str = _CLEAN, db_fails: int = 0) -> subprocess.CompletedProcess:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    for name, body in (("trivy", _FAKE_TRIVY), ("sleep", "#!/bin/sh\nexit 0\n")):
        exe = fake_bin / name
        exe.write_text(body)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "db_fails").write_text(str(db_fails))
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir(exist_ok=True)
    return subprocess.run(
        ["bash", "-c", _step_script(_workflow(), step)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "TRIVY_BLOCKING": blocking,
            "RUNNER_TEMP": str(runner_temp),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "FAKE_TRIVY_LOG": str(tmp_path / "trivy.log"),
            "FAKE_TRIVY_EXIT": str(trivy_exit),
            "FAKE_TRIVY_JSON": report,
            "FAKE_TRIVY_DB_FAILS": str(tmp_path / "db_fails"),
        },
    )


@pytest.mark.parametrize(
    "trivy_exit,blocking,report,want_exit,want_text",
    [
        (0, "false", _CLEAN, 0, None),
        (0, "true", _CLEAN, 0, None),
        (3, "false", _ONE_FINDING, 0, "::warning title=Trivy (informational)::1 HIGH/CRITICAL"),
        (3, "true", _ONE_FINDING, 1, "::error title=Trivy::1 HIGH/CRITICAL"),
        (1, "false", "", 1, "::error title=Trivy did not complete::"),
        (1, "true", "", 1, "::error title=Trivy did not complete::"),
        (2, "false", "", 1, "::error title=Trivy did not complete::"),
    ],
)
def test_trivy_exit_code_mapping_fails_closed(tmp_path, trivy_exit, blocking, report, want_exit, want_text):
    r = _run_trivy_step(tmp_path, "Scan lockfiles", trivy_exit, blocking, report)
    assert r.returncode == want_exit, r.stdout + r.stderr
    if want_text:
        assert want_text in r.stdout
    log = (tmp_path / "trivy.log").read_text()
    # Findings are told apart from errors by a dedicated exit code, and the
    # scan reuses the DB the previous step downloaded.
    assert "--exit-code 3" in log and "--skip-db-update" in log


@pytest.mark.parametrize("bad", ["True", "yes", "1", ""])
def test_trivy_rejects_malformed_mode(tmp_path, bad):
    r = _run_trivy_step(tmp_path, "Scan lockfiles", 0, bad)
    assert r.returncode == 1
    assert "must be" in r.stdout
    assert not (tmp_path / "trivy.log").exists(), "must not scan with an unknown mode"


def test_trivy_summary_records_mode_and_counts(tmp_path):
    r = _run_trivy_step(tmp_path, "Scan lockfiles", 3, "false", _ONE_FINDING)
    assert r.returncode == 0
    summary = (tmp_path / "summary.md").read_text()
    assert "Mode: informational" in summary
    assert "Dependency files scanned: 1" in summary
    assert "HIGH/CRITICAL findings with a fix: 1" in summary
    assert "Vulnerability DB updated: 2026-09-24T00:00:00Z" in summary


def test_trivy_says_when_nothing_was_scanned(tmp_path):
    r = _run_trivy_step(tmp_path, "Scan lockfiles", 0, "true", _NO_TARGETS)
    assert r.returncode == 0
    assert "No supported dependency files" in r.stdout
    assert "Dependency files scanned: 0" in (tmp_path / "summary.md").read_text()


def test_trivy_db_download_retries_then_fails_closed(tmp_path):
    ok = _run_trivy_step(tmp_path, "Download vulnerability database", db_fails=2)
    assert ok.returncode == 0, ok.stdout
    log = (tmp_path / "trivy.log").read_text()
    assert log.count("--download-db-only") == 3

    (tmp_path / "trivy.log").unlink()
    bad = _run_trivy_step(tmp_path, "Download vulnerability database", db_fails=5)
    assert bad.returncode == 1
    assert "could not download the vulnerability database" in bad.stdout
    assert (tmp_path / "trivy.log").read_text().count("--download-db-only") == 3


# Real-binary contract: run the workflow's own steps against the pinned
# Trivy. Needs network for the DB. Skipped unless `trivy` is on PATH, or
# required by SUNABA_REQUIRE_TRIVY=1 (set in sunaba's CI).

_TRIVY = shutil.which("trivy")
_needs_trivy = pytest.mark.skipif(
    _TRIVY is None and os.environ.get("SUNABA_REQUIRE_TRIVY") != "1",
    reason="trivy binary not on PATH",
)


def _npm_lock(minimist: str) -> str:
    return json.dumps({
        "name": "fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True,
        "packages": {
            "": {"name": "fixture", "version": "1.0.0", "dependencies": {"minimist": minimist}},
            "node_modules/minimist": {"version": minimist},
        },
    })


def _run_real_trivy(tmp_path: Path, lock: str, blocking: str) -> subprocess.CompletedProcess:
    assert _TRIVY, "SUNABA_REQUIRE_TRIVY=1 but trivy is not on PATH"
    work = tmp_path / "proj"
    work.mkdir(exist_ok=True)
    (work / "package-lock.json").write_text(lock)
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir(exist_ok=True)
    env = {
        "PATH": f"{Path(_TRIVY).parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", str(tmp_path)),
        "TRIVY_BLOCKING": blocking,
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    for step in ("Download vulnerability database", "Scan lockfiles"):
        r = subprocess.run(["bash", "-c", _step_script(_workflow(), step)], cwd=work,
                           capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0:
            return r
    return r


@_needs_trivy
def test_real_trivy_blocks_a_critical_with_a_fix(tmp_path):
    r = _run_real_trivy(tmp_path, _npm_lock("1.2.5"), "true")  # CVE-2021-44906, fixed in 1.2.6
    assert r.returncode == 1, r.stdout + r.stderr
    assert "::error title=Trivy::" in r.stdout
    assert "did not complete" not in r.stdout


@_needs_trivy
def test_real_trivy_informational_mode_stays_green(tmp_path):
    r = _run_real_trivy(tmp_path, _npm_lock("1.2.5"), "false")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "::warning title=Trivy (informational)::" in r.stdout


@_needs_trivy
def test_real_trivy_clean_lockfile_passes(tmp_path):
    r = _run_real_trivy(tmp_path, _npm_lock("1.2.8"), "true")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Dependency files scanned: 1" in (tmp_path / "summary.md").read_text()


# --- protect-branch.sh -----------------------------------------------------


def _project(tmp_path: Path, *stacks: str) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for rel, text in _build_config_files("p", list(stacks)).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return root


_FAKE_GH = """#!/bin/sh
# Records every call; answers just enough of the gh CLI for protect-branch.sh.
echo "$*" >> "$FAKE_GH_LOG"
case "$*" in
  "repo view --json nameWithOwner --jq .nameWithOwner") echo "octo/app"; exit 0 ;;
  "api repos/octo/app --jq .default_branch") echo "main"; exit 0 ;;
  "api repos/octo/app/commits/main/check-runs?per_page=100 --paginate --jq "*)
    printf '%b' "$FAKE_GH_CHECKS"; exit 0 ;;
  "api repos/octo/app/rulesets?includes_parents=false --paginate --jq "*)
    printf '%b' "$FAKE_GH_RULESETS"; exit 0 ;;
  "api -X "*)
    cat > "$FAKE_GH_PAYLOAD"
    if [ -n "$FAKE_GH_FAIL" ]; then echo "gh: Resource not accessible (HTTP 403)" >&2; exit 1; fi
    case "$4" in */rulesets/*) echo "${4##*/}" ;; *) echo 77 ;; esac
    exit 0 ;;
  "api repos/octo/app/rulesets/"*" --jq "*)
    if [ -n "$FAKE_GH_READBACK" ]; then printf '%b\n' "$FAKE_GH_READBACK"; exit 0; fi
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); r=[x for x in d["rules"] if x["type"]=="required_status_checks"][0]; print(d["enforcement"]+"\\t"+",".join(c["context"] for c in r["parameters"]["required_status_checks"]))' "$FAKE_GH_PAYLOAD"
    exit 0 ;;
esac
echo "unexpected gh call: $*" >&2
exit 99
"""

_ALL_GREEN = (
    "SAST (Semgrep)\tcompleted\tsuccess\tgithub-actions\t15368\n"
    "Dependency Scan (Trivy)\tcompleted\tsuccess\tgithub-actions\t15368\n"
    "Secret Scan (Gitleaks)\tcompleted\tsuccess\tgithub-actions\t15368\n"
)


def _run_protect(root: Path, tmp_path: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    gh = fake_bin / "gh"
    gh.write_text(_FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    base = {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "FAKE_GH_LOG": str(tmp_path / "gh.log"),
        "FAKE_GH_PAYLOAD": str(tmp_path / "payload.json"),
        "FAKE_GH_CHECKS": _ALL_GREEN,
        "FAKE_GH_RULESETS": "",
        "FAKE_GH_FAIL": "",
        "FAKE_GH_READBACK": "",
    }
    base.update(env)
    return subprocess.run(
        ["bash", str(root / SCRIPT), *args], cwd=root, capture_output=True, text=True, env=base
    )


def _gh_calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "gh.log"
    return log.read_text().splitlines() if log.exists() else []


def _writes(tmp_path: Path) -> list[str]:
    return [c for c in _gh_calls(tmp_path) if c.startswith("api -X ")]


def _required(payload: dict) -> list[dict]:
    rule = next(r for r in payload["rules"] if r["type"] == "required_status_checks")
    return rule["parameters"]["required_status_checks"]


def _required_contexts(payload: dict) -> list[str]:
    return [c["context"] for c in _required(payload)]


def test_protect_script_syntax():
    subprocess.run(["bash", "-n", "/dev/stdin"], input=_files()[SCRIPT], text=True, check=True)


def test_protect_dry_run_payload(tmp_path):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, "--dry-run")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["name"] == "sunaba security gates"
    assert payload["enforcement"] == "active"
    assert payload["bypass_actors"] == []
    assert payload["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    types = {rule["type"] for rule in payload["rules"]}
    assert {"deletion", "non_fast_forward", "required_status_checks"} <= types
    assert _required_contexts(payload) == ["SAST (Semgrep)", "Dependency Scan (Trivy)"]
    params = next(r for r in payload["rules"] if r["type"] == "required_status_checks")["parameters"]
    assert params["strict_required_status_checks_policy"] is False
    # A listed integration branch that does not exist yet can still be created.
    assert params["do_not_enforce_on_create"] is True
    # --dry-run makes no API calls at all.
    assert _gh_calls(tmp_path) == []


def test_protect_covers_integration_branches_and_strict(tmp_path):
    """maruda's --protect covered only the default branch."""
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, "--dry-run", "--branch", "staging",
                     "--branch", "release/v1", "--branch", "staging", "--strict")
    payload = json.loads(r.stdout)
    assert payload["conditions"]["ref_name"]["include"] == [
        "~DEFAULT_BRANCH",
        "refs/heads/staging",
        "refs/heads/release/v1",
    ]
    params = next(r for r in payload["rules"] if r["type"] == "required_status_checks")["parameters"]
    assert params["strict_required_status_checks_policy"] is True


def test_protect_requires_gitleaks_when_secrets_stack_present(tmp_path):
    root = _project(tmp_path, "secrets", "security-ci")
    payload = json.loads(_run_protect(root, tmp_path, "--dry-run").stdout)
    assert _required_contexts(payload) == [
        "SAST (Semgrep)",
        "Dependency Scan (Trivy)",
        "Secret Scan (Gitleaks)",
    ]


def test_protect_contexts_match_workflow_job_names(tmp_path):
    """A required context that no job reports blocks every PR forever."""
    root = _project(tmp_path, "secrets", "security-ci")
    payload = json.loads(_run_protect(root, tmp_path, "--dry-run").stdout)
    files = _build_config_files("p", ["secrets", "security-ci"])
    job_names = _job_names(files[WORKFLOW]) | _job_names(files[".github/workflows/gitleaks.yml"])
    assert set(_required_contexts(payload)) <= job_names


@pytest.mark.parametrize("bad", ['bad"name', "with space", "$(id)", "a;b"])
def test_protect_rejects_unsafe_branch_names(tmp_path, bad):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, "--dry-run", "--branch", bad)
    assert r.returncode == 2
    assert "unsupported branch name" in r.stderr


def test_protect_fails_without_security_workflows(tmp_path):
    root = _project(tmp_path, "python")
    (root / SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (root / SCRIPT).write_text(_files()[SCRIPT])
    r = _run_protect(root, tmp_path, "--dry-run")
    assert r.returncode == 2
    assert "no sunaba security workflow" in r.stderr


def test_protect_creates_app_bound_ruleset_after_preflight(tmp_path):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path)
    assert r.returncode == 0, r.stderr
    assert _writes(tmp_path) == ["api -X POST repos/octo/app/rulesets --input - --jq .id"]
    sent = json.loads((tmp_path / "payload.json").read_text())
    # Bound to the GitHub Actions app seen in the preflight: no other app can
    # satisfy the check by reporting the same name.
    assert [c.get("integration_id") for c in _required(sent)] == [15368, 15368]
    assert "created on octo/app (id 77)" in r.stdout
    assert "(GitHub Actions only)" in r.stdout


def test_protect_updates_existing_repository_ruleset_in_place(tmp_path):
    root = _project(tmp_path, "security-ci")
    rulesets = (
        "4242\tsunaba security gates\tRepository\n"
        "5000\tsunaba security gates\tOrganization\n"  # inherited, not ours
        "6000\tother\tRepository\n"
    )
    r = _run_protect(root, tmp_path, FAKE_GH_RULESETS=rulesets)
    assert r.returncode == 0, r.stderr
    assert _writes(tmp_path) == ["api -X PUT repos/octo/app/rulesets/4242 --input - --jq .id"]
    assert "updated on octo/app (id 4242)" in r.stdout


def test_protect_refuses_ambiguous_duplicate_rulesets(tmp_path):
    root = _project(tmp_path, "security-ci")
    rulesets = "11\tsunaba security gates\tRepository\n12\tsunaba security gates\tRepository\n"
    r = _run_protect(root, tmp_path, FAKE_GH_RULESETS=rulesets)
    assert r.returncode == 1
    assert "several rulesets" in r.stderr
    assert _writes(tmp_path) == [], "must not write when ambiguous"


@pytest.mark.parametrize(
    "checks,why",
    [
        ("SAST (Semgrep)\tcompleted\tsuccess\tgithub-actions\t15368\n", "Dependency Scan (Trivy): has never run"),
        ("SAST (Semgrep)\tcompleted\tfailure\tgithub-actions\t15368\n"
         "Dependency Scan (Trivy)\tcompleted\tsuccess\tgithub-actions\t15368\n", "latest run is failure"),
        ("SAST (Semgrep)\tin_progress\t\tgithub-actions\t15368\n"
         "Dependency Scan (Trivy)\tcompleted\tsuccess\tgithub-actions\t15368\n", "latest run is in_progress"),
        ("SAST (Semgrep)\tcompleted\tsuccess\tsome-bot\t999\n"
         "Dependency Scan (Trivy)\tcompleted\tsuccess\tgithub-actions\t15368\n", "reported by 'some-bot'"),
        ("", "has never run on main"),
    ],
)
def test_protect_preflight_refuses_unproven_checks(tmp_path, checks, why):
    """Requiring a check that never passed would wedge every PR."""
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, FAKE_GH_CHECKS=checks)
    assert r.returncode == 1
    assert "not activating" in r.stderr
    assert why in r.stderr
    assert _writes(tmp_path) == []


def test_protect_force_skips_preflight_without_binding(tmp_path):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, "--force", FAKE_GH_CHECKS="")
    assert r.returncode == 0, r.stderr
    sent = json.loads((tmp_path / "payload.json").read_text())
    assert all("integration_id" not in c for c in _required(sent))
    assert not any("check-runs" in c for c in _gh_calls(tmp_path))


def test_protect_explains_api_failures(tmp_path):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, FAKE_GH_FAIL="1")
    assert r.returncode == 1
    assert "HTTP 403" in r.stderr
    assert "admin" in r.stderr
    assert "free private repositories" in r.stderr


def test_protect_detects_a_stored_ruleset_that_differs(tmp_path):
    root = _project(tmp_path, "security-ci")
    r = _run_protect(root, tmp_path, FAKE_GH_READBACK="evaluate\\tSAST (Semgrep)")
    assert r.returncode == 1
    assert "does not match" in r.stderr


# --- dogfooding --------------------------------------------------------------


def test_sunaba_runs_the_same_security_workflow():
    """sunaba's own repository runs the generated workflow unchanged, so every
    template change is exercised by real CI before users get it."""
    own = (REPO_ROOT / WORKFLOW).read_text()
    assert own == _workflow()


def test_new_project_script_is_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    r = subprocess.run(
        [sys.executable, "-m", "sunaba_cli.cli", "new", "gates",
         "--stack", "security-ci", "--no-devcontainer", "--no-prompt"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    script = tmp_path / "gates" / SCRIPT
    assert script.stat().st_mode & stat.S_IXUSR
