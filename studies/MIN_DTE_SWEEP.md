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

## OUT-OF-SAMPLE, 20-Aug-2026: the deciding test ran, and v1's result did NOT replicate

`studies/ndte/dte_sweep_5v10.py`, Upstox, entries 2025-10-08 -> 2026-07-22, 393 trades, median
cohort, floors 5 and 10 only. The book state is warmed from 2025-08-01 so the window does not open
with an empty book. **Zero signals were dropped on a fetch failure on either floor.**

| book | DTE | IS full | IS last yr | **OOS** | OOS n | OOS win | OOS Rs/mo | +ve months |
|---|---|---|---|---|---|---|---|---|
| v2 | 5 | +26.2% | +29.5% | +29.4% | 15 | 86.7% | Rs4,565 | 6/6 |
| v2 | **10** | +27.2% | +31.0% | +27.1% | 32 | 84.4% | **Rs9,365** | 7/9 |
| v1 | 5 | +13.3% | +15.5% | +10.7% | 81 | 79.0% | Rs8,544 | 7/10 |
| v1 | **10** | +10.3% | +9.5% | **+11.8%** | 100 | **80.0%** | **Rs12,034** | **8/10** |
| v0 | 5 | +7.5% | +6.9% | +6.8% | 51 | 80.4% | Rs4,293 | 7/10 |
| v0 | **10** | +14.4% | +13.0% | **+8.6%** | 66 | **83.3%** | **Rs7,007** | 7/10 |

**v1's slope inverted between windows.** In-sample 5 beat 10 in both cuts, and the recent-year gap
was wide (+15.5% against +9.5%). Out-of-sample 10 wins on ROM, on win rate, on trade count, on
rupees a month and on positive months - every column, one direction. This is the same signature the
take-profit sweep produced for v1, which this repo already records as what a parameter carrying no
information looks like. Two windows disagreeing is the answer, not a puzzle.

Bootstrapped 90% ROM intervals overlap almost entirely, so no floor is statistically separable:
v2 [+4.7%, +50.3%] at 5 vs [+12.6%, +39.8%] at 10; v1 [+0.2%, +20.2%] vs [+3.0%, +20.7%];
v0 [-5.2%, +18.2%] vs [-1.0%, +17.6%].

**The liquidity hypothesis was not confirmed.** The in-sample open-interest curve suggested that a
longer tenor buys illiquidity, and it does in bhavcopy. Out-of-sample DTE-10 produced MORE trades
than DTE-5 in every book. Premium rejections explain it: 11,275 at DTE-5 against 9,922 at DTE-10.
Shortening the tenor kills more candidates on the Rs50 premium floor than it rescues from thin
contracts.

**Limit on that claim.** Out-of-sample open-interest rejections are 4 and 5, effectively nil,
because an Upstox candle exists only for a contract that actually traded - a dead contract is
invisible rather than rejected. So this window measures the NET of premium and liquidity together
and cannot isolate liquidity on its own. The net favours 10, which is what governs deployment.

**A harness bug was found and fixed before this run, and it would have faked the answer.** `leg()`
returned an empty dict both when Upstox failed after six retries AND when a contract genuinely
never traded, so a network timeout silently deleted a signal. The two floors run sequentially, so
whichever floor ran while the API was slow would have shown fewer trades and been read as thinner
liquidity - the hypothesis under test. A failed request now returns None, only a `status ==
success` body counts as evidence of no trade, and drops are counted and printed per floor.

**DEPLOYED SETTING CONFIRMED: `STOCK_CREDIT_MIN_DTE` stays at 10 for v2, v1 and v0.** The DTE-25
result flagged below as "the single most actionable finding" was in-sample only and is superseded
by this table.

## Verdict at the time (in-sample only, superseded above): change nothing yet

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
