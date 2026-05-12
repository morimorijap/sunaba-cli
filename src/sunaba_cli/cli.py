"""sunaba-cli: One-command devcontainer sandbox for AI agent development."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import click

from .compose import TEMPLATES_DIR, available_stacks, compose, stack_description
from .sync import (
    copy_agent_files,
    get_project,
    list_projects,
    register_project,
    sync_all,
    sync_project,
)


def _build_bootstrap(stacks: list[str]) -> str:
    """Build bootstrap.sh from base + stack-specific lines."""
    base = (TEMPLATES_DIR / "base" / "bootstrap.sh").read_text()
    extra_lines: list[str] = []
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if stack_path.exists():
            data = json.loads(stack_path.read_text())
            extra_lines.extend(data.get("_bootstrap", []))
    if extra_lines:
        base = base.rstrip() + "\n" + "\n".join(extra_lines) + "\n"
    return base


def _build_dependabot_simple(stacks: list[str], *, no_devcontainer: bool = False) -> str:
    """Build dependabot.yml without PyYAML dependency.

    When no_devcontainer is True, the `devcontainers` and `docker` ecosystems
    (which exist only because of the generated devcontainer config) are dropped.
    """
    if no_devcontainer:
        base_text = (
            "version: 2\n"
            "updates:\n"
            '  - package-ecosystem: "github-actions"\n'
            '    directory: "/"\n'
            "    schedule:\n"
            '      interval: "weekly"\n'
        )
        existing = {"github-actions"}
    else:
        base_text = (TEMPLATES_DIR / "base" / "dependabot.yml").read_text()
        existing = {"devcontainers", "docker", "github-actions"}

    extra_sections: list[str] = []

    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if stack_path.exists():
            data = json.loads(stack_path.read_text())
            dep = data.get("_dependabot")
            if dep and dep["package-ecosystem"] not in existing:
                existing.add(dep["package-ecosystem"])
                interval = dep.get("schedule", {}).get("interval", "weekly")
                directory = dep.get("directory", "/")
                extra_sections.append(
                    f'\n  - package-ecosystem: "{dep["package-ecosystem"]}"\n'
                    f'    directory: "{directory}"\n'
                    f"    schedule:\n"
                    f'      interval: "{interval}"'
                )

    if extra_sections:
        base_text = base_text.rstrip() + "\n" + "\n".join(extra_sections) + "\n"

    return base_text


def _clean_devcontainer(config: dict) -> dict:
    return {k: v for k, v in config.items() if not k.startswith("_")}


def _validate_stacks(stacks: list[str]) -> None:
    valid = set(available_stacks())
    for s in stacks:
        if s not in valid:
            click.echo(f"Error: Unknown stack '{s}'. Available: {', '.join(sorted(valid))}", err=True)
            raise SystemExit(1)


def _interactive_select_stacks() -> list[str]:
    """Prompt the user to pick stacks. Returns the selected stack list."""
    stacks_list = available_stacks()
    click.echo("No stacks specified. Select which to include:")
    click.echo("")
    for i, name in enumerate(stacks_list, 1):
        desc = stack_description(name) or "(no description)"
        click.echo(f"  {i}. {name:8s}  {desc}")
    click.echo("")
    click.echo("Enter numbers or names (comma/space separated).")
    click.echo("Examples: '1,3,7'   'python nextjs agents'   'all'   (empty = python)")

    while True:
        raw = click.prompt("Stacks", default="python", show_default=True).strip()
        if not raw:
            return ["python"]
        if raw.lower() == "all":
            return stacks_list
        tokens = [t.strip() for t in raw.replace(",", " ").split() if t.strip()]
        selected: list[str] = []
        bad: list[str] = []
        for t in tokens:
            if t.isdigit():
                idx = int(t) - 1
                if 0 <= idx < len(stacks_list):
                    selected.append(stacks_list[idx])
                else:
                    bad.append(t)
            elif t in stacks_list:
                selected.append(t)
            else:
                bad.append(t)
        if bad:
            click.echo(f"  Invalid: {', '.join(bad)}. Try again.", err=True)
            continue
        # Deduplicate, preserve order
        seen = set()
        unique = []
        for s in selected:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        if not unique:
            click.echo("  Empty selection. Try again.", err=True)
            continue
        return unique


_AGENT_FILES_BASE_DIR = TEMPLATES_DIR / "agents" / "base"
_AGENT_FRAGMENTS_DIR = TEMPLATES_DIR / "agents" / "fragments"


def _default_gitignore() -> str:
    """Return the project `.gitignore` baseline.

    Covers the secret-leak file family (cloud creds, SSH keys, service
    account JSON, agent local state, the wider `.env.*` family) plus the
    usual build / cache / OS noise. Only written by `sunaba new`;
    `sunaba rebuild` does not modify an existing `.gitignore` so user
    edits are preserved.
    """
    return (
        "# Environment files (never commit real values)\n"
        ".env\n"
        ".env.*\n"
        "!.env.example\n"
        "!.env.*.example\n"
        ".envrc\n"
        ".dev.vars\n"
        "\n"
        "# Cloud and local credentials\n"
        ".aws/\n"
        ".azure/\n"
        ".gcloud/\n"
        "gcloud-config/\n"
        "credentials.json\n"
        "**/serviceAccount*.json\n"
        "**/service-account*.json\n"
        "**/*-firebase-adminsdk-*.json\n"
        "\n"
        "# Private keys and certificates\n"
        "*.pem\n"
        "*.key\n"
        "*.p12\n"
        "*.pfx\n"
        "id_rsa*\n"
        "id_ed25519*\n"
        "\n"
        "# Agent-local state\n"
        ".claude/settings.local.json\n"
        ".codex/\n"
        ".gemini/\n"
        "\n"
        "# Build / cache\n"
        ".venv/\n"
        "node_modules/\n"
        "__pycache__/\n"
        "*.pyc\n"
        ".DS_Store\n"
    )

_STACKS_DELIMITER_START = "<!-- SUNABA STACKS START -->"
_STACKS_DELIMITER_END = "<!-- SUNABA STACKS END -->"
_USER_DELIMITER_START = "<!-- SUNABA USER START -->"
_USER_DELIMITER_END = "<!-- SUNABA USER END -->"


def _inject_between_delimiters(
    text: str, start: str, end: str, payload: str
) -> str:
    """Replace whatever is between `start` and `end` markers with `payload`.

    Preserves the marker lines. If the markers are not found, returns the
    text unchanged. `payload` is sandwiched with single newlines so it
    renders cleanly when empty.
    """
    si = text.find(start)
    ei = text.find(end)
    if si == -1 or ei == -1 or ei < si:
        return text
    before = text[: si + len(start)]
    after = text[ei:]
    if payload.strip():
        body = "\n" + payload.rstrip("\n") + "\n"
    else:
        body = "\n"
    return before + body + after


def _read_fragment(stack: str, fragment: str) -> str | None:
    """Return the fragment body (e.g. python/summary.md) or None if missing."""
    path = _AGENT_FRAGMENTS_DIR / stack / fragment
    if not path.exists():
        return None
    return path.read_text()


def _build_agent_files(
    stacks: list[str], *, no_devcontainer: bool = False
) -> dict[str, str]:
    """Compose stack-aware agent files.

    Returns a {relpath: content} dict for:
      - AGENTS.md / CLAUDE.md / GEMINI.md / skills.md (root, with stack
        sections injected between SUNABA STACKS delimiters)
      - docs/agents/<stack>.md  (per stack, full guidance.md body)
      - .claude/skills/sunaba-<stack>/SKILL.md  (Claude progressive
        disclosure; same body wrapped with YAML frontmatter)

    `no_devcontainer` is reserved for future host-only wording switches;
    today the same content is emitted in either mode.
    """
    files: dict[str, str] = {}
    if not _AGENT_FILES_BASE_DIR.exists():
        return files

    summary_lines = [
        body.rstrip()
        for s in stacks
        if (body := _read_fragment(s, "summary.md")) is not None
        and body.strip()
    ]
    tools_lines = [
        body.rstrip()
        for s in stacks
        if (body := _read_fragment(s, "tools.md")) is not None
        and body.strip()
    ]
    summary_payload = "\n".join(summary_lines)
    tools_payload = "\n".join(tools_lines)

    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        base_path = _AGENT_FILES_BASE_DIR / fname
        if not base_path.exists():
            continue
        files[fname] = _inject_between_delimiters(
            base_path.read_text(),
            _STACKS_DELIMITER_START,
            _STACKS_DELIMITER_END,
            summary_payload,
        )

    skills_base = _AGENT_FILES_BASE_DIR / "skills.md"
    if skills_base.exists():
        files["skills.md"] = _inject_between_delimiters(
            skills_base.read_text(),
            _STACKS_DELIMITER_START,
            _STACKS_DELIMITER_END,
            tools_payload,
        )

    for stack in stacks:
        guidance = _read_fragment(stack, "guidance.md")
        if guidance is None:
            continue
        files[f"docs/agents/{stack}.md"] = guidance
        frontmatter = (
            "---\n"
            f"name: sunaba-{stack}\n"
            f"description: Use when working on {stack} parts of this project, "
            f"generated by sunaba --stack {stack}.\n"
            "---\n\n"
        )
        files[f".claude/skills/sunaba-{stack}/SKILL.md"] = frontmatter + guidance

    return files


def _splice_user_region(new_content: str, existing_content: str) -> str:
    """Re-inject the existing file's USER region into the regenerated content.

    If `existing_content` carries a body between SUNABA USER START / END
    markers and `new_content` also has those markers, replace the new
    body with the existing one. Otherwise return `new_content` unchanged.
    """
    es = existing_content.find(_USER_DELIMITER_START)
    ee = existing_content.find(_USER_DELIMITER_END)
    if es == -1 or ee == -1 or ee < es:
        return new_content
    user_body = existing_content[es + len(_USER_DELIMITER_START): ee]
    return _inject_between_delimiters(
        new_content, _USER_DELIMITER_START, _USER_DELIMITER_END, user_body.strip("\n")
    )


def _parse_rule_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a rule file's YAML-ish frontmatter.

    Supports the limited shape rule files use:
      ---
      name: foo
      description: short text
      globs:
        - "tests/**/*.py"
      alwaysApply: false
      targets:
        - claude
        - cursor
      ---
      <body>

    Returns (frontmatter_dict, body_str). Avoids a runtime PyYAML dependency.
    """
    if not text.startswith("---"):
        raise ValueError("rule file is missing the leading `---`")
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        raise ValueError("rule file is missing the closing `---`")
    fm_text = parts[0].lstrip("-").lstrip("\n")
    body = parts[1].lstrip("\n")

    fm: dict = {}
    current_list_key: str | None = None
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith(" ") and current_list_key is not None:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                value = stripped[2:].strip().strip("\"'")
                fm[current_list_key].append(value)
                continue
        current_list_key = None
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            fm[key] = []
            current_list_key = key
        else:
            fm[key] = rest.strip("\"'")
    return fm, body


