# GCP

## Where secrets live

- **Google Secret Manager** — primary, versioned, IAM-gated.
- **Workload Identity Federation** — preferred for non-GCP compute
  (GitHub Actions, etc.) so no JSON keys exist at all.

## Local dev

**Application Default Credentials**:
`gcloud auth application-default login`.

## Rules

- **Never** drop `serviceAccount*.json` into the repo. If a
  service-account JSON is genuinely required, store it outside the
  repo and reference it by env var path.
- Workload Identity Federation eliminates JSON keys for CI; use it
  unless you have a specific reason not to.

## One-line agent rule

> "Never create or commit service-account JSON. Use ADC or Workload
> Identity Federation."
