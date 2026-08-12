# The CAS close is real — but NSE and BSE strike different ones

**Test:** pull every NIFTY-50 and SENSEX-30 constituent at **15:16** (the last continuous print) and
compare with that stock's **official close** (the auction equilibrium), on 3/4/5-Aug-2026. Then
check each index's own 15:15→close move against its own constituents.
**Data:** Upstox 1-min, NSE_EQ and BSE_EQ keys for the same ISINs. `scratchpad/constituents.py`,
`scratchpad/bse_vs_nse.py`.

## 1. Continuous trading really does stop at ~15:15

```
RELIANCE (NSE)  15:10 1307.4 | 15:14 1309.0 | 15:15 1309.0 | 15:16 1309.0
                15:20 1309.0 | 15:25 1309.0 | 15:29 1319.0 | official close 1319.0
```
Flat from 15:14 to 15:25, then the auction price prints at 15:29. Every constituent behaves this
way. There is no 15:16 "market price" distinct from the 15:15 one.

## 2. Both indices ARE consistent with their own constituents

Equal-weighted mean of constituent 15:16→close moves vs the index's own move:

| day | NIFTY-50 stocks (NSE) | NIFTY index | gap | SENSEX-30 stocks (BSE) | SENSEX index | gap |
|---|---:|---:|---:|---:|---:|---:|
| 3-Aug | +0.812% | **+0.818%** | +0.006pp | −0.095% | **−0.048%** | +0.046pp |
| 4-Aug | +0.668% | +0.619% | −0.049pp | +0.065% | +0.133% | +0.068pp |
| 5-Aug | +0.233% | +0.222% | −0.011pp | +0.061% | +0.101% | +0.040pp |

Reconstructed 3-Aug closes from the 15:16 index level:
* NIFTY 24573.35 × (1+0.812%) = **24772.9** vs actual **24774.30** — 1.4 points out.
* SENSEX 78677.13 × (1−0.095%) = **78602.4** vs actual **78639.03** — 37 points out.

Neither index print is an artifact. Each faithfully reflects its own exchange's auction.

## 3. The gap is BETWEEN THE EXCHANGES

The same 30 companies, same session, same 15:16 price — but different closes:

| day | SENSEX-30 auction move on **BSE** | same 30 stocks on **NSE** |
|---|---:|---:|
| 3-Aug | −0.095% (median −0.002%) | **+0.791%** (median +0.886%) |
| 4-Aug | +0.065% (median 0.000%) | +0.651% |
| 5-Aug | +0.061% (median 0.000%) | +0.196% |

**BSE's closing auction barely moved prices at all** — the median SENSEX-30 stock moved 0.00% on
every one of the three days. NSE's auction repriced the same names by up to 2%.

3-Aug closing price for the same share, NSE vs BSE:

| stock | NSE close | BSE close | gap |
|---|---:|---:|---:|
| TITAN | 5000.00 | 4900.00 | **+2.04%** |
| ASIANPAINT | 2810.00 | 2755.00 | **+2.00%** |
| AXISBANK | 1272.00 | 1252.00 | +1.60% |
| BAJAJFINSV | 2096.00 | 2065.00 | +1.50% |
| M&M | 3428.60 | 3385.50 | +1.27% |
| ICICIBANK | 1460.00 | 1444.20 | +1.09% |
| RELIANCE | 1319.00 | 1309.00 | +0.76% |
| TECHM | 1649.00 | 1650.00 | −0.06% |

Mean gap ≈ **0.89%** with NSE higher. That is a very large cross-exchange dislocation in the
official closing price of India's most liquid shares.

## 4. Which one was closer to fair?

The next session's open reconciles them. SENSEX closed 3-Aug at 78639.03 and **opened 4-Aug at
79132.97, +0.63%** — moving most of the way toward where NSE had already closed. NIFTY closed
24774.30 and opened 24703.90, −0.28%. They converged from opposite sides, with BSE doing ~2/3 of
the travelling.

Read: **BSE's auction was the stale one on 3-Aug**, plausibly thin participation in the first
sessions of the new regime. Three days cannot prove that, and this should be re-checked as the
recorder accumulates data.

## 5. Why this matters for the option work

This resolves the NIFTY 3-Aug puzzle in `ENTRY_TIME_AND_DECAY.md`. The parity forward from the
options sat at 24583.7 while the index closed 24774.30. The index was **right**. What actually
happened is that **the NSE cash auction moved ~0.8% away from the derivatives market and the
derivatives never followed within the session** — the forward was still 24589.9 at 15:39.

