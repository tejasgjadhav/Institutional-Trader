# Objective Spec — Capital-Curve Backtest (v1, 2026-06-29)

Replaces the original ask ("80% win rate + 5%/month") which your own research
(`WIN_RATE_RESEARCH_LOG.md`, `STOCK_OPTIONS_NO_EDGE.md`) showed is internally
conflicting: 80% WR is only reachable via negative-skew credit selling, where WR is
*gameable* and *anti-correlated* with profit (`rrsweep` study). We optimize return on
capital under a drawdown cap; win rate is a **reported output, never a target**.

## Goal
Measure the **monthly return on a fixed total-capital base**, net of measured costs,
that your credit-spread book can durably achieve — driven by the ONE real-data-validated edge
(the gated stock fade; the index fade is a downgraded forward-test) — and how close that
gets to the 5%/month aspiration.

## Parameters (locked with user)
| Knob | Value |
|------|-------|
| Capital base | **₹1–3 lakh** (run sensitivity at ₹1L / ₹2L / ₹3L) |
| Max drawdown (HARD constraint) | **≤ 15%** of starting capital — any config breaching is rejected regardless of return |
| Sizing | **1 lot per spread** (`*_LOTS = 1`, per the deployed forward-test rule) |
| Strategies | `stock_credit` (gated stock fade) — the one edge **VALIDATED on real 2019→Sep24 bhavcopy** (+5.3% width, 5/6 yrs). `swing_credit` (index fade) is included only as a small forward-test — it was DOWNGRADED (net −1.4% real, gate salvage failed OOS; see STOCK_OPTIONS_NO_EDGE.md Parts 10–11), so weight the book toward the stock fade |
| Costs | measured bid-ask + slippage per leg (same model as the studies) |
| Validation | longest expired-option window available (~18 mo), temporal OOS split, monthly-return bootstrap |

## Primary metric
- **Monthly return on total capital** (equity curve, not per-trade %, not %-on-margin).

## Reported outputs (descriptive — NOT optimization targets)
- Max drawdown (vs the 15% cap), win rate, profit factor, trades/month,
  avg win ÷ avg loss, monthly-return distribution, worst month, recovery time.

## The binding constraint to expose (hypothesis)
At ₹1–3 L, the limit is **not** signal availability — it's **concurrency under the DD cap**.
A single NIFTY width-3 spread risks ~₹8k (≈4% of ₹2 L); `STOCK_CREDIT_MAX_OPEN=20` at
~₹3k worst-case each = ~₹60k = **30% of ₹2 L** if a correlated gap hits them together —
that alone breaches the 15% cap. So the backtest must size the **open-position cap** to the
DD budget, and the achievable %/month falls out of *that*, not out of the raw edge.

## Success definition
An honest verdict: the achievable monthly return on ₹1–3 L at ≤15% DD, with the equity
curve, worst month, and the gap to 5%/month stated plainly. No curve-fitting to hit a number.