def _render_rule(rule_text: str) -> dict[str, str]:
    """Render a canonical rule source to its multi-target outputs."""
    fm, body = _parse_rule_frontmatter(rule_text)
    name = fm.get("name")
    if not name:
        raise ValueError("rule file missing `name` in frontmatter")
    targets = fm.get("targets") or ["claude", "cursor", "codex", "gemini"]
    description = fm.get("description", "")
    globs = fm.get("globs") or []
    always_apply = str(fm.get("alwaysApply", "false")).lower()

    out: dict[str, str] = {}

    if "cursor" in targets:
        cursor_fm = ["---", f"description: {description}"]
        if globs:
            cursor_fm.append("globs:")
            cursor_fm.extend(f"  - \"{g}\"" for g in globs)
        cursor_fm.append(f"alwaysApply: {always_apply}")
        cursor_fm.append("---")
        out[f".cursor/rules/{name}.mdc"] = "\n".join(cursor_fm) + "\n\n" + body

    if "claude" in targets:
        # Claude path-specific rules use `paths:` rather than Cursor's `globs:`.
        claude_fm = ["---", f"description: {description}"]
        if globs:
            claude_fm.append("paths:")
            claude_fm.extend(f"  - \"{g}\"" for g in globs)
        claude_fm.append("---")
        out[f".claude/rules/{name}.md"] = "\n".join(claude_fm) + "\n\n" + body

    if "codex" in targets or "gemini" in targets:
        # Fallback: a docs page either CLI can read on demand. The proposal
        # allows directory-scoped AGENTS.md / GEMINI.md when globs map
        # cleanly to a single directory; that hierarchical placement is
        # left for a follow-up.
        if globs:
            globs_block = "\n".join(f"- `{g}`" for g in globs)
        else:
            globs_block = "_(no glob scope; applies repo-wide)_"
        preamble = (
            f"# {name}\n\n"
            f"_{description}_\n\n"
            "**Globs:**\n\n"
            f"{globs_block}\n\n"
            "---\n\n"
        )
        out[f"docs/agents/rules/{name}.md"] = preamble + body

    return out


