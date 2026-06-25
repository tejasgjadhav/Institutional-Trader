# Study: Real-option 180-day optimization — the min-premium edge

## Breakthrough: real expired-option data
Upgrading to **Upstox Plus** unlocked the *expired-instruments* API (`engine/expired_options.py`),
which serves real historical option premiums for **expired** contracts back ~18–21 months. This
removed the core limitation that had capped every option backtest at ~1 month and forced the
long validations to use the underlying as a directional proxy. We re-ran everything on **real
option premiums, 180 days**.

## The sobering first result
Real option backtest, the live config (gates 1–5, **+10/−20**), 205 trades, Oct 2025→May 2026:

| | Win % | Profit (gross) |
|---|---|---|
| ALL | 59% | **−0.9%** |
| TEST (held-out 40%) | 57% | **−2.2%** |

**The win rate was fine; the risk-reward was upside-down.** A +10/−20 exit (1:2) needs a **66.7%**
win rate to break even; the gates delivered 59%. So it lost money even *gross*.

## The optimization (rounds, all train/test split)
- **Round 0 — target/stop sweep:** profitable configs all *flipped* the reward-risk (+30/−10),
  but at a low ~36% win.
- **Round 1–2 — winner/loser + "1-bar confirmation":** a tantalising "80% win on 1st-bar
  follow-through" pattern turned out to be **look-ahead** — entering realistically (next bar,
  higher price) it was **negative on every test config**. Rejected. (Classic overfit; the
  train/test discipline caught it.)
- **Round 3 — rich features, train vs test side by side:** the gates we relied on (extension,
  ORB-width, alignment-alone) **did not hold out-of-sample**. Two signals *did*:
  **momentum_z ≥ 1.0** and, dominantly, **option premium ≥ ₹30**.
- **Round 4 — robust filter:** `premium ≥ ₹30 AND aligned`, exit **+10/−15**.

## The finding (deployed)
| | Trades | Win % | Profit | avg Win/Loss |
|---|---|---|---|---|
| Old (all options, +10/−20) | 485 | 54% | **−1.5%** | +9.7 / −16.3 |
| **NEW (premium ≥₹30 + aligned, +10/−15)** | 97 | **63–64%** | **+1.0 to +1.5%** | +9.8 / −13.6 |

Held-out TEST alone: **64% win, +2.1%** (53 trades). Both train and test positive.

## Why it works — and why it's cost-robust
Cheap OTM "lottery" options (avg **₹38**) are where the losses concentrate — they decay to
nothing intraday. Richer options (≥₹30, avg **₹101**) follow through far more reliably, **and**
their % bid-ask spread is ~**3× smaller** (₹0.5 on ₹100 = 0.5%, vs ₹0.5 on ₹10 = 5%). So the
min-premium filter improves the gross number *and* shrinks the biggest hidden cost — the first
config that actively helps net survival. The −15 stop (vs −20) drops breakeven win from 67% →
**60%**, below the realised ~64%.

## Deployed config (2026-06)
- **Drop G4 (extension) and G5 (ORB-width)** — didn't hold out-of-sample.
- **Add MIN_OPTION_PREMIUM = ₹30** (in the liquidity gate) — the real edge.
- **Keep G3 alignment** (robust). **Stop −20 → −15** (stock + index).
- ~0.8 stock signals/day (selective). Index: trend-ride with −15 stop.

## Honest caveats
97 trades / ~6 months — decent, not huge; +1.5% is modest and still **gross** (the rich-option
filter mitigates but doesn't erase the spread). The real judge is the **forward paper log** on
this config. Events were NOT testable (NSE scrape is live-only, no historical event data).
