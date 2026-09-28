#!/bin/bash
# Move the engine from the Mac to the server WITHOUT two engines ever running together (two would
# send every Telegram message twice and double-book every position). Run after 15:45 or on a weekend.
# Usage: deploy/cutover.sh user@host
set -euo pipefail
H="$1"; cd "$(dirname "$0")/.."
ssh "$H" "test -f ~/saavi/institutional-trader/.env" || { echo "copy .env to the server first (README step 3)"; exit 1; }
launchctl bootout "gui/$(id -u)/com.sayali.institutionaltrader.engine" 2>/dev/null || true
sleep 3; pgrep -f engine.engine_runner && { echo "Mac engine still running — stop it first"; exit 1; }
deploy/push_to_server.sh "$H"                     # final copy of books, markers and DBs
ssh "$H" "sudo systemctl start saavi-engine && sleep 15 && systemctl is-active saavi-engine && tail -5 ~/saavi/institutional-trader/logs/app.log"
mkdir -p ~/Library/LaunchAgents/disabled && mv ~/Library/LaunchAgents/com.sayali.institutionaltrader.engine.plist ~/Library/LaunchAgents/disabled/ 2>/dev/null || true
echo "cutover done: the engine runs on $H. Mac engine disabled (plist in LaunchAgents/disabled)."
echo "Start the Mac viewer sync: deploy/viewer_sync.sh $H   (or install deploy/com.sayali.saavi-viewer-sync.plist)"
