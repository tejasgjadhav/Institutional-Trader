# 0DTE heavyweight earnings & market shocks — avoid or not? (2026-07-19)

Third and final part of the event-avoidance series (`ZERO_DTE_EVENT_DAYS.md` = calendar events,
`ZERO_DTE_PREOPEN_SIGNALS.md` = gap/vol signals). This one tests the user's specific ask: **index
heavyweight results (RELIANCE, HDFCBANK, ICICIBANK…) and known geopolitical shocks.**

## Verdict — NO for earnings. And the shock days were the *best* days we ever had.

## 1. Earnings: the release-window split decides it

Results dates came from NSE's board-meeting API, which also carries the **advance-intimation
timestamp**. Across all 367 rows the minimum lead time is **3 days** (median 14, max 41) — so this
is *proven* ex-ante knowable, not assumed. Nothing was inferred from price action.

The decisive fact is *when* results actually hit the tape:

| Release window | Count (of 367) | Effect on a position we already hold |
|---|---|---|
| **INTRADAY** (09:15-15:30) | **51** | The only genuine risk — binary lands while short gamma |
| POST_CLOSE (>15:30) | 223 | Already public before next open → that session sells the exhale |
| NON_TRADING_DAY | 88 | Same (HDFCBANK/ICICIBANK habitually report on **Saturdays**) |
| UNKNOWN | 5 | — |

**Only 14% of results releases land inside the window at all.** Most of the "earnings risk" is
structurally not risk for this strategy.

### Results, per book

| Book | Avoid results-INTRADAY | Avoid the exhale session | Avoid any results involvement |
|---|---|---|---|
| **NIFTY** (n=273) | −₹8,532 (costs) | −₹10,637 (costs) | −₹14,052 (costs) |
| **SENSEX** (n=91) | −₹6,668 (costs) | −₹322 (costs) | −₹6,991 (costs) |
| **BANKNIFTY** (n=84) | **NO OVERLAP — zero of 84** | +₹19,632 ⚠ n=6 | +₹19,632 ⚠ n=6 |
| **POOLED** (n=448) | **−₹24,336 (costs)** | +₹12,928 ⚠ see below | — |

**NIFTY and SENSEX: avoiding costs money in every variant** — exactly as the weight arithmetic
predicts. Top weights are 9-13%, so a 4% single-stock surprise is only ~0.4% of index, at or below
the pain threshold of a 0.5%-OTM spread. The index basket absorbs it.

**The intraday-results days were actively GOOD**: pooled 19 trades, **89.5% win, +13.63% of margin**.
Avoiding them costs ₹24k. Elevated pre-result IV inflates the credit we collect, and the single-name
move doesn't move the index enough to hurt.

**BANKNIFTY — the one place the arithmetic said to look, and there was nothing to see.** Banks are
~half the index, so bank results *should* matter. But **not one of 84 expiries coincided with an
intraday bank result.** BANKNIFTY is month-**end** expiry while bank results cluster mid-month, and
HDFCBANK/ICICIBANK report on Saturdays. The hypothesis is structurally starved of observations.

### The pooled "exhale case helps" row is an artifact — do not act on it

Pooled, avoiding the post-results session appears to help (+₹12,928). It doesn't survive inspection:
**the entire effect is 6 BANKNIFTY trades** (50% win, −34.56%m, −₹19,632). Strip those and the other
39 trades are *positive* (+₹6,704), i.e. avoidance would have cost money. A pooled conclusion driven
by six observations in the weakest, structurally-confounded book is not evidence — it is precisely
the few-trade-dominance failure mode this series keeps flagging.

## 2. Market shocks: descriptive only — and the result is striking

A shock list compiled today is **inadmissible as a trading rule**: every entry is on it *because* it
moved the market (survivorship-of-the-scary), and you cannot subscribe in 2019 to a list written in
2026. So this is reported as measurement, not as a filter.

Of 50 catalogued shocks (41 pre-open observable, 9 intraday surprises), **7 coincided with an
expiry** — and the books went:

| | n | Win % | Avg % of margin | Total ₹ |
|---|---|---|---|---|
| **PRE_OPEN_OBSERVABLE shock days** | 7 | **100%** | **+21.35%** | +₹12,670 |
| INTRADAY_SURPRISE shock days | 0 | — | — | — |

Every single one won, several enormously: Iran 180-missile barrage +30.87%m, the Mar'26 crude/Fed/
rupee cluster +34.56%m, US-Israel air war on Iran +12.56%m, Hindenburg-Adani +5.41%m and +14.06%m.

This is the "sell the exhale" mechanism at its clearest. By 09:15 the shock is public, the gap has
printed, strikes are set off the *post-shock* spot, and the fear premium is at its richest — then
the market spends the day calming down. **The days that feel most dangerous to trade were the most
profitable ones.** Had a geopolitical filter been running, it would have skipped all seven.

Note also: **zero intraday surprises hit an expiry**, so the genuinely unavoidable class — the one a
filter could never help with anyway — never cost us anything in this sample.

## Honest limits

- **Small n throughout.** 19 intraday-results trades, 7 shock trades, 6 BANKNIFTY exhale trades. The
  NIFTY/SENSEX "avoiding costs money" conclusion is the robust one (consistent direction, larger n);
  every per-category row under n≈10 is noise and is labelled so.
- **The 100% shock-day win rate is not a law.** Seven observations, all in a period where shocks
  happened to mean-revert. It is evidence against a shock-avoidance filter, not evidence *for* a
  shock-seeking one.
- **BANKNIFTY remains structurally confounded** (weekly→monthly expiry change, see
  `ZERO_DTE_EVENT_DAYS.md`), so its rows carry less weight than NIFTY/SENSEX regardless of n.
- Two shock rows are flagged unverified by the source research (2026-03-27 Hormuz timing;
  2026-02-01 Sunday Budget session absent from the price series). Neither coincided with an expiry.
- Results coverage is the 12 largest constituents. A mid-cap result cannot move an index enough to
  matter, so this is the right universe, but it is not exhaustive.

## Disposition

**REPORT-ONLY — no engine change.** Do not add an earnings filter and do not add a geopolitical
filter to any 0DTE book.

This closes the event-avoidance series. Across all three studies — scheduled calendar events,
pre-open magnitude signals, and now earnings and shocks — **nothing tested earns its keep.** The
consistent mechanism is that this is a *short-volatility* book: elevated pre-open uncertainty raises
the premium collected, and across 448 expiries that compensation has matched or exceeded the added
risk. **Trade the full calendar.**

Scripts: `studies/ndte/ndte16_earnings.py`. Data: `studies/ndte/nse_results_dates.py` (367 rows with
intimation lead times), `studies/ndte/india_market_shocks.py` (50 classified events).
