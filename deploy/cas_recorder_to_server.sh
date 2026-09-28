#!/bin/bash
# Move ONLY the CAS recorder to the server (independent of the Saavi engine).  deploy/cas_recorder_to_server.sh saavi
H="${1:-saavi}"
ssh "$H" "sudo systemctl enable --now saavi-cas-recorder.timer" && echo "server CAS timer on"
launchctl bootout "gui/$(id -u)/com.sayali.cas-recorder" 2>/dev/null; mkdir -p ~/Library/LaunchAgents/disabled
mv ~/Library/LaunchAgents/com.sayali.cas-recorder.plist ~/Library/LaunchAgents/disabled/ 2>/dev/null; echo "Mac CAS recorder off"
