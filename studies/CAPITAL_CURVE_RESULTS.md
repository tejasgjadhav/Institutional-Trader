# Capital-Curve Backtest — Results (2026-06-29)

Spec: `OBJECTIVE_SPEC.md`. Script: `capital_curve_bt.py`. Strategy: the **validated index fade
credit spread** (`swing_credit`, frozen config), replayed on real expired-option premiums.

## The numbers (43 trades, NIFTY+FINNIFTY, 2024-11 → 2026-06, 1 lot, GROSS of costs)

| Capital | Return/mo | Max DD | Worst mo | Win % | PF | vs ≤15% DD + 5%/mo |
|---------|-----------|--------|----------|-------|------|-------------------|
| ₹1 L | **1.63%** | **26.0%** | −14.6% | 60.5% | 1.44 | ✗ DD BREACH |
| ₹2 L | **0.82%** | 13.0% | −7.3% | 60.5% | 1.44 | DD OK, **far below 5%** |
| ₹3 L | **0.54%** | 8.7% | −4.9% | 60.5% | 1.44 | DD OK, **far below 5%** |

~2.2 trades/month. Net +₹31,174 over 20 months at 1 lot.

## Verdict
**5%/month at ≤15% DD on ₹1–3 L is not achievable on the validated edge — by a factor of ~3–6×.**
- At your ≤15% DD cap, the achievable return is **~0.8%/mo on ₹2 L** (≈10%/yr) or 0.5% on ₹3 L.
- ₹1 L *looks* better (1.63%/mo) but only by running a **26% drawdown** — it breaks the risk limit.
  This is the spec's predicted failure mode exactly: on a small base, per-trade margin is too large
  a fraction of capital, so the DD cap binds long before 5%/mo is reachable.

## Honest caveats (both directions)
- **GROSS of bid-ask.** Live fills shave the return further → real net is *below* these figures.
- **Daily-resolution replay** → losses settle near full-width (the intraday 2× stop can't fire on a
  daily close), so loss *size* is conservative-to-pessimistic vs live; but **overnight gap risk is
  real** and is exactly what produced the −14.6% month and the 26% DD on ₹1 L.
- **Thin sample (43 trades)** → 60.5% win / PF 1.44 have wide error bars; CLAUDE.md's bootstrap p5
  was negative. Treat as "low-single-digit %/mo, high variance," not a point estimate.

## The one legitimate lever (not yet run)
Return-*on-capital* at a fixed DD improves with MORE uncorrelated, smaller trades. The **stock fade**
(`stock_credit`, ~16/mo vs 2.2/mo here) would raise capital efficiency and smooth the curve — IF it
survives live fills (CLAUDE.md flags it optimistic; keep lots at 1). Running it through this same
capital-curve lens is the next honest step. Even so, it does not plausibly reach 5%/mo at ≤15% DD —
it moves ~0.8%/mo toward maybe ~1.5–2.5%/mo, still well short.
