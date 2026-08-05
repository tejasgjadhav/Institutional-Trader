# NSE session change, 3-Aug-2026 — what moved, what it broke, what we changed

On **3 August 2026** NSE changed the equity-derivatives session and how closing prices are struck.
The engine had the old session hardcoded in ~20 places, so several books were settling and signalling
against prices that no longer exist. This records the change, the measurements, and the fix.

## What actually changed

| | before | from 3-Aug-2026 |
|---|---|---|
| Equity **derivatives** close | 15:30 | **15:40** |
| **F&O stocks** continuous cash trading | to 15:30 | **to 15:15**, then auction |
| Closing Auction Session (CAS) | — | **15:15–15:35** (orders 15:20–15:30, random cutoff 15:28–15:30, match 15:30–15:35) |
| Cash close, F&O stocks | 15:30 | **15:35 — the auction equilibrium price** |
| Cash close, other equities | 15:30 | 15:30 (unchanged, 15:00–15:30 VWAP) |
| Derivatives closing price | 15:00–15:30 VWAP | **15:10–15:40 VWAP**, their own price, not the cash close |

**Every name in UNIVERSE is an F&O stock**, so all of them are auction-priced now. Index derivatives
also trade to 15:40, and index closing values derive from constituent auction prices.

## Measurement 1 — moving the scan GAINS signals

Replayed all 113 names for **3-Aug-2026**: which names break out on the 15:10 price (what the engine
used) versus on the official close (what a 15:36 scan uses).

| | breakouts |
|---|---|
| using the 15:10 price | **32** |
| using the OFFICIAL CLOSE | **46** |
| kept | 31 |
| LOST (fired at 15:10, gone by the close) | **1** — PNB |
| GAINED (missed at 15:10, present at the close) | **15** |
| **net** | **+14 (+44%)** |

Price drift 15:10 → close: **median 0.68%**, p90 1.12%, max 3.23%. **66 of 113 names moved ≥0.5%**,
17 moved ≥1.0%. The drift is the norm, not an outlier — the typical name moves 0.68% *after* the old
scan time. Gained names included ICICIBANK, KOTAKBANK, BAJFINANCE, HCLTECH, ADANIENT, HAL, BAJAJ-AUTO.

**So the 15:10 scan was not merely imprecise — it sampled a different price.** About a third of the
day's genuine breakouts never appeared at 15:10, and one name fired that the close contradicted.

*Limit:* this is the BREAKOUT count, not the fired-signal count. The c/w ≥ 0.40 gate applies on top,
and intraday option premiums cannot be replayed historically, so whether those 15 extra candidates
clear the gate is unmeasurable until it runs live.

## Measurement 2 — the 15:36–15:40 window is tradeable

Derivatives shut at 15:40, so the post-close order book **is** that window. Sampled 18 watchlist names
on 4-Aug at v2 geometry:

| | 14:45 (continuous, hedgeable) | close (15:36–15:40) |
|---|---|---|
| two-sided market | — | **17 / 18** |
| passes liquidity gate (spread ≤6%, OI ≥100) | — | **15 / 17** |
| typical spread | ~1.0% | **1.1–4.0%** |
| c/w (GRASIM / SIEMENS / COFORGE) | 0.35 / 0.29 / 0.29 | **0.38 / 0.30 / 0.31** |

83% clear the gate. The two failures (TATAELXSI 19.4%, JUBLFOOD 11.7%) and the one with no book
(BAJAJHLDNG, already 8.9% wide at 14:45) were marginal names anyway.

**c/w is stable across the auction** — it moves a point or two either way. Two consequences: the 15:17
watchlist is a good predictor of what fires at 15:36 (so a ~3.5-minute placement window is workable),
and the gate is not systematically easier or harder after the auction.

**COST CAVEAT that offsets part of the +44%:** spreads roughly **double**, ~1.0% → 2–4%. The cost
model `spf(p) = min(6, max(1, 60/p))%` assumes ~1% per leg, so it **understates entry slippage at
15:36**. More signals, each entered slightly worse.

## What we changed

