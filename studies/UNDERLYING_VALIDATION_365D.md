# 365-Day Underlying-Proxy Validation (does the signal have a year-long edge?)

Option-premium history from Upstox only reaches ~1 month back, so the option-level
backtests are short. But **5-minute underlying price data reaches ~365 days** — enough to
test the *directional edge* of the signal over a full year. We measured whether the stock
itself moves the predicted way from signal to close (no options), across 365 trading days.

## Result (1,117 signals over the year)

| Signal set | Trades | Directional hit-rate | Avg move/trade |
|------------|--------|----------------------|----------------|
| ALL 3-Family signals | 1,117 | 49% | +0.05% |
| **ALIGNED (Gate 3 on)** | 772 | **52%** | **+0.13%** |
| NOT aligned | 345 | 40% | −0.04% |

Aligned, by thirds of the year: +0.14% / +0.12% / +0.14% — consistently positive, no single
hot streak carrying it.

## What it says

1. **The raw signal alone is a coin flip** (49%, +0.05%). The alpha-z model by itself does
   not predict direction over a year.
2. **Gate 3 (market alignment) is the real edge — and it holds over 12 months** (52% hit,
   +0.13%/trade vs −0.04% for not-aligned). Confirmed on 772 trades, not a lucky month.
3. **The edge is thin** (~+0.13%/trade on the underlying, ~52% directional). Options
   *leverage* this — which is why the option backtests are modestly positive — but it is a
   small lean, not a strong predictor.

## 1-year investment & profit (all signals, with Gate 4)

- ~1.7 signals per trading day on average (~416/year); median 3 on an active day.
- Avg capital per trade ~₹19,400 (premium × lot) → **~₹32,000 deployed/day**, reused intraday.
- Gross profit, extrapolating the recent option edge: **~+₹228k/year** — but this extrapolates
  ~1 month of real premiums across a year and the recent window was a favorable patch; the
  honest range is **roughly breakeven to +₹2 lakh gross**, lower after costs.

## Caveats

Validates **direction only** (no option spread/theta/IV). Uses the legacy flow proxy
(real per-stock options flow isn't available historically), so it's slightly different from
the live signal — but the gates and alignment logic are identical.

Reproduce: `studies/underlying_validation.py`. *Generated 2026-06-20.*
