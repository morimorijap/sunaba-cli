# Contributing to sunaba-cli

Thanks for your interest! `sunaba-cli` is a small tool and contributions of
all sizes are welcome.

## Development setup

```bash
git clone https://github.com/morimorijap/sunaba-cli
cd sunaba-cli
uv sync
uv run sunaba --help
```

To try a local checkout as a global tool:

```bash
uv tool install --editable .
```

## Project layout

```
src/sunaba_cli/
├── cli.py             # Click entrypoints (new/rebuild/register/sync/list/stacks/upgrade)
├── compose.py         # Stack composition (JSON deep-merge)
├── sync.py            # Registry + agent file sync
└── templates/
    ├── base/          # Base devcontainer + bootstrap + mcp.json + dependabot
    ├── stacks/        # One JSON per stack (python, nextjs, aws, ...)
    └── agents/        # AGENTS.md / CLAUDE.md / skills.md
```

### How stack composition works

1. `compose.py` loads `templates/base/devcontainer.json`
2. For each stack passed on the CLI, it deep-merges
   `templates/stacks/<name>.json` on top
3. Merge rules: dicts recurse, lists concat + dedupe, scalars overwrite
4. Keys starting with `_` (e.g. `_bootstrap`, `_dependabot`, `_description`)
   are internal — they drive other generated files and are stripped from
   `devcontainer.json` before writing

### Adding a new stack

1. Create `src/sunaba_cli/templates/stacks/<name>.json`
2. Fill in `_description`, any `features`, `remoteEnv`, `customizations`,
   and `_bootstrap` (list of bash lines). Files the stack writes into the
   project go in `_files` (destination → template path, copied verbatim),
   and agent guidance in `templates/agents/fragments/<name>/`
3. Run `uv run sunaba stacks` to confirm it shows up
4. Test with `uv run sunaba new testproj --stack <name>`
5. Inspect the generated `.devcontainer/` and `bootstrap.sh`
6. Add tests under `tests/` (see `tests/test_security_ci.py` for the
   pattern: assert on generated text, and execute generated scripts
   against fake binaries). Generated GitHub workflows must pin actions to
   commit SHAs and images to digests; `tests/test_supply_chain.py`
   enforces it
7. For non-trivial stacks, write the design first under `thinking/`

## Releases

1. Bump `version` in `pyproject.toml` and `@click.version_option` in
   `src/sunaba_cli/cli.py`, then run `uv lock`.
2. Add a section to [CHANGELOG.md](CHANGELOG.md).
3. After the PR merges, tag the merge commit `vX.Y.Z` and publish a
   GitHub release with the changelog section.

## Code style

- Python 3.11+, type hints where they help readability
- Keep `cli.py` thin — business logic belongs in `compose.py` / `sync.py`
- No external runtime dependencies beyond `click` unless unavoidable
- Fail-closed on anything security-adjacent (paths, symlinks, lockfiles)

## Security-sensitive changes

Any change that touches path handling, symlinks, `subprocess` calls, or
`remoteEnv` injection needs extra care. Please call it out in the PR
description so reviewers know to scrutinize it. See [SECURITY.md](SECURITY.md).

## Commit messages

Conventional style appreciated:

- `feat: add rust stack`
- `fix: reject symlink writes in rebuild`
- `docs: clarify agents stack caveat`

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
