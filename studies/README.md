# Studies index

40 research write-ups. Every live tunable in this repo traces to one of them, and several document
things that were tested and deliberately **not** deployed — those are as important as the wins.

**Start here:** [`NEXT_ACTIONS.md`](NEXT_ACTIONS.md) — current recommendation and open gaps ·
[`STRATEGY_SUMMARY.md`](STRATEGY_SUMMARY.md) — canonical strategy table ·
[`CONSOLIDATED_PNL.md`](CONSOLIDATED_PNL.md) — monthly P&L model.

---

## ⚠ READ BEFORE COMPARING ANY NUMBERS — NSE session changed 3-Aug-2026

Equity **derivatives** now close at **15:40** (was 15:30), and F&O stocks stop continuous trading at
**15:15** and are priced by a **Closing Auction Session** (15:15–15:35). **Daily closes before
3-Aug-2026 are a 15:00–15:30 VWAP; after, they are auction equilibrium prices — not the same
construct.** One day against seven years invalidates nothing here, but do not read a level shift as a
regime change and do not splice pre- and post-3-Aug closes without saying so. The engine's schedule
moved with it: watchlist 15:17, scans 15:36, settlement 15:40.
See [`NSE_SESSION_CHANGE_2026_08_03.md`](NSE_SESSION_CHANGE_2026_08_03.md).

---

## Current state of the book (2026-07-19)

| Book | Status | Win | ₹/mo @1 lot | Evidence |
|---|---|---|---|---|
| ★ Stock fade v2 UNION | LIVE | 87% | ~₹20,000 | t=+13.78 · 8/8 years |
| Stock credit v1 | LIVE | 73% | ~₹12,000 | t=+7.09 · 3/3 years (OOS only) |
| 0DTE SENSEX | LIVE | 89.0% | ₹3,153 | measured · 3 years |
| 0DTE NIFTY | LIVE | 88.3% | ₹1,771 | t=+4.43 · 7/8 years |
| ~~0DTE BANKNIFTY~~ | **REJECTED 07-19** | 78.6% | — | edge ≈ 0, t=+0.10 |
| Index swing fade | paper | 54% | ~₹0 | regime-dep · failed OOS |
| Monthly futures | REGIME-OFF | 75.7% | ₹0 now | needs ~₹15L |

**Total ≈ ₹36,924/mo at 1 lot.** Edges are validated; **magnitude is still optimistic** — plan on
~50% rather than the model figure until live fills prove otherwise. See `NEXT_ACTIONS.md`.

---

## The 2026-07-19 audit session (newest)

A full pass over the 0DTE books: can we tell in advance that today is a bad day to trade?

| Study | Question | Verdict |
|---|---|---|
| [`ZERO_DTE_EVENT_DAYS.md`](ZERO_DTE_EVENT_DAYS.md) | Skip RBI / Budget / FOMC days? | ✗ costs ₹33.1k · both eras agree |
| [`ZERO_DTE_PREOPEN_SIGNALS.md`](ZERO_DTE_PREOPEN_SIGNALS.md) | Skip on overnight gap / vol regime? | ✗ every rule fails the era split |
| [`ZERO_DTE_EARNINGS_SHOCKS.md`](ZERO_DTE_EARNINGS_SHOCKS.md) | Skip heavyweight earnings / geopolitical shocks? | ✗ shock days went 7/7, +21.4%m |
| [`BANKNIFTY_0DTE_REJECTION.md`](BANKNIFTY_0DTE_REJECTION.md) | Is BANKNIFTY 0DTE worth running? | ✗ **REJECTED** · edge ≈ 0 |
| [`STOCK_BOOKS_AUDIT.md`](STOCK_BOOKS_AUDIT.md) | Is the ₹32k from the stock books real? Remove NIFTY? | ✓ both pass · **keep NIFTY** |
| [`DONCHIAN_5_10_15_20.md`](DONCHIAN_5_10_15_20.md) | Is a longer Donchian window more durable? | ✗ D5 wins on total edge/mo |
| [`NEXT_ACTIONS.md`](NEXT_ACTIONS.md) | Any change in strategy? | **No — validate, don't modify** |