def _build_rule_files(stacks: list[str]) -> dict[str, str]:
    """Walk each stack's `_rules` list and render every source."""
    files: dict[str, str] = {}
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if not stack_path.exists():
            continue
        data = json.loads(stack_path.read_text())
        for rule_rel in data.get("_rules") or []:
            rule_path = TEMPLATES_DIR / rule_rel
            resolved = rule_path.resolve()
            if not resolved.is_relative_to(TEMPLATES_DIR.resolve()):
                raise ValueError(
                    f"Stack '{name}' _rules source escapes templates: {rule_rel}"
                )
            if not resolved.exists():
                raise FileNotFoundError(
                    f"Stack '{name}' _rules source missing: {rule_rel}"
                )
            rendered = _render_rule(resolved.read_text())
            files.update(rendered)
    return files


def _build_stack_files(stacks: list[str]) -> dict[str, str]:
    """Read each chosen stack's `_files` map and return {dest: content}.

    `_files` maps a project-relative destination path to a source path under
    `templates/`. Sources are resolved under `TEMPLATES_DIR`; destinations are
    validated to reject `..` and absolute paths in callers via `_safe_target`.

    Collision rule: later stacks in the input list overwrite earlier ones
    (same convention as the deep-merge composer's scalar overwrite).
    """
    files: dict[str, str] = {}
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if not stack_path.exists():
            continue
        data = json.loads(stack_path.read_text())
        for dest, source_rel in (data.get("_files") or {}).items():
            if Path(dest).is_absolute() or ".." in Path(dest).parts:
                raise ValueError(
                    f"Stack '{name}' declares unsafe _files destination: {dest}"
                )
            source_path = TEMPLATES_DIR / source_rel
            resolved = source_path.resolve()
            if not resolved.is_relative_to(TEMPLATES_DIR.resolve()):
                raise ValueError(
                    f"Stack '{name}' _files source escapes templates: {source_rel}"
                )
            if not resolved.exists():
                raise FileNotFoundError(
                    f"Stack '{name}' _files source missing: {source_rel}"
                )
            files[dest] = resolved.read_text()
    return files


