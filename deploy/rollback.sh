#!/bin/bash
# Bring the engine back to the Mac: stop the server engine, pull its state, re-enable the Mac engine.
# Usage: deploy/rollback.sh user@host
set -euo pipefail
H="$1"; cd "$(dirname "$0")/.."
ssh "$H" "sudo systemctl stop saavi-engine; sudo systemctl disable saavi-engine"
rsync -az --exclude 'market_history.db' --exclude 'bhavcopy' --exclude 'studies.db' "$H:~/saavi/institutional-trader/data/" data/
mv ~/Library/LaunchAgents/disabled/com.sayali.institutionaltrader.engine.plist ~/Library/LaunchAgents/ 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.sayali.institutionaltrader.engine.plist
echo "rolled back: engine runs on the Mac again"
