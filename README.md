# Institutional Trader — 3-Family Alpha · NSE Intraday Options

A disciplined **paper-trading** system for NSE intraday. It scans NIFTY, BANKNIFTY
and 95 liquid stocks every 5 minutes, scores each with a 3-family model, and only
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

- **3-Family system (95 stocks):** every 5 min it (1) pulls fresh **Upstox** prices,
  (2) scores each stock into one number, **alpha-z**, (3) checks the score is strong
  and broad enough (**Gate 1**), (4) checks the price is breaking out *now* (**Gate 2**).
  Both gates pass → a **buy-option order** (OTM+1, +10%/−20%) appears for you to place.
- **ORB+VWAP system (NIFTY & BANKNIFTY):** a separate index strategy — 15-min ORB +
  VWAP + 30-min trend, buy **ATM**, **+20%/−20%** (see the section below).

The 3-Family system scans **stocks only**; the indices are handled exclusively by the
ORB+VWAP strategy.

---

## The Daily Clock (IST)

| Time | What happens |
|------|--------------|
| 08:55 | Mac wakes itself (pmset) |
| 09:00 | App auto-launches (launchd) |
| 09:00 | First NSE **event scrape** (then refreshed hourly to 1 PM) |
| **09:15** | Market opens — scanning begins, ALPHA fills |
| 09:15–09:45 | Wildest part of the day — watch only |
| **09:45** | Trading window opens |
| every 5 min | Re-scan NIFTY + BANKNIFTY + 95 stocks (~3–4 sec) |
| **13:00** | No new trades after 1 PM |
| **15:10** | Kill switch — force-close everything |
| 15:30 | Market closes |

In practice nothing fires before ~11:30 AM (scores need an hour of data); signals
cluster **12:30–1 PM**.

---

## Data Sources

- **Upstox V3 (primary, low latency)** — live LTP, 5-min candles, daily history, and
  index data (NIFTY / BANKNIFTY / VIX). ISIN-based instrument keys, auto-resolved
  from Upstox's instrument master (cached weekly).
- **NSE corporate-announcements (live scraper)** — feeds the EVENT family; scraped at
  ~9 AM and refreshed hourly to 1 PM (`engine/events.py`).
- **Yahoo Finance** — emergency fallback only (slower; never primary).

---

## The 3 Families (all live)

Three independent families; each votes LONG / SHORT / NEUTRAL, then blends into alpha-z
by weight: `alpha-z = Σ(family z × weight) ÷ Σ(weights)`.

| Family | Weight | What it measures |
|--------|--------|------------------|
| **TREND** | 0.72 | Three factors z-scored vs own history: **momentum** (60-min return, 0.37), **trend quality** (daily EMA-9 vs EMA-21 spread, 0.24), **microstructure** (15-min ORB breakout ±1, 0.04) |
| **FLOW** | 0.18 | **Live per-stock options flow** from the option chain (cached ~10 min): **OI-buildup imbalance** (writers adding puts vs calls) + **PCR trend** (put/call OI ratio rising/falling). Puts→support→bullish(+), calls→resistance→bearish(−). Symmetric, change-based |
| **EVENT** | 0.10 | **Live** NSE announcements scraped at startup + hourly 9 AM–1 PM, keyword-scored: orders/results/bonus = +1, fraud/penalty/downgrade = −1, routine = 0. Down-weighted (crude scoring) |

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
Scrapes NSE corporate announcements (startup, then hourly 9 AM–1 PM), keyword-scores each
to [−1, +1], and the EVENT z = the stock's sentiment. A neutral filing stays 0 (it does
not bias the vote). Deliberately the lowest weight — informative, not decisive.

Each family yields a **z-score**; the weighted average is the **alpha-z** (sign =
direction, size = conviction).

---

## The Two Gates

**Gate 1 — Alpha:** `|alpha-z| > 0.55` AND ≥ 2 of 3 families agree.
**Gate 2 — Confirmation:** the latest 5-min candle breaks the opening range with a
volume surge, same direction. Two independent methods must agree.

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
- **Filters:** entries before 11:00 AM · skip 0-DTE expiry-day spikes · one signal/index/day
- **Instrument:** buy **ATM** CALL/PUT (LONG→CALL, SHORT→PUT)
- **Exit:** **+20% / −20%** on the option premium
- **Live status:** WATCHING → ACTIVE → TARGET +20% / STOPPED −20%

**Options-only execution.** VWAP needs volume and the spot index reports none on Upstox,
so the VWAP line is computed from the index **futures** feed — but nothing except options
is ever traded. Config: `ORB_VWAP_*` in `engine/config.py`; logic in `engine/orb_vwap_live.py`.

> **Honest note:** Apr–Jun 2026 backtests show this is roughly breakeven (NIFTY −0.5%,
> BANKNIFTY +0.3%). It runs live to **forward-test** it, not because it is proven. Full
> study: [`studies/WIN_RATE_RESEARCH_LOG.md`](studies/WIN_RATE_RESEARCH_LOG.md).

---

## Risk, Breakeven & Go-Live Bar

- Max 3 trades/day · halt after 3 stop-outs · force-close 15:10 · never overnight.
- **Breakeven:** with +10% target / −20% stop you risk 20% to make 10%, so the
  breakeven win rate is `20 / (10+20) = ~67%`. **Below that you lose money.**
- **Go-live bar:** win rate **≥ 70%** AND profit factor > 1 across 30+ signals —
  a margin above breakeven, NOT the generic 52% you see elsewhere.

---

## Performance

The strategy logic is essentially instant; the cost is the network.

| Step | Time |
|------|------|
| Score 3 families + both gates + instrument (per stock) | **~1.6 ms** (CPU) |
| Fetch one stock's 5-min candles | ~440 ms (network) |
| **Full 95-stock scan** | **~3–4 sec** (12 threads + daily cache + batched prices) |
| Sequential (no optimisation) | ~43 sec |

A 3–4 sec scan inside a 5-minute window means a signal is seen almost the instant a
candle closes — prices barely drift.

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
  orb_vwap_live.py     PARALLEL ORB+VWAP index strategy (ATM, +20/-20, PM DECISIONS)
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
