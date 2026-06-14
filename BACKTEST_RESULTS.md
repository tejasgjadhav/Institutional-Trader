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

## Open questions / next steps
- Cutoff at 1 PM may be too tight — frequency drops below target. Consider 1:30-2:00 PM,
  or time-scaled targets (smaller target later in the day).
- 5% underlying target is unrealistic for intraday futures; either lower it (e.g. 2-3%)
  or model options on premium data.
- Samples are small (9-14 signals). Need 50-100+ signals before any number is trustworthy.
- The paper-trading month remains the real test.
