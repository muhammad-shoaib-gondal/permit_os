#!/usr/bin/env bash
# Symlink Render secret files (or AGENT_CONFIG_PATH) to /app/agent_config.yaml for Band SDK.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/agent_config.yaml"

if [[ -f "$TARGET" ]]; then
  exit 0
fi

if [[ -n "${AGENT_CONFIG_PATH:-}" && -f "${AGENT_CONFIG_PATH}" ]]; then
  ln -sf "${AGENT_CONFIG_PATH}" "$TARGET"
  echo "Linked ${AGENT_CONFIG_PATH} -> agent_config.yaml"
  exit 0
fi

for candidate in \
  /etc/secrets/agent_config.yaml \
  /etc/secrets/agent_config.yml \
  /etc/secrets/agents_config.yaml \
  /etc/secrets/agents_config.yml \
  /etc/secrets/config.yaml \
  /etc/secrets/config.yml; do
  if [[ -f "$candidate" ]]; then
    ln -sf "$candidate" "$TARGET"
    echo "Linked ${candidate} -> agent_config.yaml"
    exit 0
  fi
done

if [[ -n "${AGENT_CONFIG_YAML:-}" || -n "${AGENTS_CONFIG_YAML:-}" ]]; then
  echo "Using AGENT_CONFIG_YAML from environment (no file link needed)."
  exit 0
fi

if [[ -n "${CONDUCTOR_AGENT_ID:-}" && -n "${CONDUCTOR_API_KEY:-}" ]]; then
  echo "Using per-agent env vars for Band credentials (no file link needed)."
  exit 0
fi

echo "WARNING: No agent_config.yaml found. Set a Render Secret File (agent_config.yaml or config.yml),"
echo "         AGENT_CONFIG_PATH, AGENT_CONFIG_YAML, or CONDUCTOR_AGENT_ID + CONDUCTOR_API_KEY."