**The finding that ties them together:** this is a short-volatility book, and it is **paid for visible
fear**. A fixed-%-OTM spread sold on a scary morning collects inflated premium against a strike that
hasn't moved — so observable risk is *compensation*, not danger. Every filter keying on ex-ante-visible
stress removed exactly the trades where the market overpays. The mirror image is the one thing that
survived: **cheap premium is uncompensated tail risk** (hence the c/W ≥ 0.04 floor).

---

## By strategy

**Stock fade (the leader)** — `STOCK_FADE_TP50_UPGRADE.md` (the 96-config grid) ·
`UNION_DONCHIAN_FREQUENCY.md` · `STOCK_FADE_V2_UNION_VS_D10.md` · `DONCHIAN_5_10_15_20.md` ·
`CW_BUCKET_ANALYSIS.md` (why the c/W gate *is* the edge) · `STOCK_V1_OOS.md` ·
`PRIORITY_STOCKS_PERSISTENCE.md` · `UNIVERSE_94_VS_100_HEADTOHEAD.md` · `STOCK_BOOKS_AUDIT.md`

**0DTE index** — `INTRADAY_85PCT_0DTE_CE_SPREAD.md` · `INTRADAY_90PCT_WINRATE.md` ·
`FLIP_SIDE_CREDIT_FADE.md` · `ZERO_DTE_ENTRY_TIME.md` · plus the four 2026-07-19 studies above

**Index / swing / futures** — `INDEX_TREND_RIDE_EXIT.md` · `CAPITAL_CURVE_RESULTS.md` ·
`monthly_fut/MONTHLY_FUTURES.md`

**Gates tested and disabled** — `GATE4_DONT_CHASE.md` · `GATE5_WIDE_OPEN.md`

**Where the edge is NOT** (read before proposing anything) — `STOCK_OPTIONS_NO_EDGE.md` ·
`NONFADE_INTRADAY_SEARCH.md` · `DAILY_HIGHWIN_SEARCH.md` · `COMMODITY_HIGHWIN_SEARCH.md` ·
`COMMODITY_MCX_FEASIBILITY.md` · `BUY_STRATEGIES_2019_REALTEST.md` · `STOCK_OPTION_EXIT_CAP.md`

**Method & constraints** — `DATA_AVAILABILITY_LIMITS.md` · `REAL_OPTION_OPTIMIZATION.md` (read the
CORRECTION at the top) · `OBJECTIVE_SPEC.md` · `WIN_RATE_RESEARCH_LOG.md` ·
`UNDERLYING_VALIDATION_365D.md` · `PROPHET_FORWARD_TEST.md` · `FINAL_STRATEGY_TESTING_60DAY.md`

---

## House rules these studies enforce

1. **A rule must hold in BOTH eras independently** (bhavcopy 2019→Jul'24, Upstox Oct'24→date) or it is
   a regime artifact. This repo lost an "edge" that had 6 positive years in one regime.
2. **Swept thresholds are in-sample optimisation.** Report the era split, not the pooled best cell.
3. **Small-n is noise.** Anything under ~n=10 is labelled as such and does not drive decisions.
4. **Retrospective event lists are inadmissible as trading rules** — they are selected for having moved
   the market. Use market observables (the gap) instead.
5. **Only knowable-in-advance information may be used in an avoid rule.** Off-cycle COVID-era
   announcements sit in a separate `UNAVOIDABLE` bucket, measured but never avoided.
6. **Report gross-vs-net, sample size, and out-of-sample fragility.** Don't sell a curve-fit.

## Reproducing

Scripts live in `studies/ndte/` (0DTE + stock fade) and `studies/monthly_fut/`. Most need
`UPSTOX_ANALYTICS_TOKEN` in `.env`. `/tmp` caches are rebuilt automatically but are slow — the bhavcopy
downloaders take ~30 min. Per-trade result files for the 0DTE books are persisted **in-repo**
(`ndte13_trades.json`, `ndte14_trades_2019.json`) precisely because `/tmp` gets purged.
