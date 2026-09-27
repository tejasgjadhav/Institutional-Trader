# Take-profit sweep, all 208 F&O names, both sides (27-Sep-2026)

**Question (user).** Keep ~35 calls a month across all 208 names, but set a target of 20/30/40/50% of
the credit to raise the win rate and the net profit.

**Method.** Harness of record (run 5, per-book floor) with every book's take-profit set to 20, 30, 40,
50 or 60% of the credit, or held to expiry. Baseline = today's v2 50% / v1, v0 40%. Full band, 1 lot.
Driver `research/tp_sweep_driver.py`, report `studies/ndte/tp_sweep_report.py`.

## In-sample, 2019→Sep-2024 (complete)

| take profit | signals/mo | win | ROM | ₹/mo |
|---|---|---|---|---|
| **today: v2 50%, v1/v0 40%** | 24.8 | 81.2% | +31.4% | **₹53,995** |
| 20% | 25.8 | 89.6% | +25.1% | ₹44,597 |
| 30% | 25.3 | 86.4% | +28.3% | ₹51,321 |
| 40% | 24.9 | 82.4% | +29.7% | ₹52,486 |
| 50% | 24.6 | 78.3% | +30.0% | ₹53,698 |
| 60% | 24.2 | 74.3% | +29.6% | ₹52,092 |
| hold to expiry | 23.1 | 64.3% | +29.2% | ₹42,860 |

A lower target buys win rate and costs money: each early exit keeps less of the credit while losses
stay the same size. Signal count barely moves. Today's mix earns the most.

## Out-of-sample

Running (Upstox rate limit; contract lists now disk-cached). The report lands in
`research/tpsweep/report.txt`, the workbook sheet "Take-profit sweep" and the study database table
TP_SWEEP_208. The setting changes only if another level wins clearly in both windows.
