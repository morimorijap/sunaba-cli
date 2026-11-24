# Following up on maruda and sakuda (2026-09-20 → 2026-11-21)

> Status: **three PRs open** (#30, #31, #32). Started 2026-11-21.
> Follows [`2026-09-24-maruda-adoption/`](../2026-09-24-maruda-adoption/)
> and [`2026-09-24-security-ci-gates/`](../2026-09-24-security-ci-gates/).

sunaba adapted [northraystudio/maruda](https://github.com/northraystudio/maruda)
at `99dd798` (2026-09-20). Since then maruda reached 0.4.6 (`5f9b323`,
2026-11-07, 37 files changed), and its companion DAST tool
[northraystudio/sakuda](https://github.com/northraystudio/sakuda)
(both MIT, © 2026 NorthRay Studio株式会社) shipped about 40 PRs up to
`38bbd28` (2026-11-19). This note records what we read, what we take,
what we leave, and why.

Upstream also fixed one point that sunaba raised: maruda#34 makes the
generated Semgrep job fail on findings (`--error`). sunaba's gate already
did.

## Taken, split into three PRs

The changes touch different stacks and carry different risks, so they
ship separately, the way #27 (secrets fix) and #28 (security-ci feature)
did. CHANGELOG is written at release time (as in #29), so none of the
three edits it and they do not conflict.

| PR | Scope | Source | Why |
|---|---|---|---|
| #30 `fix(base)` | `sunaba new` writes `.gitattributes` pinning scripts to LF; sunaba's own repo gets one too | sakuda#85 (idea only) | A Windows clone with `core.autocrlf=true` checks the generated `*.sh`, hooks and `.githooks/pre-push` out with CRLF, and they fail in the Linux container. Affects every project, so it is a fix on its own |
| #31 `docs(rules)` | `nextjs-api` rule and the nextjs guidance: privilege and ownership fields come from the session, never the request; no `data: body`; no authorization from JWT claims alone | maruda#25 (idea; own wording) | "Validate the body" does not stop mass assignment when the schema accepts `role` or `ownerId`. Documentation only |
| #32 `feat(security-ci)` | Project Semgrep rules in `.semgrep/` join the `SAST (Semgrep)` job when a rule file exists; fixtures are excluded | maruda#27, #37, `docs/semgrep-rules.md` | Lets a project turn a confirmed finding into a rule that blocks regressions, with no workflow edit |

### How the security-ci change differs from maruda

maruda copies its shared rules into `.semgrep/maruda/` and generates a
`.semgrepignore` listing `.semgrep/` so rule fixtures are not reported.
sunaba deliberately generates no `.semgrepignore`: creating one replaces
Semgrep's default ignore list (`node_modules/`, `tests/`, …), and the
file is the user's. Instead the job always passes `--exclude .semgrep`.

Verified against the pinned image `semgrep/semgrep:1.178.0` before
writing the code:

| Case | Result |
|---|---|
| `--config .semgrep`, rule + vulnerable fixture, no exclude | fixture reported (the problem) |
| same with `--exclude .semgrep` | only app code reported; `node_modules/`, `tests/` still skipped by default |
| `--config .semgrep` with only fixtures (`*.ts`, `*.test.yml`) | exit 7 → the has-rules check is required |
| no `.semgrep/`, `--exclude .semgrep` only | exit 0 → excluding unconditionally is safe |
| malformed rule | exit 7 → the gate fails closed |

The step uses `set -- …` / `"$@"` instead of a bash array, so it does
not depend on the container's shell. The real-binary tests run the
step against the same image through Docker in sunaba's CI
(`semgrep-contract` job), reading the digest from the template so
there is one pin. Removing `--exclude .semgrep` makes two of them fail.

`--exclude .semgrep` also means code inside `.semgrep/` is never
scanned, so the docs add `.semgrep/` to the files that should require a
code-owner review.

### Not taken: maruda's shared `mass-assignment-request-body` rule

Considered bundling it into `.semgrep/` of generated projects. Left out:

- The job runs with `--error`, so any hit blocks a merge. The rule is
  `confidence: MEDIUM` and needed two false-positive fixes upstream
  (maruda#27 `crypto.createHmac(...).update(req.body)`, #36 object-literal
  clones) in its first two weeks.
- It targets Express-style `req.body`. sunaba's web stack is Next.js,
  whose route handlers read `await request.json()`; the rule would
  rarely fire there.
- Shipping it makes sunaba responsible for tracking upstream fixes.

The docs explain how to write such a rule; #31 covers the same risk as
guidance. Revisit if sunaba gains an Express stack.

## Not taken now

| Item | Upstream | Reason |
|---|---|---|
| PreToolUse bash guard rewritten to parse `rm` / `git push` arguments, with the old regexes as a floor and a deny/allow test matrix | maruda#15 | Belongs to Phase 4. sunaba's `harness` stack uses prefix-matched permission denies (`Bash(rm -rf:*)`, `Bash(git push --force:*)`), which likely miss `rm -fr /` or `git push origin main --force`. maruda's design is the reference when Phase 4 starts |
| `vulnerability-scan` rework: evidence principle ("a check that exists is not a check that enforces"), *Requires Runtime Verification*, CSRF / upload / auth flow / anti-automation / race checks; dependency audit split into `dependency-audit` (lockfile ownership per workspace, "not run" never counted as 0, opt-in SBOM) | maruda#30, #40–#58 | Phase 3 (skills) has not started. Start it from `5f9b323`, not `99dd798` |
| `rule-proposer` (finding → Semgrep rule + fixture, measured for false positives) | maruda#28 | Phase 3. This PR's `.semgrep/` convention is what it would write to |
| `sakuda-triage`, a `--stack dast` wiring sakuda's MCP | maruda#29, sakuda#18/#46 | sakuda's `/mcp` answers loopback only. From inside a devcontainer, `127.0.0.1` is the container, and `SAKUDA_ALLOWED_HOSTS` does not apply to `/mcp`. Not usable from a sandbox until sakuda allows it |
| Issue-cycle rules (check-before-building ladder, batch/stacked flows), progress dashboard tabs | maruda#3, #17, #19, #41, #44 | Tied to maruda's GitHub Issue workflow; outside sunaba's scope |
| Stop hook `systemMessage` placement, formatter hook skipping `.claude/skills/` | maruda (hooks) | sunaba ships neither hook |

## Found along the way

The baseline `.gitignore` ignores `.codex/`, but `--stack autopilot`
generates `.codex/config.toml`, `.codex/agents/*.toml` and
`.codex/hooks/verify.sh`. They are never committed, so teammates and CI
do not get them. Noted in #30.

Fixed separately (`fix/commit-codex-project-config`): the baseline now
ignores `.codex/*` and re-includes `config.toml`, `agents/` and `hooks/`.
An allowlist, not a list of Codex's state files, so anything else Codex
writes there stays out of git without sunaba tracking its file names.
`sync-gitignore` replaces an old `.codex/` line instead of preserving it
as a user line: git does not look inside an ignored directory, so the
re-includes would never apply while it remains.

## Sources

- maruda `99dd798..5f9b323`:
  <https://github.com/northraystudio/maruda/compare/99dd7981e7947e4ae500225f811f5db0a03c3c7e...5f9b323ccb69d325677006c00643b4dc08699a00>
- sakuda history to `38bbd28`: <https://github.com/northraystudio/sakuda/commits/main>