So the post-15:15 divergence is real and it is between **cash and derivatives**, not an index
calculation error. Options continue to price off futures; the cash auction goes where it goes.
Anything that settles on the cash close and anything that settles on a derivatives VWAP can differ
by ~0.8% on the same day.

## Limits

Three sessions, all of them the first three of the new regime, when auction participation is least
likely to be representative. Equal-weighted constituent means, not free-float cap-weighted — the
actual index weights are not held locally. That is defensible here only because the moves are
broad-based (26 of 30 SENSEX names moved >0.25% on NSE on 3-Aug, and the BSE median was 0.00% on
all three days), so no plausible weighting changes the conclusion. It would not be defensible if
the moves were concentrated in a few heavyweights.

---

# Addendum — index rebuilt from constituents at 15:18 vs the official close

No assumed weights. The index is exactly linear in constituent prices with coefficients constant
within a session, so the weights were **recovered by least squares** on the continuous session
(09:15–15:14, 1080 one-minute observations across the three days). `scratchpad/rebuild_index.py`.

**Fit quality** — the recovered formula tracking the live index:

| index | RMSE | max error | R² |
|---|---:|---:|---:|
| SENSEX (30, BSE prices) | **2.03 pts** | 28.99 pts | 0.999869 |
| NIFTY (50, NSE prices) | **0.34 pts** | 2.68 pts | 0.999952 |

**Result:**

| index | day | calc @15:18 | live index @15:18 | calc from official stock closes | OFFICIAL index close | **difference** | |
|---|---|---:|---:|---:|---:|---:|---:|
| NIFTY | Mon 3-Aug | 24,573.28 | 24,573.35 | 24,773.24 | 24,774.30 | **+201.02** | **+0.818%** |
| NIFTY | Tue 4-Aug | 24,463.42 | 24,463.45 | 24,615.20 | 24,614.90 | **+151.48** | **+0.619%** |
| NIFTY | Wed 5-Aug | 24,570.22 | 24,570.20 | 24,624.65 | 24,624.65 | **+54.43** | **+0.222%** |
| SENSEX | Mon 3-Aug | 78,677.72 | 78,677.13 | 78,639.82 | 78,639.03 | **−38.69** | **−0.049%** |
| SENSEX | Tue 4-Aug | 78,325.03 | 78,324.56 | 78,430.78 | 78,428.95 | **+103.92** | **+0.133%** |
| SENSEX | Wed 5-Aug | 78,502.52 | 78,501.85 | 78,582.39 | 78,581.00 | **+78.48** | **+0.100%** |

Two checks that make this conclusive:

1. **calc @15:18 reproduces the live index to 0.07 pts (NIFTY) and 0.6 pts (SENSEX).** The frozen
   15:18 index value is exactly what the last traded stock prices imply — it is not stale in any
   other way.
2. **Rebuilding from the official stock closes reproduces the official index close to ~1 pt
   (NIFTY) and ~1–2 pts (SENSEX).** So the official index close carries no adjustment beyond its
   constituents' auction prices.

Therefore the whole difference is the **closing auction repricing the stocks**, nothing else.
Over the three days it totals **+407 NIFTY points** and **+144 SENSEX points**, all of it struck
after the last continuous trade.

---

# Addendum 2 — why the live NIFTY calc sat ~2 pts off, per-stock (6-Aug, in-market)

Measured at ~12:00 IST with the market open (`scratchpad/diag_nifty.py`):

| weights used | calc | live index | diff |
|---|---:|---:|---:|
| fit on 5-Aug (yesterday) | 24,659.76 | 24,658.45 | **−1.31** |
| fit on 6-Aug session-so-far | 24,658.75 | 24,658.45 | **−0.30** |

**~75% of the live error was day-old weights.** Refitting on today's session removes it. The
server now auto-refits every 30 minutes during market hours (plus the manual button).

**The per-stock "culprit" table is a trap, and is recorded here so nobody trusts it later.**
Ranking stocks by contribution shift `(w_today − w_yday) · P_now` shows ±100–150-pt swings on
individual names (COALINDIA +152, WIPRO −100, DRREDDY −104…) that almost perfectly cancel. That
is **collinearity, not corporate actions**: 50 highly-correlated regressors mean the least-squares
solution is unique only in aggregate — individual fitted weights are not the index's real
free-float weights and their day-to-day changes are mostly noise redistribution. Only the summed
calc is meaningful (RMSE 0.13–0.23 pts). Do not read single-name weight changes as events.

**Stale LTPs were a minor secondary cause:** TMPV and ETERNAL lagged their own 1-min closes by
~0.17–0.19% at measurement time; everything else was fresh. Explains sub-point jitter, not the
1.3-pt bias.

