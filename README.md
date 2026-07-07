# Institutional Trader — STOCK CREDIT v2 fade (the winner) · NSE Options

**Start here — the winner:** ★ **STOCK CREDIT v2 (TP-50)** — sell a defined-risk credit spread
against a stock breakout, book the win at half the credit. **86% win rate, ~17.5%/month (model,
₹1L book), positive every year 2019→2026, validated in-sample AND out-of-sample.** Everything
else in this repo is either its supporting cast (v1 base book, index-fade forward-test, the
3-Family intraday scanner it grew out of) or the honest research trail that found it.

A disciplined **paper-trading** system for NSE options. Four books run in parallel — the
flagship is the **STOCK CREDIT v2 (TP-50) fade**: sell a defined-risk credit spread against a
stock breakout, book the win at half the credit. **85.35% win in-sample (2019→Sep'24) ·
87.88% out-of-sample (Oct'24→Jul'26) · positive every year · MODEL ~₹17.5k/mo on a ₹1L book.**
Alongside it: the v1 stock fade, an index-fade forward-test, and the intraday 3-Family
buy-option scanner. Signals only — **you place every order yourself in Upstox; the software
never sends orders.** It is a process for collecting honest evidence, not a proven money-maker
(live fills remain the unproven link — practical planning ≈ half of model).

> Full plain-language walkthrough is on the **README tab** inside the dashboard. The
> **current** research + backtests live in **`studies/`** (and the in-app **STUDIES tab**).
> `How_We_Built_The_Strategy.pdf` / `BACKTEST_RESULTS.md` are the earlier build journey
> (historical — superseded by `studies/`).

---

## Replicate from a clone

```bash
git clone https://github.com/tejasgjadhav/Institutional-Trader.git institutional-trader
cd institutional-trader && ./setup.sh     # venv + deps + .env template + launchd jobs
# add your UPSTOX_ANALYTICS_TOKEN to .env, then:
launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine
.venv/bin/python main.py                  # read-only dashboard
```

Everything needed is in the repo: the 5 live paper books start empty and populate on their
schedules (0DTE at 9:16 on expiry days; credit scans 15:10 daily). Runtime data (`data/`,
`.env`, logs) is gitignored — a clone is a fresh, working instance. The legacy 3-Family 5-min
scan ships DISABLED (`SCAN_3FAMILY_ENABLED=False` — it fed only its own hidden paper book and
caused API rate-limit storms; flip to True to resume that forward-test).

## Current lineup (updated 2026-07-07)

| Book | Cadence | Validated result (real premiums) | Status |
|---|---|---|---|
| ★ Stock fade v2 (TP-50) | 4–6/mo, multi-day | 85% IS / 88% OOS win · +24.5/+31.9% of width | LIVE paper · gold on SWING TRADES |
| Stock credit v1 | ~10/mo, multi-day | 54% win · +5.3% of width (2019–24 clean) | LIVE paper |
| 0DTE NIFTY CE spread | Tuesdays 9:16 | 90.4% win OOS · +5.85%/margin (rv5 filter + ₹5-pt credit floor) | LIVE paper since 2026-07-07 (day-1 WIN) |
| 0DTE SENSEX CE spread | Thursdays 9:16 | 88.8% win · +7.6%/margin (89 expiries, 21-mo history) | LIVE paper — first signal 2026-07-09 |
| 0DTE BANKNIFTY CE spread | Monthly expiry | 79.5%/+7.4%m 2019-24 wk + 91%/+11%m monthlies | LIVE paper — next 2026-07-28 |
| 3-Family stocks (BUY) | daily scan | direction +0.107%/tr real, but −1.0% net as options | paper only, HIDDEN from UI 2026-07-07 |

Notes (2026-07-07): NIFTY 0DTE's first live paper trade settled a WIN (thin-credit week —
which prompted the ₹5-pt credit sanity floor, user-reviewed). 3-Family stays RUNNING by
deliberate decision (its 5-min scan is the engine's data heartbeat; its direction edge is real
but un-monetizable net of option-buying costs) — it is simply hidden from the dashboard.
Consolidated expected P&L (model vs plan-on), the 0DTE studies, gates (calm-regime rv5,
thin-credit floor), stop-loss verdict and the near-daily rejection: see
`studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md` and the STUDIES tab.

## Quick Start

```bash
cd ~/files/institutional-trader

# Headless ENGINE (does all the work; normally run by launchd)
.venv/bin/python -m engine.engine_runner          # daemon loop
.venv/bin/python -m engine.engine_runner --once   # one cycle (testing)

# Read-only VIEWER (the desktop dashboard)
.venv/bin/python main.py

# Health & tools
.venv/bin/python -c "from engine.api_diagnostics import diagnose; diagnose()"
.venv/bin/python -m engine.events          # refresh NSE event scores now
.venv/bin/python -m engine.notifications   # show alert channels + send test
```

