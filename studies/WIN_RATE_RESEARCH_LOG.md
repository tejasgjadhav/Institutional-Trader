# Win-Rate Optimization Study — Index & Stock Options

**Goal of this research:** find a buy-only intraday options strategy with a **durable high win rate** (target: 70%, later relaxed to "any reliable edge"), validated **out-of-sample**, on NSE data via Upstox.

**Headline conclusion (read this first):**
> Across **seven independent methods**, the directional intraday signal sits at **~50–57% win rate out-of-sample** and does not durably exceed it. Every result that *looked* like 70%+ turned out to be one of three things: a **small-sample artifact** (n≈13–21 trades), a **look-ahead bug**, or an **unstable train/test partition** that fails when re-sampled. A genuine, sample-robust 70% — or even a reliable 60% — is **not present in this data**. The only edges that survive honest validation are (a) **exit asymmetry** (tight stop / large target → low win rate but positive expectancy) and (b) a **weak mean-reversion tilt** (fading extension beats chasing breakouts).

This document records every study, its method, its numbers, and its honest verdict — including the mistakes caught along the way.

---

## 1. Methodology (common to all studies)

- **Data:** Upstox V3 historical/intraday candles. 5-min bars for intraday, daily bars for trend context. Index futures used where index spot lacks volume (see §6).
- **Instrument traded:** buy-only options. LONG → CALL, SHORT → PUT. Outcomes measured on the **option premium** (what a trader actually exits on), not the underlying.
- **Validation:** every study uses a **temporal train/test split by day** (~55–60% train / 40–45% test). The TEST column is the only one that matters; the TRAIN column is shown precisely to expose overfitting (it is almost always inflated).
- **Win-rate honesty:** where possible, outcomes are scored at a **symmetric exit** (e.g. +20/−20) so the win rate is not a mechanical artifact of a tight target. Breakeven win rate = stop / (target + stop).
- **Costs:** all P&L figures are **GROSS of the bid-ask spread**, which on single-stock options is the great unmeasured cost. Index ATM options have tight, knowable spreads — a key reason index options are preferable (see §6, §9).
- **Data ceiling:** Upstox serves ~60 calendar days of 5-min history; option-premium history for older contracts thins out fast. Effective maximum depth in these studies is **~38 trading days (Apr 1 – Jun 12, 2026)**.

---

## 2. Study A — Directional signal ceiling (baseline)

**Question:** how high can the 3-family alpha / individual technical signals push win rate?

**Methods tried:** individual signals (RS, VWAP, GAP, MOM, VOL, ORB); K-of-N confluence; weighted composite (weights derived on train); logistic-regression ML classifier of winners vs losers.

**Results (out-of-sample):**
| Method | OOS win rate | Note |
|--------|-------------|------|
| Individual signals | ~57% | best single signals |
| K-of-N confluence | 57% flat, → 43% at high K | more agreement did **not** help |
| Weighted composite | ~60% | |
| ML (logistic regression) | train 79% → **test 24%** | textbook overfit; winners/losers statistically identical |

**Verdict:** the directional signal caps at **~57–60% out-of-sample**. The original "72% win rate" was an **18-trade artifact**; on large samples it regresses to ~48–60%. The breakeven for the then-live +10%/−20% exit is 67%, which the signal cannot clear.

---

## 3. Study B — Risk-reward sweep (`rrsweep.py`)

**Question:** does any target/stop ratio achieve both high win rate AND profit?

**Setup:** 85 fixed-gate signals, 30 days (train 44 / test 41), 54 target/stop combinations.

**Result:** **no combination has both profitability and a high win rate** — they are mutually exclusive.
- High win rate (65–68%) only at wide-stop/small-target (R:R 0.2–0.3) → **loses money** (test −3.50/trade).
- Profit only at tight-stop/high-target (R:R 1.7–5.0) → **low win rate** (31–47%).
- Best OOS net: **+15%/−5% (R:R 3:1)** → 35% win, **+1.34/trade test**; and +15%/−3% (R:R 5:1) → +1.72/trade test.

**Verdict:** win rate and profit are structurally opposed for this signal. The profitable zone is **low-win / high-reward asymmetric**, not high-win.

---

## 4. Study C — ORB volume benchmark: opening-range vs rolling (`orbmode.py`)

**Question:** the original ORB used the *opening-range* volume average (strict, "early morning"); a later fix used a *rolling-recent* average. The strict version once showed ~78% — is it a genuine quality filter?

**Setup:** 30 days, train/test split, both benchmarks head-to-head.

**Results (+10/−20):**
| Benchmark | signals | ALL | TRAIN | **TEST** |
|-----------|---------|-----|-------|------|
| opening (strict) | 59 (2.0/day) | 58% | 69% | **47%** |
| rolling (current) | 80 (2.7/day) | 64% | 75% | **52%** |

**Verdict:** the remembered "78%" was the **TRAIN/in-sample** number; on held-out days the strict benchmark drops to **47%** — *worse* than rolling and below a coin flip. The selectivity hypothesis is **disproven**. Config kept on `rolling`.

