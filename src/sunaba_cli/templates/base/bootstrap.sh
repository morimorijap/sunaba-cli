#!/usr/bin/env bash
set -euo pipefail

echo "=== Sunaba Bootstrap ==="

# Fix ownership of named-volume cache dirs (root-owned by default on first mount)
for d in "$HOME/.npm" "$HOME/.cache/uv" "$HOME/.cache"; do
  if [ -d "$d" ] && [ "$(stat -c '%u' "$d")" != "$(id -u)" ]; then
    echo "Fixing ownership of $d"
    sudo chown -R "$(id -u):$(id -g)" "$d"
  fi
done

# Ensure ~/.local/bin is on PATH
grep -q 'HOME/.local/bin' ~/.profile 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile
export PATH="$HOME/.local/bin:$PATH"

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
