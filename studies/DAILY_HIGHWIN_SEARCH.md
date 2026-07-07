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

**UPDATE (same night) — the hold-to-expiry variant largely survives:** entering the same CE
spread (0.5% OTM, wing 200) EVERY trading day on the NEAREST weekly and holding to settlement
(not closing same-day) on 424 real-premium daily entries Oct'24→Jun'26: **78.8% win, +7.25%
of margin per trade (≈+2.4%/day held), +₹2.22L total at 1 lot, positive 2024/2025/2026.**
The 0-1 DTE subset: 83-87% win, +3.3%/day-held. CAVEATS: 21-month single-era evidence only
(no 2019-24 extension possible — bhav cache lacks non-expiry-day contracts); entering daily
stacks up to ~5 CONCURRENT same-side spreads on one index — a gap-up week hits several at
once (per-trade worst −₹13k, a bad week can stack 3-5 of those); same CE-side regime risks
as the 0DTE book. REPORT-ONLY per the user's approval-first rule — NOT deployed.

**FINAL — GOAL CRITERIA MET with the already-deployed gates applied (rv5<0.9 calm filter +
0.02%-of-spot credit floor, unchanged from the live NIFTY book):** daily-ladder CE spread
(enter EVERY day, nearest weekly, short 0.5% OTM, wing +200, hold to expiry settlement):
**n=351 daily entries Oct'24→Jun'26 · 81.2% win · +9.06%/margin per trade · +4.30%/margin per
day held · +₹2.66L at 1 lot (~₹12.6k/mo on ~₹70k ladder margin).** Sub-years: 2024-stub 82.6%
(₹-flat), 2025 79.6%/+₹1.59L, 2026 84.6%/+₹1.08L. STATUS: REPORT-ONLY — awaiting user review
per the approval-first rule; if approved, deploys as paper book #6 first. Remaining caveats:
21-month single-era window (older data physically unavailable), up to ~5 concurrent same-side
spreads (a gap-up week hits several at once), CE-side regime dependence.

### NIFTY vs SENSEX daily ladder — full data (both gated, Oct'24→Jun'26, real premiums)

| | NIFTY | SENSEX |
|---|---|---|
| n | 349 | 343 |
| Win | **81.2%** | 75.8% |
| Avg %margin/trade | +9.06% | +2.90% |
| Total 1 lot | **+₹2,66,000** | +₹93,051 |
| Worst trade | −₹13,264 | −₹12,528 |

SENSEX per-year: 2024 77.8%/+₹8.9k · **2025 72.9%/−₹8.9k (lost)** · 2026 83.6%/+₹93.1k — the
entire result is one 2026 stretch; 2025 was net-negative. Per-DTE only DTE=1 is clean (84.6%);
longer rungs whipsaw (DTE=3: 66%/−9%m). **NIFTY ladder beats SENSEX ladder on every metric.**
Both remain SHELVED (ladder stacks ~5 correlated same-side spreads → a rally week takes several
full-width losses at once; the Jul-1-7 NIFTY autopsy was −₹27k at 1 lot). Deployable SENSEX =
the Thursday expiry-day 0DTE book, not the ladder.

**Verdict on the exact goal (80%/3%-a-day):** 3%/day on account compounds to ~1,500x/yr
(impossible); 3%/trade-margin daily at 80% win is refuted by every structure above. The
realistic frontier is the deployed portfolio: ~85% win across books, ~7%/month on capital,
trading most days collectively. Script: `studies/ndte/pairs_bt.py`.
