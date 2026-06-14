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

## Run E — Chasing 70%+ win rate (the honest way: train/test + costs)

Request: "take the winners, devise signals for >70% win rate." Fitting rules to
past winners = overfitting, so instead: split 120 days into LEARN (first 60%) and
PROVE (last 40%), find the high-win rule on LEARN, validate on unseen PROVE data.

### 70%+ win rate IS achievable — and it survived out-of-sample (not overfit)
With a **small target + wide stop** exit (target 0.2-0.3%, stop 2-3%):
| exit | overall win | TRAIN win | TEST (unseen) win |
|------|-------------|-----------|-------------------|
| tgt 0.2% / stop 3% | 82% | 81% | **85%** |
| tgt 0.3% / stop 3% | 73% | — | ~84% |

The win rate held on data the rule never saw → it's a **real structural property**, not
curve-fitting. (It comes from the EXIT asymmetry, not a predictive signal — entries are
~random directionally; you just book tiny gains fast and give losers room.)

### But it does NOT make money after costs — the fatal catch
| target | stop | win% | gross exp%/trade | net @0.05% cost | net @0.10% cost |
|--------|------|------|------------------|-----------------|-----------------|
| 0.2% | 3% | 82% | +0.058 | +0.008 | **−0.042** |
| 0.3% | 3% | 73% | +0.067 | +0.017 | **−0.033** |
| 0.5% | 3% | 61% | +0.082 | +0.032 | −0.018 |

- 70%+ win rate **requires target ≤0.3%**. But intraday round-trip cost (brokerage + STT +
  exchange + GST + stamp) is **~0.10%** — larger than the 0.06-0.07% gross edge.
- So on the **underlying/equity**, the high-win setup is **net-negative after real costs.**
- On **options**, the leverage cuts BOTH ways: the wide 3% underlying stop becomes a
  catastrophic premium loss (−30-40%), so 25% losing trades can swamp 75% small wins.
  Whether option net P&L is positive is **unknown** — it needs forward testing on real
  option premium (can't backtest expired contracts).

### Honest verdict on "70%+ win rate"
- ✅ Achievable and out-of-sample robust (~73-85%) via small-target/wide-stop exit.
- ❌ Not profitable after costs on equity; unproven (likely negative) on options.
- This is the textbook **"high win rate, no edge"** outcome: the win rate is real, the
  PROFIT is not. The only honest way to settle the options version is to paper-trade it
  forward on live option premium for 30+ sessions and read the actual P&L.

## Run F — BUY options on REAL premium (the first encouraging result)

Method: recent 20 sessions (option premium only exists for current contracts).
For each signal BUY the ATM option (CALL=long, PUT=short), exit on the PREMIUM.

### Premium-exit sweep (ranked by win rate)
| premium target | premium stop | trades | win rate | exp/trade | net |
|----------------|--------------|--------|----------|-----------|-----|
| **+10%** | −20% | 13 | **77%** | +3.74% | +48.6% |
| +15% | −20% | 13 | 69% | +2.21% | +28.7% |
| +20% | −20% | 13 | 62% | −0.10% | −1.3% |

**Booking a quick +10% on the option premium with a −20% stop → 77% win rate AND
positive expectancy (+3.74%/trade) on real data, buying only.** The leverage makes the
small-target/wide-stop pattern actually pay (unlike on the underlying).

### Caveats (why it's "promising", not "proven")
- **Only 13 trades / 7 active days** — far too small to trust (77% = 10W/3L).
- All **stock** options; NIFTY/BANKNIFTY fired 0 signals in 20 days (indices are calmer).
- **Recent-only** — can't extend back (expired contracts unavailable).
- **Costs not modelled** — stock-option bid-ask + STT could eat part of +10%
  (index options have tighter spreads, but those didn't fire).

### Implemented as the live config (forward-test to confirm)
- `OPTIONS_ONLY_MODE = True` · BUY CALL (long) / PUT (short) only
- `PREMIUM_TARGET_PCT = 10` · `PREMIUM_STOP_PCT = 20`
- Dashboard PM screen now shows the exact order: strike, expiry, live premium,
  target/stop premium, lot, capital — e.g. `BUY NIFTY 23600 CE 16-Jun @ Rs179` ·
  tgt Rs197 · stop Rs143 · cap Rs11,654.
- NIFTY/BANKNIFTY added to the scan (low capital: Nifty ~Rs12k/lot, BankNifty ~Rs28k).
- **The honest test is forward**: paper-trade this for 30+ sessions; if 77% holds on a
  real sample after costs, it's an edge. If it reverts to ~50-60%, it was small-sample luck.

## Run G — 30-day option test (the 77% was small-sample luck)

Larger sample (30 days, 14 stock-option trades; Nifty/BankNifty fired 0 signals).
Tested target +10% with various stops:

| target / stop | win rate (hit target) | win rate (closed green) | exp/trade |
|---------------|----------------------|-------------------------|-----------|
| +10% / −10% | **50%** | 64% | +3.56% |
| +10% / −15% | — | 64% | +2.49% |
| +10% / −20% | 50% | 71% | +3.47% |

### Conclusion
- The earlier **77% (13 trades) / 88% (8 trades)** were **small-sample artifacts**. On 30 days
  nothing clears 70% — real win rate is ~**50–65%**.
- Tested the user's requested **10%/10% (1:1)** → 50% target-hit / 64% green → **below 70%,
  NOT implemented** (per the rule "implement only if >70%").
- Config left at +10% / −20% (the least-bad of the set; 71% green but only 14 trades).
- Net is positive (+3.5%/trade) but on 14 trades that's not trustworthy, and costs aren't modelled.
- **Verdict unchanged: promising mechanics, NO proven edge. Only a 30+ session forward
  paper-test on live premium (with real costs) can settle it.**

## Open questions / next steps
- **Lower OPTION_CONVICTION_THRESHOLD** (e.g. 0.70 → 0.60) so CALL/PUT actually trigger,
  then re-run the option-premium sweep (the infra is built and proven to fetch premium).
- Cutoff at 1 PM may be too tight — frequency drops below target. Consider 1:30-2:00 PM,
  or time-scaled targets (smaller target later in the day).
- 5% underlying target is unrealistic for intraday futures; either lower it (e.g. 2-3%)
  or model options on premium data.
- Samples are small (9-14 signals). Need 50-100+ signals before any number is trustworthy.
- The paper-trading month remains the real test.
