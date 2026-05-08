# Secrets and API key management for sunaba-cli

> Status: **draft / in review**. Started 2026-05-09.

API keys for AI providers (OpenAI, Anthropic, Google) are increasingly
finding their way into public repositories. The exposure window is short
— scrapers find them within minutes — and the financial damage is
real. Coding agents make this worse: an agent that writes `.env` files
or reads from one location and copies to another can silently widen the
surface.

This folder works through what `sunaba-cli` should ship to make the
"keys leaked from a generated project" failure mode hard to hit.

## Threat model in one paragraph

We are **not** trying to defend against a malicious agent inside the
container, or against a compromised host. We are trying to defend against
the everyday case: an agent (or a tired developer) writes a real API key
into a file, that file ends up in a git commit, and the commit ends up on
GitHub. Adjacent: the developer pastes a key into a `.env.local` to
"just get it working," then forgets the file exists when they merge.

The fix is **not** to make agents perfect. The fix is to make the leak
path mechanically harder:

1. Keep the secret in **one** place.
2. Make every other place a **reference** to that one place.
3. Make `git` refuse to commit anything that even looks like a secret.
4. Push every secret out of the repo entirely once the project leaves
   `localhost`.

## Files in this folder

1. [`01-current-state.md`](01-current-state.md) — what `sunaba` does today
   for secrets, and where the gaps are.
2. [`02-research-notes.md`](02-research-notes.md) — per-cloud notes
   (Vercel · Firebase · Azure · AWS · GCP) and the
   "Foundry → APIM → Gemini → Cosmos" pattern the user asked us to work
   through.
3. [`03-llm-consultation-brief.md`](03-llm-consultation-brief.md) — brief
   sent to Codex / Gemini Pro Preview for independent critique.
4. [`04a-gemini-review.md`](04a-gemini-review.md) — `gemini-3.1-pro-preview`.
5. [`04b-codex-review.md`](04b-codex-review.md) — Codex CLI (`gpt-5.5`,
   high reasoning effort). Codex used its workspace-write sandbox to
   author this file directly; no edits beyond a rename to match the
   `04a` / `04b` convention.
6. [`05-proposal.md`](05-proposal.md) — synthesized proposal: what to add
   to `sunaba-cli` templates, what to add to `SECURITY.md`, and what to
   leave to the user.

## Constraints

Same as the harness PR:

- **Templates only.** `sunaba-cli` is a generator. Anything we ship is a
  file the user owns and can edit. No runtime, no fetched secrets, no
  background agent.
- **Honest about the limits.** Cloud-managed secrets do not protect
  against an agent inside the container reading runtime env vars. The
  README's "what sunaba does NOT protect you from" section already says
  this; the new docs must echo it.
- **Opt-in over default.** A new `--stack` or set of files is fine; a
  silent change to existing project generation is not.
