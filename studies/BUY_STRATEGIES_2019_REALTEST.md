# BUY strategies on REAL 5-min data, ALL years 2019→date (Zerodha Kite)

The credit-spread fades could be tested back to 2019 because they're multi-day (daily option
closes from [NSE bhavcopy] suffice). The two **intraday BUY** strategies — ORB+VWAP index and
3-Family stocks — need *intraday* data, which Upstox only holds ~1–2 years back. **Zerodha Kite
Connect's historical API returns 5-min bars back to 2019**, so this is the first multi-year,
all-regime test of the BUY strategies.

**What can and cannot be tested.** Kite gives real 5-min *underlying* bars 2019→date. Intraday
*option premiums* for expired contracts do not exist anywhere historically (Kite has no
expired-instruments listing). So — exactly like `UNDERLYING_VALIDATION_365D.md` — this measures the
**real directional edge on the underlying** (signal → close move in the signal direction), NOT
option P&L. Direction only: no spread/theta/IV/−15% stop/costs.

## 3-Family — FULL gate stack, driven by the ACTUAL production code
Ran `engine.signals.compute_all_families` + `is_orb_confirmed` on the Kite 5-min bars, applying the
real gates: **Gate 1** (alpha-z > 0.55 AND ≥2 families agree), **Gate 2** (ORB break + 1.2× volume
surge), **Gate 3** (market alignment). Gates 4/5 are OFF in production (excluded). FLOW uses the
engine's own VIX/Nifty/volume fallback (real options flow isn't historical); EVENT neutral (no
historical news); Gate 6 liquidity is an option-level cost filter (can't reconstruct). 100/100
stocks, **19,454 full-gate signals**:

| Year | Signals | Hit% | Avg underlying move |
|------|---------|------|---------------------|
| 2019 | 2,687 | 53.3% | +0.236% |
| 2020 | 4,008 | 51.3% | +0.117% |
| 2021 | 3,086 | 46.2% | +0.017% |
| 2022 | 3,072 | 52.6% | +0.135% |
| 2023 | 1,597 | 49.3% | +0.140% |
| 2024 | 2,266 | 48.5% | +0.056% |
| 2025 | 1,669 | 53.4% | +0.079% |
| 2026 | 1,069 | 49.9% | +0.033% |
| **ALL** | **19,454** | **50.6%** | **+0.107%** |

**The gates are real — and this is a fairer verdict than "overfit."** A simplified proxy (ORB +
trend + alignment, WITHOUT the alpha-z and volume-surge gates) is a coin flip: 48% hit, −0.02%.
Adding the real Gate 1 (alpha-z) + Gate 2 (volume surge) lifts it to **50.6% hit, +0.107%/trade,
positive in EVERY year 2019→2026** — a small but genuinely durable directional edge, matching and
extending the 365-day study (+0.13%/trade) across 8 years and every regime.

**But a durable direction edge ≠ a profitable strategy.** +0.107% is the *underlying* move. The
strategy buys OTM+1 options, exits +10%/−15%: options leverage that lean ~10×, but theta, IV, the
bid-ask on entry+exit, the −15% stops, and Gate 6 liquidity eat it. That is exactly why the engine's
own **real-option 1-year test came in −1.0% net (55% win)** (`REAL_OPTION_OPTIMIZATION.md`). The
direction is real; the option-buying wrapper can't monetize it net of costs.

## ORB+VWAP index — real signal on Kite 5-min, trend-ride on the underlying
Reconstructed the faithful signal (15-min opening range + VWAP + 30-min trend + clean-trend filter,
per `engine/orb_vwap_live.py`; VWAP = equal-weight cumulative typical price, since index spot has no
volume). Measured the underlying move captured by the trend-ride exit (arm after a favorable move,
exit on VWAP reclaim, hard adverse stop, else EOD). 2,303 signals:

| Year | NIFTY hit / avg move | BANKNIFTY hit / avg move |
|------|----------------------|--------------------------|
| 2019 | 47% / +0.091% | 38% / +0.103% |
| 2020 | 30% / −0.060% | 32% / +0.138% |
| 2021 | 41% / +0.026% | 37% / +0.081% |
| 2022 | 44% / +0.084% | 36% / +0.038% |
| 2023 | 49% / +0.021% | 29% / −0.060% |
| 2024 | 45% / +0.057% | 41% / +0.056% |
| 2025 | 49% / +0.037% | 42% / −0.031% |
| 2026 | 35% / −0.028% | 33% / +0.017% |
| **ALL** | **42% / +0.031%** | **36% / +0.049%** |

**Verdict: a thin, inconsistent lean — weaker than the recent 18-month window implied.** Only
+0.04% of underlying move per trade at ~39% hit (the low hit-rate is the trend-ride's asymmetric
shape), and **negative in ~2 of 8 years per index** (NIFTY 2020/2026; BANKNIFTY 2023/2025). The
+0.9%/18-mo figure was on the favorable end. Options leverage it, but theta/IV/−15% stops/costs eat
most — matching the engine's "+0.8% gross → ~0% net" standing.

## Bottom line for the two BUY strategies
| | Signals | Hit | Avg move | Consistency | Net (option-buying) |
|---|---|---|---|---|---|
| **3-Family (full gates)** | 19,454 | 50.6% | +0.107% | positive **every** year | −1.0% (real-option yr) |
| **ORB+VWAP** | 2,303 | 39% | +0.040% | negative ~2/8 yrs per index | ~0% net |

3-Family's *directional* edge is more durable and consistent than ORB+VWAP's, and neither is
"overfit noise" — but **neither survives option-buying costs net.** They stay paper forward-tests.

## Reproduce
- Data source: [[zerodha-kite]] historical API, 5-min, `continuous=False`, tokens NIFTY 256265 /
  BANKNIFTY 260105 / stocks via `instruments("NSE")`. India VIX 264969 (FLOW proxy).
- 3-Family full-gate: `/tmp/family3_fullgate_bt.py` (drives the real `compute_all_families` +
  `is_orb_confirmed`; caches 5-min per stock in `/tmp/k5m/`). → `DONE-FAM3FULL`.
- ORB+VWAP: `/tmp/orbvwap_kite_bt.py` → `DONE-ORBVWAP`.
- Daily directional baseline: `/tmp/family3_daily_proxy.py`.
