# Donchian D5 / D10 / D15 / D20 — is a stricter window more sustainable than D5? (2026-07-19)

**The question.** The deployed v2 stock-fade scans a UNION of Donchian windows (5/10/15/20) and
takes the *first* that breaks. But a close that breaks a 10/15/20-day high has **necessarily**
broken the 5-day high too — the longer windows are **supersets** of D5, and the scanner checks D5
first, so **UNION ≡ D5** in practice. The prior study (`DONCHIAN_D5_VS_D10.md`) established this on
the Oct'24→date window only and recommended validating on 2019-24 bhavcopy before drawing a
conclusion. This study does that: **each of D5 / D10 / D15 / D20 run STANDALONE** (its own breakout
stream, its own re-entry gap — NOT the union) across the **full 2019→date history**, to answer
whether a stricter, longer window is a more *durable / sustainable* edge than the frequency-heavy D5.

**Config (deployed v2, identical for all four).** Short 2-OTM, width 4, TP 50% of credit, stop 3×,
gate credit/width ≥ 0.40 + short prem ≥ ₹50, min-DTE 10, re-entry 3d. Entry at signal-day close
(matches the engine's 15:10 scan). Costs = the prior-study per-leg slippage model (`spf`, richer for
cheaper legs, ≈ the "2.5% slippage + ₹20×4/lot" spec) + intrinsic settlement at expiry. Universe =
`engine.config.UNIVERSE` (~100 stocks). **Paper system — VALIDATION ONLY; the live engine is
unchanged.**

**Data — two eras, stitched.**
- **2019→Sep'24:** NSE F&O bhavcopy (daily option OHLC per strike), re-downloaded to
  `/tmp/bhav_cache_stk` (1359 trading days, ~100-stock OPTSTK rows w/ OHLC+OI) via
  `studies/ndte/bhav_dl_stk_opt.py`. Backtest `studies/ndte/stkfade_d5_10_15_20_bhav.py`.
- **Oct'24→date:** real Upstox expired-instrument premiums.
  Backtest `studies/ndte/stkfade_d5_10_15_20_oct24.py` (the `stkfade_d5_vs_d10.py` engine, CONFIGS
  extended to all four). Stitched in-notebook from the two per-trade JSONs.

**Cross-checks (both pass).** Oct'24 D5 = 200 tr / 87.5% / +32.5%w vs the known 203 / 87.2% / +31.5%w;
D10 = 142 / 88.0% / +31.5%w vs known 148 / 88.5% / +31.5%w (tiny deltas = a few Upstox API drops +
fresh days). Bhav **D10 = 273 tr / 85.3% / +26.9%w** reproduces the documented v2 IS figure
(**273 / 85.35% / +26.2%w**, `STOCK_FADE_TP50_UPGRADE.md`) essentially exactly — n identical, win to
0.05pp — confirming the signal/gating/exit pipeline is faithful.

## Result — 2019→date (full history)

| Window | n | signals/mo | Win % | Net (% of width) | Total edge/mo* |
|---|---|---|---|---|---|
| **D5** (= deployed UNION) | 569 | 6.3 | 85.4% | +29.1% | **1.83** |
| **D10** | 415 | 4.6 | **86.3%** | +29.0% | 1.33 |
| **D15** | 343 | 3.8 | 85.4% | +27.2% | 1.03 |
| **D20** | 296 | 3.3 | 83.4% | +26.2% | 0.86 |

\* Total edge/mo = signals/mo × net-per-trade (in width-units) — the aggregate monthly throughput,
which is what actually earns money. signals/mo uses 91 calendar months (Jan 2019 → Jul 2026).

**Two-era split** (the per-year table below shows it directly — 2019-23 are bhavcopy, 2025-26 are
Upstox, **2024 blends both**: bhav Jan-Sep + Upstox Oct-Dec):

| Window | bhav 2019→Sep'24 (n / win / net%w) | Upstox Oct'24→date (n / win / net%w) |
|---|---|---|
| D5  | 369 / 84.3% / +26.2% | 200 / 87.5% / +32.5% |
| D10 | 273 / 85.3% / +26.9% | 142 / 88.0% / +31.5% |
| D15 | 227 / 84.1% / +25.5% | 116 / 87.9% / +29.6% |
| D20 | 200 / 82.0% / +24.1% |  96 / 86.5% / +29.3% |

### Per year, combined (win% / net%w / n)