def _stacks_owning_path(stacks: list[str]) -> dict[str, list[str]]:
    """Return {dest_path: [stack_name, ...]} for every `_files`-emitted path.

    Used by orphan reporting on `rebuild --remove`. Order in the value list
    matches stack ordering (later stacks at the end).
    """
    owners: dict[str, list[str]] = {}
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if not stack_path.exists():
            continue
        data = json.loads(stack_path.read_text())
        for dest in (data.get("_files") or {}).keys():
            owners.setdefault(dest, []).append(name)
    return owners


def _scan_orphans(
    project_dir: Path, removed_stacks: list[str], remaining_stacks: list[str]
) -> list[tuple[str, list[str]]]:
    """Return [(relpath, [removed_stack_owners])] for files left behind.

    A file is an orphan if (a) it currently exists in the project, (b) at
    least one of `removed_stacks` would have emitted it via `_files`, and
    (c) no stack in `remaining_stacks` would emit it.

    We do NOT delete. We report so the user can `rm` themselves.
    """
    all_known = set(available_stacks())
    removed_owners = _stacks_owning_path(
        [s for s in removed_stacks if s in all_known]
    )
    remaining_emitted = set(_stacks_owning_path(remaining_stacks).keys())
    orphans: list[tuple[str, list[str]]] = []
    for relpath, owners in removed_owners.items():
        if relpath in remaining_emitted:
            continue
        target = project_dir / relpath
        if target.exists():
            orphans.append((relpath, owners))
    orphans.sort(key=lambda x: x[0])
    return orphans


def _build_config_files(
    name: str, stacks: list[str], *, no_devcontainer: bool = False
) -> dict[str, str]:
    """Compose all config file contents for a project. Returns {relpath: content}.

    When no_devcontainer is True, `.devcontainer/*` are skipped and
    `dependabot.yml` is filtered to drop devcontainer/docker ecosystems.
    Host-agnostic files (`.mcp.json`, `.vscode/settings.json`) are still emitted.

    Stack `_files` emissions (e.g. `--stack harness` adds `.claude/...`) are
    merged in here too. Later stacks overwrite earlier on collision.
    """
    config = compose(stacks)
    config["name"] = f"sunaba-{name}"

    post_start_parts = []
    for s in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{s}.json"
        if stack_path.exists():
            data = json.loads(stack_path.read_text())
            psc = data.get("postStartCommand", "")
            if psc:
                post_start_parts.append(psc)
    if post_start_parts:
        config["postStartCommand"] = " && ".join(post_start_parts)

    clean_config = _clean_devcontainer(config)
    files: dict[str, str] = {}

    if not no_devcontainer:
        files[".devcontainer/devcontainer.json"] = (
            json.dumps(clean_config, indent=2, ensure_ascii=False) + "\n"
        )
        files[".devcontainer/bootstrap.sh"] = _build_bootstrap(stacks)

    files[".github/dependabot.yml"] = _build_dependabot_simple(
        stacks, no_devcontainer=no_devcontainer
    )

    # .mcp.json for Claude Code -> codex/gemini-cli via MCP
    mcp_template = TEMPLATES_DIR / "base" / "mcp.json"
    if mcp_template.exists():
        files[".mcp.json"] = mcp_template.read_text()

    vscode_settings = (
        clean_config.get("customizations", {}).get("vscode", {}).get("settings", {})
    )
    if vscode_settings:
        files[".vscode/settings.json"] = (
            json.dumps(vscode_settings, indent=2, ensure_ascii=False) + "\n"
        )

    # Stack-aware agent file composition (root AGENTS/CLAUDE/GEMINI/skills.md
    # with stack-specific sections injected between SUNABA STACKS delimiters,
    # plus docs/agents/<stack>.md and .claude/skills/sunaba-<stack>/SKILL.md).
    files.update(_build_agent_files(stacks, no_devcontainer=no_devcontainer))

    # Stack `_files` emissions (later stacks win on collision). These run
    # AFTER the stack-aware agent files so a stack like `harness` can
    # override the composed AGENTS.md with its stronger ratchet version.
    files.update(_build_stack_files(stacks))

    # Stack `_rules` emissions (multi-target rule renders for Claude /
    # Cursor / Codex / Gemini). Rule paths don't collide with the
    # earlier passes' outputs, but `update()` keeps the same later-wins
    # convention if anything ever does.
    files.update(_build_rule_files(stacks))

    return files


# Stack-specific host commands needed when running without a devcontainer.
# Maps stack name -> (command, human description).
_STACK_HOST_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "python": ("uv", "Python package manager (--stack python)"),
    "aws": ("aws", "AWS CLI (--stack aws)"),
    "azure": ("az", "Azure CLI (--stack azure)"),
    "gcp": ("gcloud", "Google Cloud CLI (--stack gcp)"),
    "neon": ("neonctl", "Neon Postgres CLI (--stack neon)"),
    "nextjs": ("vercel", "Vercel CLI (--stack nextjs)"),
}

