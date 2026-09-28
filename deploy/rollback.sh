#!/bin/bash
# FALLBACK: run the engine on the Mac again (28-Sep-2026). One command:  deploy/rollback.sh saavi
#  1. stops the server engine (if the server answers)   2. stops the viewer sync, so it can never
#  overwrite the Mac engine's live files   3. pulls the server's latest state (if reachable)
#  4. re-enables and starts the Mac engine   5. verifies exactly one engine is running.
# If the server does NOT answer, it refuses unless you add --force: a server that is alive but
# unreachable would keep sending Telegram messages, and two engines double every signal.
set -u
H="${1:-saavi}"; FORCE="${2:-}"; cd "$(dirname "$0")/.."
PL=~/Library/LaunchAgents; U=$(id -u)
if ssh -o ConnectTimeout=10 -o BatchMode=yes "$H" true 2>/dev/null; then
  ssh "$H" "sudo systemctl stop saavi-engine; sudo systemctl disable saavi-engine" && echo "server engine stopped + disabled"
  REACH=1
else
  echo "!! server $H not reachable"; REACH=0
  [ "$FORCE" = "--force" ] || { echo "   refusing: re-run with --force ONLY if the server is truly down (AWS console shows Stopped)"; exit 1; }
fi
launchctl bootout "gui/$U/com.sayali.saavi-viewer-sync" 2>/dev/null; mkdir -p "$PL/disabled"
[ -f "$PL/com.sayali.saavi-viewer-sync.plist" ] && mv "$PL/com.sayali.saavi-viewer-sync.plist" "$PL/disabled/"
pkill -f "deploy/viewer_sync.sh" 2>/dev/null; echo "viewer sync stopped"
if [ "$REACH" = 1 ]; then
  rsync -az --exclude 'market_history.db' --exclude 'bhavcopy' --exclude 'studies.db' "$H:~/saavi/institutional-trader/data/" data/ && echo "latest state pulled from server"
else
  echo "using the Mac's last synced copy of the state (viewer sync keeps it within ~1 minute)"
fi
[ -f "$PL/disabled/com.sayali.institutionaltrader.engine.plist" ] && mv "$PL/disabled/com.sayali.institutionaltrader.engine.plist" "$PL/"
launchctl bootstrap "gui/$U" "$PL/com.sayali.institutionaltrader.engine.plist" 2>/dev/null || launchctl kickstart -k "gui/$U/com.sayali.institutionaltrader.engine"
sleep 12
N=$(pgrep -f engine.engine_runner | wc -l | tr -d " "); echo "Mac engines running: $N"
[ "$N" = 1 ] && echo "ROLLBACK DONE — the engine runs on the Mac again." || echo "!! check: expected exactly 1 Mac engine"
