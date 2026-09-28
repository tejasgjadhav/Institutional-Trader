# Moving the Saavi engine to a machine that never sleeps (28-Sep-2026)

Why: the Mac slept through scan windows on five of six trading days in the week of 21-Sep. The
engine never failed; the machine under it did. A small always-on Linux server fixes that.

What moves: the headless engine only (`python -m engine.engine_runner`). The Mac keeps the Saavi UI
as a viewer that copies the server's live state every minute. Telegram works from anywhere, so every
signal still reaches the channel directly from the server. Study history (2 GB) stays on the Mac.

What you need (only you can do these): a server running **Ubuntu 22.04** in an Indian region with
1 GB RAM (1 vCPU is enough), your SSH key on it, and its IP address. Python 3.10 on 22.04 matches
the pinned libraries; Ubuntu 24.04 does not (numpy 1.24).

Steps
1. Create the server; note `user@ip`. Check you can `ssh user@ip` from the Mac.
2. `deploy/push_to_server.sh user@ip` — copies code and live state (not .env).
3. Copy your secrets yourself: `scp .env user@ip:~/saavi/institutional-trader/.env`
4. `ssh user@ip bash ~/saavi/institutional-trader/deploy/server_setup.sh` — India timezone, Python,
   libraries, and a systemd service that restarts on crash and on every boot (not started yet).
5. After 15:45 or on a weekend: `deploy/cutover.sh user@ip` — stops and disables the Mac engine,
   copies the final state, starts the server engine. Two engines never run at once.
6. `deploy/viewer_sync.sh user@ip` — keeps the Mac UI current.

Rollback at any time: `deploy/rollback.sh user@ip`.

Notes: the Upstox analytics token was issued 10-Jun-2026 and is read-only market data (no daily
login). Paper trading places no orders, so no static-IP registration is needed. The three CAS/IEP
recorders stay on the Mac for now; they can move the same way later.

## LIVE since 28-Sep-2026 20:06 — AWS Lightsail Mumbai
- Server `saavi-engine`, Ubuntu 22.04.5, 512 MB + 1 GB swap, $5/month (+ GST), static IP **13.206.60.104**.
- SSH alias `saavi` (in `~/.ssh/config`, key `~/.ssh/saavi_lightsail`). Engine: systemd `saavi-engine`
  (restarts on crash, starts on boot). Logs: `~/saavi/institutional-trader/logs/app.log` on the server.
- Mac: engine disabled (plist in `~/Library/LaunchAgents/disabled/`); UI is a viewer; viewer sync
  (`com.sayali.saavi-viewer-sync`) and watchdog (`com.sayali.saavi-watchdog`) start at login.

## FALLBACK — back to the Mac in one command (drilled 28-Sep-2026, both directions passed)
    cd ~/files/institutional-trader && deploy/rollback.sh saavi
Stops the server engine, stops the viewer sync (so it cannot overwrite the Mac engine's files), pulls
the server's latest state, re-enables the Mac engine and checks exactly one engine runs. If the server
does not answer, it refuses unless you add `--force` — use that ONLY when the AWS console shows the
instance stopped, or two engines would double every Telegram signal.
Return to the server: `deploy/cutover.sh saavi` (after 15:45 or at a weekend).
Check any time: `deploy/status.sh saavi`. The watchdog shows a Mac notification if the server's
heartbeat is older than 12 minutes during 09:10–15:50 on weekdays; it never switches engines itself.
