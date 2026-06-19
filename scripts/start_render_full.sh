#!/usr/bin/env bash
# One Render Web Service: API + UI + all Band agents (no second paid service).
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/ensure_agent_config.sh || true

echo "Starting PermitOS (API + 4 Band agents)..."

bash scripts/agent_supervisor.sh agents.jurisdiction.agent &
bash scripts/agent_supervisor.sh agents.building.agent &
bash scripts/agent_supervisor.sh agents.site_environmental.agent &
bash scripts/agent_supervisor.sh agents.packager.agent &

# Keep container alive on API only — agent crashes must not kill the web service.
exec python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
