# Stock fade v2 — TP-50 geometry upgrade (goal: >65% win EVERY year, validated OOS)

**Question:** can the validated stock fade (54% win, +5.3% of width) be reshaped to win >65% in
every regime 2019–2026 with good profit — without breaking out-of-sample?

**Method:** 96-config grid on REAL NSE bhavcopy premiums 2019→Sep'24 (`/tmp/stkfade_grid.py`):
Donchian {5,10,15,20} × short {1,2}-OTM × width {3,4} × take-profit {0, 50%, 75% of credit} ×
stop {2×, 3×}. Gate unchanged (credit/width ≥ 0.40 + prem ≥ ₹50 + OI). Entry **and exit** slippage
charged (`/tmp/stkfade_grid2.py`). Then the winner re-run on a fresh source + window the search
never saw: Upstox expired-instruments, Oct'24→Jul'26 (`/tmp/stkfade_oos3.py`) — the same OOS
discipline that killed the index-fade gate (STOCK_OPTIONS_NO_EDGE.md Part 11).

## The winning config (vs deployed v1)

| Parameter | v1 (deployed) | **v2 (winner)** |
|---|---|---|
| Donchian | 10 | 10 (unchanged) |
| Short strike | 1-OTM | **2-OTM** |
| Width | 3 | **4** |
| Take-profit | 75% of max profit | **50% of the credit** |
| Stop | 2× credit | **3× credit** |
| Gate | credit/width ≥ 0.40 + prem ≥ ₹50 | unchanged |

Not a curve-fit cell: **27 of 96 configs** hit the goal; the whole TP-50/stop-3× neighborhood passes
across every Donchian and width. Mechanism: book the win at half the credit (early IV-crush harvest),
give losers 3× room to mean-revert, sell from 2 strikes deeper.

## Results — real premiums, entry + exit costs

**In-sample (bhavcopy 2019→Sep'24, 273 trades, ~4/mo):**

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | ALL |
|---|---|---|---|---|---|---|---|
| Win% | 100 | 90 | 86 | 88 | 79 | 82 | **85%** |
| Net (% width) | +64.3 | +27.0 | +13.5 | +31.6 | +20.1 | +24.6 | **+24.5%** |

**Out-of-sample (Upstox Oct'24→Jul'26, 132 trades, ~6/mo) — search never saw this data:**

| Year | 2024 | 2025 | 2026 | ALL OOS |
|---|---|---|---|---|
| Win% | 87 | 86 | 91 | **88%** |
| Net (% width) | +19.5 | +34.9 | +31.3 | **+31.9%** |

**8 straight calendar years positive, win ≥79% every year, 405 trades total.** Goal (>65% win every
regime + profit) exceeded in-sample AND out-of-sample.

## Trade-offs & honest caveats
- **Frequency drops:** deeper geometry clears the c/w gate less often — **718→273 gated trades**
  (~10/mo → ~4–6/mo). Fewer, much better trades.
- **Live fills unproven.** Model = daily-close fills + slippage model on 4-leg mid-cap spreads. This
  repo's history says live < backtest (min-prem +1.5%→−1.0%; stock fade +16-25%→+5.3% when cleaned).
  Plan on meaningfully less than the model's ~8–15%/mo on deployed margin; **1 lot until a
  20–30-trade live-fill comparison confirms the per-trade net.**
- OOS is ~21 months — one broad era; durability rests on the 8-year in-sample breadth.
- Take-profit exits assume you can close near the modeled daily closes.

## Exact trade-level distribution (not averages)

**In-sample (273 trades): 233 WINS / 40 LOSSES = 85.35%.** Win size (% of width): min +5.7,
median **+32.0**, max +92.0. Loss size: mildest −15.1, median **−51.1**, worst **−71.9**.
60 calendar months traded, only **4 negative months (7%)** — worst month Nov-2023 (−208 %w units,
a loss cluster), best +419, median month +85. Longest consecutive-loss streak: **4**.
**OOS (132 trades): 116 WINS / 16 LOSSES = 87.88%.** Wins: min +16.3, median +34.8, max +93.0.
Losses: worst −69.3, median −57.8. Per-trade records: `/tmp/stkfade_exact_trades.json`,
`/tmp/stkfade_oos.json`.

## Exposure cap (extremes removed) — DEPLOYED in v2
Rupee exposure per trade (width × lot) varies ~10× across the universe; a few giant-notional names
drove the worst month (Feb-2021 −₹2.28L at 1 lot) and the +₹9.6L best month. Capping **width × lot ≤
₹40k** (90th pctile; drops 26/256 trades) leaves the win rate at **85.7%** and gives a clean, honest
distribution at 1 lot: **monthly median ₹16.0k / mean ₹17.0k · best +₹58.3k · worst −₹26.4k · worst
single loss −₹21.6k · 5/54 months negative.** The cap is live in `stock_credit_v2.py`.

## P&L — model vs practical (honest, both on the record)

The MODEL column is the measured backtest arithmetic (405 real-premium trades, entry+exit slippage
charged) — not a guess. The PRACTICAL column is a ~50% planning discount, justified only by this
repo's history that live fills come in under model (min-prem +1.5%→−1.0%; v1 fade +16–25%→+5.3%
clean). The LIVE column is the truth and gets filled by the forward test (~20–30 trades ≈ 1 month);
when it lands, it replaces both.

| Metric | MODEL (backtest) | PRACTICAL (plan on) | LIVE (forward test) |
|---|---|---|---|
| Win rate | 85% in-sample · 88% OOS | ≥70% still expected | TBD |
| Net per trade (% of width) | +24.5% → +31.9% | ~+12–16% | TBD |
| Net per trade, 1 lot (₹) | ~₹8–14k | ~₹4–7k | TBD |
| Trades / month | 4–6 | 4–6 | TBD |
| **Monthly, 1 lot (capped)** | **median ₹16k · mean ₹17k** | **~₹8–10k** | TBD |
| **Monthly, 2 lots (capped)** | **median ₹32k · mean ₹34k** | **~₹16–20k** | TBD |
| Margin deployed (2 lots) | ~₹1.5–2.5L + stop buffer | same | — |

If LIVE tracks ≥60% of MODEL for a month, scale to 2 lots and adopt the model numbers with a
smaller haircut. If LIVE lands at/below PRACTICAL, stay at 1 lot and investigate fills.

## Status
**DEPLOYED 2026-07-04 as a PARALLEL book (engine/stock_credit_v2.py, 1 lot) alongside v1; ORB+VWAP retired from the PM dashboard.** Wiring = `STOCK_CREDIT_SHORT_OFFSET=2,
STOCK_CREDIT_WIDTH=4 (var names per config.py), STOCK_CREDIT_TAKE_PROFIT=0.50, STOCK_CREDIT_STOP_MULT=3.0`.

## Reproduce
`/tmp/stkfade_grid.py` (96-config grid, DONE-GRID) → `/tmp/stkfade_grid2.py` (exit-cost re-score,
DONE-GRID2) → `/tmp/stkfade_oos3.py` (threaded OOS, DONE-OOS, `/tmp/stkfade_oos.json`). Data:
`/tmp/bhav_cache_stk/` (1,359 days) + Upstox expired-instruments API.