**One session model** in `config.py` — `CASH_CLOSE` 15:30 · `CAS_END` 15:35 · `FNO_CLOSE` 15:40 ·
**`SETTLE_AFTER` 15:40**. The close had been a bare literal in **seven** separate places
(`agent.py`, `swing_credit.py`, `stock_credit.py`, `stock_credit_v2.py` + v0, `monthly_fut.py` at
15:25, `monthly_call.py` with no gate at all) and `MARKET_CLOSE` was honoured by almost nothing.
`agent.is_market_open()` now tracks `FNO_CLOSE`; new `is_cash_open()` covers the cash session.

**Settlement** — all books settle after `SETTLE_AFTER`, and the price priority is **inverted** in
`swing_credit`/`stock_credit`/`stock_credit_v2`(+v0): **official daily close first, live spot only as
fallback**. Previously they preferred live spot, which at 15:30 is guaranteed to be a pre-auction
print — they were settling every expiry on the wrong price. `monthly_call` gained the time gate it
never had (it settled from 00:00 on expiry day).

**Schedule** — watchlist build + digest **15:17** (first moment the continuous session is complete;
the build takes 11–19 s so the old 14:45/15:05 split is unnecessary), scans **15:36**, EOD booking
15:40. Scan measured at ~20–30 s, so signals land ~15:36:30 with ~3.5 minutes to place.

**0DTE early profit close** — `ZERO_DTE_EARLY_CLOSE_FRAC = 0.95` on all three intraday expiries.
Books the win once the spread has given back 95% of its credit rather than holding to expiry.

> ⚠️ **The early-close rule cannot be backtested.** Both 0DTE books are validated *as hold-to-expiry*
> (NIFTY 88.3%, SENSEX 89.0%) and intraday option premium history does not exist beyond ~1 month
> (`DATA_AVAILABILITY_LIMITS.md`). Unlike v1's TP-40, which was tested on 242 real trades, this ships
> **unmeasured**. Set the fraction to 0 to revert to pure hold-to-expiry.

## Why no backtest — and what to do instead

Running the 15:10-vs-close comparison over Kite's 2019→date history was considered and **rejected**:
CAS began 3-Aug-2026, so all earlier history has a different closing mechanism. A multi-year run would
measure the OLD microstructure precisely and say nothing about the new one. Kite also cannot supply
intraday option premiums for expired contracts.

**Instead, instrument daily**: log the breakout set at 15:10 vs the official close, and option
bid-ask/OI at 15:36. After ~10 sessions that decides, on new-regime evidence, whether the +44% holds
and whether the window stays liquid.

## Effect on existing research — read before comparing any numbers

Every backtest in `studies/` uses daily closes that were a **15:00–15:30 VWAP** before 3-Aug-2026 and
are **auction equilibrium prices** after. **These are not the same construct.** One day against seven
years invalidates nothing, but do not read the level shift as a regime change, and do not splice
pre- and post-3-Aug closes without noting it.

## Data-feed note

At 18:15 on 4-Aug the Upstox feed carried **no 4-Aug data at all** (neither daily nor 5-min), and the
3-Aug 5-min series stops at **15:25** — the auction print never appears intraday, only in the daily
bar. Same-day analysis must use live quotes, not history. This is the second sighting of the feed lag
that caused the SENSEX ticker bug the same morning.

## Sources

