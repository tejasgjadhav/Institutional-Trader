# Institutional Trader — 3-Family Alpha · NSE Intraday Options

A disciplined **paper-trading** system for NSE intraday. It scans NIFTY, BANKNIFTY
and 94 liquid stocks every 5 minutes, scores each with a 3-family model, and only
flags a trade when it clears two strict gates. Every trade is a **bought option**
(CALL/PUT) and you place the order yourself in Upstox — the software never sends
orders. It is a process for collecting honest evidence, not a proven money-maker.

> Full plain-language walkthrough is also on the **README tab** inside the dashboard.
> The complete research story (with the mistakes) is in **`How_We_Built_The_Strategy.pdf`**
> and the numbers are in **`BACKTEST_RESULTS.md`**.

---

## Quick Start

```bash
cd ~/files/institutional-trader

# Desktop dashboard (default)
.venv/bin/python main.py

# CLI single scan / continuous / stats
.venv/bin/python main.py --cli
.venv/bin/python main.py --loop
.venv/bin/python main.py --status

# Health & tools
.venv/bin/python -c "from engine.api_diagnostics import diagnose; diagnose()"
.venv/bin/python -m engine.events          # refresh NSE event scores now
.venv/bin/python -m engine.notifications   # show alert channels + send test
```

Auto-start weekdays (Mac wakes 8:55, app launches 9:00):
```bash
launchctl load ~/Library/LaunchAgents/com.sayali.institutionaltrader.plist
```

---

## What It Does (in one breath)

Two strategies run in parallel, both reported on **PM DECISIONS**, both options-only,
both manual-execution:

- **3-Family system (94 stocks):** every 5 min it (1) pulls fresh **Upstox** prices,
  (2) scores each stock into one number, **alpha-z**, (3) checks the score is strong
  and broad enough (**Gate 1**), breaking out *now* (**Gate 2**), aligned with the Nifty
  (**Gate 3**), and not already over-extended (**Gate 4**). All gates pass → a
  **buy-option order** (OTM+1, +10%/−20%) appears for you to place.
- **ORB+VWAP system (NIFTY & BANKNIFTY):** a separate index strategy — 15-min ORB +
  VWAP + 30-min trend + clean-trend filter, buy **ATM**, **trend-ride exit** (VWAP-reclaim
  after +12%, hard −20% stop) — see the section below.

The 3-Family system scans **stocks only**; the indices are handled exclusively by the
ORB+VWAP strategy.

---

## The Daily Clock (IST)

