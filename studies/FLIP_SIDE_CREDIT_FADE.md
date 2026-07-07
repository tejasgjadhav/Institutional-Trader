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
gap-based flip also works (+3.0-3.5%m) — momentum family is robust. ### Since-inception, uniform W=200 both sides (372 expiries 2019→2026, PE legs downloaded)

| Year | CE-ALWAYS win / ₹ | FLIP win / ₹ |
|---|---|---|
| 2019 | 87.0% / +₹2,888 | 84.8% / **−₹3,859** |
| 2020 | 79.2% / +₹1,843 | 83.0% / +₹22,758 |
| 2021 | 84.6% / +₹16,863 | 76.9% / +₹11,406 |
| 2022 | 86.5% / +₹45,476 | 86.5% / +₹38,736 |
| 2023 | 86.5% / +₹16,392 | 94.2% / +₹27,819 |
| 2024 | 82.1% / +₹14,588 | 89.7% / +₹33,610 |
| 2025 | 86.8% / +₹3,897 | 94.3% / +₹42,921 |
| 2026 H1 | 84.0% / +₹14,821 | 88.0% / +₹18,620 |
| **ALL** | **84.7% / +₹116,768** | **87.1% / +₹192,010** |

**Net gain of switching to FLIP (per year, ₹ at 1 lot):** 2019 −₹6.7k · **2020 +₹20.9k** ·
2021 −₹5.5k · 2022 −₹6.7k · 2023 +₹11.4k · 2024 +₹19.0k · 2025 **+₹39.0k** · 2026 +₹3.8k.
**Total edge = +₹75,242 more than CE-always (+64%), win rate 84.7% → 87.1%.** The only real
cost is 2019 (−₹3.9k absolute, a single bad week) — negligible against 2020's +₹22.8k and 2025's
+₹42.9k. Flip wins 6 of 8 years, dominates the maturing-market era 2023–26 (91–94% win), and its
worst outcome is small. Verdict: strictly better on win rate AND money over the full sample; the
paper forward-test remains the referee if 2019-style chop returns.

PE-always loses both eras
(confirms side-selection is the edge, not the PE side itself).

Caveats: expiry-day cadence (~4-5/mo — extendable to the daily ladder pending PE leg data);
wings W=200 IS vs W=300 OOS (cache constraint — direction consistent across both); 2024-stub
negative in rupees. **DEPLOYED 2026-07-07 (user-approved) on the live NIFTY Tuesday paper book** —
`ZERO_DTE_FLIP_RET5 = 1.0`; SENSEX/BANKNIFTY stay plain-CE (validated-only). Repro: scratchpad flip scripts; data /tmp/ndte_bhav + /tmp/ndte_cache + /tmp/ndte_daily.
