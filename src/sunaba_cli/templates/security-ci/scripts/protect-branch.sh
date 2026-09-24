#!/usr/bin/env bash
# Make the security checks required before merging, using a GitHub
# repository ruleset named "sunaba security gates".
#
#   scripts/protect-branch.sh [--branch NAME]... [--strict] [--force] [--dry-run]
#
# Targets the default branch plus every --branch (e.g. an integration
# branch such as `staging` that PRs merge into first). Requires the checks
# the repository's workflows define, blocks force pushes and branch
# deletion, and grants no bypass — admins included. Re-running updates the
# same ruleset instead of adding another.
#
# Before activating anything it checks that every required check has
# already passed on the default branch's latest commit and came from
# GitHub Actions, then binds each check to that app so no other app can
# report it. --force skips that preflight (not recommended).
#
# Needs: gh (authenticated, repository admin). Rulesets are available on
# public repositories, and on private repositories with GitHub Pro, Team,
# or Enterprise — not on free private repositories.
#
# Adapted and modified from `setup.sh --protect` in northraystudio/maruda
# (MIT, Copyright (c) 2026 NorthRay Studio株式会社):
#   https://github.com/northraystudio/maruda/blob/99dd7981e7947e4ae500225f811f5db0a03c3c7e/harness/scripts/setup.sh#L881-L918
# sunaba changes: repository rulesets instead of classic branch
# protection, extra branches (maruda protects only the default branch),
# contexts derived from the workflows present, a preflight that refuses to
# require checks that have not passed, app-bound checks, idempotent
# updates, a read-back, and --dry-run. The MIT license notice is in
# docs/security/THIRD_PARTY_NOTICES.md.
set -euo pipefail

RULESET_NAME="sunaba security gates"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

branches=()
strict=false
force=false
dry_run=false
while [ $# -gt 0 ]; do
  case "$1" in
    --branch)
      [ $# -ge 2 ] || { echo "error: --branch needs a name" >&2; exit 2; }
      if ! printf '%s' "$2" | grep -Eq '^[A-Za-z0-9._/-]+$'; then
        echo "error: unsupported branch name: $2" >&2
        exit 2
      fi
      case " ${branches[*]-} " in *" $2 "*) ;; *) branches+=("$2") ;; esac
      shift 2
      ;;
    --strict) strict=true; shift ;;
    --force) force=true; shift ;;
    --dry-run) dry_run=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "error: run this inside the project's git repository" >&2
  exit 2
}

# Require exactly the checks this repository's workflows produce.
contexts=()
if [ -f "$root/.github/workflows/security-scan.yml" ]; then
  contexts+=("SAST (Semgrep)" "Dependency Scan (Trivy)")
fi
if [ -f "$root/.github/workflows/gitleaks.yml" ]; then
  contexts+=("Secret Scan (Gitleaks)")
fi
if [ ${#contexts[@]} -eq 0 ]; then
  echo "error: no sunaba security workflow found under .github/workflows/" >&2
  exit 2
fi

join() {
  local sep="$1"; shift
  local out="" item
  for item in "$@"; do out="${out:+$out$sep}$item"; done
  printf '%s' "$out"
}

# payload <integration_id or empty>
payload() {
  local app_id="$1" refs checks c b
  refs='"~DEFAULT_BRANCH"'
  for b in ${branches[@]+"${branches[@]}"}; do refs="$refs, \"refs/heads/$b\""; done
  checks=""
  for c in "${contexts[@]}"; do
    if [ -n "$app_id" ]; then
      checks="${checks:+$checks, }{\"context\": \"$c\", \"integration_id\": $app_id}"
    else
      checks="${checks:+$checks, }{\"context\": \"$c\"}"
    fi
  done
  cat <<EOF
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": [$refs], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": $strict,
      "do_not_enforce_on_create": true,
      "required_status_checks": [$checks]
    }}
  ]
}
EOF
}

if [ "$dry_run" = true ]; then
  payload ""
  exit 0
fi

hint() {
  cat >&2 <<'EOF'
Check that:
  - `gh auth status` shows an account that is an admin of this repository
    (401: not logged in; 403: not an admin, or the plan lacks rulesets;
    404: wrong repository, or no access);
  - the repository is public, or on GitHub Pro / Team / Enterprise — rulesets
    are not available on free private repositories. Until then, the checks
    still run and report; they just cannot block the merge button.
EOF
}

