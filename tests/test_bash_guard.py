"""PreToolUse bash guard (`--stack harness`): deny/allow matrix.

The cases up to "sunaba additions" are adapted from northraystudio/maruda
(MIT, Copyright (c) 2026 NorthRay Studio株式会社):
https://github.com/northraystudio/maruda/blob/5f9b323ccb69d325677006c00643b4dc08699a00/harness/tests/run.sh#L205-L279

Every case runs under each bash found: /bin/bash (3.2 on macOS, where
`--no-devcontainer` projects run the hook) and the `bash` on PATH (5.x in
the devcontainer and CI).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sunaba_cli.cli import _build_config_files

GUARD = ".claude/hooks/pre-bash-guard.sh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")


def _bashes() -> list[str]:
    found = []
    for b in ("/bin/bash", shutil.which("bash")):
        if b and Path(b).exists() and os.path.realpath(b) not in {os.path.realpath(x) for x in found}:
            found.append(b)
    return found


BASHES = _bashes()


@pytest.fixture(scope="module")
def guard(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("hooks") / "pre-bash-guard.sh"
    path.write_text(_build_config_files("p", ["harness"])[GUARD])
    return path


def _run(bash: str, guard: Path, payload: str, env: dict | None = None,
         prefix: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([*(prefix or []), bash, str(guard)], input=payload,
                          capture_output=True, text=True, env=env, timeout=30)


def _decision(r: subprocess.CompletedProcess) -> str:
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return "allowed"
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]


CASES = [
    (True, 'rm -rf /'),
    (True, 'rm -fr /'),
    (True, 'rm -r -f /'),
    (True, 'rm -rf -- /'),
    (True, 'rm --recursive --force /'),
    (True, 'rm -Rf /*'),
    (True, 'rm -fr ~'),
    (True, 'rm -rf ~/projects'),
    (True, 'rm -rf $HOME'),
    (True, 'rm -rf *'),
    (True, 'sudo rm -rf /'),
    (True, 'cd /tmp && rm -fr /'),
    (True, 'bash -c "rm -fr /"'),
    (True, 'echo $(rm -rf ~)'),
    (True, 'git push -f origin main'),
    (True, 'git push origin +main'),
    (True, 'git push --force origin refs/heads/main'),
    (True, 'git push --force-with-lease origin HEAD:main'),
    (True, 'git -C repo push -uf origin master'),
    (True, 'git push --force origin main>/dev/null'),
    (True, 'git push --force origin main 2>&1'),
    (True, 'git push --force "$(git remote)" main'),
    (True, 'git push --force `git remote` main'),
    (True, 'git push --force origin $(git branch --show-current)'),
    (True, 'git push --force origin HEAD:`git branch --show-current`'),
    (True, '(git push --force "$(git remote)" main)'),
    (True, '(cd x && git push --force `git remote` HEAD:main 2>&1)'),
    (True, 'git push --force origin {main,develop}'),
    (True, 'git push --force origin {develop,main}'),
    (True, 'git push --force "https://host/x(y).git" main'),
    (True, 'git push --force-with-lease=main:abc123 origin'),
    (True, 'git push --force-with-lease=main origin'),
    (True, 'git push --force-with-lease=refs/heads/main:abc origin'),
    (True, 'GIT push -f origin MAIN'),
    (True, 'git push --force origin HEAD:heads/main'),
    (True, 'git push --force origin heads/main'),
    (True, 'git push --force origin +HEAD:heads/master'),
    (True, 'git push --force origin HEAD:Heads/Main'),
    (True, 'git push --force origin HEAD:refs/heads/master'),
    (True, 'git push --force origin feat/x >main.log'),
    (True, 'git push --force origin >/dev/null main'),
    (True, 'git push --force origin 2>/dev/null main'),
    (True, 'git push --force origin &>/dev/null main'),
    (True, 'git push --force >/dev/null origin main'),
    (True, 'git push --force origin 2>&1 main'),
    (True, 'git push --force origin < /dev/null main'),
    (True, 'rm -rf />/dev/null'),
    (True, 'rm -rf >/dev/null /'),
    (True, 'rm -rf 2>&1 /'),
    (True, 'rm -rf 2> /dev/null ~'),
    (True, 'rm -rf $(echo x) /'),
    (True, '(cd /tmp; rm -rf /)'),
    (True, 'terraform destroy'),
    (True, 'docker system prune -af'),
    (True, 'echo x >> .env'),
    (False, 'terraform plan'),
    (False, 'rm -rf node_modules'),
    (False, 'rm -rf ./build'),
    (False, 'rm -f /tmp/x.log'),
    (False, 'rm -r ~/scratch-no-force'),
    (False, 'git push origin feature/x'),
    (False, 'git push origin main'),
    (False, 'git push --force origin feat/domain-model'),
    (False, 'git push --force-with-lease origin feat/maintenance-fix'),
    (False, 'git push origin +feat/x'),
    (False, 'git push --force "$(git remote)" feat/x'),
    (False, 'git push origin $(git branch --show-current)'),
    (False, 'git push --force origin feat/x >/dev/null 2>&1'),
    (False, 'rm -rf $(mktemp -d)'),
    (False, 'git push --force-with-lease=feat/x:abc123 origin'),
    (False, 'git push --follow-tags origin main'),
    (False, 'git push --force origin feat/main'),
    (False, 'git push --force origin HEAD:tags/main'),
    (False, 'rm -rf build >/dev/null 2>&1'),
    (False, 'kubectl delete pod my-pod'),
    # sunaba additions
    (True, 'git push origin main --force'),
    (True, 'git push origin main -f'),
    (True, 'sudo rm -fr /'),
    (True, 'cd sub && git push --force origin main'),
    (True, 'aws s3 rm s3://bucket --recursive'),
    (True, 'gcloud projects delete my-proj'),
    (True, 'echo SECRET=x > .env'),
    (False, 'echo x > .env.example'),
    (False, 'git push --force-with-lease origin HEAD:feat/x'),
    (False, 'rm -rf dist build .pytest_cache'),
    (False, 'uv run pytest -q'),
    # Found in review: line continuations and whole-repo pushes.
    (True, 'rm -fr \\\n/'),
    (True, 'git push --force \\\n  origin main'),
    (True, 'git push origin --mirror'),
    (True, 'git push --force origin --all'),
    (True, 'git push -f --branches origin'),
    (False, 'git push origin --all'),
    (False, 'git push --tags origin'),
    (False, 'printf "a\\nb"'),
]


@pytest.mark.parametrize("bash", BASHES)
@pytest.mark.parametrize("deny,cmd", CASES)
def test_guard_matrix(guard, bash, deny, cmd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    want = "deny" if deny else "allowed"
    assert _decision(_run(bash, guard, payload)) == want, cmd


def test_deny_output_is_a_pretooluse_decision(guard):
    r = _run(BASHES[0], guard, json.dumps({"tool_input": {"command": "rm -rf /"}}))
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "ask the user" in out["permissionDecisionReason"]


@pytest.mark.parametrize("bash", BASHES)
@pytest.mark.parametrize("payload", ["not json", "", "{}", '{"tool_input":{}}', "[1,2]"])
def test_unparseable_input_is_no_opinion(guard, bash, payload):
    r = _run(bash, guard, payload)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


@pytest.mark.parametrize("bash", BASHES)
@pytest.mark.parametrize("cmd", ["git push -f origin main", "rm -fr /"])
def test_denials_hold_without_temp_files(guard, bash, cmd):
    """Here-strings need a temp file; with file writes failing (ulimit -f 0)
    the parser must still see the command."""
    payload = json.dumps({"tool_input": {"command": cmd}})
    r = subprocess.run(
        [bash, "-c", 'trap "" XFSZ; ulimit -f 0; exec "$0" "$1"', bash, str(guard)],
        input=payload, capture_output=True, text=True, timeout=30,
    )
    assert _decision(r) == "deny"


def test_missing_jq_says_so_instead_of_passing_silently(guard, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "cat").symlink_to(shutil.which("cat"))
    r = _run(BASHES[0], guard, json.dumps({"tool_input": {"command": "rm -rf /"}}),
             env={"PATH": str(bin_dir)})
    assert r.returncode == 0
    assert r.stdout == ""
    assert "jq not found" in r.stderr


def test_settings_wire_the_guard_from_any_directory():
    """$CLAUDE_PROJECT_DIR: a relative path breaks once the agent cd's into
    a subdirectory, and a hook that cannot start does not block anything."""
    files = _build_config_files("p", ["harness"])
    settings = json.loads(files[".claude/settings.json"])
    entries = settings["hooks"]["PreToolUse"]
    handlers = [h for e in entries if e["matcher"] == "Bash" for h in e["hooks"]]
    assert handlers == [{
        "type": "command",
        "command": 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-bash-guard.sh"',
    }]
    # The prefix-matched deny rules stay as a second layer.
    deny = settings["permissions"]["deny"]
    assert "Bash(rm -rf:*)" in deny and "Bash(git push --force:*)" in deny
    # Stop keeps its relative path: verify.sh checks the current checkout,
    # which in a worktree is not $CLAUDE_PROJECT_DIR.
    stop = [h["command"] for e in settings["hooks"]["Stop"] for h in e["hooks"]]
    assert stop == ["bash .claude/hooks/verify.sh"]


def test_guard_ships_with_its_license_notice():
    files = _build_config_files("p", ["harness"])
    assert files[GUARD].startswith("#!/usr/bin/env bash\n")
    assert "northraystudio/maruda" in files[GUARD]
    notice = files[".claude/hooks/THIRD_PARTY_NOTICES.md"]
    assert "MIT License" in notice and "NorthRay Studio" in notice
