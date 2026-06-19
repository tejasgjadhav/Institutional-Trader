# Final Strategy Testing — 60 Day

The live 3-Family stock strategy with the **market-alignment gate (Gate 3)** added,
backtested over 30 and 60 days. This is the configuration now running in production.

> **Headline (60-day, gross of costs):** with the market-alignment filter the strategy
> wins **59%** of trades and returns **+₹30,911 (+1.7% on deployed capital)** — vs
> **+₹17,299 (+0.7%)** without the filter. Same win rate, **nearly double the P&L**,
> fewer trades — because the filter removes the trend-fighting trades that lose *bigger*.

---

## The strategy tested

3-Family Alpha on the 94-stock universe, buy-only options, with **three gates**:

1. **Alpha** — `|alpha-z| > 0.55` AND ≥ 2 of 3 families (TREND / FLOW / EVENT) agree.
2. **ORB confirmation** — latest 5-min candle breaks the opening range with a volume surge,
   same direction.
3. **Market alignment (NEW)** — the trade must agree with the Nifty's intraday direction:
   only **LONG when Nifty is up**, only **SHORT when Nifty is down**. (`MARKET_ALIGN_FILTER`)

- **Instrument:** buy OTM+1 CALL (LONG) / PUT (SHORT), nearest expiry.
- **Exit:** **+10% target / −20% stop** on the option premium (the live config).
- **Sizing for this test:** 1 lot per signal, one signal per stock per day, 09:45–13:00 window.

---

## Results

Live exit (+10% / −20%), 1 lot each, **GROSS of brokerage / STT / spread.**

### 30-day (May 27 – Jun 15)
| Set | Trades | Win % | Net/trade | P&L | Return on capital |
|-----|--------|-------|-----------|-----|-------------------|
| ALL signals (no filter) | 74 | 58% | −0.26% | +₹15,688 | +1.0% |
| **ALIGNED only (Gate 3)** | **57** | **60%** | **+0.48%** | **+₹18,903** | **+1.6%** |
| *blocked (not-aligned)* | 17 | 53% | −2.75% | −₹3,215 | −1.0% |

### 60-day
| Set | Trades | Win % | Net/trade | P&L | Return on capital |
|-----|--------|-------|-----------|-----|-------------------|
| ALL signals (no filter) | 109 | 59% | −0.01% | +₹17,299 | +0.7% |
| **ALIGNED only (Gate 3)** | **83** | **59%** | **+0.58%** | **+₹30,911** | **+1.7%** |
| *blocked (not-aligned)* | 26 | 58% | −1.91% | −₹13,611 | −2.4% |

---

## What the numbers say

1. **The filter's value is risk, not hit-rate.** Win rate barely moves (58→60% at 30d,
   flat ~59% at 60d). The gain is in *magnitude*: aligned trades net **+0.58%/trade** while
   the blocked trades net **−1.91%/trade**. Trades that fight the tape, when wrong, get run
   over (they hit the −20% stop). Removing them is most of the P&L improvement.
2. **P&L roughly doubles over 60 days** (+₹17,299 → +₹30,911) by cutting the 26 not-aligned
   trades that lost −₹13,611 together.
3. **Consistent across both windows** — the not-aligned subset is the loser in both
   (−1.0% at 30d, −2.4% at 60d).

This is the live-trade version of the June-18 losers analysis: PFC and MARUTI both shorted
into a *rising* Nifty and got run over. Gate 3 blocks exactly that pattern.

---

## Honest caveats

- **All figures are GROSS of costs.** ~83 trades × ~₹40–80 (brokerage + STT) ≈ ₹3,300–6,600;
  net 60-day ≈ **+₹24,000–27,000**. Bid-ask spread on stock options is the remaining
  unmodelled cost — only forward paper-trading settles it.
- **59% win is still below the 67% breakeven** that +10/−20 theoretically needs. The result
  is net-positive only because the capital-weighted winners outweigh the −20% stops — a
  margin that costs and spread can erode.
- **Sample is modest** — ~40–60 trading days with usable option-premium history (Upstox
  caps how far back option candles go). Treat the % as directional, not a promised return.
- **Equal-weighted per-trade vs capital-weighted rupee differ** — the rupee P&L (what you
  actually make at 1 lot) is positive; the equal-weighted per-trade average is near flat for
  the unfiltered set. The filter makes both clearly positive.

---

## Verdict

The market-alignment gate is the one signal change with clear, repeated, out-of-sample
evidence: **same win rate, ~2× the P&L, fewer trades.** It is now live (`MARKET_ALIGN_FILTER
= True`). The honest framing remains: this is a **~59% directional, modestly-profitable-gross**
strategy whose real edge is *cutting the trend-fighting losers* — not a high win rate. The
paper-trading month with real costs is still the final judge.

**Reproduce:** `.venv/bin/python studies/align_bt.py` (edit `collect(60)` → `collect(30)`
for the shorter window). Requires a valid `UPSTOX_ANALYTICS_TOKEN` in `.env`.

*Generated 2026-06-19. All P&L gross of bid-ask spread.*
