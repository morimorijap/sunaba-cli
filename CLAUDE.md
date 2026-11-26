# CLAUDE.md

## Temporary files

- Put temporary files (scratch scripts, intermediate output, test artifacts, logs) in `tmp/` at the repository root — not in `/tmp`, `/private/tmp`, or other system temp directories.
- Create `tmp/` if it does not exist (`mkdir -p tmp`).
- `tmp/` is listed in `.gitignore`; never commit anything from it.
