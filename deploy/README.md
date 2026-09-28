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
