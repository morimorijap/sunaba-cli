# Subagent dispatch protocol

The orchestrator (the agent driving the session) decides when to dispatch
subagents based on this flowchart.

## Planner

Dispatch IF any of:

- Task touches >= 3 files.
- Task involves unknown code (the orchestrator hasn't read it yet).
- Task changes a schema / API surface / auth / secrets / infra.
- The user asks for a plan explicitly.

Skip the planner for:

- Single-file bug fixes where the failing test already names the fix.
- Documentation-only edits.

The planner writes its output to
`claudedocs/plans/<YYYY-MM-DD>-<slug>.md`.

## Implementer

The orchestrator (or a dedicated subagent) does the edits. Updates a
checkpoint after every coherent slice (see "Checkpoints" below).

## Reviewer → Verifier

After the implementer completes a slice:

1. **Reviewer** reads the diff. If it returns a 🛑 Blocker, hand back
   to the implementer.
2. **Verifier** runs `.claude/hooks/verify.sh` (or
   `.codex/hooks/verify.sh` from Codex CLI). Acts on the structured
   exit code:
   - Exit 0 — all checks passed; compare against plan's acceptance
     criteria.
   - Exit 2 — `SUNABA_VERIFY_FAILED`; orchestrator dispatches the
     implementer to fix.
   - Exit 1 — `SUNABA_BUDGET_EXCEEDED`; stop, hand off to human.

The verifier is **deterministic** (a bash script). The verifier *role
file* describes how to interpret the bash output and compare against
the plan; the role file does not decide whether code is correct.

## Checkpoints

Write to `claudedocs/checkpoints/<slug>.md`:

- after a plan is accepted,
- before a broad edit,
- after each failed verification pass,
- before the final response.

A checkpoint should be short — what's done, what's pending, the most
recent verifier output. The point is resumability when an autopilot run
hits its budget cap or a human interrupts mid-task.

## Budget defaults

The verify hook caps autonomy via three env vars:

- `SUNABA_AUTOPILOT_MAX_ITERS` (default 5)
- `SUNABA_AUTOPILOT_MAX_MINUTES` (default 30)
- `SUNABA_AUTOPILOT_MAX_CHANGED_FILES` (default 25)

When any cap is hit, the hook exits 1 with `SUNABA_BUDGET_EXCEEDED`.
The orchestrator must stop and surface the situation to the human, not
continue retrying.