**Residual ~0.3 pt after refit** is sampling asynchrony (50 LTP timestamps vs the index tick are
not simultaneous) plus fit residual. That is the floor for this method; it is well under the
±3-pt jitter already documented for the live view.

---

# Addendum 3 — do stock FUTURES predict the cash auction print? (learn Mon+Tue, test Wed)

**Question:** futures trade 15:15→15:40 while cash sits in auction. Does the futures move
15:15→15:27 anticipate the cash auction print at ~15:28? (`scratchpad/fut_predict.py`,
all 50 NIFTY names, nearest-expiry futures, 1-min bars.)

**NO — on every test.**

| | corr(fut move, auction move) | futures-implied beats naive? | direction hit rate |
|---|---:|---|---:|
| Mon+Tue (train, n=100) | **−0.017** | 49/100 — coin flip | — |
| Wed (test, n=50) | — | 22/50, MAE 0.319% vs 0.292% naive | 23/40 (57%, ns) |

Futures were FLAT through the window (mean move +0.000%) while the cash auction moved +0.74% on
average. The six largest Wednesday auction moves (+0.71% to +0.87%) had futures moves of −0.15%
to +0.34% — no anticipation, sometimes the wrong sign.

**The "fitted" predictor is a cautionary tale.** Regressing on Mon+Tue just learns the constant
(+0.74% mean auction lift, b≈0). Applied to Wednesday, where the mean lift was only +0.29%, it
scored WORSE than doing nothing (0.519% vs 0.292% MAE). The auction lift's magnitude is not
stable enough to trade on three days of history; only its SIGN (positive on NSE, all 3 days,
mean +0.81/+0.67/+0.23%) is suggestive, and that needs the daily recorder to accumulate.

**Futures don't even converge AFTER the print.** Wednesday's futures-vs-auction gap was +0.207%
just before the print and +0.216% at 15:39 — the futures market simply ignores the cash auction,
consistent with Monday's index-level finding (parity forward 190 pts below the NIFTY close).
Cash-auction price and derivatives price are two coexisting prices for the same stock; neither
converges to the other intraday. Whatever settles on one vs the other inherits that gap.

---

# Addendum 4 — modelling the auction print itself (train Mon–Wed, test Thu 6-Aug)

**The exact CAS price cannot be recomputed from public data.** NSE strikes the equilibrium from
the auction ORDER BOOK: the price that maximises executable volume, ties broken by minimum order
imbalance, then proximity to the reference (15:15 last-traded) price. No retail feed carries those
orders. Anything buildable is a statistical model of the LIFT, not the mechanism.

**Thursday broke the pattern before any model could use it.** NIFTY auction lift by day:
**+201 → +152 → +54 → +8 pts** — monotone decay to nothing. Per-stock mean lift: train (Mon–Wed)
+0.571%, test (Thu) +0.059%. And SENSEX, inert for three days, jumped **+168 pts on its own
expiry day** (6-Aug) — the "BSE auction is dead" reading has an expiry-day exception.

**Every trained model lost to doing nothing** (`scratchpad/auction_model.py`, n=150 train /
50 test, features: 14:15→15:15 momentum, 15:00→15:15 momentum, day return — none correlate,
|r|≤0.24):

| model | train MAE | Thu MAE | Thu NIFTY index error |
|---|---:|---:|---:|
| naive (lift = 0) | 0.605% | **0.201%** | **−8.05 pts** |
| constant (train mean) | 0.395% | 0.533% | +132.5 pts |
| momentum r60 | 0.388% | 0.555% | +138.7 pts |
| full linear | 0.369% | 0.577% | +145.2 pts |

**Conclusion:** the Mon–Wed lift was a TRANSIENT of the regime change (institutional flow finding
the new auction), already decayed by day 4. With it gone, the live calculated index at 15:15 IS
the best available estimate of the 15:29 print — Thursday it was 8 pts off on NIFTY. Models
trained on the transient days actively mispredict (+133 to +145 pts). Do not deploy an auction
model on this history; let the daily recorder accumulate a real sample, and re-examine only if
the lift re-emerges with a stable driver (watch expiry days on BOTH exchanges separately).

**Ops note (fixed 7-Aug):** the scheduled 15:50 calc-vs-print run failed on 6-Aug — the official
close needs the DAILY bar, which does not exist same-day (stale-bar trap). Now uses the intraday
last print (== auction close, verified) for today, and the default run also re-records the prior
session (idempotent), so any miss self-heals next day.
