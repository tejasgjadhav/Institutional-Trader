# How many days to expiry? The first test of a rule nobody had measured (17-Aug-2026)

`STOCK_CREDIT_MIN_DTE = 10` has governed every stock signal this system has ever fired, and until
today **no study in this repo had tested it.** Every study that mentions DTE holds it fixed at 10
while sweeping something else, and the only "DTE sweep" on record belongs to the rejected low-c/w
rescue. It appears to have been inherited from the index swing book, where the comment calls 10 "the
sweet spot" without naming a file.

## Why it was worth testing

The user found the reason on 17-Aug. On that day the floor pushed the books past the 25-Aug expiry
and into 29-Sep, 43 days out, where ASIANPAINT's 2640 PE had **zero open interest and no last
trade** — a quote of ₹41.95 bid against ₹64.95 ask, a 44% spread, on a contract nobody had touched.
So the rule may be *creating* the illiquidity that the open-interest gate then filters out.

His counter-hypothesis, which this measures directly: a lower floor gives more signals, but the
**₹50 premium floor starts to bite**, because a nearer expiry carries less time value. Both effects
are real and they push opposite ways.

## Method

`studies/ndte/dte_sweep.py`, in-sample, bhavcopy 2019-01-01 → 2024-09-30, 1,418 sessions, full
universe. Everything else is the harness of record: legs joined by date, spot from put-call parity,
open interest required on both legs at entry **and on every exit-check day**, one open position per
symbol, the live hierarchy, exit costs charged, no stop. Read on the median cohort, c/w 0.40–0.50
(v0: 0.35–0.40), where all 21 real live fills sit.

## The result

**v2 — the deployed 10 days is the peak, and it looks like a real optimum.**

| DTE ≥ | n | WIN | ROM-₹ | ₹/trade | signals/mo | ₹/month | +ve yrs |
|---|---|---|---|---|---|---|---|
| 3 | 173 | 79.2% | +23.2% | ₹4,907 | 2.6 | ₹12,862 | 6/6 |
| 5 | 187 | 79.7% | +26.2% | ₹5,628 | 2.8 | ₹15,946 | 6/6 |
| 7 | 191 | 79.1% | +26.4% | ₹5,498 | 2.9 | ₹15,912 | 6/6 |
| **10** | **217** | 78.8% | **+27.2%** | **₹5,798** | 3.3 | **₹19,063** | 6/6 |
| 15 | 247 | 77.7% | +19.9% | ₹4,592 | 3.7 | ₹17,184 | 6/6 |
| 20 | 240 | 77.1% | +20.4% | ₹4,773 | 3.6 | ₹17,355 | 6/6 |
| 25 | 213 | 75.1% | +19.6% | ₹5,119 | 3.2 | ₹16,520 | 6/6 |

It rises smoothly to 10 and falls away after, on both ROM and rupees per month. A smooth peak with
agreeing neighbours is what a real optimum looks like; a spike between two low cells is what noise
looks like. The inherited assumption is correct for v2.

**v1 — runs the opposite way, and its deployed setting is its WORST cell.**

| DTE ≥ | n | WIN | ROM-₹ | ₹/trade | ₹/month |
|---|---|---|---|---|---|
| 3 | 303 | 80.2% | +13.1% | ₹2,127 | ₹9,766 |
| 5 | 322 | 81.1% | +13.3% | ₹2,341 | ₹11,421 |
| 7 | 336 | 81.2% | +12.9% | ₹2,357 | ₹11,998 |
| **10** | 359 | 79.1% | **+10.3%** | ₹2,016 | ₹10,967 |
| 15 | 359 | 79.7% | +13.5% | ₹2,696 | ₹14,665 |
| 20 | 340 | 80.0% | +14.1% | ₹3,056 | ₹15,745 |
| **25** | 283 | **82.7%** | **+17.5%** | **₹4,270** | **₹18,309** |

v1 improves almost monotonically as the tenor lengthens. At 25 days it wins more often, earns twice
as much per trade, and would be worth roughly ₹7,300 a month more than the deployed 10 — on fewer
trades. That is the single most actionable finding in this study.

**v0 — a spike at 10, which is the shape of noise.**

+9.8% at 7 days, **+14.4% at 10**, then +8.0% at 15. One cell at nearly twice its neighbours, on
n=237, is not an optimum. Positive 5 of 6 years at every floor.

## The premium-versus-liquidity tradeoff is real, and premium dominates

| DTE ≥ | rejected on premium ≥ ₹50 | rejected on open interest |
|---|---|---|
| 3 | **60,766** | 7,615 |
| 10 | 54,347 | 11,833 |
| 25 | 41,974 | 26,501 |

Premium rejections outnumber open-interest rejections roughly **eight to one** across the whole
grid. Shortening the tenor from 25 days to 3 costs about 19,000 extra premium rejections and saves
about 19,000 open-interest rejections — the two effects are of similar size and pull opposite ways,
exactly as the user predicted. The net optimum then lands differently per book, because v2's
2-OTM/width-4 geometry and v1's 1-OTM/width-3 geometry price time value differently.

## Verdict: change nothing yet

v2 is already at its best setting. v0's peak is noise. v1's result is genuinely interesting and
points at 25 days, but **this is in-sample only, and in-sample is the window that chose these
parameters in the first place.**

The take-profit sweep is the cautionary precedent: v1's TP slope **inverted** between windows — lower
was better in-sample, higher was better out-of-sample — which is what a parameter carrying no
information looks like. A DTE result that only exists in-sample deserves the same suspicion,
particularly for v1, where the in-sample slope is smooth and monotonic in a way that would be very
easy to over-trust.

**The out-of-sample DTE sweep is the deciding test and has not been run.** Until it is, the deployed
floor stays at 10 for all three books.

## Open, and related

The in-sample open-interest buckets from the same run show ROM **decaying** as open interest rises —
v2 pays +38.2% at 2–5 lots and +2.4% at 25+. Either illiquid contracts genuinely carry richer
premium, or their marks are stale and flattering the result. If it is the latter, then a shorter
tenor helps twice over, because nearer strikes are more liquid. The out-of-sample window can
separate the two, because an Upstox candle exists only for a contract that actually traded, so
phantom trades cannot appear there at all.

Script: `studies/ndte/dte_sweep.py`. Data: `research/bhav_optstk.pkl`, rebuilt 17-Aug-2026 by
`studies/ndte/build_is_pickle.py`.