---

## 5. Study D — Timeframe study: 5 / 10 / 15-min candles (`tf.py`, `tf60.py`)

**Question:** does a slower candle (fewer fakeouts) lift the win rate?

**Setup:** resample 5-min → 10/15-min, scale ORB (30-min) and momentum (60-min) windows, run identical gate, 30 and 60 days, train/test.

**⚠️ Look-ahead bug caught here.** The first run showed spectacular numbers — 15-min at **83% out-of-sample**, +20/−10 at 73%. It was *too clean*, which triggered an audit of the resampling code. The bug: each resampled candle was labeled with its **start** time, so the backtest entered the option ~15 min *before the candle completed*, capturing the very move that formed the breakout. **The entire result was the bug.**

**After fixing (enter at candle close, no peeking):**
| Timeframe | window | +10/−20 TEST | +20/−10 TEST | days net-winning |
|-----------|--------|------|------|------|
| 15-min | 60d (41 sig) | 42% | 33% | 12/23 = **52%** |
| 10-min | 60d (57 sig) | 50% | 33% | 14/27 = **52%** |

**Verdict:** with the leak removed, slower candles land on the **same ~52% wall** as 5-min. The wall is **timeframe-invariant** — strong evidence it's a property of the market, not the parameters. **Lesson: a backtest that suddenly solves the problem is usually a bug, not a discovery.**

---

## 6. Study E — ORB + VWAP on index options (`orbvwap.py`)

**Question:** test a specific, well-formed strategy — 15-min ORB + VWAP-hold + break-and-retest entry + ITM/ATM strike + structure exit (ride until underlying loses VWAP), on NIFTY/BANKNIFTY index options.

**Data discovery:** index **spot candles have Volume = 0** → VWAP impossible on spot. Fix: run ORB+VWAP on the **index futures** (real volume: NIFTY ~7.1M, BANKNIFTY ~1.2M/day, tracks the index). Option premiums for both indices (ATM + ITM) confirmed available, 75 bars/day.

**Setup:** 40 days (~27 with data), ATM & ITM strikes, stop 25/30/35%, with/without clean-trend filter, plus 4 exit modes.

**Results (the exit rule is the whole story):**
| Strike | Exit logic | n | Win% | Net/trade | TEST |
|--------|-----------|---|------|-----------|------|
| ATM | **spec** (exit on first VWAP touch) | 45 | 16% | −3.93 | 8% |
| ITM | spec | 48 | 21% | −2.95 | 7% |
| ATM | breathe (hold; arm VWAP only after +12%) | 45 | 53% | +0.50 | 48% |
| **ATM** | **breathe + clean filter** | 37 | **57%** | **+0.53** | **52%** |

**Verdict:** as literally specified, the strategy **loses badly** — entering on a retest *near* VWAP then exiting on the first tick back across VWAP is a hair-trigger that stops out on noise (44/45 trades exit on VWAP for a small loss). The only fix is to **stop honoring the VWAP exit early** — at which point what's actually working is just "buy ATM option on the ORB break, hold to EOD with a stop," and it lands back on the **same ~52% wall, breakeven gross**. The strategy's signature feature (the VWAP structure exit) is its weakness, not its edge.

**Useful byproduct:** index options are a genuine practical upgrade — tight, *measurable* spreads, unlike the 95-stock universe where spread is a black box.

---

## 7. Study F — Index-option factor study with decorrelation (`factor_study.py`)

