# Daily-trading high-win search (>80% win, >3%/day) — EXHAUSTIVE FALSIFICATION (2026-07-07)

**User goal:** a non-expiry strategy tradeable EVERY day, >=80% win, >=3%/day gain (stocks/index/F&O).

All five daily-frequency structures the data supports have now been tested on real prices/premiums:

| Structure | Test | Result |
|---|---|---|
| Intraday direction (stocks) | 234 strategies, 7.5y, 100 stocks 5-min | best ~72% win at ~0.00% net — 80%+ only via geometry that earns 0 |
| High-win geometry | 2,400 cells | 92% win, ~0 gross, negative net |
| Non-expiry option selling | 333 day-trades, 1-6 DTE, real premiums | NET NEGATIVE — edge is expiry-day theta only |
| **Intraday pairs mean-reversion** | **10 pairs (ret-corr>=0.75), 3,670 trades 2019-26, z>=2 entry, same-day exit, 0.12% costs** | **45.1% win, -0.14%/trade notional (-0.34% on margin) — FAILS both IS and OOS** |
| Expiry-day CE spreads | validated | works (85-90% win) but weekly, and expiry excluded by the goal |

**Verdict: the target does not exist in this data.** 3%/day on account compounds to ~1,500x/yr
(impossible); 3%/trade-margin daily at 80% win is refuted by every structure above. The
realistic frontier is the deployed portfolio: ~85% win across books, ~7%/month on capital,
trading most days collectively. Script: `studies/ndte/pairs_bt.py`.
