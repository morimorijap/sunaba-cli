# Next.js stack

This sandbox uses Node.js 22 (in the base image) and the Vercel CLI.

## Day-to-day

```sh
npm ci --ignore-scripts   # install (sunaba bootstrap also runs this on container start)
npm run dev               # local dev server
npm test                  # tests
npm run build             # production build
```

## Conventions

- Server-only env vars (database URLs, API keys) stay server-only.
  Only variables prefixed `NEXT_PUBLIC_` are exposed to the browser.
  **Never** put a secret behind `NEXT_PUBLIC_*`.
- API routes and Server Actions take `role`, `userId`, `ownerId`,
  prices and similar fields from the session on the server, never from
  the request. Write only explicitly picked fields to the database
  (no `data: body`).
- Use `vercel env pull .env.local` to sync env vars from Vercel for
  local dev. The resulting `.env.local` stays untracked.
- Re-deploy after changing Vercel env vars; otherwise the build
  container still has stale values.

## What not to do

- Don't commit `.env.local` or any `.env.*` file (sunaba's `.gitignore`
  already covers these).
- Don't paste secrets into source files. Run `vercel env add` and
  `vercel env pull` instead.
