#!/bin/bash
# Run ON THE SERVER (Ubuntu 22.04) once: bash ~/saavi/institutional-trader/deploy/server_setup.sh
set -euo pipefail
sudo timedatectl set-timezone Asia/Kolkata
sudo apt-get update -y && sudo apt-get install -y python3.10-venv python3-pip rsync sqlite3
cd ~/saavi/institutional-trader
python3.10 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r deploy/requirements-server.txt
mkdir -p logs data
sed "s/__USER__/$USER/g" deploy/saavi-engine.service | sudo tee /etc/systemd/system/saavi-engine.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable saavi-engine        # starts on every boot; NOT started now — cutover.sh starts it
echo "server ready. Next, from the Mac: deploy/cutover.sh $USER@<server-ip>"
