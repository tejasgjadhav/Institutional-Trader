# Study: Per-stock win-rate selection is overfit — the 13 persistent winners

## Question
Can we raise the win rate by trading only the stocks with the highest historical win rate
(a "reverse" universe — pick winners, not market-cap)?

## Method
Backtested **158 candidate F&O stocks** over **365 days** with the live gate stack (Gates 1–5,
+10/−20 exit; Gate 6 liquidity is live-only and cannot be backtested). For each stock, split
its trades into **TRAIN (older 60% of the year)** and a **held-out TEST (newer 40%)**. Ranked
stocks by TRAIN win rate, selected the top 60, then measured their win rate on the TEST period
they were never selected on. Minimum 4 train trades to qualify (kills 3/3=100% flukes).

## Result — selection by win rate does NOT persist

| Universe | TRAIN win% (optimized) | TEST win% (held-out) |
|---|---|---|
| **Top 60 by win rate** | 64% | **49%** |
| Whole eligible pool | 54% | 46% |

- The top-60 **collapsed 15 points** out-of-sample (64% → 49%) and beat the pool by only
  **+3 points** on unseen data. Individual reversion was brutal: CGPOWER 86%→0%,
  ADANIPORTS 80%→0%, GODREJPROP 80%→0%, ETERNAL 78%→25%.
- **Conclusion:** per-stock win rate over ~1 year is mostly noise around the strategy's base
  rate. A 60-stock "highest win rate" universe gives ~49% forward, not 64%. **The edge is in
  the gates (timing/setup), not in which stock.** We did NOT deploy a win-rate-selected universe.

## The one real signal — 13 stocks that won in BOTH windows

Only 13 of 158 stocks had a win rate that held up across both independent halves
(train ≥55% AND test ≥50%): combined **~75% over 110 trades**.

```
BAJFINANCE  RECLTD  AUROPHARMA  JINDALSTEL  INDIANB  AUBANK  BAJAJHLDNG
POWERGRID  ASHOKLEY  TATAELXSI  SHRIRAMFIN  INDUSINDBK  PERSISTENT
```

## What we deployed
- **Universe stays broad (100 stocks)** — breadth = more valid setups = more signals; the gates
  carry the edge.
- These 13 are tagged `config.PRIORITY_STOCKS` and flagged with **★** in the read-only UI
  (WATCHLIST + ALPHA), so the user can choose to focus / size up on them.
- The engine **still scans and fires on all 100** — the tag changes nothing in selection, so the
  overall win rate is unchanged (~55–59% option / ~52–54% directional, gross). Trading only the
  13 would historically show ~75% but with far fewer signals and a small sample — a tilt, not a
  guarantee.

## Honesty
110 trades across 13 names ≈ 8/stock — still a small per-stock sample. Two windows of agreement
is suggestive, not proof. Treat the ★ as a soft tilt and let the forward paper log be the judge.
