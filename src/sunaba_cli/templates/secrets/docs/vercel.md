# Vercel

## Where secrets live

Vercel **Project Settings → Environment Variables**. Three scopes:
*Development*, *Preview*, *Production*. Secrets default to *sensitive*
in `vercel env add` for prod / preview — values cannot be read back
from the dashboard or `vercel env ls` once stored.

## Local dev

`vercel env pull .env.local` writes a local mirror. **`.env.local` is
in `.gitignore`** (and `sunaba`'s expanded baseline already covers it).

## Rules

- Anything prefixed `NEXT_PUBLIC_*` ships to the browser. **Never put
  a real secret behind that prefix.**
- Edit Vercel env vars in the dashboard or via `vercel env add`. Do
  not paste them into source files.
- Re-deploy after changing env vars; otherwise the build container
  still has the old values.

## One-line agent rule

> "Never write secrets to `.env.local` manually. Always run
> `vercel env add` and `vercel env pull`."
