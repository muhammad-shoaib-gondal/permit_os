#!/usr/bin/env bash
# Run all four Band specialist agents in one container (Render Background Worker / VPS).
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/ensure_agent_config.sh

if [[ ! -f agent_config.yaml && -z "${AGENT_CONFIG_YAML:-}" && -z "${AGENTS_CONFIG_YAML:-}" && -z "${CONDUCTOR_AGENT_ID:-}" ]]; then
  echo "ERROR: No Band credentials. Add a Render Secret File (agent_config.yaml or config.yml),"
  echo "       set AGENT_CONFIG_PATH, AGENT_CONFIG_YAML, or per-agent env vars."
  exit 1
fi

echo "Starting PermitOS Band agents (jurisdiction, building, site, packager)..."

bash scripts/agent_supervisor.sh agents.jurisdiction.agent &
bash scripts/agent_supervisor.sh agents.building.agent &
bash scripts/agent_supervisor.sh agents.site_environmental.agent &
bash scripts/agent_supervisor.sh agents.packager.agent &

wait
