# INDEX FADE EXIT SWEEP — does the v1-stock early-booking exit rescue the NIFTY index fade?

**Date:** 2026-07-31 · **Script:** `studies/ndte/idxfade_oos_exits.py` · **Log:** `/tmp/idxfade_oos.log`

## Question

The v1 STOCK fade jumped 54% → 85–86% win when the exit changed from hold-to-expiry/stop-2×
to early booking (TP-40/TP-50 of credit, no stop) — same trades, same n (`V1_WINRATE_SWEEP`,
`stkfade_v1_oos_exits.py`). The INDEX swing fade is booked at 54% win / −1.4%w with the old
exit. Was the exit sweep ever tried on the index? **It had not been — this is that run.**

## Method

Clone of the proven n-preserving harness (`studies/ndte/stkfade_v1_oos_exits.py`), NIFTY only:

- **OOS window:** Oct 2024 → 2026-07-31 (the expired-instruments real-premium window). OOS FIRST
  by design; no IS tuning was done here.
- **Geometry = deployed engine** (`engine/swing_credit.py` / `config.SWING_*`): daily Donchian-10
  breakout at close, FADE (up-break → bear-call short 1-OTM CE +3 wide; down-break → bull-put),
  nearest expiry ≥ 10 DTE, entry at close, re-entry 3d per side. **NO c/w or premium gate.**
- Each trade's daily premium path fetched ONCE from Upstox expired-instruments; all four exits
  walked on the SAME 67 trades (n identical across configs, so win% moves are exit-only).
- **Costs:** `spf()` slippage (1–6% of premium per leg) charged at entry AND exit, as in the
  stock script. Gross of brokerage/STT beyond that slippage model.
- Data note: the expired day-candle endpoint returned ~2 near-duplicate candles per date
  (closes differ ~0.2%); harmless to the walk (repeated points can't newly trigger a TP/stop)
  but it inflates the printed `pathdays`.

## Result — SAME 67 trades (30 CE / 37 PE), four exits, net of spf slippage

| Exit | n | Win % | Net %width | Avg win %w | Avg loss %w | 2024 (n=10) | 2025 (n=37) | 2026 (n=20) |
|---|---|---|---|---|---|---|---|---|
| deployed hold / stop 2× | 67 | 68.7% | **+11.2%w** | +37.9 | −47.2 | +7.3%w / 70% | +14.3%w / 70% | +7.5%w / 65% |
| TP-75 / stop 2× | 67 | 70.1% | +9.2%w | +33.0 | −46.8 | +13.4%w / 80% | +11.2%w / 70% | +3.3%w / 65% |
| TP-50 / no-stop | 67 | 76.1% | +6.9%w | +25.5 | −52.3 | +3.2%w / 80% | +12.3%w / 81% | **−1.3%w** / 65% |
| TP-40 / no-stop | 67 | 77.6% | +4.9%w | +22.3 | −55.5 | +3.2%w / 80% | +9.5%w / 84% | **−2.6%w** / 65% |

**c/w distribution (n=67):** min 0.05 · p25 0.33 · **median 0.40** · p75 0.48 · max 0.53.
Higher than the ~0.2–0.35 expected — NIFTY 1-OTM +3-wide at ≥10 DTE prices near the stock
gate's 0.40 line on its own.

## Verdict — honest

**No. No n-preserving exit reaches ~80% win, and every tightening of the exit LOWERS net.**

1. The stock jump does not replicate. Best win% is 77.6% (TP-40/no-stop) vs 85–86% on stocks,
   and it costs more than half the net (+11.2%w → +4.9%w). On stocks the same switch preserved
   net; here win% and net trade off monotonically.
2. Mechanism: removing the stop lets index losers run to near max-loss (avg loss −47.2 →
   −55.5%w) while early booking caps winners (+37.9 → +22.3%w). The index fade's P&L comes
   from the big held winners; the stock edge came from rich-IV credits decaying fast.
3. The early-booking exits are already NEGATIVE in 2026 YTD (−1.3%w / −2.6%w, n=20) while the
   deployed hold/stop-2× is +7.5%w on the same trades — the "better win rate" exit is the
   worse strategy in the most recent regime.

## Caveats (do not skip)

- **This OOS window is ONE regime — and a known-favorable one.** Oct'24→Jun'26 is exactly the
  window that showed "+12%" before the 2019→Sep'24 bhavcopy test came back **−1.4%w** out-of-time
  (CLAUDE.md Part 10). The +11.2%w hold figure here is regime-flattered, not a revalidation.
  The index fade also previously FAILED OOS on direction/flush gates (Part 11) — the base
  strategy remains regime-dependent/unproven regardless of exit.
- n=67 over 21 months; per-year cells are n=10–37. Thin.
- Costs are the spf slippage model only (entry+exit), gross of brokerage/STT/fees.
- Settlement uses index close intrinsic on expiry date; entry at the daily close.

**Bottom line:** the early-booking exit is not a rescue for the index fade. It manufactures
win rate by capping winners and letting losers run — the opposite of what made it work on
gated stocks. Nothing here justifies re-enabling `SWING_CREDIT_ENABLED`.