Auto-start (engine always-on; viewer auto-launches 9:00 weekdays):
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sayali.institutionaltrader.engine.plist  # engine
launchctl load ~/Library/LaunchAgents/com.sayali.institutionaltrader.plist                           # viewer
```

---

## Architecture — Engine vs Viewer (two processes)

The trading **engine** and the desktop **app** are decoupled, so the engine runs the full
daily schedule **whether or not the app is open**.

| | Headless **ENGINE** (`engine/engine_runner.py`) | Desktop **VIEWER** (`main.py` → `engine/ui_terminal.py`) |
|---|---|---|
| launchd job | `…institutionaltrader.engine` (KeepAlive, always on) | `…institutionaltrader` (auto-launch 9:00 weekdays) |
| Role | scan · fire signals · resolve · EOD-book · save data | **read-only** display |
| Schedule | wakes every **5 s** in market hours; scans every 5 min; 15:30 force-book | re-reads disk every 15 s |
| Writes | `engine.db`, `signals.db`, `trade_log.json`, `latest_scan.json`, `market_snapshot.json` | nothing |

**All data is saved locally daily** in `data/engine.db` — every scan (one row per stock with
its full gate state) and every market snapshot — apart from trade outcomes, which stay in
`trade_log.json`. The viewer never scans, fires, resolves, books, or writes a DB; it only
reads what the engine wrote (header: `READ-ONLY VIEWER — engine scan Nm ago`). So a viewer
crash can't stop trading, and execution latency is independent of the display.

---

## What It Does (in one breath)

Four books run in parallel, all reported on **PM DECISIONS** (leader first, gold-highlighted),
all options-only, all manual-execution:

- **★ STOCK CREDIT v2 — TP-50 (THE LEADER, SELL):** Donchian-10 stock breakout → sell a credit
  spread AGAINST it (short 2-OTM, width 4), gate credit/width ≥ 0.40 + prem ≥ ₹50 + ₹40k exposure
  cap; **take profit at 50% of the credit, stop 3×**. 86% win, ~4–6 signals/mo, positive every year
  2019→2026 (in-sample + OOS). `studies/STOCK_FADE_TP50_UPGRADE.md`
- **Stock credit spread v1 (SELL):** same fade, original geometry (1-OTM, width 3, TP 75%) — the
  validated base edge (+5.3% of width, 54% win on 2019→Sep'24). Runs in parallel for comparison.
- **Index fade NIFTY/FINNIFTY (SELL, forward-test):** downgraded on real pre-2024 data
  (regime-dependent) — kept small, signals ~15:10.
- *(ORB+VWAP index was RETIRED 2026-07 — thin/inconsistent on real 2019→date 5-min data.)*

The intraday BUY scanner:

- **3-Family system (100 stocks):** every 5 min it (1) pulls fresh **Upstox** prices,
  (2) scores each stock into one number, **alpha-z**, (3) checks the score is strong
  and broad enough (**Gate 1**), breaking out *now* (**Gate 2**), aligned with the Nifty
  (**Gate 3**), the OTM+1 option is **rich enough (≥ ₹30, Gate 5b)** and liquid enough
  (**Gate 6**). All pass → a **buy-option order** (OTM+1, **+10%/−15%**) appears for you to
  place. *(Gates 4 "don't-chase" and 5 "wide-open" were retired in 2026-06 — they didn't
  hold up on the real-option 180-day backtest; the min-premium gate is kept as a cost/quality filter, not a proven profit edge.)*
- **ORB+VWAP system (NIFTY & BANKNIFTY):** a separate index strategy — 15-min ORB +
  VWAP + 30-min trend + clean-trend filter, buy **ATM**, **trend-ride exit** (VWAP-reclaim
  after +12%, hard **−15%** stop) — see the section below.

> **2026-06 — real option data, and an honest 1-year reality check.** An Upstox Plus upgrade
> unlocked historical premiums for *expired* contracts, so the strategy is now backtested on
> **actual option P&L**, not the underlying proxy. A min-premium config *looked* like +1.5% on
> 180 days — but over a **full year it was −1.0% (55% win): overfit to a recent window.**
> **Stocks have no proven durable edge** — the min-premium gate is kept only for its tighter
> spread (a cost filter), not for profit. The **INDEX** trend-ride (−15 stop) *did* hold:
> **+0.9% over 18 months, both train and test** — the one real, thin edge. See
> `studies/REAL_OPTION_OPTIMIZATION.md` (CORRECTION at top). All figures GROSS.

The 3-Family system scans **stocks only**; the indices are handled exclusively by the
ORB+VWAP strategy.

---

## When do signals come? (all books, IST)

| Time | Book | What fires |
|------|------|-----------|
| **~15:10 daily** | **★ STOCK CREDIT v2 (leader)** | Donchian-10 needs the day's close → engine scans once after 15:10; ~4–6 spreads/mo appear on PM DECISIONS (gold section) to place before 15:30 |
| ~15:10 daily | Stock credit v1 | same scan, original geometry (~10/mo) |
| ~15:10 daily | Index fade NIFTY/FINNIFTY | same scan (~2–3/mo, forward-test) |
| 09:45–13:00 (peak 10:30–11:00) | 3-Family stocks (BUY) | intraday scanner, ~1–2 signals/day |
| — | ORB+VWAP | retired 2026-07 |

**Practical routine: one look at ~15:10–15:25 covers all three credit books** (they hold days–weeks,
nothing intraday to babysit); the 3-Family scanner is the only intraday screen if you follow it.

## The Daily Clock (IST)

| Time | What happens |
|------|--------------|
| 08:55 | Mac wakes itself (pmset) |
| always-on | **Engine** daemon runs (launchd KeepAlive) — independent of the app |
| 09:00 | **Viewer** (read-only dashboard) auto-launches; first NSE **event scrape** (then ~every 20 min to 1 PM) |
| **09:15** | Market opens — engine starts scanning, ALPHA fills |
| 09:15–09:45 | Wildest part of the day — watch only |
| **09:45** | Trading window opens |
| every 5 min | Engine re-scans NIFTY + BANKNIFTY + 100 stocks (~0.6–2.7 sec) |
| **13:00** | No new trades after 1 PM |
| **15:10** | Kill switch for intraday BUYS · **CREDIT SCAN fires: ★v2 + v1 + index swing spreads appear on PM DECISIONS** |
| **15:30** | Market closes — **every OPEN paper trade is force-booked WIN/LOSS at the close** (Mon–Fri) |

Signals are selective — **~1–2 a day** (365-day study: ~1.7/day), many days none. The
directional edge is strongest **10:30–11:00** and thins through the afternoon.

---

## Data Sources

- **Upstox V3 (primary, low latency)** — live LTP, 5-min candles, daily history, and
  index data (NIFTY / BANKNIFTY / VIX). ISIN-based instrument keys, auto-resolved
  from Upstox's instrument master (cached weekly).
- **NSE corporate-announcements (live scraper)** — feeds the EVENT family; scraped at
  ~9 AM and refreshed ~every 20 min to 1 PM (`engine/events.py`).
- **Yahoo Finance** — emergency fallback only (slower; never primary).

---

## The 3 Families (all live)

Three independent families; each votes LONG / SHORT / NEUTRAL, then blends into alpha-z
by weight: `alpha-z = Σ(family z × weight) ÷ Σ(weights)`.

| Family | Weight | What it measures |
|--------|--------|------------------|
| **TREND** | 0.72 | Three factors z-scored vs own history: **momentum** (60-min return, 0.37), **trend quality** (daily EMA-9 vs EMA-21 spread, 0.24), **microstructure** (15-min ORB breakout ±1, 0.04) |
| **FLOW** | 0.18 | **Live per-stock options flow** from the option chain (cached ~10 min): **OI-buildup imbalance** (writers adding puts vs calls) + **PCR trend** (put/call OI ratio rising/falling). Puts→support→bullish(+), calls→resistance→bearish(−). Symmetric, change-based |
| **EVENT** | 0.10 | **Live** NSE announcements scraped at startup + ~every 20 min, 9 AM–1 PM, keyword-scored: orders/results/bonus = +1, fraud/penalty/downgrade = −1, routine = 0. Down-weighted (crude scoring) |

### TREND — `signals.compute_trend_family()`
Momentum = z-score of the latest 60-min intraday return vs the day's distribution.
Trend quality = z-score of the daily EMA-9 − EMA-21 spread. Microstructure = +1/−1 on a
15-min opening-range breakout.

**Sub-factor weights** (in `config.FAMILY_WEIGHTS['TREND']['factor_weights']`, normalised in
code by their sum 0.65): momentum **0.37 (~57%)**, trend-quality **0.24 (~37%)**,
microstructure **0.04 (~6%)**.

**How the weights were set — honest:** they are **hit-rate-informed, not rigorously
optimised**. TREND carries the biggest *family* weight (0.72) because it was the only family
with a real edge in testing; momentum is the strongest sub-factor; **microstructure is
deliberately tiny because that ORB breakout is also Gate 2** — keeping it ~6% of the score
avoids double-counting the same signal in both the alpha-z and the gate. Fitting all weights
to data (instead of hand-setting) is a known open improvement, not yet done.

### FLOW — `signals._flow_from_options()` + `options_flow.fetch_options_flow()`
Pulls the live Upstox option chain per stock and computes, from current vs previous OI:
**OI-buildup imbalance** `(ΔputOI − ΔcallOI) / (|ΔputOI|+|ΔcallOI|)` (±0.2 thresholds) and
**PCR trend** `PCR − PCR_prev` (±0.02). OI-writing view: writers sell puts expecting
support (bullish) and calls expecting resistance (bearish). Symmetric and scale-free —
no absolute-PCR-level term (stock PCRs sit below 1.0, which would bias it). Falls back to
the legacy VIX/Nifty proxy only if the chain is unavailable.

### EVENT — `events.refresh_event_scores()` + `signals.compute_event_family()`
Scrapes NSE corporate announcements (startup, then ~every 20 min, 9 AM–1 PM), keyword-scores each
to [−1, +1], and the EVENT z = the stock's sentiment. A neutral filing stays 0 (it does
not bias the vote). Deliberately the lowest weight — informative, not decisive.

Each family yields a **z-score**; the weighted average is the **alpha-z** (sign =
direction, size = conviction).

---

## The Gates

**Gate 1 — Alpha:** `|alpha-z| > 0.55` AND ≥ 2 of 3 families agree.
**Gate 2 — Confirmation:** the latest 5-min candle breaks the opening range with a
volume surge, same direction. Two independent methods must agree.
**Gate 3 — Market alignment:** the trade must NOT fight the Nifty's intraday direction —
only LONG when Nifty is up, only SHORT when Nifty is down (`MARKET_ALIGN_FILTER`).
*Backtest: 60-day P&L +₹17,299 → +₹30,911 (≈2×), win ~59%, fewer trades — by cutting
the trend-fighting losers. Full report:*
[`studies/FINAL_STRATEGY_TESTING_60DAY.md`](studies/FINAL_STRATEGY_TESTING_60DAY.md).
**Gate 4 — Don't chase:** skip a signal if the stock has already moved more than
`MAX_ENTRY_EXTENSION_PCT` (2.9%) in the trade's direction from the day's open — buying an
already-extended stock loses edge. *365-day underlying validation: over-extended entries
won ~45% vs ~55% for the sweet spot; held-out per-trade edge +0.13% → +0.16%. Option-level:
60-day win 59% → 61%, P&L +₹32,519 → +₹36,792, return-on-capital +1.7% → +2.8% on fewer
trades; 30-day +₹13,114 at +1.5% (vs +1.1%). The 2.9 cap beat the tighter 2.6 on every
metric — it cuts only the extreme chasers.* (`ENTRY_EXTENSION_FILTER`)
**Gate 5 — Wide open:** require the first-30-min opening range to be at least
`ORB_RANGE_WIDTH_MIN` (0.8%) of price wide — a wide range means real morning momentum
(cleaner breakouts); a narrow, quiet open is chop. *Found via a 90-day option search,
**validated on 365 days (506 trades)**: directional win 51% → 54%; option win **30-day
61% → 66%, 60-day 66% → 70%** at +10/−20 (kept the same risk-reward). Pure arithmetic on
candles already in hand — zero added latency.* (`ORB_RANGE_FILTER`)
**Gate 6 — Liquidity:** before firing, fetch the exact OTM+1 option's **live bid/ask + OI**
and require a two-sided market, spread ≤ `MAX_OPTION_SPREAD_PCT` (4%) of mid, and OI ≥
`MIN_OPTION_OI` (100). *Why: you buy at the ask, sell at the bid — with a +10% target a wide
spread eats the edge, and a stale LTP isn't a real price. Checked **only** for signals that
already cleared Gates 1-5 (~1-2/day) → ~1-2 extra quote calls/day, negligible.*
(`LIQUIDITY_FILTER`)

### Watching the gates fill — the WATCHLIST tab

Every stock that clears Gate 1 lands on **WATCHLIST** with a live per-gate readout:
**G1 / G2 / G3 / G4 / G5 / G6** each show `PASS` or `wait`, plus a progress column
(`5/6  next: liquidity`) and `6/6  READY -> PM` when it fires. The list is sorted
closest-to-firing on top, so you can see exactly which gate each candidate is waiting on.

---

## Instrument & Exit — Buy Options Only

Every signal becomes a **bought option** (never sold):

- **LONG → buy CALL · SHORT → buy PUT**
- **Strike: OTM+1**, but **only if its premium ≥ ₹30** (Gate 5b — skip cheap lottery options,
  the biggest source of losses on the real-option backtest)
- **Nearest expiry** (Nifty weekly, BankNifty/stocks monthly)
- **Exit on the option premium:** **+10% target / −15% stop** (−15, tightened from −20 in
  2026-06: drops the breakeven win rate from 67% → 60%, below the realised ~64%)

You exit on the option's own price, not the stock — leverage means a small underlying
move swings the premium 10%+.

---

## Parallel Strategy — ORB+VWAP Index — ⛔ RETIRED 2026-07

> Retired after the real Kite 5-min test back to 2019: +0.04%/trade underlying direction, ~39% hit,
> negative in ~2 of 8 years per index → ~0% net as options. Its PM slot now shows STOCK CREDIT v2.
> Kept below for the historical record; `ORB_VWAP_ENABLED=False`.

A second, independent strategy runs **alongside** the 3-Family system on **NIFTY &
BANKNIFTY index options only**, shown in its own section on **PM DECISIONS**:

- **Signal:** 15-min Opening-Range Breakout + hold VWAP + aligned with the 30-min trend
- **Clean-trend filter:** only enter when VWAP is sloped the trade's way **and** price is
  already >0.25% extended from the day's open (cuts the marginal, chop-prone breaks)
- **Filters:** entries before 11:00 AM · skip 0-DTE expiry-day spikes · one signal/index/day
- **Instrument:** buy **ATM** CALL/PUT (LONG→CALL, SHORT→PUT)
- **Exit — trend-ride (NEW):** let the winner **run**; exit only when the futures **reclaim
  VWAP** *after* the trade is already +12% in profit; **hard −15% premium stop** throughout;
  otherwise square off at the close. (Replaced the old fixed +20% target.)
- **Live status:** WATCHING → ● RIDING → EXITED VWAP / STOPPED −15%

**Why the change.** ORB+VWAP is a *trend-following* setup, but the old fixed **+20%
target** capped winners while still taking full **−20%** stops — backwards for a trend
strategy. The 60-day backtest is unambiguous:

| Exit | Trades | Win % | Net/trade |
|------|--------|-------|-----------|
| Old: fixed +20% target | 49 | 27% | **−2.60%** |
| **New: trend-ride + clean filter** | 38 | **63%** | **+0.80%** |

The fix turns a clearly-losing config into a roughly-breakeven-gross one by keeping the
big winners that pay for the −20% stops.

**Options-only execution.** VWAP needs volume and the spot index reports none on Upstox,
so the VWAP line is computed from the index **futures** feed — but nothing except options
is ever traded. Config: `ORB_VWAP_*` in `engine/config.py`; logic in `engine/orb_vwap_live.py`.

> **Honest note:** even the new config is only **~+0.8%/trade gross** and fragile
> out-of-sample — after costs it is roughly **breakeven**, not a money-maker. It runs live
> to **forward-test** it, not because it is proven. The trend-ride fix stops the *bleeding*
> (the −2.6%/trade the fixed target was costing); it does not make the index a profit engine. Full
> study: [`studies/INDEX_TREND_RIDE_EXIT.md`](studies/INDEX_TREND_RIDE_EXIT.md).

---

## Parallel Strategy — Swing Credit Spread (the 3rd — DOWNGRADED on real pre-2024 data)

> **⚠️ CORRECTION (2026-07): this index swing is NOT the validated edge.** The numbers below are the
> Oct 2024→date window. When re-tested on **real NSE bhavcopy premiums 2019→Sep 2024** (181 trades) the
> index fade was **net-negative (−1.4% of width)**, positive only in 2019 & 2024 (favorable regimes). A
> direction+flush gate that looked like +15.1%/78% win in-sample **failed out-of-sample** (−2.8% on a
> fresh window; the direction edge reversed) and was reverted. **The one strategy that DID validate on
> real multi-year data is the STOCK fade credit spread** (below) — +5.3% of width, 54% win, positive
> 5 of 6 years. The index swing now runs as a small regime-dependent forward-test only. See
> `studies/STOCK_OPTIONS_NO_EDGE.md` Parts 10–11.

A **third** strategy runs alongside the other two — multi-day. It does the opposite of buying: it
**SELLS** a defined-risk credit spread and harvests theta. Shown in its own **SWING CREDIT SPREADS**
section on **PM DECISIONS**, between the stock and index sections.

- **Signal:** a daily **Donchian-10 breakout** on NIFTY / FINNIFTY.
- **The twist — FADE it:** index breakouts *mean-revert*, so we sell *against* the breakout
  (up-break → **bear-call** spread, down-break → **bull-put** spread). Selling *with* the breakout
  won only 40%; fading wins ~65%.
- **Construct:** mid-tenor (~2-week expiry), short **1 strike OTM**, long **3 strikes** further
  (defined risk), held **to expiry**; hard stop if cost-to-close hits **2× the credit**.
- **Multi-day:** overnight carry — **not** squared at 15:30. Marked-to-market through the day.
- **Live status:** WATCHING → OPEN (live P&L) → WIN / LOSS.

**Why it works where everything else failed.** Buying pays the bid-ask *and* fights theta; stock
credit spreads pay 4 legs of wide stock-option slippage; index *follow*-spreads are directionally
wrong. The fade spread removes all three drags at once — it **sells** (theta works for it), on
**index** options (tightest bid-ask in India), and trades **with the reversion**.

**Backtest — ~20 months of REAL expired-option data (the largest set available):**

| | Trades | Win % | Net/trade (real costs) | Cost ×2 | Holdout boot p5 |
|---|--------|-------|------------------------|---------|-----------------|
| Deployed fade config | 61 | 66% | **+12.3% on margin** | +6.8% | **−9.7%** (high variance) |

**Robustness — the strong evidence.** A 5-definition × 5-index test (396 signals, real costs) shows
the fade edge holds across **every** breakout definition (Donchian-10/15/20/30 + prior-week, all
net-positive on holdout) — a genuine *"breakouts revert"* behavior, not a D-10 fit. It is **not**
uniform across indices, though: NIFTY (PF 1.95) and **FINNIFTY** (PF 1.44) are clean edges;
**BANKNIFTY tested −6.7%** (40 trades — its earlier +13% was small-sample luck) and was **dropped**;
MIDCPNIFTY is marginal and skipped. **Live lineup = NIFTY + FINNIFTY.** It is positive-EV but
**high-variance** (a loss ≈ full margin), so on a thin holdout the bootstrap 5th-percentile is
negative — hence: forward-test, size small.

**Economics at 1 lot, NIFTY + FINNIFTY, Donchian-10, real costs (live strike geometry):**

| | Trades | Win % | Net/trade | ~Per month (1 lot) |
|---|--------|-------|-----------|--------------------|
| NIFTY | 54 | 72% | +21.7% / PF 1.95 | ~₹1,300 |
| FINNIFTY | 38 | 63% | +17.2% / PF 1.44 | ~₹700 |

~**2–3 signals/month**, each held ~3 weeks, ≤2 open at once. Config: `SWING_*` (incl. `SWING_LOTS`)
in `engine/config.py`; logic in `engine/swing_credit.py`; book in `data/swing_positions.json`.

> **Honest note:** still a **FORWARD-TEST** — backtest fills ≠ live fills, and FINNIFTY trades
> **monthly-only** options (NSE killed index weeklies in Nov 2024), so its live slippage may run
> above the model. **Sizing:** ~₹1–2k/month at 1 lot; a ₹5.5L margin can technically stack ~38 lots
> but a normal 3-loss streak would then exceed the account — **never fill the margin; ~5 lots is the
> prudent ceiling** (`SWING_LOTS`, keep at 1). The lineup (NIFTY + FINNIFTY, BANKNIFTY dropped) and
> the mechanism's robustness across breakout definitions come from a 5×5 test — full record:
> [`studies/STOCK_OPTIONS_NO_EDGE.md`](studies/STOCK_OPTIONS_NO_EDGE.md) (Parts 5–7).

---

## Parallel Strategy — Stock Credit Spread (the 4th, high-frequency) — ✅ THE VALIDATED EDGE

> **UPGRADED 2026-07: v2 (TP-50) now runs as a PARALLEL book and is THE LEADER.** Same signal+gate,
> short 2-OTM / width 4 / take-profit 50% of credit / stop 3× / ₹40k exposure cap: **85.35% win
> in-sample (233W/40L, 2019→Sep'24) · 87.88% OOS (Oct'24→Jul'26) · positive EVERY year · MODEL
> ₹17.5k/mo on a ₹1L book (~17.5%/mo; practical ≈ half until live fills prove it).** ORB+VWAP was
> retired from the dashboard to make room. Full math: `studies/STOCK_FADE_TP50_UPGRADE.md`.
>
> **v1 below remains valid and runs in parallel.** This is the one strategy family that validated on real multi-year data. On NSE bhavcopy premiums
> 2019→Sep 2024 (718 gated trades) it held **+5.3% of width (~+9%/trade on margin), 54% win, positive
> in 5 of 6 years** — across COVID (2020), a topping regime (2024) and a bull run, where the index fade
> only worked in favorable years. Caveats kept honest: the real edge is ~⅓–½ of the recent-window
> figures below (65%→54% win, +16–25%→+5.3%), 2023 was −4.5%, and it's validated on historical premiums
> not live fills. Keep lots at 1. See `studies/STOCK_OPTIONS_NO_EDGE.md` Part 10.

The **frequency** sibling of the index swing — the same fade, on the full ~100-stock universe, so it
fires **~16×/month** (vs the index's ~3). Shown in its own **STOCK CREDIT SPREADS** section.

- **Signal:** a daily **Donchian-10 breakout** on any F&O stock → **FADE** it (sell a credit spread).
- **The gate that makes it work:** only trade when **credit ≥ 40% of the strike width** *and* short
  premium ≥ ₹50, *and* it passes a **live liquidity gate** (OI, bid-ask). A breakout spikes IV → rich
  premium; fading sells the inflated premium and rides the reversion + IV crush. (A *generic* stock
  credit spread loses −4.7% — the gate is the edge.)
- **Construct:** short 1-OTM, long 3 strikes wide, nearest monthly ≥10 DTE, hold to expiry, 2× stop.
- **Caps:** ≤5 new/day, ≤20 open at once (breakouts cluster — avoid a one-day pile-on).

**Backtest (full universe, ~19 mo, real expired-option premiums, credit/width≥0.40 + prem≥₹50):**

| | Trades | Win % | Net/trade | Holdout p5 | Breadth |
|---|--------|-------|-----------|-----------|---------|
| Stock fade, gated | 307 (~16/mo) | 65% | +16% (5% slip) / +25% (3%) | +6.8% | 76/100 |

Survives a 7%/leg slippage floor; concentrated in mid-caps. Config: `STOCK_CREDIT_*` in
`engine/config.py`; logic in `engine/stock_credit.py`; book in `data/stock_credit_positions.json`.

> **Honest note:** the ~+20%/month-on-margin backtest is **optimistic** — no persistent edge pays
> that; it will shrink live. The unmodelled risk is real mid-cap 4-leg fills + gap risk on ~16
> concurrent shorts. It runs as a **FORWARD-TEST at 1 lot** to find the real number. **Do not fill
> your margin** — ~16 correlated mid-cap shorts hit together on a bad day. Full record:
> [`studies/STOCK_OPTIONS_NO_EDGE.md`](studies/STOCK_OPTIONS_NO_EDGE.md) (Part 8).

---

## Risk, Breakeven & Go-Live Bar

- No per-day trade cap — every qualifying signal is taken · halt after 3 stop-outs · never overnight.
- **Daily EOD booking:** every open paper trade is force-closed WIN/LOSS at the **15:30 close** (Mon–Fri), unless its +target/−stop hit earlier. Runs off the 1-sec clock, so it always fires (`paper_resolver` + `ui._maybe_eod_book`).
- **Breakeven:** with +10% target / −15% stop you risk 15% to make 10%, so the
  breakeven win rate is `15 / (10+15) = 60%`. The current min-premium config realises ~64% on
  the real-option backtest — **above breakeven**, which is the point of the 2026-06 change.
- **Go-live bar:** win rate **≥ 70%** AND profit factor > 1 across 30+ signals —
  a margin above breakeven, NOT the generic 52% you see elsewhere.

---

## Refresh Cadence & Latency

The **engine** does the work and writes to disk; the read-only **viewer** re-reads disk
every 15 s. Engine cadence and data freshness:

| Component | Recompute cadence (engine) | Data freshness |
|-----------|-------------------|----------------|
| **Full scan** (3 families, 100 stocks + 2 indices) | **every 5 min** (engine wakes every 5 s) | — |
| **TREND** | every 5 min | live 5-min candles · daily EMA cached per day |
| **FLOW** | every 5 min | option chain cached **~10 min** (`options_flow._TTL`) → OI/PCR ≤10 min old |
| **EVENT** | score read every 5 min | NSE scrape at **startup + ~every 20 min, 9 AM–1 PM** → sentiment ≤1 hour old |
| **ORB+VWAP index** | every 5 min | futures intraday (live, 5-min bars) |
| **Market snapshot** (NIFTY/BANKNIFTY/VIX) | **every ~5 sec** (engine writes `market_snapshot.json`) | live LTP → 5-min candle → prev close |
| Viewer display | re-reads disk every **15 s** | shows whatever the engine last wrote |

**Scan latency** (measured, full universe, 16 parallel workers):

| Step | Time |
|------|------|
| Score 3 families + all 6 gates (per stock, CPU) | ~1.6 ms |
| One stock's full scan incl. all fetches | ~1.1 sec (cold) / ~0.17 sec (warm) |
| **Full 100-stock scan — cold cache** | **~2.7 sec** (16 workers, pooled keep-alive) |
| **Full 100-stock scan — warm cache** | **~0.6 sec** |
| Sequential (no parallelism) | ~43 sec |

**Bottom line:** signal granularity = the **5-min candle**; the engine surfaces a new signal
within seconds of the 5-min mark; the viewer shows it within ≤15 s. Options flow is ≤10 min
old; events ≤1 hour old.

---

## Signal Notifications (optional, free-first)

Every trade-ready signal can alert you on multiple channels (`engine/notifications.py`).
Each fires only if its keys are set in `.env`:

- **Telegram** — free, reliable (Bot API).
- **WhatsApp** — free (CallMeBot).
- **Phone call** — CallMeBot free TTS (best-effort) or Twilio (paid, reliable).
- *(WhatsApp voice calls are not possible — no third-party API.)*

Run `python -m engine.notifications` for the one-time setup steps.

---

## Paper Trading

The dashboard keeps **LIVE paper trades** and the **30-day historical simulation**
strictly separate (a toggle in the TRADE LOG tab). Run it forward for 30+ sessions and
judge the live log against the go-live bar. **Honest status (current 6-gate config):**
60-day backtest **61% win, +₹36,792 (+2.8% on capital, GROSS)**; 365-day directional edge
**~52%**. Net of brokerage + STT + spread it is roughly **breakeven** — a thin, real-but-small
edge, **not proven profitable**. Only forward, costed data settles it. See the **Studies** table.

---

## Studies / Research Log

Every change was backtested before going live (or deliberately **not** deployed). All P&L
is **gross of costs**; option backtests use ~1 month of real premium history, so treat
short-window rupee figures as directional. The in-app **STUDIES** tab shows the same list.

| # | Study | Question | Headline result | Status |
|---|-------|----------|-----------------|--------|
| ★ | [**Strategy Summary (start here)**](studies/STRATEGY_SUMMARY.md) | Where does every strategy stand on real data? | **One table: gated stock fade VALIDATED; index fades regime-dep/illiquid; BUY strategies real-but-tiny direction edge, not net.** | canonical |
| ★ | [**Stock fade v2 — TP-50 upgrade**](studies/STOCK_FADE_TP50_UPGRADE.md) | Can the fade win >65% EVERY year? | **85% win / +24.5% width in-sample (2019–24) · 88% / +31.9% OOS (Oct24→Jul26) · ≥79% win all 8 yrs · ~4–6 tr/mo** | **DEPLOYED (parallel book, 1 lot)** |
| ★ | [**Real-Option Optimization**](studies/REAL_OPTION_OPTIMIZATION.md) | What's the edge on REAL option P&L (Upstox Plus)? | **STOCK 180d +1.5% did NOT hold 1yr (−1.0%, overfit). INDEX trend-ride +0.9% over 18mo holds.** | honest |
| 1 | [Win-Rate Research Log](studies/WIN_RATE_RESEARCH_LOG.md) | How high can win rate go? | A ~52–57% out-of-sample wall; edge must come from filtering | baseline |
| 2 | [Gate 3 — Market Alignment](studies/FINAL_STRATEGY_TESTING_60DAY.md) | Does not fighting the Nifty help? | 60d: ~59% win, P&L +₹17k → +₹31k (~2×) | **LIVE** |
| 3 | [Gate 4 — Don't Chase](studies/GATE4_DONT_CHASE.md) | Do over-extended entries lose edge? | 60d: win 59→61%, RoC +1.7→+2.8%, fewer trades | **LIVE** |
| 4 | [Gate 5 — Wide Open](studies/GATE5_WIDE_OPEN.md) | Can a 5th gate raise win rate at the same +10/−20? | 365d win 51→54%; option 30d 61→66%, 60d 66→70% | **LIVE** |
| 5 | [Index Trend-Ride Exit](studies/INDEX_TREND_RIDE_EXIT.md) | Why did the index lose daily? | Fixed +20% cap → trend-ride: win 27→63% | **LIVE** |
| 6 | [365-Day Directional Validation](studies/UNDERLYING_VALIDATION_365D.md) | Does the edge last a year? | Aligned 52% hit, +0.13%/trade, holds 12 months | validated |
| ★ | [**BUY strategies 2019→date (real Kite 5-min)**](studies/BUY_STRATEGIES_2019_REALTEST.md) | Do the intraday BUY edges hold across ALL regimes? | **3-Family full-gate: 50.6% hit, +0.107%/tr, +ve EVERY year (dir real, but −1.0% net as options). ORB+VWAP: +0.04%/tr, −ve ~2/8 yrs.** | honest |
| 7 | [Stock Option Exit Cap](studies/STOCK_OPTION_EXIT_CAP.md) | Remove the +10% cap? | Inconsistent / high variance — kept +10% | not deployed |
| 8 | [Prophet Forward-Test](studies/PROPHET_FORWARD_TEST.md) | Can forecasting predict it? | 20d direction worse than a coin flip | not deployed |
| 9 | [Data Availability Limits](studies/DATA_AVAILABILITY_LIMITS.md) | Can we backtest 180/365d on options? | Option premiums only ~1 month back | reference |

**Bottom line:** a ~54–70% win, thin-but-real edge (option windows small; 365-day directional
~54%). Gates 3, 4 & 5 are the proven wins; the index trend-ride stops a bleed; the exit-cap and
forecasting ideas were tested and correctly not deployed. Real profitability is unproven until
the forward paper month logs real fills.

---

## Files

```
engine/
  config.py            all strategy parameters
  instruments.py       symbol -> Upstox ISIN key resolver (cached)
  data_fetcher.py      Upstox V3 (LTP, 5-min, daily, indices) + batched LTP + cache
  data_utils.py        index closes (live/last, day change)
  events.py            NSE announcement scraper + keyword scoring (EVENT family)
  signals.py           3-family scoring + alpha-z + ORB gate
  orb_vwap_live.py     PARALLEL ORB+VWAP index strategy (ATM, trend-ride exit, PM DECISIONS)
  swing_credit.py      PARALLEL swing credit-spread (index · multi-day · fade breakout · regime-dep, forward-test)
  stock_credit.py      PARALLEL stock credit-spread (4th · high-frequency fade · gated credit/width)
  options.py           ATM/offset strike resolver + live option order builder
  portfolio.py         instrument decision + sizing
  trade_log.py         paper log: win rate, PF, expectancy, go-live check
  signal_db.py         SQLite DB of every PM signal (Gate-2 stocks + ORB+VWAP index), accrues daily
  notifications.py     Telegram / WhatsApp / phone-call alerts
  agent.py             5-min scan orchestrator (parallel) + hourly event refresh
  engine_runner.py     HEADLESS ENGINE daemon — runs the schedule, writes all data
  store.py             data/engine.db — daily scan rows + market snapshots
  ui_terminal.py       READ-ONLY desktop viewer (default)
  api_diagnostics.py / signal_frequency.py / backtest120.py / option_live_backtest.py
main.py                viewer launcher
deploy/                launchd plists (engine + viewer)
setup.sh / .env.example         one-shot install from a fresh clone
CLAUDE.md                       project context + setup for Claude Code
studies/                        CURRENT research log (8 studies) + reproducible scripts
How_We_Built_The_Strategy.pdf / BACKTEST_RESULTS.md   historical build journey (superseded by studies/)
data/engine.db                  SQLite: every scan (gate state) + market snapshot, daily
data/signals.db                 SQLite log of all PM signals (gitignored)
data/trade_log.json             paper-trade outcomes (gitignored)
.env                            Upstox token + notification keys (DO NOT COMMIT)
```

---

*For educational use only. Not financial advice. Markets carry risk of loss.*