# Always-required commands when running --no-devcontainer (agent CLIs + MCP runtime).
_BASE_HOST_REQUIREMENTS: list[tuple[str, str]] = [
    ("claude", "Claude Code CLI"),
    ("codex", "OpenAI Codex CLI"),
    ("gemini", "Google Gemini CLI"),
    ("npx", "Node.js / npx (MCP: gemini-cli, playwright, chrome-devtools)"),
    ("uvx", "uv / uvx (MCP: notebooklm-mcp-cli)"),
]


def _missing_host_commands(
    stacks: list[str], which: callable = shutil.which
) -> list[tuple[str, str]]:
    """Return [(command, reason)] for host commands that are not on PATH.

    Used by --no-devcontainer mode to warn the user about anything they need
    to install themselves. `which` is injectable for tests.
    """
    requirements: list[tuple[str, str]] = list(_BASE_HOST_REQUIREMENTS)
    for s in stacks:
        if s in _STACK_HOST_REQUIREMENTS:
            requirements.append(_STACK_HOST_REQUIREMENTS[s])
    return [(cmd, reason) for cmd, reason in requirements if which(cmd) is None]


def _safe_target(project_dir: Path, relpath: str) -> Path:
    """Resolve a relative path under project_dir, rejecting traversal and symlinks.

    Fail-closed: any component that is an existing symlink, any resolved path
    that escapes project_dir, or any parent-escape segment ('..') is rejected.
    """
    root = project_dir.resolve()
    if ".." in Path(relpath).parts or Path(relpath).is_absolute():
        raise ValueError(f"Unsafe relative path: {relpath}")
    target = project_dir / relpath
    # Reject any existing symlink along the path (file or parent dir).
    probe = target
    while probe != project_dir and probe != probe.parent:
        if probe.is_symlink():
            raise ValueError(f"Refusing to write through symlink: {probe}")
        probe = probe.parent
    # Resolve parents that exist; ensure the eventual location stays inside root.
    existing = target
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    if not existing.resolve().is_relative_to(root):
        raise ValueError(f"Target escapes project directory: {target}")
    return target


def _write_files(project_dir: Path, files: dict[str, str]) -> list[str]:
    """Write generated files to disk. Returns list of relative paths written.

    Refuses to write through symlinks or outside project_dir.
    """
    written = []
    for relpath, content in files.items():
        full = _safe_target(project_dir, relpath)
        full.parent.mkdir(parents=True, exist_ok=True)
        # If an existing symlink slipped past the earlier check (race), remove it.
        if full.is_symlink():
            raise ValueError(f"Refusing to overwrite symlink: {full}")
        full.write_text(content)
        if relpath.endswith(".sh"):
            full.chmod(0o755)
        written.append(relpath)
    return written


def _diff_files(project_dir: Path, files: dict[str, str]) -> dict[str, str]:
    """Return {relpath: status} where status is 'new', 'modified', or 'unchanged'."""
    diff = {}
    for relpath, content in files.items():
        full = _safe_target(project_dir, relpath)
        if not full.exists():
            diff[relpath] = "new"
        elif full.is_symlink():
            # Surface as modified so the user sees it in the diff; write path rejects it.
            diff[relpath] = "modified"
        elif full.read_text() != content:
            diff[relpath] = "modified"
        else:
            diff[relpath] = "unchanged"
    return diff


@click.group()
@click.version_option(version="0.2.1")
def main():
    """sunaba-cli: One-command devcontainer sandbox for AI agent development."""
    pass


