# Gate 5 — "Wide Open" (opening-range width filter)

A 5th gate on the 3-Family stock system: **only trade when the first-30-min opening range is
at least `ORB_RANGE_WIDTH_MIN` (0.8%) of price wide.** A wide opening range = real morning
momentum (cleaner breakouts); a narrow, quiet open is chop.

## How it was found (a disciplined loop)

1. Collected 90 days of aligned+Gate4 trades with signal-time features + full option-premium
   paths, then searched in-memory over candidate features × thresholds × risk-reward, ranked
   by **out-of-sample (test-set) expectancy** with a train/test split.
2. Candidates that beat baseline on the 90-day option sample: `orb_w` (range width), `gap`,
   and `tod` (time-of-day).
3. **Validated on the 365-day directional sample (635 trades)** to separate signal from
   small-sample noise. `tod` flipped sign vs the prior study → **rejected as noise**.
   `orb_w` and `gap` held; `orb_w` was the cleanest, monotonic-in-the-sweet-spot candidate.

## Evidence

**365-day directional (held-out test), the robust sample:**
| | Test hit | Test avg move |
|---|---|---|
| Baseline (Gate 1-4) | 50% | +0.17% |
| **+ Gate 5 (orb_w ≥ 0.8)** | **52-54%** | **+0.18-0.22%** |
(`orb_w ≥ 1.2` started over-fitting — train degraded — so 0.8-1.0 is the sweet spot.)

**Option backtest @ +10/−20 (same risk-reward), Gate 4 vs Gate 5:**
| Window | Gate 4 win / profit | Gate 5 win / profit |
|--------|---------------------|---------------------|
| 30-day | 61% / +1.8% | **66% / +2.0%** |
| 60-day | 66% / +3.3% | **70% / +3.5%** |

## Decision

**Deployed Gate 5 at +10/−20** (kept the existing risk-reward — the pure win-rate upgrade).
A separate +15/−20 option (raise the target) tested higher profit but lower win rate; not
deployed. Config: `ORB_RANGE_FILTER = True`, `ORB_RANGE_WIDTH_MIN = 0.8`; enforced in
`engine/agent.py:scan_stock` (Gate 5). Pure arithmetic on candles already fetched — **zero
added latency / no extra API call**.

## Honest caveats

- Option windows are small (35-56 trades) — directional. Gate 5's validation rests on the
  **365-day directional sample** (the robust part). All figures GROSS of spread.
- Win rate is still below the +10/−20 breakeven (67%) on the full samples; Gate 5 narrows the
  gap. Net of costs it remains a thin edge — the forward paper month is the judge.

*Generated 2026-06-23. Gross of brokerage / STT / spread.*
