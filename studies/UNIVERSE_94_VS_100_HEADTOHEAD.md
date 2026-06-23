# Study: Universe — hand-picked 94 beats free-float-mcap 100 (head-to-head)

## Question
We briefly switched the universe from a hand-picked 94 to the top-100 NSE stocks by free-float
market cap (NIFTY-100-equivalent). Did that help or hurt? The old 94's recorded Gate-5 numbers
(66%/70%) looked higher than the new 100's (55%/59%) — but those were measured on **different**
~1-month option windows (real option data only goes back ~1 month), so the comparison was
confounded by market regime.

## Method
Backtested the **union** of both universes (122 stocks) **once**, over the **same** 60-day
window, identical gates 1–5 and +10/−20 exit, then split the resulting trades by universe
membership. This isolates the universe effect from the time-window effect.

## Result — the 94 genuinely wins (same window)

| Universe | Trades | Win% | Profit (on capital) |
|---|---|---|---|
| **OLD 94** | 57 | **67%** | **+3.4%** |
| **NEW 100 (mcap)** | 56 | 61% | +1.3% |
| In both (unchanged) | 41 | 63% | +3.0% |
| **OLD-only (names removed by mcap)** | 16 | **75%** | **+4.3%** |
| **NEW-only (names added by mcap)** | 15 | **53%** | **−2.8%** |

The bottom two rows are the verdict: the **mid-caps the mcap-ranking removed were the best
performers** (75%, +4.3%), and the **mega-caps it added are net losers** (53%, −2.8%).

## Why
This is a **momentum / opening-range-breakout** strategy. Larger market cap ⇒ less intraday
movement ⇒ fewer clean breakouts and weaker follow-through. Ranking the universe by **size**
optimises for exactly the wrong property. The volatile mid-caps (NMDC, SAIL, POLYCAB, MPHASIS,
COFORGE, LUPIN, JUBLFOOD, …) are where the breakout edge lives.

## Decision
**Reverted to the hand-picked 94**, plus the 5 persistent-winner PRIORITY names not already in
it (JINDALSTEL, INDIANB, AUBANK, BAJAJHLDNG, TATAELXSI) and ETERNAL (ex-ZOMATO) → **100 names**.
The ★ priority tier (see PRIORITY_STOCKS_PERSISTENCE.md) is unchanged.

## Caveat
~16/15 trades in the differentiating buckets is a smallish sample, but the direction is
consistent with the common-41 base (63%) and with the mechanism. Lesson: **select the universe
by tradeable intraday movement, not by market cap.** A future refinement is to rank by ATR /
historical breakout-win-rate rather than size.