- [Business Standard — NSE F&O market timing change from 3 Aug 2026](https://www.business-standard.com/markets/news/nse-f-o-market-timing-change-here-s-what-new-timings-are-from-august-3-2026-126060101006_1.html)
- [Closing Auction Session (CAS) explained — NSE/BSE closing price rules 2026](https://www.sahi.com/blogs/closing-auction-session-cas-explained-nse-bse-closing-price-rules-2026)
- [Outlook Business — SEBI closing auction session, new timings from August 3](https://www.outlookbusiness.com/markets/sebi-closing-auction-session-new-stock-market-timings-from-august-3)

## VERIFIED 5-Aug-2026 — the price the 15:36 scan reads IS the official close

The open question this change rested on: does the daily bar our scan reads at 15:36 carry the CAS
equilibrium price, or a pre-auction print? If the latter, the breakout input would not be the close
the backtests were built on and the whole retiming would be built on sand. Settled empirically.

**Test 1 — the feed's daily-close construction changed on 3-Aug.** Daily close vs the last 5-min
intraday print, same day, 6 liquid names:

| session | daily close == last intraday print |
|---|---|
| 30-Jul (pre) | **0 / 6** |
| 31-Jul (pre) | **0 / 6** |
| 3-Aug (post) | **5 / 6** |
| 4-Aug (post) | **6 / 6** |

Before the change the official close was a 15:00–15:30 VWAP, so it necessarily differed from any
single print. After, it is a single auction crossing — which for liquid names lands on the last
continuous price. The change is visible in the data on exactly the right date.

**Test 2 — against the authority.** NSE bhavcopy (`BhavCopy_NSE_CM_..._20260804_F_0000.csv.zip`)
for 4-Aug vs the Upstox daily bar we scan:

| | Upstox daily | NSE bhavcopy | diff |
|---|---|---|---|
| GRASIM | 3,138.00 | 3,138.00 | 0.00 |
| TCS | 2,460.00 | 2,460.00 | 0.00 |
| RELIANCE | 1,290.90 | 1,290.90 | 0.00 |
| SBIN | 1,042.70 | 1,042.70 | 0.00 |
| INFY | 1,167.50 | 1,167.50 | 0.00 |
| ICICIBANK | 1,454.60 | 1,454.60 | 0.00 |

**Exact to the paisa, 6/6.** The number the 15:36 scan reads is the official close — the same field
the bhavcopy backtests were built on. The Donchian input is unchanged in kind.

**Consequence — the retiming CLOSED a gap, it did not open one.** The old 15:10 scan read a price
that was NOT the close and disagreed with it on about a third of names (32 vs 46 breakouts, median
drift 0.68%). Live had silently drifted from the backtest; 15:36 restores the match.

**What remains genuinely open, and is NOT resolved by the above:**
1. **The close's construction changed mid-series** — VWAP before 3-Aug, auction after. Test 1 shows
   these are different objects. Whether post-breakout reversion behaves identically on auction
   closes is untested and, on 3 sessions, untestable. Monitor; do not assume.
2. **Execution is dearer.** Spreads at 15:36–15:40 run 2–4% against the ~1% the cost model assumes,
   so realised net per trade should come in below backtest even with the signal set correct.
3. **+44% more signals at worse fills** — the net of (1) more trades and (2) costlier entry is not
   yet measured either way.

---

# PROS AND CONS OF THE 15:36 RETIMING — a fair accounting (5-Aug-2026)

Written because the retiming was justified on signal fidelity alone, and the cost side had been
noted but never priced. Both are quantified here. The honest summary is that the change is
**probably net positive and clearly correct in principle, but the size of the gain is unmeasured
and v0 is close enough to break-even to matter.**

## PRO 1 — the extra signals are not a new population. They are the one the backtest measured.

This is the strongest argument and it was missed in the original write-up.

Every v0/v1/v2 backtest defines a breakout on the **daily close**:

```python
c = cl[i]                                     # the DAILY CLOSE
typ = "CE" if c > hi[i-dc:i].max() else ("PE" if c < lo[i-dc:i].min() else None)
```

and takes its entry premium from the option's **daily close** (`P["C"][di, si]` in-sample,
`sp[0]` out-of-sample). So the population behind 84–87% win rates is *names that broke out on the
close* — the "46" set, not the "32" set a 15:10 scan saw.

**The old timing traded a biased ~70% subset of the validated population, and included one name
(PNB) the close contradicted.** The +44% is therefore not new risk being taken on; it is recovery of
signals the edge was measured on. That reframes the whole change: 15:36 is a *correction*, and the
burden of proof runs the other way — 15:10 was the untested variant.

*Limit:* the c/w ≥ 0.40 gate sits on top of the breakout, and whether the recovered names clear it
at the same rate is unmeasured. Measured across the auction on 18 names, c/w moved only a point or
two either way, which is weak evidence that the pass-rate is roughly stable.

## PRO 2 — entry premium is now priced off the right underlying

The backtest enters at the option's daily close, i.e. a premium corresponding to the **closing**
underlying. A 15:15 fill was priced off an underlying a median **0.68%** away from where it closed,
so the premium paid did not correspond to the premium the backtest assumed. A 15:36–15:40 fill is
priced off the settled close. Strictly more faithful — though "enter at the daily close" remains an
idealisation nobody can actually transact at, under either timing.

## PRO 3 — settlement is now on the right price

Independent of signals: the books had preferred live spot over the official close, so every expiry
settled on a guaranteed pre-auction print. Now official-close-first. This is a pure correctness gain
with no offsetting cost.

## CON 1 — entry costs roughly double, and it is priced

Spreads at 15:36–15:40 run **2–4%** against the **~1%/leg** the cost model `spf()` charges. On the
4-Aug GRASIM trade (short ₹64.50, long ₹39.65, lot 250):

| real spread | entry cost | model charged | extra per trade |
|---|---|---|---|
| 2% | ₹521 | ₹311 | **₹210** |
| 3% | ₹781 | ₹311 | **₹470** |
| 4% | ₹1,042 | ₹311 | **₹730** |

At 3% that is **6% of v2's measured net per trade, 17% of v0's**.

## The two effects together — how much signal gain is needed to break even

| book | net/trade | at 2% spread | at 3% | at 4% |
|---|---|---|---|---|
| v2 | ₹7,831 | +2.8% | **+6.4%** | +10.3% |
| v1 | ₹3,601 | +6.2% | **+15.0%** | +25.4% |
| v0 | ₹2,808 | +8.1% | **+20.1%** | +35.1% |

Against a measured **+44%** breakout gain, all three clear their break-even at every spread
assumption. Modelled monthly, at a 3% spread:

| book | before | +0% signals | +20% | +44% (measured) |
|---|---|---|---|---|
| v2 | ₹28,975 | ₹27,236 | ₹32,683 | **₹39,219** |
| v1 | ₹43,212 | ₹37,572 | ₹45,086 | **₹54,104** |
| v0 | ₹16,286 | ₹13,560 | ₹16,272 | **₹19,527** |

Read the `+0%` column as the downside case: **if the extra breakouts do not survive the c/w gate,
the retiming is a net LOSS** — −6% on v2, −13% on v1, −17% on v0. The whole benefit rests on the
signal gain being real after gating.

## CON 2 — the placement window is 3.5 minutes and unhedgeable

Signals land ~15:36:30; derivatives shut 15:40. The underlying's cash session ended at 15:15, so
between the signal and the close there is no way to hedge or leg in against stock. Mitigated by the
15:17 watchlist naming candidates ~19 minutes ahead, and by the 09:30 re-check that re-validates a
missed call the next morning — but a missed fill is a real, recurring cost that no backtest models.

## CON 3 — the closing price changed construction mid-series

Pre-3-Aug closes are a 15:00–15:30 VWAP; after, a single auction crossing. Visible in the data:
daily close equalled the last intraday print **0/6** before the change and **11/12** after. Donchian
bands built from VWAP closes and fed auction closes are not strictly the same object. Untested, and
on a handful of sessions untestable.

## CON 4 — the headline number is one day

**+44% is a single session (3-Aug), 113 names.** It is a breakout count, not a fired-signal count.
Everything above scales off it, so everything above inherits its fragility.

## Verdict

Keep the retiming. It is right in principle regardless of the arithmetic — the old scan was
demonstrably unfaithful to the validated construct, and PRO 3 is a pure correctness fix. On the
numbers it also looks net positive for all three books, with a comfortable margin on v2 and a
thinner one on v0.

**But do not bank the +39k/+54k figures.** They rest on a one-day breakout count surviving the c/w
gate at an unchanged rate, which is exactly the thing not yet measured. The `+0%` column is the
scenario that must be ruled out, and only forward data can do it.

**What to measure, in priority order:**
1. **Fired signals per month, before vs after.** The single number that decides this. Baseline: v2
   3.7/mo, v1 12/mo, v0 5.8/mo.
2. **Realised entry slippage vs the `spf()` model**, per leg, on every fill. Confirms which column
   of the cost table is real.
3. **Missed fills** — signals that fired but could not be placed inside 15:36–15:40.
4. Win rate of close-only breakouts (the recovered 15) vs those already broken by 15:10 — tests
   whether the recovered population behaves like the rest.
