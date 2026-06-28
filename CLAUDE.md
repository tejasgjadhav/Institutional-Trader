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

**3-Family stocks** → alpha-z (TREND 0.72 + FLOW 0.18 + EVENT 0.10), then the gates:
1. **Alpha** — |alpha-z| > 0.55 AND ≥2/3 families agree.
2. **ORB** — latest 5-min candle breaks the opening range with a volume surge.
3. **Market alignment** — only LONG when Nifty up / SHORT when Nifty down (`MARKET_ALIGN_FILTER`). Robust out-of-sample.
4. **Don't chase** (extension) — **DISABLED 2026-06**: didn't hold on the real-option 180d test.
5. **Wide open** (ORB-width) — **DISABLED 2026-06**: same.
5b. **Min option premium** — only trade when the OTM+1 option ≥ `MIN_OPTION_PREMIUM` (₹30) (`MIN_OPTION_PREMIUM_FILTER`). **The real edge** from the 180d backtest: cheap lottery options (avg ₹38) bleed out; richer ones (avg ₹101) follow through AND have ~3× smaller spread.
6. **Liquidity** — OTM+1 option needs a live two-sided market: spread ≤ `MAX_OPTION_SPREAD_PCT` (4%), OI ≥ `MIN_OPTION_OI` (100). Checked with 5b after gates 1-3 pass. Fails open on a quote error.
All pass → buy OTM+1 CALL/PUT, exit **+10% / −15%** on premium (−15 stop drops breakeven win 67%→60%).

**ORB+VWAP index** (NIFTY/BANKNIFTY, parallel) → 15-min ORB + VWAP + 30-min trend + clean-trend
filter → buy ATM, **trend-ride exit** (exit on VWAP reclaim after +12%, hard **−15%** stop).

**Swing credit spread** (NIFTY/FINNIFTY, the 3rd strategy, multi-day) → daily **Donchian-10**
breakout → **SELL a credit spread AGAINST it** (fade: up-break → bear-call, down-break → bull-put),
mid-tenor (≥10 DTE), short 1-OTM, width 3, **hold to expiry**, hard stop at 2× credit. Overnight
carry — NOT squared at 15:30. Signals-only paper forward-test (`engine/swing_credit.py`,
`config.SWING_*`); its own **SWING CREDIT SPREADS** section on PM DECISIONS between stocks and index.
The one validated edge — robust across 5 breakout defs (D10/15/20/30/prior-week) AND across NIFTY+FINNIFTY (BANKNIFTY dropped: tested −6.7%). HIGH variance; still forward-test.

**Stock credit spread** (the 4th strategy, high-FREQUENCY ~16/mo) → same fade, on the full ~100-stock
universe, but GATED: credit/width ≥ 0.40 (rich premium = elevated post-breakout IV — the edge) +
short premium ≥ ₹50 + live liquidity gate (OI, bid-ask) + per-day/total-open caps. Backtest 65% win,
+16–25% net/trade, holdout p5 +6.8%, 76/100 stocks. The credit/width gate is essential — a *generic*
stock spread LOSES (−4.7%, the 4-leg slippage wall). Signals-only paper forward-test
(`engine/stock_credit.py`, `config.STOCK_CREDIT_*`); own STOCK CREDIT SPREADS PM + trade-log section.
**Backtest is OPTIMISTIC (~20%/mo on margin won't fully survive live mid-cap fills) — KEEP LOTS AT 1.**

**REAL option data (expired-instruments / Upstox Plus) — honest standing after the 1-year test:**
- **STOCKS: no proven durable edge.** The min-premium config looked like +1.5% (64% win) on a
  180-day window but came in at **−1.0% (55% win) over a full year** — overfit to a recent
  regime. Min-premium is kept only for the *spread/cost* benefit (richer options, ~3× tighter
  spread), NOT as a profit edge. Treat stocks as a paper forward-test, not a money-maker.
- **INDEX: thin but durable edge.** Trend-ride (−15 stop) ran **+0.9% over 18 months (453 trades),
  positive on both train and test.** The one real (small) edge.
- **STOCK multi-day credit spreads: rejected on real cost.** Sell-premium/theta-harvest looked
  like +6.9% holdout on an *estimated* cost, but **real per-leg cost (₹1,137/trade, 4 legs) flipped
  it to −4.7% net, PF 0.87.** Dead. See `studies/STOCK_OPTIONS_NO_EDGE.md` Part 4.
- **INDEX fade credit spread: VALIDATED & deployed (the 3rd strategy).** Selling a credit spread
  *against* a daily index breakout (theta + tightest bid-ask + trades with the reversion) clears
  measured costs: **+12–20% net/trade (live geometry), PF 1.4–1.95, survives 2× cost**. **Robust
  across 5 breakout definitions** (D10/15/20/30 + prior-week — genuine reversion, not a D10 fit).
  **HIGH variance** (wins ~+40–60% of margin, losses ~−100%; thin-holdout bootstrap p5 negative —
  positive EV but a bad draw can lose). At 1 lot: **~₹1–2k/month** (margin ~₹6–7k/trade).
  **Lineup = NIFTY + FINNIFTY** (a 5-index robustness test DROPPED BANKNIFTY: −6.7% on 40 trades,
  its earlier +13% was 14-trade luck; MIDCPNIFTY marginal+thin → skipped). Runs as a parallel paper
  FORWARD-TEST in `engine/swing_credit.py` (`SWING_LOTS` sizes it; keep at 1). See Parts 5–7. NOTE:
  the *follow* version (with the breakout) loses (40% win); the edge is specifically the **fade**.
  (An earlier +4%/p5+2.3% figure was a width-bookkeeping bug — now fixed; the live engine was always correct.)
- Lesson: a train/test split *inside a short window* is not true out-of-sample; use the longest
  window the data allows. See `studies/REAL_OPTION_OPTIMIZATION.md` (CORRECTION at the top).
Old gates 4/5 are OFF tunables; everything is GROSS of costs.
The universe is the hand-picked ~100 (mostly mid/large-cap movers) — NOT ranked by market cap:
a head-to-head showed a free-float-mcap top-100 *lost* to it (61% vs 67% on the same window),
because mega-caps don't break out. Select by intraday movement, not size — see
`studies/UNIVERSE_94_VS_100_HEADTOHEAD.md`.

**Priority stocks (`config.PRIORITY_STOCKS`, 13 names):** the only stocks whose gates-1-5 win
rate persisted out-of-sample (train→test, ~75%/110 trades). Per-stock win-rate selection
overfits (top-60 by win rate: 64% train → 49% test), so the universe stays broad at 100 and the
engine fires on all of them; these 13 are just **★-flagged in the read-only UI** as a focus tilt
— they do NOT change engine selection or the overall win rate. See `studies/PRIORITY_STOCKS_PERSISTENCE.md`.

## Key files

```
engine/engine_runner.py   HEADLESS ENGINE daemon — the schedule + all writes
engine/store.py           data/engine.db — daily scan rows + market snapshots
engine/agent.py           run_scan orchestrator (3-Family + ORB+VWAP), execute_signals
engine/signals.py         3-family scoring + alpha-z + ORB gate
engine/orb_vwap_live.py   index ORB+VWAP strategy (trend-ride exit)
engine/swing_credit.py    SWING credit-spread strategy (multi-day · fade · book in data/swing_positions.json)
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
