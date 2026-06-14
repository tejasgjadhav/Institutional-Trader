# Backtest Results

Honest record of what the strategy actually produced on real Upstox data.
Updated whenever parameters change.

## Configuration tested
- Cutoff: **no new trades after 1:00 PM**
- Targets: **1% (cash equity)**, **5% (futures + CALL/PUT options)** — measured on the *underlying* price
- Stop: 1% from entry (all instruments)
- Gates: |alpha-z| > 0.55 AND ≥2 of 3 families agree AND 5-min ORB breakout + volume

---

## Run A — 3 trading days (Jun 10-12), targets 2% (old), cutoff 3 PM
- Frequency: **4.7 names/day** (1, 2, 11)
- Target-hit rate: **14%** (2 of 14)
- Most signals fired 1-3 PM and force-closed; net +6.89% was drift on a trend day, not target hits.

## Run B — 15 trading days (May 25 - Jun 12), targets 1%/5%, cutoff 1 PM
- Signals: **9 total over 15 days = 0.6 names/day** (BELOW 1/day)
- Outcomes: **0 WIN · 2 LOSS · 7 FORCED**
- Target-hit rate: **0%** — not a single signal reached its target in 15 days
- Win rate 0% · Profit factor 1.38 · Net +1.14% (pure forced-close drift)

### What Run B tells us
1. **The 1 PM cutoff cut frequency hard** — from 4.7/day to 0.6/day. Most signals
   were firing 1-3 PM; cutting at 1 PM removed them. Below the 1-2/day target.
2. **The 5% underlying target was never hit intraday** in 15 days. A 5% move in the
   *underlying* price within one session is rare — every derivative signal force-closed.
3. **The 1% equity target was also never hit** (only 1 equity signal, force-closed +0.73%).

### Important caveat on the 5% target for OPTIONS
The backtest measures a 5% move in the **underlying stock price**. For CALL/PUT options,
a trader actually exits on a 5% move in the **option premium**, which — because of
leverage — happens on a much smaller underlying move (often <1%). So this backtest
**understates** option win rate: it is the correct model for *futures* (premium ≈ underlying)
but the *wrong* proxy for *options*. To test options properly we need historical
option-premium series (Upstox option-chain history), not underlying candles.

---

## Run C — Option-aware sweep, 15 trading days (May 25 - Jun 12)

Method: collect every signal's forward path once (OPTION PREMIUM for CALL/PUT,
underlying for equity/futures), then sweep cutoff × target × stop in memory.

### Headline finding: the strategy almost never produces options
Of **21 signals over 15 days** (1.4/day): **20 EQUITY · 1 FUTURE · 0 OPTIONS.**

Why: a signal is classified at its FIRST qualifying bar, where conviction has just
crossed the 0.55 gate — almost always in the 0.55-0.70 band → EQUITY (LONG) or
FUTURE (SHORT). |alpha-z| > 0.70 (the option trigger) essentially never happens at
entry. So the "5% on option premium" question is moot until options actually fire —
there are none to test. To make options trigger, lower OPTION_CONVICTION_THRESHOLD.

### Equity sweep (the real signal mix) — ranked by win rate
| cutoff | target | stop | signals/day | win rate | W/L/Forced |
|--------|--------|------|-------------|----------|------------|
| 15:00  | 0.5%   | 2.0% | 2.5 | **45%** | 9/0/11 |
| 15:00  | 0.5%   | 1.5% | 2.5 | 45% | 9/1/10 |
| 14:00  | 0.5%   | 2.0% | 0.9 | 43% | 3/0/4 |
| 15:00  | 0.5%   | 0.5% | 2.5 | 40% | 8/6/6 |

