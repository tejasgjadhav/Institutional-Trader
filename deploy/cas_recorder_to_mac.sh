#!/bin/bash
# Move ONLY the CAS recorder back to the Mac (independent of the Saavi engine).  deploy/cas_recorder_to_mac.sh saavi
H="${1:-saavi}"
ssh -o ConnectTimeout=10 "$H" "sudo systemctl disable --now saavi-cas-recorder.timer" 2>/dev/null && echo "server CAS timer off" || echo "server not reachable — Mac recorder enabled anyway (the server timer may still run)"
mv ~/Library/LaunchAgents/disabled/com.sayali.cas-recorder.plist ~/Library/LaunchAgents/ 2>/dev/null
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.sayali.cas-recorder.plist && echo "Mac CAS recorder on (15:50 + 16:20 weekdays)"