command -v gh >/dev/null 2>&1 || {
  echo "error: GitHub CLI (gh) not found — https://cli.github.com" >&2
  exit 2
}
repo="$(cd "$root" && gh repo view --json nameWithOwner --jq .nameWithOwner)" || {
  echo "error: gh cannot resolve this repository (is 'origin' on GitHub? run 'gh auth status')" >&2
  exit 2
}
default_branch="$(gh api "repos/$repo" --jq .default_branch)" || { echo "error: cannot read $repo" >&2; hint; exit 1; }

# --- Preflight: every required check must already have passed, from GitHub
# Actions, on the default branch's latest commit. Requiring a check GitHub
# has never seen, or one that is red, blocks every PR.
app_id=""
if [ "$force" = false ]; then
  runs="$(gh api "repos/$repo/commits/$default_branch/check-runs?per_page=100" --paginate \
    --jq '.check_runs[] | [.name, .status, (.conclusion // ""), (.app.slug // ""), (.app.id | tostring)] | @tsv')" || {
    echo "error: cannot read check runs on $default_branch" >&2; hint; exit 1; }
  problems=""
  for c in "${contexts[@]}"; do
    line="$(printf '%s\n' "$runs" | awk -F '\t' -v n="$c" '$1 == n' | head -n 1)"
    if [ -z "$line" ]; then
      problems="$problems\n  - $c: has never run on $default_branch"
      continue
    fi
    status="$(printf '%s' "$line" | cut -f2)"
    conclusion="$(printf '%s' "$line" | cut -f3)"
    slug="$(printf '%s' "$line" | cut -f4)"
    id="$(printf '%s' "$line" | cut -f5)"
    if [ "$slug" != "github-actions" ]; then
      problems="$problems\n  - $c: reported by '$slug', not GitHub Actions"
    elif [ "$status" != "completed" ] || [ "$conclusion" != "success" ]; then
      problems="$problems\n  - $c: latest run is ${conclusion:-$status}, not success"
    else
      app_id="$id"
    fi
  done
  if [ -n "$problems" ]; then
    printf 'error: not activating — these checks have not passed on %s:%b\n' "$default_branch" "$problems" >&2
    echo "Push the workflows to $default_branch, fix any failures, then re-run." >&2
    echo "(--force requires them anyway; PRs will wait until they report.)" >&2
    exit 1
  fi
fi

ids="$(gh api "repos/$repo/rulesets?includes_parents=false" --paginate \
  --jq '.[] | [.id, .name, .source_type] | @tsv')" || { echo "error: cannot list rulesets for $repo" >&2; hint; exit 1; }
ids="$(printf '%s\n' "$ids" | awk -F '\t' -v n="$RULESET_NAME" '$2 == n && $3 == "Repository" { print $1 }')"
if [ "$(printf '%s\n' "$ids" | grep -c .)" -gt 1 ]; then
  echo "error: several rulesets are named \"$RULESET_NAME\" on $repo; delete all but one" >&2
  echo "  (Settings → Rules → Rulesets), then re-run." >&2
  exit 1
fi

if [ -n "$ids" ]; then
  method=PUT; endpoint="repos/$repo/rulesets/$ids"; action=updated
else
  method=POST; endpoint="repos/$repo/rulesets"; action=created
fi

errfile="$(mktemp)"
trap 'rm -f "$errfile"' EXIT
if ! id="$(payload "$app_id" | gh api -X "$method" "$endpoint" --input - --jq .id 2>"$errfile")"; then
  echo "error: GitHub rejected the ruleset for $repo:" >&2
  sed 's/^/  /' "$errfile" >&2
  hint
  exit 1
fi

# Read back what GitHub stored.
stored="$(gh api "repos/$repo/rulesets/$id" \
  --jq '[.enforcement, ([.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context] | join(","))] | @tsv')"
if [ "$stored" != "$(printf 'active\t%s' "$(join ',' "${contexts[@]}")")" ]; then
  echo "error: the stored ruleset does not match what was sent:" >&2
  printf '  %s\n' "$stored" >&2
  exit 1
fi

echo "Ruleset \"$RULESET_NAME\" $action on $repo (id $id)"
echo "  branches: $(join ', ' "$default_branch (default)" ${branches[@]+"${branches[@]}"})"
echo "  required checks: $(join ', ' "${contexts[@]}")${app_id:+ (GitHub Actions only)}"
echo "  strict (branch must be up to date): $strict"
echo "To undo: Settings → Rules → Rulesets → \"$RULESET_NAME\"."
