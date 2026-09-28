#!/bin/bash
# Mac-side watchdog (launchd, every 5 min). Weekdays 09:10-15:50: if the server's heartbeat (copied by
# the viewer sync) is older than 12 minutes, show a Mac notification with the one fallback command.
# It never starts the Mac engine by itself — two engines would double every Telegram signal.
cd "$(dirname "$0")/.."
d=$(date +%u); t=$(date +%H%M); [ "$d" -le 5 ] && [ "$t" -ge 0910 ] && [ "$t" -le 1550 ] || exit 0
[ -f ~/Library/LaunchAgents/com.sayali.institutionaltrader.engine.plist ] && exit 0   # engine is on the Mac
age=$(python3 -c "import json,datetime as D;ts=json.load(open('data/market_snapshot.json'))['ts'];print(int((D.datetime.now(D.timezone(D.timedelta(hours=5,minutes=30)))-D.datetime.fromisoformat(ts)).total_seconds()//60))" 2>/dev/null || echo 999)
if [ "$age" -gt 12 ]; then
  osascript -e "display notification \"Server engine silent for ${age} min. If it stays silent run: deploy/rollback.sh saavi\" with title \"Saavi engine\" sound name \"Basso\""
  echo "$(date) server heartbeat ${age} min old — notified" >> logs/watchdog.log
fi
