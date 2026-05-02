#!/usr/bin/env bash
set -euo pipefail

echo "=== Sunaba Bootstrap ==="

uid="$(id -u)"
gid="$(id -g)"

# Docker named volumes are root-owned on first mount. When a child volume
# (e.g. ~/.config/gh, ~/.local/share/com.vercel.cli) is mounted, Docker
# auto-creates the parent directories as root, which breaks `mkdir`/`pip
# install --user` later. Ensure each parent exists and is owned by the
# runtime user. mkdir+chown (rather than `install -d -o`) is intentional:
# `install -d` does not change ownership of an already-existing directory,
# so it would silently leave a root-created parent root-owned.
for d in "$HOME/.config" "$HOME/.local" "$HOME/.local/share" \
         "$HOME/.local/bin" "$HOME/.cache"; do
  sudo mkdir -p "$d"
  sudo chown "$uid:$gid" "$d"
done

# Cache volumes are large; only chown if the top dir is wrong-owned (cheap
# heuristic — full -R would be slow on warm caches).
for d in "$HOME/.npm" "$HOME/.cache/uv" "$HOME/.cache/ms-playwright"; do
  if [ -d "$d" ] && [ "$(stat -c '%u' "$d")" != "$uid" ]; then
    echo "Fixing ownership of $d"
    sudo chown -R "$uid:$gid" "$d"
  fi
done

# Helper for config volumes (auth tokens, session state). These are tiny and
# historically suffer from "directory user-owned but a child file is
# root-owned" drift after a `sudo` invocation, which the shallow stat check
# above would silently skip. Always chown -R; cost is < 10ms. Stacks call
# this from their own _bootstrap snippets for stack-specific volumes.
sunaba_fix_config_dir() {
  if [ -e "$1" ]; then
    sudo chown -R "$uid:$gid" "$1"
  fi
}

# gh-config is mounted in base/devcontainer.json (github-cli is in base
# features), so chown it here. Other auth volumes are owned by stacks.
sunaba_fix_config_dir "$HOME/.config/gh"

# Ensure ~/.local/bin is on PATH
grep -q 'HOME/.local/bin' ~/.profile 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile
export PATH="$HOME/.local/bin:$PATH"

# --- Git / SSH ---
# VS Code Dev Containers forwards the host ssh-agent socket into the container
# via SSH_AUTH_SOCK, so `git push` over SSH works as long as the host has run
# `ssh-add`. We just need the ssh client binary and a safe-directory marker.
if ! command -v ssh >/dev/null 2>&1; then
  echo "Installing openssh-client..."
  sudo apt-get update -qq && sudo apt-get install -y -qq openssh-client
fi
git config --global --add safe.directory "$PWD" 2>/dev/null || true

# --- AI Agents (common) ---
# NOTE: Intentionally using @latest for agent CLIs. This is a deliberate
# supply-chain tradeoff: we want users to always get the newest agent
# capabilities. If you need reproducibility, fork and pin these versions.
if ! command -v claude >/dev/null 2>&1; then
  echo "Installing Claude Code (latest)..."
  npm install -g "@anthropic-ai/claude-code@latest"
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "Installing Codex (latest)..."
  npm install -g "@openai/codex@latest"
fi

if ! command -v gemini >/dev/null 2>&1; then
  echo "Installing Gemini CLI (latest)..."
  npm install -g "@google/gemini-cli@latest"
fi

# --- Stack-specific (appended by sunaba-cli) ---
