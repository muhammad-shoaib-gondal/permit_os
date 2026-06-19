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

python -m agents.jurisdiction.agent &
python -m agents.building.agent &
python -m agents.site_environmental.agent &
python -m agents.packager.agent &

# If any agent exits, bring down the container so Render restarts it.
wait -n
exit $?
