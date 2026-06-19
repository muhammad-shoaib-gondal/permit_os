#!/usr/bin/env bash
# Run all four Band specialist agents in one container (Render Background Worker / VPS).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f agent_config.yaml ]]; then
  echo "ERROR: agent_config.yaml missing. Add it as a Render Secret File at /app/agent_config.yaml"
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