**Question (user's framing):** study winners vs losers, carve out *uncorrelated* technical factors, group them with a statistical score, and see how high a win rate the composite reaches.

**Method:**
1. **Event set:** every 5-min bar 9:30–13:00, both indices. Direction = sign(close − VWAP) on futures. Buy morning-ATM option in that direction. Label = win at **symmetric +20/−20** (baseline ~50%, so any lift is a real edge).
2. **17 factors** across families: VWAP/location, momentum, volatility, volume/participation, structure, time-of-day, cross-index breadth. Each signed to favour the chosen direction.
3. **Decorrelation:** correlation matrix on TRAIN; greedily keep the highest-edge factor of each cluster with |r| > 0.7.
4. **Statistical score:** univariate edge = point-biserial corr(factor, win) on TRAIN. Composite = Σ(edge·z-score) over kept factors. Threshold swept on TRAIN, validated on TEST.

**The key finding — it's mean-reversion, not trend:** every "chase the breakout" factor has a **negative** edge:
| Factor | edge (r) | reading |
|--------|----------|---------|
| EMA9−21 spread | **−0.20** | more trend-aligned → *lower* win rate |
| ORB range | **+0.19** | wider opening (volatile day) → higher win rate |
| VWAP distance | **−0.14** | more extended past VWAP → *worse* |
| momentum / RSI | negative | chasing momentum *hurts* |

Decorrelation collapsed 17 factors → 12 (momentum, RSI, VWAP-distance, ORB-distance are largely one factor wearing several hats).

**Composite out-of-sample (first run, 40d → 33 days data, 14 test days):** win rate rose monotonically with the threshold — 48% → 53% → 56% → **59% at the top decile** (+2.33/trade, n=76). This was the most promising result of the study.

---

## 8. Study G — Robustness check: does Study F survive re-sampling? (`factor_study.py`, 30 vs 38-day windows)

**Question:** is the ~59% real, or a partition artifact? Re-ran the identical study on two overlapping windows.

**Result — the two windows flatly contradict each other:**
| Threshold | **Last 30 days** TEST | **Last 38 days** TEST |
|-----------|----------------------|----------------------|
| top 50% | 47% / −2.52 | 55% / −0.19 |
| top 30% | 47% / −3.18 | 61% / +0.81 |
| top 20% | 50% / −2.65 | 64% / +2.53 |
| top 10% | 58% / +0.90 | 81% / +10.13 (n=21) |
| 1 trade/day | **45% / −4.27** (n=11) | **75% / +5.04** (n=16) |

**Verdict — this falsifies the edge.** The 30-day window is a *subset* of the 38-day window, same factors, same method — yet one says "no edge, net-negative (~47%)" and the other says "60–81% edge." The result hinges entirely on which ~8 April days land in the split. The headline numbers are all small-sample (n = 16–21), and the *same* 1-trade/day metric flips from 45% to 75% just by changing the window. **Widening the sample didn't confirm the 59% — it broke it.** The only stable element is the mean-reversion **sign** structure, which is too weak to manufacture a reliable win rate.

---

## 9. Cross-cutting findings

1. **The ~52–57% wall is real and method-invariant.** It appears in individual signals, confluence, composites, ML, three timeframes, ORB+VWAP, and a 17-factor decorrelated study. That consistency is itself strong evidence it's a market property: intraday direction off price/volume is near-random out-of-sample.
2. **High win rate and profitability are mutually exclusive** for this signal (Study B). Profit lives in **exit asymmetry** (tight stop, large target, ~35% win, positive EV), not in win rate.
3. **Mean-reversion beats trend-chasing** (Study F). Fading extension from VWAP/EMA has a (weak) positive sign; chasing breakouts has a negative one. This is the one directional insight that repeats.
4. **Three recurring mirages** produced every false "70%+": **small samples** (n ≈ 13–21), a **look-ahead bug**, and an **unstable partition**. Each was caught only by widening the sample, auditing the code, or re-sampling the split.
5. **Index options > single stocks** for going forward: tight, measurable spreads make the one remaining unknown (transaction cost) knowable.

---

## 10. What actually survives honest validation

- **Asymmetric exit (+15%/−5%, R:R 3:1):** ~35% win, **+1.34/trade out-of-sample** (Study B). The most robust *profitable* config found. Gross of spread.
- **Weak mean-reversion tilt on index ATM:** ~55–59% in favourable samples, but **not stable** under re-sampling (Study G). Not trustworthy as a standalone edge yet.
- **Nothing reaches a durable 70%, or even a reliable 60%.**

---

## 11. Recommendation

Stop trying to mine a win rate the market is not offering. The defensible path forward is **forward paper-trading**, not more curve-fitting on ~15 test days:

1. **Forward-test the asymmetric config** (+15/−5, R:R 3:1) on index ATM options, logged, for one month — to measure the one thing backtesting cannot: the real spread cost.
2. Optionally, **forward-test the mean-reversion tilt** (fade VWAP/EMA extension on wide-range days, take profit on the bounce) in parallel — let live data, not partition luck, judge it.

Live forward data is now the only honest way to settle whether *any* of this is net-positive after costs.

---

## 12. Reproducibility

All study scripts are in this `studies/` directory and run against the live `engine/` modules:

| Script | Study | What it does |
|--------|-------|--------------|
| `rrsweep.py` | B | 54-combo risk-reward sweep with train/test |
| `orbmode.py` | C | opening vs rolling ORB volume benchmark |
| `tf.py`, `tf60.py` | D | 5/10/15-min timeframe study (incl. look-ahead fix) |
| `probe.py`, `probefut.py` | E | data-availability probes (index volume, option premiums, futures) |
| `orbvwap.py` | E | ORB+VWAP index-option strategy, 4 exit modes |
| `factor_study.py` | F, G | 17-factor decorrelation + composite, 30/38-day windows |

**Run:** `.venv/bin/python studies/<script>.py` from the repo root. All require a valid `UPSTOX_ANALYTICS_TOKEN` in `.env` (gitignored — never committed).

**Supporting engine changes made for this research (behavior-preserving defaults):**
- `config.py`: added `VOLUME_BENCHMARK_MODE = "rolling"` (Study C) and `MOMENTUM_BARS = 12` (Study D), both defaulting to existing behavior.
- `signals.py`: `is_orb_confirmed` and the momentum factor read those config values.
- `filter_backtest.py`: added +20/−10 and +10/−5 (2:1) outcome columns.

---

*Last updated: 2026-06-15. All P&L gross of bid-ask spread. TEST = held-out out-of-sample days; TRAIN shown to expose overfitting. Sample sizes are small (≤38 trading days available) — treat all numbers as directional, not definitive.*
