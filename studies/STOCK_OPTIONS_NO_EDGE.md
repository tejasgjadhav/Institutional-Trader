# Study: Intraday NSE stock-option BUYING has no net edge (definitive)

## Mandate
Find the highest-performing intraday NSE stock-options *buying* strategy on real option data,
net of realistic costs, validated out-of-sample. Reject anything that isn't robust.

## Data (the upgrade that made this honest)
Upstox Plus **expired-instruments API** (`engine/expired_options.py`) provides real historical
premiums for expired contracts (~18 months). So everything below is on **actual option P&L**,
not the underlying proxy. Underlying 5-min limits the window to ~1 year; this study uses 180
days of ORB+alpha signals (rich feature set) + 18 months of gap-reversal signals.

## Cost model (NSE options, round-trip, per trade)
Brokerage (Rs20×2) + STT (0.0625% on sell premium) + exchange txn (~0.035%) + GST (18% on
brokerage+txn) + stamp (0.003%) + **premium-dependent bid-ask/slippage** (≈ clamp(60/premium,
1%, 6%) — rich options ~1–1.7%, cheap options ~5–6%). This is realistic-to-generous.

## Gate 2 (ORB) — verified applied
All 485 ORB+alpha signals are ORB-confirmed: 0 below the 1.2× volume-surge threshold,
vol-ratio 1.2–145, every microstructure non-zero. The poor results are NOT a missing-gate bug.

## What was tested and found (all NET of costs, 120d train / 60d holdout)

| Strategy | Trades | Best holdout NET | Verdict |
|---|---|---|---|
| Alpha+ORB+gates+min-premium (deployed) | 59–289 | ~breakeven, **neg. expectancy**, <100 tr | ❌ |
| **Mix-and-match: 3,312 filter combos** (z, momentum, trend-quality, vol-surge, ORB-width, VIX, day-range, time, alignment, min-premium × exits) | ≥100 each | **0 of 3,312 cleared the bar** | ❌ |
| Oops gap-reversal — stocks (1,656 trades) | 1,656 | **−2.2%** (best), PF<1 | ❌ |
| Oops gap-reversal — index (130) | 130 | negative / noise | ❌ |

**Robustness bar** (mandate's own rules): train net>0 AND holdout net>0 AND ≥100 trades AND
holdout PF>1. **Nothing met it.** Several configs were positive on train and sharply negative on
holdout (textbook overfit); a tempting "1-bar confirmation" pattern was look-ahead and failed.

## The conclusion — structural, not a parameter problem
**No intraday NSE stock-option *buying* strategy in this sample produces a net-positive,
out-of-sample, ≥100-trade edge after realistic costs.** The reason is structural: buying options
pays the **bid-ask spread + STT on every round trip (~2–4% of premium)**, and a ~50–55%
directional hit rate on a leveraged payoff cannot consistently cover that. More iteration against
the same data only manufactures overfit — proven repeatedly here.

## Recommendation
- **Do not allocate capital to intraday stock-option buying.** It is structurally negative-EV
  net of costs; this is a documented, rigorously-tested result, not a tuning gap.
- The only durable signal in the whole system is the **thin index trend-ride** (+0.9% *gross*
  over 18 months — costs thin even that).
- The structural fix for "edge eaten by costs" is **selling premium** (collect spread+theta
  instead of paying it) — out of scope (the mandate forbids it, correctly for risk).
- Treat the system as what it is: a disciplined paper forward-test and a research engine whose
  real value is **honestly disproving losing ideas before they cost money** — which it did here.

## Method note for the record
This negative result is strong *because* of the discipline: real option premiums, full costs,
held-out validation, a ≥100-trade floor, and a 3,312-config systematic search. A less rigorous
study would have reported one of the in-sample "winners" (e.g. +1.5% on 180 days) and been wrong.