@main.command()
@click.argument("name")
@click.option("--stack", "-s", multiple=True, help="Stack to include (repeatable). Omit to pick interactively.")
@click.option("--path", "-p", type=click.Path(), default=None, help="Parent directory.")
@click.option("--no-agents", is_flag=True, default=False, help="Skip agent files.")
@click.option("--no-prompt", is_flag=True, default=False, help="Disable interactive stack prompt (default to python).")
@click.option(
    "--no-devcontainer",
    is_flag=True,
    default=False,
    help="Skip devcontainer files. Generates host-only setup (agent files, .mcp.json, .vscode, dependabot).",
)
def new(
    name: str,
    stack: tuple[str, ...],
    path: str | None,
    no_agents: bool,
    no_prompt: bool,
    no_devcontainer: bool,
):
    """Create a new sandbox project with devcontainer configuration.

    Examples:
        sunaba new myapp                            # interactive stack picker
        sunaba new myapp --stack python             # explicit
        sunaba new webapp --stack nextjs --stack aws
        sunaba new headless --no-prompt             # script-safe, defaults to python
        sunaba new local --stack python --no-devcontainer   # host-only, skip devcontainer
    """
    if stack:
        stacks = list(stack)
    elif no_prompt or not sys.stdin.isatty():
        stacks = ["python"]
    else:
        stacks = _interactive_select_stacks()
    parent = Path(path) if path else Path.cwd()

    if "/" in name or "\\" in name or ".." in name or name.startswith("-"):
        click.echo("Error: Project name must be a simple name without path separators or '..'.", err=True)
        raise SystemExit(1)

    project_dir = parent / name
    if not project_dir.resolve().is_relative_to(parent.resolve()):
        click.echo("Error: Project path escapes parent directory.", err=True)
        raise SystemExit(1)

    _validate_stacks(stacks)

    if project_dir.exists():
        click.echo(f"Error: Directory already exists: {project_dir}", err=True)
        click.echo("Hint: use 'sunaba rebuild' to change stacks on an existing project.", err=True)
        raise SystemExit(1)

    project_dir.mkdir(parents=True)

    files = _build_config_files(name, stacks, no_devcontainer=no_devcontainer)
    written = _write_files(project_dir, files)
    for relpath in written:
        click.echo(f"  Created {relpath}")

    if not no_agents:
        # Skip agent files that a stack `_files` map already wrote so we don't
        # clobber e.g. the harness stack's AGENTS.md with the generic one.
        skip = {fname for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "skills.md") if fname in files}
        copied = copy_agent_files(project_dir, skip=skip)
        if copied:
            click.echo(f"  Copied agent files: {', '.join(copied)}")

    (project_dir / ".gitignore").write_text(_default_gitignore())

    # Generic SECURITY.md scaffold — written on project creation only.
    # `sunaba rebuild` deliberately leaves it alone so user edits to the
    # report channel, scope statement, etc. survive across rebuilds.
    security_template = TEMPLATES_DIR / "base" / "SECURITY.md"
    if security_template.exists():
        (project_dir / "SECURITY.md").write_text(security_template.read_text())
        click.echo("  Created SECURITY.md")

    register_project(name, project_dir, stacks)

    mode_label = "host-only" if no_devcontainer else "devcontainer"
    click.echo(
        f"\nSunaba '{name}' created at {project_dir} "
        f"(stacks: {', '.join(stacks)}, mode: {mode_label})"
    )

    if no_devcontainer:
        missing = _missing_host_commands(stacks)
        if missing:
            click.echo(
                "\nWarning: the following host commands are not on PATH. "
                "Install them on the host before running the agents:"
            )
            for cmd, reason in missing:
                click.echo(f"  - {cmd}  ({reason})")
        click.echo("\nNext steps:")
        click.echo(f"  cd {project_dir}")
        click.echo("  # Run agents directly on the host (claude / codex / gemini).")
    else:
        click.echo("\nNext steps:")
        click.echo(f"  cd {project_dir}")
        click.echo("  code .")
        click.echo("  # VS Code: Cmd+Shift+P -> 'Dev Containers: Reopen in Container'")


def _resolve_target(name_or_path: str) -> tuple[str, Path, list[str]]:
    """Resolve a name or path to (name, project_dir, current_stacks).

    Tries registered name first, then path, then cwd-relative dir.
    Returns empty stacks if not registered.
    """
    entry = get_project(name_or_path)
    if entry is not None:
        return name_or_path, Path(entry["path"]), list(entry.get("stacks") or [])

    candidate = Path(name_or_path).expanduser()
    if candidate.is_absolute() or "/" in name_or_path:
        if candidate.exists() and candidate.is_dir():
            return candidate.name, candidate.resolve(), []
    cwd_candidate = Path.cwd() / name_or_path
    if cwd_candidate.exists() and cwd_candidate.is_dir():
        return cwd_candidate.name, cwd_candidate.resolve(), []

    raise FileNotFoundError(name_or_path)


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--stack", "-s", multiple=True, required=True, help="Stack list for this project.")
@click.option("--name", default=None, help="Override registry name (defaults to directory name).")
def register(path: str, stack: tuple[str, ...], name: str | None):
    """Register an existing project directory with sunaba.

    Existing devcontainer files are NOT modified. Use 'sunaba rebuild' after
    registering to regenerate/apply stack changes.

    Examples:
        sunaba register /path/to/existing-project --stack python --stack nextjs
    """
    project_dir = Path(path).resolve()
    stacks = list(stack)
    _validate_stacks(stacks)
    proj_name = name or project_dir.name
    register_project(proj_name, project_dir, stacks)
    click.echo(f"Registered '{proj_name}' at {project_dir} (stacks: {', '.join(stacks)})")
    click.echo("Next: sunaba rebuild " + proj_name + "  # to regenerate devcontainer files")


