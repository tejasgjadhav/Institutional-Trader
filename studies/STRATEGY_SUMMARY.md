# Strategy Summary — current structure & real-data status

The canonical one-table view of every strategy and tested variant, with its **real-data** verdict
(as of 2026-07). All four live strategies are **paper forward-tests** — none is proven on live fills.
Detail per row is in the linked study. See also the STUDIES tab in the app (mirrors this).

## The 4 live strategies

| # | Strategy | Type | Signal + gates | Real-data test | Result | Verdict | Status |
|---|----------|------|----------------|----------------|--------|---------|--------|
| 1 | **Stock credit spread** | SELL · multi-day fade | Donchian-10 breakout → sell credit spread AGAINST it; **gate: credit/width ≥ 0.40 + prem ≥ ₹50** + liquidity + caps | bhavcopy 2019→Sep'24, 718 trades (hold-to-expiry) **+ OOS Upstox Oct'24→Jul'26, 346 trades (deployed TP-75)** | **IS: +5.3% of width, 54% win, +ve 5/6 yrs · OOS: 73.4% win, +17.9% of width, +ve all 3 yrs** | ✅ **VALIDATED incl. OOS** (TP-75 lifts win rate — see `STOCK_V1_OOS.md`) | deployed, 1 lot (control book) |
| 1b | **Stock fade v2 — TP-50 upgrade** | SELL · multi-day fade | Same signal+gate; **short 2-OTM, width 4, take-profit 50% of credit, stop 3×** | bhavcopy 2019→Sep'24 (273 tr) **+ OOS Upstox Oct'24→Jul'26 (132 tr)** | **85% win / +24.5% in-sample · 88% win / +31.9% OOS · win ≥79% ALL 8 yrs** | ✅ **VALIDATED incl. OOS** (fewer trades: ~4–6/mo vs ~10) | **LIVE (parallel book, 1 lot)** |
| 1c | **Monthly futures pullback (REV1-v2)** | BUY FUT · monthly cycle | NIFTY>200DMA at cycle start → 8 worst 1-mo losers above own 200DMA → 5 highest-vol → buy front-month FUT; TP +2% (decay +1% d12) / SL −5% on close; **live earnings-skip** | real bhavcopy futures 2018→Jul'26, 281 IS + 70 OOS trades | **75.1% win IS / 75.7% OOS · ~3.9%/mo on margin · worst mo −20%** | ✅ **VALIDATED incl. OOS** (10%/mo goal shown infeasible; needs ~₹15L) | **PAPER 2026-07-10** (`engine/monthly_fut.py`, `studies/monthly_fut/`) |
| 2 | **Index fade credit spread** (NIFTY/FINNIFTY) | SELL · multi-day fade | Donchian-10 breakout → sell credit spread AGAINST it (no c/w gate) | bhavcopy 2019→Sep'24, 181 trades | **−1.4% of width**, +ve only 2019 & 2024; dir+flush gate salvage FAILED OOS | ✗ regime-dependent, not durable | forward-test (downgraded) |
| 3 | **3-Family stocks** | BUY · intraday | alpha-z > 0.55 + ≥2 families · ORB break + 1.2× volume surge · market alignment | Kite 5-min 2019→date, 19,454 signals | **dir +0.107%/tr, 50.6% hit, +ve EVERY year**; net −1.0% as option-buying | ~ real DIRECTION edge, not net-profitable | forward-test |
| 4 | **ORB+VWAP index** (NIFTY/BANKNIFTY) | BUY · intraday | 15-min ORB + VWAP + 30-min trend + clean-trend → buy ATM, trend-ride exit | Kite 5-min 2019→date, 2,303 signals | **dir +0.04%/tr, ~39% hit, −ve ~2/8 yrs**; ~0% net | ~ thin & inconsistent | **RETIRED 2026-07** (PM slot → stock fade v2) |

## Rejected / dropped variants (where the edge is NOT)

| Variant | Real-data test | Result | Decision |
|---------|----------------|--------|----------|
| **MIDCPNIFTY** index fade | bhavcopy 2022→Sep'24, ~15 trades | ~20% win, −25 to −28% of width, illiquid (options only from mid-2022) | ✗ reject |
| **BANKNIFTY** index fade | 5-def × 5-index robustness, 40 trades | −6.7% (earlier +13% was 14-trade luck) | ✗ dropped from lineup |
| Index spread **FOLLOWING** the breakout | grid + validate | ~40% win, −26 to −39% | ✗ rejected → breakouts REVERT (fade instead) |
| **Generic (ungated)** stock credit spread | bhavcopy, 6,844 trades | −1.1% (real 4-leg slippage) | ✗ rejected → the credit/width gate IS the edge |
| Stock **option-buying** (min-premium) | real-option full year, 232 trades | −1.0% (looked +1.5% on 180d — overfit) | min-premium kept for cost/spread only, not profit |

## The through-line
- **Only the gated STOCK fade (row 1) is validated on real multi-year premiums.** The credit/width
  gate is the edge — strip it and it loses like everything else.
- The **index fades (rows 2, MIDCPNIFTY, BANKNIFTY) are regime-dependent or illiquid** — not durable.
- The **BUY strategies (rows 3–4) have a real but tiny DIRECTION edge** (3-Family's is durable and
  positive every year; ORB+VWAP's is thinner) that **option-buying costs eat net** → forward-tests.
- Fades need only daily option closes ([NSE bhavcopy], back to 2019); the intraday BUY strategies
  needed 5-min underlying bars ([Zerodha Kite], back to 2019 — Upstox only reaches ~1–2 yr).

**Sources:** rows 1–2 + variants → `STOCK_OPTIONS_NO_EDGE.md`; rows 3–4 →
`BUY_STRATEGIES_2019_REALTEST.md` + `UNDERLYING_VALIDATION_365D.md`; costs/window →
`REAL_OPTION_OPTIMIZATION.md`, `DATA_AVAILABILITY_LIMITS.md`; capital → `CAPITAL_CURVE_RESULTS.md`.
