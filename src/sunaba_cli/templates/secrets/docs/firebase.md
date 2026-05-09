# Firebase / Google Cloud

## Where secrets live

For **Cloud Functions v2**, use **Cloud Secret Manager** via
`defineSecret(...)`. The legacy `firebase functions:config:set` is
deprecated for new projects.

For **Hosting / SSR** that runs on Cloud Run, use the same Secret
Manager via the Cloud Run integration.

## Local dev

Use **Application Default Credentials**: `gcloud auth
application-default login`. Avoid downloading service-account JSON
keys.

## Rules

- **Never commit `*-firebase-adminsdk-*.json`** or any
  `serviceAccount*.json`. (sunaba's `.gitignore` covers these.)
- The Firebase emulator's `.runtimeconfig.json` belongs in the
  emulator dir only, not at repo root, never committed.

## One-line agent rule

> "Never download or create service-account JSON files. Authenticate
> exclusively via `gcloud auth application-default login`."
