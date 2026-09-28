#!/bin/bash
# Mac UI as a viewer: pull the server's live state every 60 s so the Saavi window stays current.
# Usage: deploy/viewer_sync.sh user@host
H="$1"; cd "$(dirname "$0")/.."
while true; do
  rsync -az -e "ssh -i $HOME/.ssh/saavi_lightsail -o StrictHostKeyChecking=accept-new" --exclude 'market_history.db' --exclude 'bhavcopy' --exclude 'studies.db' "$H:~/saavi/institutional-trader/data/" data/ 2>/dev/null
  rsync -az -e "ssh -i $HOME/.ssh/saavi_lightsail" "$H:~/saavi/institutional-trader/logs/app.log" logs/app.log 2>/dev/null
  sleep 60
done
