#!/usr/bin/env bash
# One-shot local setup from a fresh GitHub clone (macOS).
#   git clone <repo> && cd institutional-trader && ./setup.sh
# Creates the venv, installs deps, seeds .env, and installs+starts the launchd jobs
# (headless engine = always on; read-only viewer = auto-launch 9:00 weekdays).
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PY="$REPO/.venv/bin/python"
LA="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
cd "$REPO"

echo "==> Repo: $REPO"

# 1) venv + dependencies
if [ ! -x "$PY" ]; then
  echo "==> Creating virtualenv (.venv)"
  python3 -m venv .venv
fi
echo "==> Installing dependencies"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt
# optional: studies need prophet + matplotlib (skip if it fails — engine doesn't need them)
"$PY" -m pip install -q prophet matplotlib 2>/dev/null || echo "   (skipped optional study deps)"

# 2) .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from template — EDIT IT and add your UPSTOX_ANALYTICS_TOKEN before running."
fi
mkdir -p data logs

# 3) launchd jobs — generated with THIS clone's absolute path (so it works anywhere)
gen_plist () {  # $1=label  $2=ProgramArguments-xml  $3=extra-xml
  cat > "$LA/$1.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key><array>$2</array>
  <key>WorkingDirectory</key><string>$REPO</string>
  $3
  <key>StandardOutPath</key><string>$REPO/logs/$1.out.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/$1.err.log</string>
</dict></plist>
PLIST
}

ENGINE_ARGS="<string>/usr/bin/arch</string><string>-arm64</string><string>$PY</string><string>-m</string><string>engine.engine_runner</string>"
VIEWER_ARGS="<string>/usr/bin/arch</string><string>-arm64</string><string>$PY</string><string>$REPO/main.py</string>"
WEEKDAYS9="<key>StartCalendarInterval</key><array><dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer></dict><dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>9</integer></dict><dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>9</integer></dict><dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>9</integer></dict><dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>9</integer></dict></array>"

gen_plist "com.sayali.institutionaltrader.engine" "$ENGINE_ARGS" "<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>"
gen_plist "com.sayali.institutionaltrader"        "$VIEWER_ARGS" "$WEEKDAYS9<key>RunAtLoad</key><false/>"

echo "==> Loading launchd jobs"
launchctl bootout "gui/$UID_NUM/com.sayali.institutionaltrader.engine" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM/com.sayali.institutionaltrader" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$LA/com.sayali.institutionaltrader.engine.plist"
launchctl bootstrap "gui/$UID_NUM" "$LA/com.sayali.institutionaltrader.plist"

echo ""
echo "==> Done. The engine is now running (KeepAlive). To open the viewer now:"
echo "    $PY $REPO/main.py"
echo "    (or it auto-launches at 9:00 on weekdays)"
echo "==> If you haven't yet: edit .env and add UPSTOX_ANALYTICS_TOKEN, then:"
echo "    launchctl kickstart -k gui/$UID_NUM/com.sayali.institutionaltrader.engine"
