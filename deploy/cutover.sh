#!/bin/bash
# Move the engine to the server WITHOUT two engines ever running together. After 15:45 or weekends.
# Usage: deploy/cutover.sh saavi
set -euo pipefail
H="${1:-saavi}"; cd "$(dirname "$0")/.."; PL=~/Library/LaunchAgents; U=$(id -u)
ssh "$H" "test -f ~/saavi/institutional-trader/.env" || { echo "copy .env to the server first"; exit 1; }
launchctl bootout "gui/$U/com.sayali.institutionaltrader.engine" 2>/dev/null || true
sleep 3; if pgrep -f engine.engine_runner >/dev/null; then echo "Mac engine still running — stop it first"; exit 1; fi
mkdir -p "$PL/disabled"; [ -f "$PL/com.sayali.institutionaltrader.engine.plist" ] && mv "$PL/com.sayali.institutionaltrader.engine.plist" "$PL/disabled/"
deploy/push_to_server.sh "$H"
ssh "$H" "sudo systemctl enable saavi-engine >/dev/null 2>&1; sudo systemctl start saavi-engine && sleep 20 && systemctl is-active saavi-engine && tail -4 ~/saavi/institutional-trader/logs/app.log | cut -c1-140"
sed "s/__HOST__/$H/" deploy/com.sayali.saavi-viewer-sync.plist > "$PL/com.sayali.saavi-viewer-sync.plist"
launchctl bootstrap "gui/$U" "$PL/com.sayali.saavi-viewer-sync.plist" 2>/dev/null || true
echo "CUTOVER DONE — engine on $H; Mac engine disabled; viewer sync on. Fallback: deploy/rollback.sh $H"
