# AWS

## Where secrets live

- **AWS Secrets Manager** — primary, with rotation, KMS encryption,
  and fine-grained IAM.
- **Systems Manager Parameter Store** with `SecureString` — cheaper
  alternative for static-ish secrets.
- **IAM roles + STS** — for compute (EC2 / ECS / Lambda / EKS).
  Prefer role assumption over static `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY`.

## Local dev

**IAM Identity Center / SSO** for short-lived tokens
(`aws sso login`). Avoid long-lived `AKIA...` access keys.

## Rules

- **Never commit `aws_access_key_id` / `aws_secret_access_key`** to
  any file in the repo tree.
- The host's `~/.aws/` is mounted into the devcontainer if you have
  it; the *project tree's* `.aws/` is in `.gitignore`. Don't conflate
  them.

## One-line agent rule

> "Never request or create long-lived IAM access keys (`AKIA...`).
> Authenticate exclusively using `aws sso login`."