@main.command()
@click.argument("name_or_path")
@click.option("--stack", "-s", multiple=True, help="New stack list (replaces current).")
@click.option("--add", multiple=True, help="Add stack(s) to current list.")
@click.option("--remove", multiple=True, help="Remove stack(s) from current list.")
@click.option("--dry-run", is_flag=True, default=False, help="Show diff without writing.")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation.")
def rebuild(
    name_or_path: str,
    stack: tuple[str, ...],
    add: tuple[str, ...],
    remove: tuple[str, ...],
    dry_run: bool,
    yes: bool,
):
    """Rebuild an existing sandbox with a new stack configuration.

    Accepts either a registered project name or a path to an existing
    directory. Unregistered directories are auto-registered if --stack
    is provided.

    Examples:
        sunaba rebuild myapp --stack python --stack aws    # replace stacks
        sunaba rebuild myapp --add nextjs                   # add stack
        sunaba rebuild myapp --remove docker                # remove stack
        sunaba rebuild /path/to/project --stack python     # auto-register + rebuild
        sunaba rebuild myapp --add gcp --dry-run            # preview only
    """
    try:
        name, project_dir, current_stacks = _resolve_target(name_or_path)
    except FileNotFoundError:
        click.echo(f"Error: '{name_or_path}' is neither a registered project nor an existing directory.", err=True)
        click.echo("Hint: use 'sunaba register <path> --stack ...' first, or pass an existing path.", err=True)
        raise SystemExit(1)

    if not current_stacks and not (stack or add):
        click.echo(f"Error: '{name}' is not registered and has no known stacks.", err=True)
        click.echo("Hint: specify --stack to register and rebuild in one step.", err=True)
        raise SystemExit(1)

    if not project_dir.exists():
        click.echo(f"Error: Project directory missing: {project_dir}", err=True)
        raise SystemExit(1)

    if stack:
        new_stacks = list(stack)
    else:
        new_stacks = list(current_stacks)
        for s in add:
            if s not in new_stacks:
                new_stacks.append(s)
        for s in remove:
            if s in new_stacks:
                new_stacks.remove(s)

    if not new_stacks:
        click.echo("Error: Resulting stack list is empty.", err=True)
        raise SystemExit(1)

    _validate_stacks(new_stacks)

    click.echo(f"Project: {name} ({project_dir})")
    click.echo(f"  Current stacks: {', '.join(current_stacks) or '(unknown)'}")
    click.echo(f"  New stacks:     {', '.join(new_stacks)}")
    click.echo("")

    files = _build_config_files(name, new_stacks)
    diff = _diff_files(project_dir, files)

    click.echo("Changes:")
    for relpath, status in diff.items():
        marker = {"new": "+", "modified": "~", "unchanged": "="}[status]
        click.echo(f"  {marker} {relpath} ({status})")

    has_changes = any(s != "unchanged" for s in diff.values())
    if not has_changes:
        click.echo("\nNothing to change.")
        # Still update registry if stacks metadata changed
        if new_stacks != current_stacks:
            register_project(name, project_dir, new_stacks)
            click.echo("Updated registry metadata.")
        return

    if dry_run:
        click.echo("\nDry run — no files written.")
        return

    if not yes:
        if not click.confirm("\nApply these changes?", default=False):
            click.echo("Aborted.")
            return

    written = _write_files(project_dir, files)
    click.echo(f"\nWrote {len(written)} file(s).")
    register_project(name, project_dir, new_stacks)
    click.echo(f"Registry updated. Project now uses: {', '.join(new_stacks)}")

    removed = [s for s in current_stacks if s not in new_stacks]
    if removed:
        orphans = _scan_orphans(project_dir, removed, new_stacks)
        if orphans:
            click.echo(
                f"\nStack(s) {', '.join(removed)} were removed. "
                "The following files are no longer managed by any selected stack "
                "and were left in place:"
            )
            for relpath, owners in orphans:
                click.echo(f"  {relpath}    (was emitted by --stack {', '.join(owners)})")
            click.echo(
                "\nDelete them manually if you no longer need them, or restore the "
                f"stack(s) with:  sunaba rebuild {name} --add {' --add '.join(removed)}"
            )


@main.command()
@click.argument("name", required=False)
@click.option("--all", "sync_all_flag", is_flag=True, help="Sync all registered projects.")
def sync(name: str | None, sync_all_flag: bool):
    """Sync agent instruction files to registered projects."""
    if sync_all_flag:
        results = sync_all()
        if not results:
            click.echo("No registered projects found.")
            return
        for proj_name, proj_path, copied in results:
            click.echo(f"  {proj_name} ({proj_path}): {', '.join(copied) if copied else 'no files'}")
        click.echo(f"\nSynced {len(results)} project(s).")
    elif name:
        proj_path, copied = sync_project(name)
        if proj_path is None:
            click.echo(f"Error: Project '{name}' not found in registry.", err=True)
            raise SystemExit(1)
        click.echo(f"  Synced to {proj_path}: {', '.join(copied) if copied else 'no files'}")
    else:
        click.echo("Error: Provide a project name or use --all.", err=True)
        raise SystemExit(1)


def _merge_gitignore(existing: str, baseline: str) -> tuple[str, list[str]]:
    """Merge `baseline` into `existing`, preserving user lines that are
    not already present. Returns (merged_text, added_lines).

    Strategy: emit the baseline verbatim, then append any lines from
    existing that don't already match a baseline line. This keeps the
    `.gitignore`'s structure (sections / blank lines / comments)
    deterministic and the user's additions visible at the end.
    """
    baseline_lines = baseline.splitlines()
    baseline_pattern_lines = {
        ln.strip() for ln in baseline_lines if ln.strip() and not ln.lstrip().startswith("#")
    }
    existing_lines = existing.splitlines()
    extras: list[str] = []
    for ln in existing_lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped in baseline_pattern_lines:
            continue
        extras.append(ln)
    merged = baseline.rstrip("\n") + "\n"
    if extras:
        merged += "\n# --- preserved from existing .gitignore ---\n"
        merged += "\n".join(extras) + "\n"
    return merged, extras


