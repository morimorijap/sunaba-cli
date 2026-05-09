---
name: python-tests
description: Python tests use pytest fixtures, not unittest classes.
globs:
  - "tests/**/*.py"
alwaysApply: false
targets:
  - claude
  - cursor
  - codex
  - gemini
---

# Python test rules

- Use pytest fixtures. Do not introduce `unittest.TestCase`.
- Tests live under `tests/` and mirror the source layout
  (`src/foo/bar.py` → `tests/foo/test_bar.py`).
- Prefer `uv run pytest -q` (project-local, deterministic). Don't use
  the system `pytest`.
- Don't generate fixtures with real-looking secrets — use synthetic
  data and the project's existing factory helpers.
