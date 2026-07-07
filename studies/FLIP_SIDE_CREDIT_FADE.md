# FLIP-side index credit fade — momentum-gated PE/CE selection (2026-07-07 night)

**User goal:** an index credit-fade model that FLIPS between PE and CE by gates, >=80% win.

**Rule (frozen on IS before OOS):** each NIFTY weekly expiry morning, if 5-day return >= +1.0%
-> SELL the PE spread (short 0.5% OTM below spot, wing beyond); else SELL the CE spread (short
0.5% OTM above, wing beyond). Hold to same-day settlement. Mechanism: momentum continuation —
never sell calls into a grinding rally (the exact failure of the CE ladder in the Jul-1-7 week).

| Real premiums, costs 2.5%+brokerage | n | Win | Avg %margin | Total 1 lot |
|---|---|---|---|---|
| IS 2019-Sep24 CE-always (baseline) | 282 | 84.0% | +2.66% | +Rs89,056 |
| IS FLIP | 282 | 85.8% | +3.82% | +Rs137,523 |
| OOS Oct24-Jun26 CE-always | 89 | 87.6% | +2.47% | +Rs32,876 |
| **OOS FLIP (frozen rule)** | **89** | **91.0%** | **+4.36%** | **+Rs65,426** |

OOS per year: 2024-stub 83%/−Rs7.7k (12 tr, lot-transition era) · 2025 94.2%/+Rs44.6k ·
2026 88.0%/+Rs28.6k. Threshold neighborhood 0.5–2.0 all beat baseline IS (not a fit cell);
gap-based flip also works (+3.0-3.5%m) — momentum family is robust. PE-always loses both eras
(confirms side-selection is the edge, not the PE side itself).

Caveats: expiry-day cadence (~4-5/mo — extendable to the daily ladder pending PE leg data);
wings W=200 IS vs W=300 OOS (cache constraint — direction consistent across both); 2024-stub
negative in rupees. **REPORT-ONLY — not deployed; needs user review per the approval-first
rule.** Repro: scratchpad flip scripts; data /tmp/ndte_bhav + /tmp/ndte_cache + /tmp/ndte_daily.
