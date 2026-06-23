# CLAUDE.md — Institutional Trader (project context for Claude Code)

Read this first. It is the canonical context for working on this repo. Add task-specific
instructions on top of it.

## What this is

A **paper-trading** algo system for NSE (Indian market) intraday **options**. It scans
NIFTY, BANKNIFTY and ~100 liquid stocks every 5 minutes, scores each with a 3-family model,
and surfaces buy-option signals on a dashboard. **It never places orders** — the user places
them manually in Upstox. Status: a forward paper-test of a thin, ~52–61% directional,
roughly-breakeven-after-costs edge. **Not proven profitable.** Be honest about this always.

## Architecture — two processes (decoupled)

| | Headless **ENGINE** (`engine/engine_runner.py`) | Desktop **VIEWER** (`main.py` → `engine/ui_terminal.py`) |
|---|---|---|
| launchd job | `com.sayali.institutionaltrader.engine` (KeepAlive, always on) | `com.sayali.institutionaltrader` (auto-launch 9:00 weekdays) |
| Role | scan · fire signals · resolve paper trades · 15:30 EOD-book · save all data | **read-only** display |
| Cadence | wakes every **5 s** in market hours; scans every 5 min; idles (5-min sleep) when closed | re-reads disk every 15 s |
| Writes | `engine.db`, `signals.db`, `trade_log.json`, `latest_scan.json`, `market_snapshot.json` | **nothing** |

The engine runs the full schedule **whether or not the viewer is open**. The viewer only
reads what the engine wrote, so a viewer crash can never stop trading. Do not put trading
logic in the GUI — it belongs in the engine.

## Setup from a fresh clone (macOS, Apple Silicon)

```bash
git clone <repo-url> institutional-trader && cd institutional-trader
./setup.sh                 # venv + deps + .env template + launchd jobs (engine starts)
# then edit .env, add UPSTOX_ANALYTICS_TOKEN, and:
launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine
.venv/bin/python main.py   # open the read-only viewer (or it auto-launches 9:00 weekdays)
```

`setup.sh` generates the launchd plists with the clone's absolute path, so it works from any
location. Reference plists are in `deploy/`. Requires Python 3.9+, a free Upstox **Analytics**
token (read-only data feed — no trading token needed).

## Strategy (what the gates do)

**3-Family stocks** → alpha-z (TREND 0.72 + FLOW 0.18 + EVENT 0.10), then 6 gates:
1. **Alpha** — |alpha-z| > 0.55 AND ≥2/3 families agree.
2. **ORB** — latest 5-min candle breaks the opening range with a volume surge.
3. **Market alignment** — only LONG when Nifty up / SHORT when Nifty down (`MARKET_ALIGN_FILTER`).
4. **Don't chase** — skip if the stock already moved > `MAX_ENTRY_EXTENSION_PCT` (2.9%) from the open.
5. **Wide open** — first-30-min opening range must be ≥ `ORB_RANGE_WIDTH_MIN` (0.8%) of price (`ORB_RANGE_FILTER`). Validated 365d: dir win 51→54%, option 60d 66→70% at +10/−20.
6. **Liquidity** — the OTM+1 option must have a live two-sided market: spread ≤ `MAX_OPTION_SPREAD_PCT` (4%), OI ≥ `MIN_OPTION_OI` (100) (`LIQUIDITY_FILTER`). Checked ONLY after gates 1-5 pass (~1-2 quote calls/day). Fails open on a quote error.
All 6 pass → buy OTM+1 CALL/PUT, exit **+10% / −20%** on premium.

**ORB+VWAP index** (NIFTY/BANKNIFTY, parallel) → 15-min ORB + VWAP + 30-min trend + clean-trend
filter → buy ATM, **trend-ride exit** (exit on VWAP reclaim after +12%, hard −20% stop).

Gates 3, 4 & 5 are the proven wins (validated on 365 days). See `studies/` for all 9 studies.

## Key files

```
engine/engine_runner.py   HEADLESS ENGINE daemon — the schedule + all writes
engine/store.py           data/engine.db — daily scan rows + market snapshots
engine/agent.py           run_scan orchestrator (3-Family + ORB+VWAP), execute_signals
engine/signals.py         3-family scoring + alpha-z + ORB gate
engine/orb_vwap_live.py   index ORB+VWAP strategy (trend-ride exit)
engine/paper_resolver.py  closes PENDING paper trades on the option premium
engine/options.py         strike resolver + live option order builder
engine/signal_db.py       SQLite log of every PM signal
engine/trade_log.py       paper log: win rate, PF, expectancy
engine/data_utils.py      market snapshot (batched LTP + fallbacks)
engine/config.py          ALL tunables (gates, exits, universe, paths)
engine/ui_terminal.py     READ-ONLY viewer (tabs: PM / WATCHLIST / ALPHA / TRADE LOG / STUDIES / README)
main.py                   viewer launcher
deploy/                   launchd plists (engine + viewer)
studies/                  research log (9 .md studies) + reproducible scripts
data/                     engine.db / signals.db / trade_log.json (gitignored runtime data)
```

## Operating conventions (follow these)

- **SECURITY:** `.env` holds the Upstox token + notification keys. It is **gitignored and must
  NEVER be committed/pushed.** Before every commit verify: `git diff --cached --name-only | grep -q "\.env$"` returns nothing.
- **Restart after engine/UI code changes** (launchd does not hot-reload):
  - engine: `launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`
  - viewer: `kill -9 $(pgrep -f main.py); sleep 3; launchctl kickstart gui/$(id -u)/com.sayali.institutionaltrader`
  - (plain `kickstart -k` does NOT restart a detached GUI process — kill it first.)
- **Backtest before deploy.** Never change a live tunable on a hunch. Run the 30/60-day option
  backtest (and the 365-day underlying study for direction) and show the numbers first. Several
  "good-looking" ideas (time-of-day filter, removing the +10% cap, index gates) were tested and
  correctly **not** deployed.
- **Data limits:** real option-premium history is only ~1 month back; index futures ~33 days.
  Daily price = 2+ yrs, 5-min price = ~1 yr. Long backtests must use the underlying proxy or a
  paid vendor — see `studies/DATA_AVAILABILITY_LIMITS.md`.
- **Honesty over optimism.** This is a thin, unproven edge. Always frame results gross-vs-net,
  sample size, and out-of-sample fragility. Don't sell a curve-fit.
- **Commits:** branch off main if needed; end commit messages with the Co-Authored-By trailer.

## Health checks

```bash
pgrep -f engine.engine_runner   # engine alive?
pgrep -f main.py                # viewer alive?
.venv/bin/python -c "from engine import store; print(store.stats())"   # engine.db counts
tail logs/engine.out.log        # engine log
.venv/bin/python -m engine.engine_runner --once   # run one engine cycle manually
```
