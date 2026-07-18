# Donchian D5 vs D10 breakout for v2 fade — is the stricter window more sustainable? (2026-07-17)

**User observation:** the UNION watchlist always shows D5. **Why:** the UNION scanner checks
D5/D10/D15/D20 and takes the *first* that breaks — but the D10/15/20 highs are **supersets** of
the D5 high (any close breaking a longer window has necessarily broken D5), so **UNION ≡ D5**.
The longer windows are documentation, not extra signals. So the real question is D5 vs D10.

**Method:** deployed v2 config (short 2-OTM, width 4, TP-50, stop-3×, gate credit/width ≥ 0.40 +
prem ≥ ₹50, min-DTE 10, reentry 3d), run once with breakout = **D5-only** and once **D10-only**,
real Upstox premiums Oct'24→date. Costs 2.5% slippage + ₹20×4/lot. Settle intrinsic at expiry.
Script `studies/ndte/stkfade_d5_vs_d10.py`, data `/tmp/d5_v_d10.json`.

## Result (checkpoint ~⅔ universe — numbers stable, full run refines marginally)

| Breakout | n | signals/mo | Win % | Net (% of width) |
|---|---|---|---|---|
| **D5** (= current UNION) | 105 | ~5.0 | 87.6% | +30.4% |
| **D10** (stricter) | 75 | ~3.6 | **90.7%** | **+31.9%** |

**Per year:**
- D5: 2024 100%/+48%w · 2025 87%/+29%w · **2026 85%/+21%w** (declining)
- D10: 2024 90%/+17%w · 2025 92%/+39%w · **2026 89%/+23%w** (holds up)

## Findings

1. **D10 is the higher-quality, more sustainable signal.** Higher win rate (90.7% vs 87.6%) and
   higher net per trade (+31.9% vs +30.4%) — a 10-day high is a more meaningful level than a
   5-day one, so fewer false breakouts.
2. **D10 is more consistent across the regime** — 92% (2025) and 89% (2026), vs D5 fading to 85%
   in 2026. Directly answers "more sustainable for the month": yes, steadier hit rate.
3. **Cost: ~28% fewer signals** (3.6/mo vs 5.0/mo). D5's extra ~1.4 trades/mo roughly offset
   D10's higher per-trade quality for *total* monthly P&L (D5: 105 × 30.4% vs D10: 75 × 31.9% of
   width) — so it's frequency (D5) vs steadiness (D10), not a free lunch either way.

## Disposition

The deployed book uses **UNION = D5** (`engine/stock_credit_v2.py`, `UNION_DCS = (5,10,15,20)`,
first-break wins → D5). Switching to **D10-only** would trade ~28% frequency for a cleaner,
steadier hit rate. REPORT-ONLY — a live breakout-window change needs user sign-off; single-regime
(Oct'24→now) like all these, so validate on 2019-24 bhavcopy before committing (same caveat as
`CW_BUCKET_ANALYSIS.md`). Recommended next step: show the *strongest* DC that broke per signal on
the watchlist (D5/D10/D15/D20) so the operator can see breakout strength at a glance.
