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

## CLOSING FINDING — this book is paid for visible fear

Written verbatim from the decider's ruling, because it is the durable output of the whole series and
should stop the next "avoid the scary day" proposal before it consumes another test budget:

> A fixed-%-OTM credit spread sold on a scary morning collects inflated premium against a strike that
> hasn't moved; **observable risk is compensation, not danger.** Every avoidance filter that keys on
> ex-ante-visible stress (gap, VIX, spikes, shocks — 7/7 wins) removes exactly the trades where the
> market overpays. The only threats to this book are (a) *intraday surprises*, which occurred zero
> times in 448 expiries and cannot be filtered ex ante, and (b) true crisis regimes (VIX≥25), which
> are too rare to test.

The mirror image of that finding is the one thing that did survive: if rich premium is where the edge
lives, **cheap premium is where it dies.** Pooled c/W buckets show a monotone gradient in which win
rate is an *inverse* mirage — the cheapest bucket has the highest win rate and still loses money:

| c/W bucket | n | Win % | Avg %margin | Total ₹ |
|---|---|---|---|---|
| 0.00-0.04 | 60 | **91.7%** | **−0.49%** | **−₹1,878** |
| 0.04-0.08 | 103 | 87.4% | −0.30% | +₹5,689 |
| 0.08-0.12 | 104 | 89.4% | +6.02% | +₹82,258 |
| 0.12-0.18 | 88 | 84.1% | +5.95% | +₹57,823 |
| 0.18+ | 93 | **81.7%** | **+10.03%** | +₹89,555 |

Same shape as the stock book's validated c/w≥0.40 gate (`CW_BUCKET_ANALYSIS.md`). This was *predicted
in advance* by the closing finding, so it is a confirmed hypothesis rather than a dredge.

## Also tested and rejected: India VIX (the last open item)

`ndte17_vix_final.py`, prior-close VIX so no lookahead. Every variant fails, most in the *opposite*
direction to the prior: skip `vix_spike≥+10%` costs ₹17,227 and the flagged days were **92.9% win,
+13.32%m**. `vix_level≥15/18/20` cost ₹123,708 / ₹74,473 / ₹37,171, failing in *both* eras.
`vix_level≥25` is the sole positive sign (Era A +₹10,603, n=11) but Era B has n=1 — untestable, not
proven, and effectively a description of COVID. **Logged as a revisit condition only:** if Era B ever
accrues ≥10 expiries with prior-close VIX≥25, rerun that one test. Half-sizing never rescued any
rule; ex-worst-day removal never changed a sign.

## Disposition

Do not add an earnings filter, a geopolitical filter, a gap filter, a VIX filter, or any swept
credit threshold. **TWO structural exclusions were DEPLOYED** (2026-07-19), both on structural
grounds rather than as statistical edges — neither makes a regime claim, so the both-eras rule does
not govern them:

1. **Election blackout** (`ZERO_DTE_ELECTION_BLACKOUT`, all three books) — national counting days +
   the exit-poll reaction session. Scheduled *inside-window* binary; short premium is structurally
   the wrong trade against a bimodal outcome. **Never triggered in 448 expiries**, so measured cost
   is exactly ₹0 — 2024-06-04 (NIFTY −5.9%) was dodged by calendar luck, not design. Zero-premium
   insurance against the book's known ruin mode.
2. **Minimum credit/width ≥ 0.04** (`ZERO_DTE_MULTI_MIN_CW`, **SENSEX + BANKNIFTY only**) — NIFTY is
   untouched, already carrying the same principle via `ZERO_DTE_MIN_CREDIT_PCT`. 0.04 is the
   *structural boundary of the negative-EV bucket*, deliberately **not** the sweep's argmax: the
   0.06-0.12 cutoffs scored better and were **explicitly rejected** as in-sample optima on small
   skip-counts (BANKNIFTY skipped n=9). Purpose is to stop selling near-zero credit against a full
   settlement tail — negative EV by arithmetic, not by regime.

Everything else in the series is dead. The consistent mechanism is that this is a *short-volatility*
book: elevated pre-open uncertainty raises the premium collected, and across 448 expiries that
compensation matched or exceeded the added risk. **Trade the full calendar**, minus the two
structural exclusions above.

Standing constraint recorded: **SENSEX is permanently outside the era-split framework** (single-era
book — BSE weeklies launched 2023), so it may only ever receive structural rules, never swept ones.
Script fix applied: an era with zero observations now returns *single-era only*, never a silent pass
— the earlier version would have green-lit single-era artifacts.

Scripts: `studies/ndte/ndte16_earnings.py`. Data: `studies/ndte/nse_results_dates.py` (367 rows with
intimation lead times), `studies/ndte/india_market_shocks.py` (50 classified events).
