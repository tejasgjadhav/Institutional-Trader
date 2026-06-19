# Index ORB+VWAP — Trend-Ride Exit (the fix for the daily index losses)

The live NIFTY/BANKNIFTY ORB+VWAP strategy was losing nearly every day. Root cause
found and fixed; this is the evidence. **Only the index strategy changed — the 3-Family
stock system is untouched.**

## The problem

ORB+VWAP is a **trend-following** setup, but it exited on a **fixed +20% premium target /
−20% stop**. A fixed target *caps winners* while you still take *full −20% stops* — exactly
backwards for a trend strategy. Live, this showed up as **big losers, tiny winners**: two
BANKNIFTY −20% stop-outs (≈ −₹3,000 each) wiped out every small gain.

## The fix

- **Trend-ride exit:** let the winner run; exit only when the futures **reclaim VWAP**
  *after* the trade is already **+12%** in profit (`ORB_VWAP_ARM_PCT`); keep a **hard −20%
  premium stop** throughout; otherwise square off at the close.
- **Clean-trend entry filter** (`ORB_VWAP_CLEAN_TREND`): only enter when VWAP is sloped the
  trade's way **and** price is already >0.25% extended from the day's open.

Config: `ORB_VWAP_EXIT_MODE = "trend_ride"` in `engine/config.py`. Logic shared by the live
scanner (`engine/orb_vwap_live.trend_ride_walk`) and the paper resolver
(`engine/paper_resolver.py`).

## Results (gross of costs, ATM index options, −20% stop)

### 30-day
| Exit | Trades | Win % | Net/trade | avg Win / avg Loss |
|------|--------|-------|-----------|--------------------|
| OLD: fixed +20% target | 45 | 27% | **−2.52%** | +16.0 / −9.3 |
| **NEW: trend-ride + clean filter** | 34 | **65%** | **+1.21%** | +9.5 / −14.0 |
| trend-ride, no clean filter | 45 | 60% | +0.79% | +10.5 / −13.8 |

### 60-day
| Exit | Trades | Win % | Net/trade | avg Win / avg Loss |
|------|--------|-------|-----------|--------------------|
| OLD: fixed +20% target | 49 | 27% | **−2.60%** | +15.0 / −9.0 |
| **NEW: trend-ride + clean filter** | 38 | **63%** | **+0.80%** | +8.9 / −13.1 |
| trend-ride, no clean filter | 49 | 57% | +0.02% | +10.1 / −13.5 |

## What the numbers say

1. **The fixed target was the bleed.** −2.5%/trade with a 27% win rate, in both windows.
   It exited most trades on a small VWAP loss before they could reach +20%, while still
   eating the full −20% stops.
2. **Trend-ride flips it.** Letting winners ride to the close (most exits are EOD) takes the
   win rate to 60–65% and the per-trade result positive. The exit mix moves from
   "mostly VWAP-loss" to "mostly EOD" with a handful of VWAP/stop exits.
3. **The clean filter adds a bit and trims junk** — fewer trades (45→34 / 49→38), higher
   win rate, better net.

## Honest caveats

- **Gross of costs.** After brokerage + STT + spread the new config is realistically
  **~breakeven**, not a money-maker. The fix stops the −2.5%/trade *bleeding*; it does not
  turn the index into a profit engine.
- **Fragile out-of-sample.** On the train/test split the edge shrinks and sometimes flips
  slightly negative on the held-out half. Treat the % as directional.
- **Backtest entry vs live entry differ slightly** — the backtest uses a break-and-retest
  entry; the live scanner uses break + hold-VWAP + 30-min-trend + clean filter. The
  dominant, well-supported change is the **exit**, which is identical in both.

## Reproduce

`.venv/bin/python studies/orb_trend_ride_bt.py` (edit `N = 30` / `N = 60`). Requires a valid
`UPSTOX_ANALYTICS_TOKEN` in `.env`.

*Generated 2026-06-19. All P&L gross of bid-ask spread.*
