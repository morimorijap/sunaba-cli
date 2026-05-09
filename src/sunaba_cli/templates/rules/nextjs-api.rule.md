---
name: nextjs-api
description: Validate request payloads in Next.js API routes; never expose server-only env to the browser.
globs:
  - "app/api/**/*.ts"
  - "app/api/**/*.tsx"
  - "pages/api/**/*.ts"
alwaysApply: false
targets:
  - claude
  - cursor
  - codex
  - gemini
---

# Next.js API route rules

- Validate every request body / query / params with a schema library
  (Zod / Valibot). Reject unknown shapes early with `400`.
- Server-only env vars stay server-only. Anything prefixed
  `NEXT_PUBLIC_*` ships to the browser; never put a secret behind
  that prefix.
- Return typed responses (`Response` or `NextResponse<T>`); don't
  emit ad-hoc objects from handlers.
- Errors: log on the server with a request id, return only the safe
  user-facing message in the response.
