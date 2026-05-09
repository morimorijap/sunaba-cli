# docs/secrets/

How and where to keep secrets out of this repository, by cloud.

> **Read first:** the AGENTS.md "Secrets" section. Tools and
> documentation help, but they do not protect a real, billing-enabled
> API key from an autonomous agent that decides to exfiltrate it.
> The only architectural mitigation against that failure mode is the
> [Azure Foundry → APIM → Gemini → Cosmos](azure-foundry-apim-gemini-cosmos.md)
> pattern (or a non-Azure equivalent gateway).

## Pages

- [Vercel](vercel.md)
- [Firebase / Google Cloud](firebase.md)
- [AWS](aws.md)
- [GCP](gcp.md)
- [Azure: Foundry → APIM → Gemini → Cosmos (the "key behind a proxy" pattern)](azure-foundry-apim-gemini-cosmos.md)

## Defense-in-depth, in order

1. **`.gitignore`** — file never enters the index.
2. **Pre-commit hook (gitleaks)** — file blocked at `git commit`.
3. **GitHub secret scanning + push protection** — push blocked
   server-side. Enable in repo settings.
4. **Provider rotation hooks** — major providers participate in
   GitHub's partner program and auto-rotate found keys.
5. **`git filter-repo` / GitHub support** — last-resort cleanup.

`sunaba`'s `--stack secrets` ships layers 1 and 2. Layer 3 you enable.
Layers 4 and 5 are out of scope.