@main.command("sync-gitignore")
@click.argument("name_or_path", required=False)
@click.option("--all", "sync_all_flag", is_flag=True, help="Walk every registered project.")
@click.option("--dry-run", is_flag=True, default=False, help="Show diff without writing.")
@click.option("--force", is_flag=True, default=False,
              help="Apply to any directory, even if it isn't a registered sunaba project.")
def sync_gitignore_cmd(
    name_or_path: str | None, sync_all_flag: bool, dry_run: bool, force: bool
):
    """Bring an existing project's `.gitignore` up to the current sunaba baseline.

    `sunaba new` writes the current baseline; `sunaba rebuild` does not
    touch `.gitignore` (preserves user edits). Use this command on
    existing projects after upgrading sunaba-cli to absorb new ignore
    patterns (e.g. cloud credential files, agent local state) without
    losing your own additions.

    Examples:
      sunaba sync-gitignore myapp           # diff + confirm
      sunaba sync-gitignore myapp --dry-run # diff only
      sunaba sync-gitignore --all           # walk every registered project
    """
    baseline = _default_gitignore()
    targets: list[tuple[str, Path]] = []
    if sync_all_flag:
        for n, entry in list_projects().items():
            p = Path(entry["path"])
            if p.exists():
                targets.append((n, p))
    elif name_or_path:
        try:
            n, p, _stacks = _resolve_target(name_or_path)
        except FileNotFoundError:
            if force and Path(name_or_path).is_dir():
                n, p = Path(name_or_path).name, Path(name_or_path).resolve()
            else:
                click.echo(
                    f"Error: '{name_or_path}' is not a registered project. "
                    "Pass --force to apply to any directory.",
                    err=True,
                )
                raise SystemExit(1)
        targets.append((n, p))
    else:
        click.echo("Error: Provide a project name/path or use --all.", err=True)
        raise SystemExit(1)

    any_changes = False
    for n, project_dir in targets:
        gi_path = _safe_target(project_dir, ".gitignore")
        existing = gi_path.read_text() if gi_path.exists() else ""
        merged, extras = _merge_gitignore(existing, baseline)
        if existing == merged:
            click.echo(f"  {n}: .gitignore already at baseline")
            continue
        any_changes = True
        click.echo(f"\nProject: {n} ({project_dir})")
        click.echo(f"  baseline lines added: ~{len([l for l in baseline.splitlines() if l.strip() and not l.lstrip().startswith('#')])}")
        click.echo(f"  user lines preserved: {len(extras)}")
        if dry_run:
            click.echo("  (dry run — not written)")
            continue
        gi_path.write_text(merged)
        click.echo(f"  wrote {gi_path}")

    if not any_changes:
        click.echo("\nNothing to update.")


@main.command("list")
def list_cmd():
    """List all registered sandbox projects."""
    projects = list_projects()
    if not projects:
        click.echo("No registered projects.")
        return
    # Compute column widths
    name_width = max((len(n) for n in projects), default=4)
    for name, entry in projects.items():
        path = entry["path"]
        stacks = entry.get("stacks") or []
        exists = "ok" if Path(path).exists() else "missing"
        stack_str = ", ".join(stacks) if stacks else "(unknown)"
        click.echo(f"  {name:{name_width}s}  [{exists}]  stacks: {stack_str}")
        click.echo(f"  {'':{name_width}s}  path: {path}")


@main.command()
def stacks():
    """List available stacks."""
    for name in available_stacks():
        desc = stack_description(name) or "(no description)"
        click.echo(f"  {name:10s}  {desc}")


DEFAULT_UPGRADE_REPO = "git+https://github.com/morimorijap/sunaba-cli"


@main.command()
@click.option("--repo", default=None, help="Git URL override (default: public GitHub).")
def upgrade(repo: str | None):
    """Upgrade sunaba-cli to the latest version from GitHub."""
    if repo is None:
        repo = DEFAULT_UPGRADE_REPO
    else:
        if repo.startswith("http"):
            repo = f"git+{repo}"
        elif not repo.startswith("git+"):
            repo = f"git+{repo}"

    uv_bin = shutil.which("uv")
    if uv_bin is None:
        click.echo(
            "Error: 'uv' is not on PATH. Install it from https://docs.astral.sh/uv/ "
            "and try again.",
            err=True,
        )
        raise SystemExit(1)

    # `uv tool upgrade` only accepts package names, not git URLs. For a
    # tool installed from a git URL, the canonical "pull latest" form is
    # `uv tool install --reinstall <git-url>`.
    click.echo("Upgrading sunaba-cli...")
    result = subprocess.run(
        [uv_bin, "tool", "install", "--reinstall", repo],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(result.stdout.strip() or result.stderr.strip() or "Upgraded successfully.")
    else:
        click.echo(f"Error: {result.stderr.strip() or result.stdout.strip()}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
