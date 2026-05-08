# verify-change

Use **after implementation, before final response.**

## Steps

1. Inspect `git diff --stat` and `git diff`.
2. Run the smallest relevant checks (typecheck, lint, the touched test
   file).
3. Report failures with exact command output, not paraphrased.
4. Record unresolved risk in `claudedocs/traces/<short-name>.md` only
   when it is genuinely useful for future sessions.
