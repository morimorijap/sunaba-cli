"""sunaba-cli: One-command devcontainer sandbox for AI agent development."""

from __future__ import annotations

import json
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


def _build_config_files(
    name: str, stacks: list[str], *, no_devcontainer: bool = False
) -> dict[str, str]:
    """Compose all config file contents for a project. Returns {relpath: content}.

    When no_devcontainer is True, `.devcontainer/*` are skipped and
    `dependabot.yml` is filtered to drop devcontainer/docker ecosystems.
    Host-agnostic files (`.mcp.json`, `.vscode/settings.json`) are still emitted.
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

    return files


def _stack_features_for_warning(stacks: list[str]) -> list[tuple[str, list[str]]]:
    """For each stack, return (stack, [feature short-names]) for devcontainer
    features that won't auto-install in --no-devcontainer mode. Stacks with no
    features are omitted.
    """
    out: list[tuple[str, list[str]]] = []
    for name in stacks:
        stack_path = TEMPLATES_DIR / "stacks" / f"{name}.json"
        if not stack_path.exists():
            continue
        data = json.loads(stack_path.read_text())
        features = data.get("features") or {}
        if not features:
            continue
        tools = [fid.split("/")[-1].split(":")[0] for fid in features]
        out.append((name, tools))
    return out


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
@click.version_option(version="0.1.0")
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
        copied = copy_agent_files(project_dir)
        if copied:
            click.echo(f"  Copied agent files: {', '.join(copied)}")

    gitignore = (
        ".venv/\nnode_modules/\n__pycache__/\n.env\n.env.local\n*.pyc\n.DS_Store\n"
    )
    (project_dir / ".gitignore").write_text(gitignore)

    register_project(name, project_dir, stacks)

    mode_label = "host-only" if no_devcontainer else "devcontainer"
    click.echo(
        f"\nSunaba '{name}' created at {project_dir} "
        f"(stacks: {', '.join(stacks)}, mode: {mode_label})"
    )

    if no_devcontainer:
        manual = _stack_features_for_warning(stacks)
        if manual:
            click.echo(
                "\nWarning: --no-devcontainer skips devcontainer features. "
                "Install these tools on the host yourself if you need them:"
            )
            for stack_name, tools in manual:
                click.echo(f"  - {stack_name}: {', '.join(tools)}")
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
        repo = f"git+{repo}" if not repo.startswith(("git+", "http")) else repo
        if repo.startswith("http"):
            repo = f"git+{repo}"

    click.echo("Upgrading sunaba-cli...")
    result = subprocess.run(
        [sys.executable, "-m", "uv", "tool", "upgrade", repo],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(result.stdout.strip() or "sunaba-cli is up to date.")
    else:
        click.echo("Trying reinstall...")
        result = subprocess.run(
            [sys.executable, "-m", "uv", "tool", "install", "--upgrade", repo],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            click.echo(result.stdout.strip() or "Upgraded successfully.")
        else:
            click.echo(f"Error: {result.stderr.strip()}", err=True)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
