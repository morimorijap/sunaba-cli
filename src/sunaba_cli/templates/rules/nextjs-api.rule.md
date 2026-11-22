---
name: nextjs-api
description: Validate request payloads in Next.js API routes; take privilege and ownership fields from the session, never the request; never expose server-only env to the browser.
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
- Privilege and ownership fields (`role`, `isAdmin`, `userId`,
  `ownerId`, `tenantId`, `price`, `status`, …) never come from the
  request body, query or a client-editable cookie. Derive them on the
  server from the authenticated session, re-read from the database on
  each request.
- Never write the request body to the database as-is
  (`prisma.user.update({ data: body })`, `Object.assign(record, body)`).
  Pick the allowed fields explicitly, or parse with a schema that strips
  unknown keys (Zod's default `.object()` does; `.passthrough()` does
  not). Apply the same schema on create, update and any bulk/import
  route that writes the same model (mass assignment).
- Don't authorize from JWT claims alone. A role in a token is what was
  true when it was issued; check the current role or ownership on the
  server before the write.
- Server-only env vars stay server-only. Anything prefixed
  `NEXT_PUBLIC_*` ships to the browser; never put a secret behind
  that prefix.
- Return typed responses (`Response` or `NextResponse<T>`); don't
  emit ad-hoc objects from handlers.
- Errors: log on the server with a request id, return only the safe
  user-facing message in the response.
