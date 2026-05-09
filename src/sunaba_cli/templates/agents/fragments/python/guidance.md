# Python stack

This sandbox uses Python 3.14 with `uv` for dependency management.

## Day-to-day

```sh
uv sync                  # install / update deps from pyproject.toml
uv run pytest -q         # run tests
uv run ruff check        # lint
uv run ruff format       # format
```

## Conventions

- Edit `pyproject.toml` directly to add deps; let `uv sync` resolve.
  Don't write to `requirements.txt`.
- Type-hint new code. The project does not require 100% coverage,
  but new functions should annotate args and return types.
- Tests live under `tests/`. Match the source path structure.

## What not to do

- Don't run `pip install` against the project's `.venv`.
- Don't commit the `.venv/` (already in `.gitignore`).
- Don't generate fixtures with real-looking secrets.