- **Best win rate ≈ 45%**, achieved with a tiny **0.5% target**. Still below the 52% go-live bar.
- Larger targets → lower win rate (most moves don't travel far intraday).
- **More than half of trades FORCE-CLOSE** (never reach target or stop) → the moves are
  small/choppy; the gates fire late in weak momentum.
- "inf" / high PF rows are unreliable: PF here ignores forced-close P&L.

### Honest conclusion
- This is, in practice, an **equity-long intraday strategy** (~95% of signals).
- Its best achievable win rate on 15 days of real data is **~45%** with a 0.5% target —
  not yet a proven edge, and below the 52% bar.
- Options can't be evaluated until the conviction threshold is lowered so they fire.
- 21 signals is still a small sample.

## Run D — 120 trading days, 2:1 reward:risk (stop = target/2) — THE REAL TEST

Method: 120 days, all 95 stocks, **379 signals** (a genuine sample at last).
Stop fixed at exactly half the target (your rule: 5%→2.5%, 1%→0.5%). Swept
conviction (alpha ≥ 0.55-0.85), breadth, cutoff, and target to maximise win rate.
Signals: 193 CALL · 102 PUT · 29 FUTURE · 55 EQUITY (simulated on the **underlying**
directional move — 120-day option premium isn't available for expired contracts).

### Win-rate sweep (combos with ≥40 signals = trustworthy), ranked by win rate
| alpha≥ | breadth | cutoff | target | stop | signals | /day | **win rate** | net% | exp%/trade |
|--------|---------|--------|--------|------|---------|------|----------|------|------------|
| 0.75 | 2 | 13:00 | 1.0% | 0.5% | 59 | 0.7 | **34%** | +7.3 | +0.124 |
| 0.55 | 2 | 13:00 | 1.0% | 0.5% | 75 | 0.9 | 31% | +5.7 | +0.076 |
| 0.65 | 2 | 13:00 | 1.0% | 0.5% | 69 | 0.8 | 30% | +3.8 | +0.055 |
| 0.85 | 2 | 15:00 | 0.5% | 0.25% | 228 | 2.6 | 30% | −3.3 | −0.014 |
| 0.55 | 2 | 15:00 | 0.5% | 0.25% | 379 | 4.3 | 28% | −5.0 | −0.013 |

### THE HARD TRUTH — no durable edge at 2:1 R:R
- **A 2:1 strategy needs >33.3% win rate just to break even** (risk 1 to make 2 means you
  break even at 1-in-3). The best combo is **34%** — right at breakeven, no real edge.
- **~28-34% win rate is exactly what RANDOM entries produce at 2:1.** Over 379 signals the
  strategy shows essentially no directional edge.
- Best combo expectancy: **+0.124%/trade** — statistically indistinguishable from zero,
  and that's the *single best* of 200 combos (likely in-sample luck).
- Stricter conviction (alpha 0.75) and a 1 PM cutoff help marginally, but not enough.

### Why the earlier "45%" was an illusion
That 45% used target 0.5% with a **2% stop** — i.e. risking 2% to make 0.5% (R:R 0.25).
You "win" often but each loss erases four wins. Under your sane 2:1 rule the honest win
rate is ~30%. **High win rate and good R:R are in tension; without an edge you can have
one but not both.**

### Bottom line
- The win rate you can achieve at 2:1 is **~34% (breakeven), not higher.**
- The strategy does not demonstrate a tradeable edge over 120 days of real data.
- Trade log for the best combo: `trade_log_120d.csv` (59 trades, +7.3% net over ~6 months).
- Options can't rescue it: option P&L tracks the underlying direction, which is ~random here,
  and options add theta decay on top.

## Open questions / next steps
- **Lower OPTION_CONVICTION_THRESHOLD** (e.g. 0.70 → 0.60) so CALL/PUT actually trigger,
  then re-run the option-premium sweep (the infra is built and proven to fetch premium).
- Cutoff at 1 PM may be too tight — frequency drops below target. Consider 1:30-2:00 PM,
  or time-scaled targets (smaller target later in the day).
- 5% underlying target is unrealistic for intraday futures; either lower it (e.g. 2-3%)
  or model options on premium data.
- Samples are small (9-14 signals). Need 50-100+ signals before any number is trustworthy.
- The paper-trading month remains the real test.
