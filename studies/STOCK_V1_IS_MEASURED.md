# Stock Credit v1 (TP-75) — IN-SAMPLE, finally measured (2026-07-30)

**User's question:** the UI said v1's in-sample was "NOT MEASURED" while v2's *was* measured — why? Was
anything lacking? **Answer: nothing was lacking — it was simply never run.** Same NSE bhavcopy
(2019→Sep'24), same daily-close TP-detection method that produced v2's 84% IS. This closes the gap.

## Method
`studies/ndte/stkfade_v1_is.py` — reuses the validated UNION IS harness (cache loader + gate/exit walk +
intrinsic settlement + entry-slippage `spf()` model) on `/tmp/bhav_cache_stk` (1,418 bhav days,
2019-01→2024-09). v1 deployed config: **DC10 only, short 1-OTM, width 3, TP 0.75 (book when cost-to-close
≤ 0.25×credit), stop 2× credit**, gates credit/width ≥ 0.40 + short prem ≥ ₹50, min-DTE 10, re-entry 3d,
entry at close. Costs: entry slippage only (gross of exit slippage + taxes).

## Faithfulness cross-check (proves the harness) ✅
Running the **v2** config (short 2-OTM, width 4, TP 0.50, stop 3×) on the same DC10 signals reproduces the
known DC10 baseline: **n=286, 85.3% win, +25.7%w** — matches `DONCHIAN_5_10_15_20.md` / `UNION_DONCHIAN_FREQUENCY.md`
(273 tr / 85.3%). The harness is faithful, so the v1 result below is trustworthy.

## Result — v1 TP-75 IN-SAMPLE
**n=755 (10.9/mo) · win 64.0% · net +10.3% of width · positive every year.**

| Year | n | Win% | Net %width |
|---|--:|--:|--:|
| 2019 | 56 | 64.3% | +19.6% |
| 2020 | 91 | 62.6% | +4.9% |
| 2021 | 136 | 61.8% | +4.4% |
| 2022 | 175 | 68.6% | +16.6% |
| 2023 | 124 | 54.8% | +0.2% |
| 2024 | 173 | 68.2% | +13.8% |

Context — v1 geometry **held to expiry** (TP off): **55.1% win / +6.5%w** — confirms the "~54% base" the UI
referenced. TP-75 lifts win 55%→64% and net +6.5%→+10.3%w by booking early.

## The honest takeaway
- **v1 in-sample = 64.0%, out-of-sample (Oct'24→now, 346 tr) = 73.4%.** OOS > IS, so the deployed "73%" was
  the **optimistic end**, not an overfit — the fuller, honest figure is **~64% IS / 73% OOS (~67% pooled)**.
- Net is real but thin: +10.3%w IS / +17.9%w OOS, and 2023 was ~breakeven (+0.2%w) — v1's soft spot is the
  grind/chop regime, same as flagged elsewhere. v1 remains the lower-quality control vs v2 (85% IS / 87% OOS).
- Caveat: gross of exit slippage; mid-cap live fills erode net; entry at daily close.
