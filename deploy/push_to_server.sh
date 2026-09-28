#!/bin/bash
# From the Mac: copy the code and the LIVE state (not the 2 GB of study history) to the server.
# Usage: deploy/push_to_server.sh user@host      (.env is NOT copied — see deploy/README.md)
set -euo pipefail
H="$1"; cd "$(dirname "$0")/.."
ssh "$H" "mkdir -p ~/saavi/institutional-trader"
if ssh "$H" "systemctl is-active --quiet saavi-engine"; then
  echo "server engine is LIVE — refusing to overwrite its state with the Mac's copy (use cutover/rollback, or copy single files)"; exit 1
fi
rsync -az --delete --exclude .venv --exclude .git --exclude research --exclude .env \
  --exclude 'data/market_history.db' --exclude 'data/bhavcopy' --exclude 'data/studies.db' \
  --exclude 'logs/*' --exclude '__pycache__' ./ "$H:~/saavi/institutional-trader/"
echo "pushed code + live state to $H"
