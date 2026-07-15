# Credit/width bucket analysis — is there an edge below the 0.40 gate? (2026-07-15)

**Question (user):** at c/w 0.35 (and 0.30), the win rate is still >74% — is that tradeable, or
is the only cost a worse risk/reward?

**Method:** deployed v2 UNION fade (UNION Donchian 5/10/15/20, short 2-OTM, width 4, TP-50,
stop-3×, prem≥₹50, live two-sided quote, min-DTE 10, reentry 3d) with the **credit/width gate
lowered to 0.30** so the sub-gate population is visible. Real Upstox expired-option premiums
**Oct'24→Jul'26** (629 trades). Costs: 2.5% slippage + ₹20×4/lot. Settle intrinsic at expiry.
Script `studies/ndte/stkfade_cw_buckets.py`, data `/tmp/cw_buckets.json`.

## Result — win rate barely drops, but the MONEY is a gradient

| c/w bucket | n | Win % | **Net (% of width)** | Avg win | Avg loss |
|---|---|---|---|---|---|
| **0.30–0.35** | 279 | 76.3% | **+1.1%** | +19.6% | −61.3% |
| **0.35–0.40** | 163 | 82.2% | **+9.2%** | +21.3% | −64.9% |
| **≥0.40 (deployed)** | 187 | 87.2% | **+31.7%** | +37.6% | −55.4% |

0.35–0.40 by year: **2024 +20.2% · 2025 +8.1% · 2026 +7.8% — positive every year.**

## Findings

1. **Win rate is a mirage below the gate.** It only falls 87% → 82% → 76% across the buckets —
   still "high" everywhere, because TP-50 books wins early. Looking at win rate alone, 0.35 looks
   fine. It isn't the right metric.
2. **The edge is a gradient, not a cliff.** Net collapses 31.7% → 9.2% → 1.1% of width:
   - **≥0.40** = the clean core edge (+31.7%, 87% win, lowest-variance losses).
   - **0.35–0.40** = a REAL but diminished edge (+9.2%, ~⅓ of core), positive all 3 years, but
     with a brutal −65% average loss (high variance).
   - **0.30–0.35** = near-breakeven (+1.1%); after real-fill slippage (~20% haircut) → ~zero/neg.
     **Not worth trading.**
3. **Payoff asymmetry is why high win rate ≠ profit.** At 0.35 the win (~+20% of width, half a
   thin credit) vs loss (~−65%) is a ~1:3 payoff → breakeven win rate ≈ 76%. The observed 76%
   (0.30–0.35) sits right on breakeven; the 82% (0.35–0.40) clears it enough for +9%.
4. **Booking to expiry ("keep the full credit") makes it WORSE, not better.** Hold-to-expiry
   crushes the win rate (repo evidence: base fade at ≥0.40 = 54% win / +5.3%w vs TP-50 87% /
   +31.7%). The fade edge is the *early* IV crush; TP-50 captures it. No exit tweak rescues a
   thin credit.

## Honest caveats (READ before acting)

- **SINGLE REGIME.** Oct'24→Jul'26 only (~2 years). NOT validated on 2019→Sep'24 (bhavcopy
  purged). This repo's index-fade failure proves single-regime edges can vanish OOS. Treat
  0.35–0.40 as PROMISING, not PROVEN.
- Numbers are **gross of real-fill slippage** beyond the modeled 2.5%; plan ~⅓ lower on 4-leg
  mid-cap fills. +9.2% → ~+7% realistic; +1.1% → ~0/negative.
- The −65% avg loss = high variance; size small.

## Disposition

Keep the **≥0.40 book as the validated core** (unchanged). If deployed, **0.35–0.40 goes in as a
SEPARATE secondary tier** — 1 lot, tracked apart, labeled unvalidated-OOS — never merged into the
core book's stats. **Validate on 2019–24 bhavcopy before trusting it.** REPORT-ONLY pending the
engine two-tier split (spec in HANDOFF) and user review — the two-tier deployment is a live change,
not done in the session that produced this.