- **D5:**  2019 96/+60(23) · 2020 88/+22(48) · 2021 85/+22(65) · 2022 90/+32(73) · 2023 79/+20(78) · 2024 81/+27(102) · 2025 85/+32(114) · 2026 89/+28(66)
- **D10:** 2019 100/+64(18) · 2020 90/+27(31) · 2021 86/+14(51) · 2022 88/+32(51) · 2023 79/+20(62) · 2024 83/+23(75) · 2025 87/+36(76) · 2026 90/+29(51)
- **D15:** 2019 100/+66(14) · 2020 92/+20(24) · 2021 83/+9(41) · 2022 91/+35(46) · 2023 78/+18(54) · 2024 79/+19(61) · 2025 86/+33(59) · 2026 91/+32(44)
- **D20:** 2019 100/+72(12) · 2020 90/+20(21) · 2021 81/+6(36) · 2022 90/+32(40) · 2023 74/+16(47) · 2024 76/+18(54) · 2025 83/+33(48) · 2026 92/+32(38)

Every window is **net-positive every calendar year 2019→2026** — the c/w ≥ 0.40 gate holds across
both regimes (this is the durable part, and it is *not* about which Donchian window you pick).

## Findings

1. **A longer window is NOT more durable.** Win rate peaks at **D10 (86.3%)**, is flat at D5/D15
   (85.4%), and *falls* at D20 (83.4%). Net-per-trade **declines monotonically** past D10
   (+29.1 → +29.0 → +27.2 → +26.2%w). If "stricter = more sustainable" were true, D20 would lead on
   quality; instead it trails on win, net, AND frequency. The hypothesis is **falsified** beyond D10.

2. **D10 is a hair steadier, at a real frequency cost.** D10's +0.9pp win over D5 is genuine but
   marginal, and it buys **no** net-per-trade advantage (+29.0 vs +29.1%w — a tie). For that 0.9pp it
   gives up **~37% of the signals** (4.6 vs 6.3/mo). The weak year (2023, 79% for both) and the soft
   patch (2021, D10 +14%w vs D5 +22%w) show D10 is not a durability upgrade — the down-years hit both.

3. **D5's frequency wins on total throughput.** Aggregate monthly edge (freq × net) is **D5 1.83 >
   D10 1.33 > D15 1.03 > D20 0.86** width-units/mo. D5 earns ~38% more total edge per month than D10
   because the two have equal per-trade quality and D5 simply trades more. There is no free lunch in
   the other direction — the longer windows sacrifice throughput for a win-rate bump that only D10
   even delivers, and only barely.

4. **Both eras agree on the ordering.** Oct'24 real premiums and 2019-24 bhavcopy independently rank
   D5≈D10 > D15 > D20 on net/width and put D20 last on win rate. The Upstox era runs ~2-6pp higher
   win and ~+3-6%w richer across the board (thinner-IV recent regime + real intraday exits vs
   close-only bhav), but the **relative** verdict is regime-robust.

## Verdict

**No — a longer Donchian window (D10/15/20) does not give a more sustainable edge than D5.** D10 is
marginally steadier on win rate (86.3% vs 85.4%) but identical on net-per-trade and ~37% less
frequent; D15 and D20 are **worse on every axis** (win, net, and frequency). Because per-trade
quality is flat from D5 to D10 and then decays, **D5's higher frequency is worth it** — it delivers
the most total monthly edge with no loss of durability. The deployed **UNION (≡ D5)** is the right
choice on this evidence; if anything, D10-only is the only defensible alternative and it trades
throughput for a negligible steadiness gain.

**Disposition: REPORT-ONLY.** No live change — the engine keeps `UNION_DCS = (5,10,15,20)`
(first-break = D5). This validates, across the full 2019→date history and both data regimes, the
single-regime conclusion the prior D5-vs-D10 study could only suggest. The real edge is the
**c/w ≥ 0.40 gate**, not the Donchian window; keep lots at 1 and treat all four as the same
paper-forward-tested book.

## Honesty notes

- **Costs are the `spf` per-leg slippage model** (the same one the deployed-era cross-check script
  uses), not a literal flat 2.5%+₹20×4 — chosen so D5/D10 reproduce the known numbers and the two
  eras stay comparable. All figures are net of it; intrinsic settlement at expiry.
- **A daily-OHLC-low TP proxy was tried and REJECTED.** Detecting the TP touch as
  `short.LOW − long.HIGH ≤ (1−TP)·credit` inflated bhav win rates to **97-98%** — it assumes both
  legs hit their favourable extremes at the same instant, which daily bhavcopy cannot support. The
  study uses **close-only** exit detection in both eras (matching the documented v2 pipeline), which
  cross-checks the 85.35% documented figure. The close-only numbers are the honest ones.
- **Single-config, not a fresh grid.** This tests only the deployed v2 geometry across four windows;
  it does not re-optimise strike/width/TP/stop. The point was durability of the *window*, not a new
  parameter hunt.
