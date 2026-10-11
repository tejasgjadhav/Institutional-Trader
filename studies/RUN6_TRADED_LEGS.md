# Run 6: the harness of record counts traded prices only (11-Oct-2026)

**What changed.** `studies/ndte/deployed_backtest.py` has two new flags, both ON by default.
- `RUN6_TRADED_LEGS`: a leg counts only on days it traded, on entry day and on every take-profit day.
  In-sample, a leg is untraded when its close and open interest are both unchanged from its previous
  row. Out of sample, a leg is untraded when the NSE trade count is 0 or the Upstox candle volume is 0.
- `RUN6_BP_SUBFLOOR`: the live bull-put sub-floor for v1 and v0 (short at least Rs10 and credit × lot
  at least Rs3,000).

A `FRIC` friction multiplier was also added (default 1.0). With both flags OFF, run 6 reproduces run 5
row for row (IS 1,144, OOS 561). With traded legs ON and the sub-floor OFF, it reproduces the stale-print
audit exactly (IS 959, OOS 507). Checks: research/run6/test_run6.py and validate_core.py.

**Why.** The stale-print audit (10-Oct-2026, research/audit_stale/) found that run 5 entered and booked
take-profits on carried-forward closes of contracts that did not trade. The c/w gate preferentially
picked those stale-cheap wings, which inflated credit. The highest c/w ever seen live is 0.47, while
run 5 had 11–29% of its trades at c/w 0.50 or more.

## Results (1 lot, friction 1.0x, all c/w; 107 live names; vlc out of scope)

| Book | Win IS / OOS | ROM IS / OOS | Trades IS / OOS | Rs/month IS / OOS |
|---|---|---|---|---|
| v2 (TP-50, short ≥ Rs50) | 61.3% / 81.9% | +5.4% / +22.3% | 238 / 72 | Rs1,566 / Rs8,138 |
| v1 (TP-40, D10, short ≥ Rs30, BP sub-floor) | 77.4% / 79.9% | +10.7% / +11.1% | 624 / 313 | Rs7,709 / Rs16,865 |
| v0 (c/w 0.35–0.40, short ≥ Rs30, BP sub-floor) | 83.4% / 81.3% | +7.3% / +6.5% | 283 / 155 | Rs3,514 / Rs6,416 |
| **System** | **75.5% / 80.6%** | **+8.6% / +10.9%** | **16.6 / 24.2 a month** | **Rs12,789 / Rs31,419** |

- IS is 2019 to Sep 2024 (69 months). OOS is Oct 2024 to 10-Aug-2026 (22.3 months, Upstox cache).
- The complete NSE path to 18-Sep-2026 gives 78.7% win, +9.0% ROM, 25.3 trades a month and Rs27.2k a
  month. The Upstox cache has 2,397 evaluations with no legs, so OOS counts are a floor.
- At 0.75x friction the system is IS +10.8% (Rs16.2k a month) and OOS +12.8% (Rs36.7k a month).
- Average win and loss: IS Rs3,414 and Rs7,396; OOS Rs3,899 and Rs9,479.
- Worst trade: −Rs28.3k IS, −Rs22.0k OOS. Max drawdown: Rs128.5k IS, Rs140.7k OOS.
- The median cohort (c/w 0.40–0.50, v0 its whole band) is IS 78.4% / +6.6% and OOS 80.7% / +9.8%.

**Against run 5,** the system's IS ROM falls from +22.6% to +8.6% and OOS from +16.8% to +10.9%. v2's
in-sample case largely disappears (+34% to +5%). The strategy is still positive in both windows and in
5 of 6 in-sample years.

## Goal rework on run 6 (user's goal: max signals, win ≥ 75%, positive net for system and each addition)

Pre-registered in research/run6/prereg.json, chosen on IS only. **No addition passes.** The live system
already meets the goal on its own.

| Addition | Result |
|---|---|
| v1 geometry on union (non-D10) breakout days | +2.9 a month IS, +4.4 OOS, about +10% ROM in both, but negative on next-session entry in IS. Watch item only. |
| Bull-put c/w side gate 0.36 | Net loser (IS −1.2%) |
| Sigma-distance book k = 0.10 | Fails the next-session check in both windows; −39.5% on 14 post-CAS trades |
| Sigma-distance book k = 0.40, c/w ≥ 0.35 | About 1–2 a month at high ROM, but fails the next-session check in IS |
| v2 bull-put sub-floor | Fails OOS (−12.5% on 7 trades) |
| Forward rule as a filter | Cuts signals with no IS gain |
| Strike buffer p10 | Picked after reading OOS; worse IS |

Stacking every addition gives about 38 trades a month at 79% win and +8.4% OOS, but its next-session
ROM is negative and it lost 34% on 15 post-CAS trades. The extra signals depend on the signal-day close.

## Two-month what-if (entries 11-Aug to 9-Oct-2026; reported only, not used to select anything)

| Line | Signals | Total Rs at 1 lot |
|---|---|---|
| Live engine, actual | 5 | +Rs1,696 (one open v0 LTM at −Rs2,576) |
| Run-6 rules replayed, fault-free | 9 | +Rs3,268 |
| Plus v1 on union days | +4 | +Rs11,780 added |
| Plus every addition stacked | +31 | −Rs121,633 added |

The engine's missed scans in this window (25-Aug, 22-Sep, 25-Sep and late scans) had no qualifying
signal under run-6 rules, so they cost nothing.

**Multiple testing.** The Oct-2024+ window has now been read by at least 15 studies. Treat any new
rule found on it with suspicion; the forward record is the only clean test left.
