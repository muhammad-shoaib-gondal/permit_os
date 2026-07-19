#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python scripts/print_deploy_config.py
exec python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
