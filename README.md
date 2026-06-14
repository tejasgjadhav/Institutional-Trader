# Institutional Trader — 3-Family Alpha · NSE Intraday

A disciplined **paper-trading** framework. It watches 95 NSE stocks all day, scores
each one, and only flags a trade when a stock clears two strict gates. **You place
every order yourself in Upstox** — the system never sends orders. It is a process for
collecting honest evidence, not a proven money-maker.

> The same content is available in-app on the **README** tab of the dashboard.

---

## Quick Start

```bash
cd /Users/sayali/files/institutional-trader

# Desktop terminal (default)
.venv/bin/python main.py

# CLI single scan / continuous / stats
.venv/bin/python main.py --cli
.venv/bin/python main.py --loop
.venv/bin/python main.py --status

# API health check
.venv/bin/python -c "from engine.api_diagnostics import diagnose; diagnose()"
```

Auto-start weekdays at 09:00:
```bash
launchctl load ~/Library/LaunchAgents/com.sayali.institutionaltrader.plist
```

---

## 1 · What It Does (in one breath)

Every 5 minutes during market hours it:
1. pulls fresh prices from **Upstox**,
2. gives each stock a single score called **alpha-z**,
3. checks if the score is strong and broad enough (**Gate 1**),
4. checks if the price is actually breaking out right now (**Gate 2**).

If both gates pass, the stock appears on **PM DECISIONS** with exact entry, stop,
target and quantity. You place that order manually in Upstox.

---

## 2 · The Daily Clock (all times IST)

| Time | What happens |
|------|--------------|
| 08:55 | Mac wakes up automatically |
| 09:00 | App auto-launches |
| **09:15** | Market opens — scanning begins, ALPHA + WATCHLIST fill up |
| 09:15–09:45 | First 30 min is the wildest part — we only watch, no trades |
| **09:45** | Trading window opens — confirmed signals become PM DECISIONS |
| every 5 min | Re-scan all 95 stocks; at most one new trade per scan |
| **15:00** | No new trades after this (afternoon is thin) |
| **15:10** | Kill switch — every open position is force-closed |
| 15:30 | Market closes — trade log shows the day's wins/losses |
| 15:35 | Re-rank the tradeable universe on the latest 60-day history |

---

## 3 · Data Sources & API Schedule

### Upstox V3 — primary feed (low latency)
- **Live LTP** — checked continuously to watch stops & targets
- **5-min candles** — heartbeat of the scan: breakout + volume checks every 5 min
- **Daily history** — ~400 days for trend/momentum maths and the 60-day backtest
- **Indices** — Nifty 50, Bank Nifty, India VIX, fetched every 5 sec for the top bar & regime

Instrument keys are **ISIN-based** (e.g. `NSE_EQ|INE467B01029`). The system
auto-downloads Upstox's instrument master and caches it for 7 days, so symbols map
to keys automatically (`engine/instruments.py`).

### NSE public API — options & events
PCR, max-pain, corporate filings — used by the FLOW and EVENT families.
*(Options-chain integration is the next planned addition.)*

### Yahoo Finance — emergency fallback only
Only used if the Upstox token is missing/expired. Slower, so never the primary path.

---

## 4 · The 3 Families

Seven small checks grouped into 3 independent **families**. Each votes LONG, SHORT, or
NEUTRAL. Grouping avoids fake breadth — momentum, trend and the volume-break all move
together, so they count as one idea.

| Family | Weight | Asks |
|--------|--------|------|
| **TREND** | 0.65 | Is it moving strongly? momentum + trend quality + opening-range microstructure |
| **FLOW** | 0.17 | What are big players doing? options positioning (PCR/max-pain) + regime (Nifty, VIX) |
| **EVENT** | 0.18 | Any news driving it? headlines + live NSE filings *(experimental)* |

A 4th family (mean-reversion) was removed — it won only 47.6% in backtests.

---

## 5 · The Alpha-Z Calculation

Each family produces a **z-score**: how unusual the reading is.
`0 = average · +1 = bullish · −1 = bearish · ±2 = extreme`

Blend into one number, the **alpha-z**, as a weighted average:

```
alpha-z = Σ(family z × family weight) ÷ Σ(weights)
```

**Worked example (bearish stock):**
```
TREND z=−0.9 (w 0.65) · FLOW z=−0.6 (w 0.17) · EVENT z=+0.2 (w 0.18)
top    = (−0.9×0.65) + (−0.6×0.17) + (0.2×0.18) = −0.651
bottom = 0.65 + 0.17 + 0.18 = 1.00
alpha-z = −0.65   → bearish, above 0.55 bar, 2/3 agree SHORT → PASSES Gate 1
```
Sign = direction, size = conviction.

---

## 6 · The Two Gates

**Gate 1 — Alpha Gate**
- `|alpha-z|` strictly greater than **0.55**
- at least **2 of 3** families agree on direction
- stock is in the proven universe (top **10** by expectancy)

→ puts the stock on the **WATCHLIST**, awaiting ORB breakout.

**Gate 2 — ORB Breakout + Volume**
- latest 5-min candle closes beyond the opening-range (above high = LONG, below low = SHORT)
- with a volume surge

Two independent methods must agree before money is risked. Both gates pass → **PM DECISIONS**.

---

## 7 · Position-Sizing Calculations

Fixed risk **₹2,000/trade** · Reward:Risk **2:1** · stop capped at **1%** so the
target stays reachable intraday.

```
Stop       = Entry − 1% of Entry
Risk/share = Entry − Stop
Quantity   = ₹2,000 ÷ Risk/share        (rounded down, min 1)
Target     = Entry + 2 × Risk/share
```

**Example at Entry = ₹1,000:** Stop 990 · Risk/share 10 · Qty 200 · Target 1,020.

---

## 8 · Which Instrument?

| Conviction \|alpha-z\| | LONG | SHORT |
|---|---|---|
| 0.55–0.70 | Cash Equity | Future |
| above 0.70 | CALL option | PUT option |

Strike = at-the-money from the live NSE chain. If option IV > 40 (too expensive),
falls back to Futures.

---

## 9 · Risk Controls

- Max **3** trades/day
- **3** stop-outs in a row → halt for the day
- Every position force-closed at **15:10** — never hold overnight
- Position size derived from the stop distance, not guesswork

---

## 10 · Paper Trading & Go-Live Rule

For the first month the system records every signal to its outcome (WIN at target,
LOSS at stop, FORCED at 3:10 PM). The TRADE LOG is your honest scorecard.

**Go-live bar:** win rate ≥ **52%** AND profit factor > **1** across **30+** signals.
Below that, the edge isn't proven — don't automate.

> Honest note: factor hit-rates are barely above a coin-flip; after brokerage + taxes
> the edge is thin. Treat every signal as a hypothesis and judge it by the log over
> many sessions.

---

## Files

```
engine/
  config.py            all strategy parameters (edit here)
  instruments.py       symbol → Upstox ISIN key resolver (auto-cached)
  data_fetcher.py      Upstox V3 (LTP, 5-min, daily, indices) + Yahoo fallback
  data_utils.py        index closes + API health
  signals.py           3-family scoring + alpha-z + ORB
  portfolio.py         position sizing, risk
  trade_log.py         paper log, win rate, PF, expectancy
  agent.py             orchestrator (5-min scan)
  ui_terminal.py       dark terminal dashboard (default)
  api_diagnostics.py   data-source health checks
main.py                launcher
.env                   Upstox Analytics Token (DO NOT COMMIT)
data/                  trade_log.json, instrument cache
logs/                  app.log
```

---

*For educational use only. Not financial advice.*
