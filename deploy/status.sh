#!/bin/bash
# Where is the engine running, and is it alive?   deploy/status.sh saavi
H="${1:-saavi}"; cd "$(dirname "$0")/.."
echo "Mac engine processes: $(pgrep -f engine.engine_runner | wc -l | tr -d " ")"
[ -f ~/Library/LaunchAgents/com.sayali.institutionaltrader.engine.plist ] && echo "Mac engine auto-start: ENABLED" || echo "Mac engine auto-start: disabled"
ssh -o ConnectTimeout=8 -o BatchMode=yes "$H" 'echo "server engine: $(systemctl is-active saavi-engine) / boot: $(systemctl is-enabled saavi-engine)"; python3 -c "import json;print(\"server heartbeat:\", json.load(open(\"$HOME/saavi/institutional-trader/data/market_snapshot.json\"))[\"ts\"][:19])"' 2>/dev/null || echo "server: NOT reachable"
python3 -c "import json;print('Mac copy heartbeat:', json.load(open('data/market_snapshot.json'))['ts'][:19])" 2>/dev/null
