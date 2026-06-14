#!/usr/bin/env bash
# One-shot setup from a fresh clone (macOS and Linux).
#   git clone <repo> && cd Institutional-Trader && ./setup.sh
# Creates the virtualenv, installs the requirements and seeds .env. It does not install any
# background job: start the engine yourself when you want it running.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PY="$REPO/.venv/bin/python"
cd "$REPO"

echo "==> Repo: $REPO"

if [ ! -x "$PY" ]; then
  echo "==> Creating virtualenv (.venv)"
  python3 -m venv .venv
fi
echo "==> Installing dependencies"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from the template. Edit it and add your UPSTOX_ANALYTICS_TOKEN."
fi

mkdir -p data logs

cat <<'EOF'

Done.

  Run one cycle:   .venv/bin/python -m engine.engine_runner --once
  Run the engine:  .venv/bin/python -m engine.engine_runner
  Open the app:    .venv/bin/python main.py

Read DISCLAIMER.md before you run anything. The one strategy that ships with this repository
is a teaching example that has never been backtested, and the author does not trade it.
EOF
