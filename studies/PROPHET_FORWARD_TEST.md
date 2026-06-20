# Prophet Forward-Test (forecasting models — and why they don't help here)

Used Facebook **Prophet** to forecast NIFTY/BANKNIFTY prices and the strategy equity curve,
then cross-validated the forecast error. Analysis only — Prophet is **not** wired into the
live app.

## 1. Index price forecasts (20 trading days ahead, 80% band)

| | Last | +20d forecast | 80% range |
|---|------|---------------|-----------|
| NIFTY | 24,168 | 23,447 (−3.0%) | −6.8% to +0.8% |
| BANKNIFTY | 57,964 | 56,134 (−3.2%) | −6.8% to +0.2% |

## 2. Cross-validation — the forecast is worse than a coin flip

Rolling-origin CV (14 retrain cutoffs, predict 20 days each):

| Horizon | NIFTY error | BANKNIFTY error |
|---------|-------------|-----------------|
| 1–5 days | 1.9% | 2.7% |
| 16–20 days | **5.3%** | **9.3%** |

- The **20-day error (±5.3% / ±9.3%) is bigger than the move it predicts (−3%)** — the
  forecast carries ~zero information at that horizon.
- **20-day directional hit-rate: NIFTY 43%, BANKNIFTY 21%** — both *below* the 50% coin flip.
  Trading off Prophet's direction would lose money.

## 3. Equity-curve forecast — a statistical trap

Naive Prophet on the cumulative equity projected +₹45k/month with a *narrow, all-positive*
band. That is an **artifact**: forecasting a cumulative (integrated) series gives falsely
confident bands, and it extrapolated an early hot streak. The honest projection from the
**daily** P&L distribution: **+₹14k/month, 80% range −₹5k to +₹33k, ~17% chance of a losing
month** — and gross of costs.

## Verdict

Daily-horizon markets are near-random; Prophet's strengths (trend + seasonality) don't
transfer. The only real forward-test is the live paper month with real fills. Kept out of
the app deliberately.

Reproduce: `studies/` Prophet scripts (require `prophet`, `matplotlib`). *Generated 2026-06-20.*