| Time | What happens |
|------|--------------|
| 08:55 | Mac wakes itself (pmset) |
| 09:00 | App auto-launches (launchd) |
| 09:00 | First NSE **event scrape** (then refreshed ~every 20 min to 1 PM) |
| **09:15** | Market opens — scanning begins, ALPHA fills |
| 09:15–09:45 | Wildest part of the day — watch only |
| **09:45** | Trading window opens |
| every 5 min | Re-scan NIFTY + BANKNIFTY + 94 stocks (~0.6–2.7 sec) |
| **13:00** | No new trades after 1 PM |
| **15:10** | Kill switch — exit guideline (don't hold into the last 20 min) |
| **15:30** | Market closes — **every OPEN paper trade is force-booked WIN/LOSS at the close** (Mon–Fri) |

In practice nothing fires before ~11:30 AM (scores need an hour of data); signals
cluster **12:30–1 PM**.

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
15-min opening-range breakout. Combined by the factor weights above.

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
`MAX_ENTRY_EXTENSION_PCT` (2.6%) in the trade's direction from the day's open — buying an
already-extended stock loses edge. *365-day underlying validation: over-extended entries
won ~45% vs ~55% for the 1.5–2.6% sweet spot; held-out per-trade edge +0.13% → +0.16%.
Option-level 60-day: same profit on 26% fewer trades → return-on-capital +1.7% → +2.5%,
win 59% → 60%. (30-day too small to show the effect.)* (`ENTRY_EXTENSION_FILTER`)

---

## Instrument & Exit — Buy Options Only

Every signal becomes a **bought option** (never sold):

- **LONG → buy CALL · SHORT → buy PUT**
- **Strike: OTM+1** (one strike out-of-the-money — best risk-adjusted in testing)
- **Nearest expiry** (Nifty weekly, BankNifty/stocks monthly)
- **Exit on the option premium:** **+10% target / −20% stop**

You exit on the option's own price, not the stock — leverage means a small underlying
move swings the premium 10%+.

---

## Parallel Strategy — ORB+VWAP Index (forward-test)

A second, independent strategy runs **alongside** the 3-Family system on **NIFTY &
BANKNIFTY index options only**, shown in its own section on **PM DECISIONS**:

- **Signal:** 15-min Opening-Range Breakout + hold VWAP + aligned with the 30-min trend
- **Clean-trend filter:** only enter when VWAP is sloped the trade's way **and** price is
  already >0.25% extended from the day's open (cuts the marginal, chop-prone breaks)
- **Filters:** entries before 11:00 AM · skip 0-DTE expiry-day spikes · one signal/index/day
- **Instrument:** buy **ATM** CALL/PUT (LONG→CALL, SHORT→PUT)
- **Exit — trend-ride (NEW):** let the winner **run**; exit only when the futures **reclaim
  VWAP** *after* the trade is already +12% in profit; **hard −20% premium stop** throughout;
  otherwise square off at the close. (Replaced the old fixed +20% target.)
- **Live status:** WATCHING → ● RIDING → EXITED VWAP / STOPPED −20%

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
> study: [`studies/WIN_RATE_RESEARCH_LOG.md`](studies/WIN_RATE_RESEARCH_LOG.md).

---

## Risk, Breakeven & Go-Live Bar

- No per-day trade cap — every qualifying signal is taken · halt after 3 stop-outs · never overnight.
- **Daily EOD booking:** every open paper trade is force-closed WIN/LOSS at the **15:30 close** (Mon–Fri), unless its +target/−stop hit earlier. Runs off the 1-sec clock, so it always fires (`paper_resolver` + `ui._maybe_eod_book`).
- **Breakeven:** with +10% target / −20% stop you risk 20% to make 10%, so the
  breakeven win rate is `20 / (10+20) = ~67%`. **Below that you lose money.**
- **Go-live bar:** win rate **≥ 70%** AND profit factor > 1 across 30+ signals —
  a margin above breakeven, NOT the generic 52% you see elsewhere.

---

## Refresh Cadence & Latency

How often each piece updates and how fresh the data is:

| Component | Recompute cadence | Data freshness |
|-----------|-------------------|----------------|
| **Full scan** (3 families, 94 stocks + 2 indices) | **every 5 min** (`scan_timer`) | — |
| **TREND** | every 5 min | live 5-min candles · daily EMA cached per day |
| **FLOW** | every 5 min | option chain cached **~10 min** (`options_flow._TTL`) → OI/PCR ≤10 min old |
| **EVENT** | score read every 5 min | NSE scrape at **startup + ~every 20 min, 9 AM–1 PM** → sentiment ≤1 hour old |
| **ORB+VWAP index** | every 5 min | futures intraday (live, 5-min bars) |
| **Market header** (NIFTY/BANKNIFTY/VIX) | **every 3 sec** (`mkt_timer`) | live LTP → 5-min candle → prev close |
| Clock / status | every 1 sec | — |

**System update latency** (measured, full universe, 12 parallel workers):

| Step | Time |
|------|------|
| Score 3 families + both gates (per stock, CPU) | ~1.6 ms |
| One stock's full scan incl. all fetches | ~1.1 sec (cold) / ~0.17 sec (warm) |
| **Full 94-stock scan — cold cache** | **~2.7 sec** (16 workers, pooled keep-alive) |
| **Full 94-stock scan — warm cache** | **~0.6 sec** |
| Sequential (no parallelism) | ~43 sec |

**Bottom line:** signal granularity = the **5-min candle**; a new signal surfaces within **≤5 min**
of forming, and the scan compute itself is **0.6–2.7 sec**. Header is near-real-time (3 sec). Options
flow is ≤10 min old; events ≤1 hour old.

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
judge the live log against the go-live bar. Honest status: backtests show ~72% on tiny
samples (13–34 trades) — **no proven edge yet**; only forward, costed data settles it.

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
  options.py           ATM/offset strike resolver + live option order builder
  portfolio.py         instrument decision + sizing
  trade_log.py         paper log: win rate, PF, expectancy, go-live check
  signal_db.py         SQLite DB of every PM signal (Gate-2 stocks + ORB+VWAP index), accrues daily
  notifications.py     Telegram / WhatsApp / phone-call alerts
  agent.py             5-min scan orchestrator (parallel) + hourly event refresh
  ui_terminal.py       dark dashboard (default)
  api_diagnostics.py / signal_frequency.py / backtest120.py / option_live_backtest.py
main.py                launcher
How_We_Built_The_Strategy.pdf   teaching casebook (with the mistakes)
BACKTEST_RESULTS.md             every backtest run, honestly documented
studies/                        win-rate research log + reproducible study scripts
data/signals.db                 SQLite log of all PM signals (gitignored; `python -m engine.signal_db`)
.env                            Upstox token + notification keys (DO NOT COMMIT)
```

---

*For educational use only. Not financial advice. Markets carry risk of loss.*
