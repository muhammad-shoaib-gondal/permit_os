#!/usr/bin/env bash
# One Render Web Service: API + UI + all Band agents (no second paid service).
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/ensure_agent_config.sh

echo "Starting PermitOS (API + 4 Band agents)..."

python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 4

python -m agents.jurisdiction.agent &
python -m agents.building.agent &
python -m agents.site_environmental.agent &
python -m agents.packager.agent &

wait -n
exit $?
