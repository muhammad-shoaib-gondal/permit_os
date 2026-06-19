#!/usr/bin/env bash
# Ensure /app/agent_config.yaml exists for the Band SDK (Render secret files, env YAML, etc.).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/agent_config.yaml" ]]; then
  echo "agent_config.yaml already present."
  exit 0
fi

# Prefer Python (reads /etc/secrets, AGENT_CONFIG_YAML, per-agent env vars).
if python - <<'PY'
from shared.band_client.config import materialize_agent_config_file
path = materialize_agent_config_file()
if not path:
    raise SystemExit(1)
print(f"Band credentials ready at {path}")
PY
then
  exit 0
fi

# Shell fallback: copy known Render secret paths.
for candidate in \
  "${AGENT_CONFIG_PATH:-}" \
  /etc/secrets/agent_config.yaml \
  /etc/secrets/agent_config.yml \
  /etc/secrets/agents_config.yaml \
  /etc/secrets/agents_config.yml \
  /etc/secrets/config.yaml \
  /etc/secrets/config.yml; do
  if [[ -n "$candidate" && -f "$candidate" ]]; then
    cp "$candidate" "${ROOT}/agent_config.yaml"
    echo "Copied ${candidate} -> agent_config.yaml"
    exit 0
  fi
done

if [[ -d /etc/secrets ]]; then
  echo "Contents of /etc/secrets:"
  ls -la /etc/secrets/ || true
fi

echo "ERROR: No Band credentials found."
echo "  Render → Environment → Secret Files → Filename: agent_config.yaml"
echo "  (or agents_config.yaml) — mounted at /etc/secrets/<filename>"
echo "  Or set AGENT_CONFIG_YAML with the full YAML body."
exit 1
