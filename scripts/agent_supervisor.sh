#!/usr/bin/env bash
# Restart a Band agent module if it exits (429 / transient errors).
set -uo pipefail
mod=$1
delay="${BAND_AGENT_RESTART_SEC:-30}"
while true; do
  if python -m "$mod"; then
    echo "Agent $mod exited cleanly"
    break
  fi
  echo "Agent $mod exited — restart in ${delay}s"
  sleep "$delay"
done
