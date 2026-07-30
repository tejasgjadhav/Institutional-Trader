# Is 2019→2026 (~7 years) enough lookback to validate these books? (2026-07-30)

**Question asked:** before starting LIVE in ~2 months, is the 2019→date backtest window long
enough, or should we go further back?

**Short answer: 7 years is close to the maximum these instruments allow, and it is a
reasonably good 7 years — but its sufficiency comes from the *risk structure* (defined-risk
spreads) plus the ongoing forward test, not from the calendar span alone.** Going further back
is mostly impossible for the thing that actually matters (real option premiums and the
credit/width gate), and where it is possible (underlying-only proxies) it cannot test the
deployed edge. Details below.

> **Scope note.** This is a data-availability / methodology / risk-structure analysis. It is
> NOT personalized investment advice and it does not say whether, when, or with how much money
> anyone should trade live. It states what the backtest evidence supports, what it cannot
> support, and what the remaining unknowns are — consistent with this repo's standing rule:
> honesty over optimism.

---

## 1. Does 2019→2026 cover enough distinct regimes?

What the window actually contains, and how each book behaved in it (all figures from the
studies in this directory — real bhavcopy premiums 2019→Sep'24 in-sample, real Upstox
premiums Oct'24→date out-of-sample):

| Regime in-window | Character | Evidence it stressed the books |
|---|---|---|
| **Mar 2020 COVID crash** | ~−38% in a month; India VIX ~86 — the *fastest* crash in NSE history | v2: 2020 = 90% win, +27.0%w. Gated v1: 53% win, **+0.4%w (barely survived)**. 0DTE NIFTY FLIP: 79% win, positive. |
| 2020–21 melt-up | one-way bull, IV collapse | v2 +13.5%w (2021), its *thinnest* bull year |
| **2022 rate-shock bear** | Russia–Ukraine, ~−17% drawdown, sustained | v2 +31.6%w; gated v1 +13.4%w — best non-2019 year |
| **2023 grind/chop** | the fade's actual worst regime | gated v1 **−4.5%w (a losing year)**; v2's worst month (Nov-2023, a genuine loss cluster) |
| 2023–24 bull, Sep'24 top | euphoria then ~−13% correction into Feb'25 | covered by the OOS window itself |
| 2025–26 (OOS era) | tariff shock Apr'25, India-Pak May'25, chop | OOS 87–88% win held through it |

So the window contains: one historic crash, one sustained bear, one losing chop year, two
bulls, and several exogenous shocks. Crucially, **the books' worst results did NOT come from
the crash** — they came from grinding/trending periods (2023, Nov-2023, Feb-2021). That is
consistent with the audited mechanism (`ZERO_DTE_EVENT_DAYS.md` etc.): this book is *paid for
visible fear* — crash-era IV inflates the credit and widens the effective cushion — while its
real enemy is a quiet market that trends through the short strike. The window contains
multiple instances of the actual failure mode, which matters more than raw year-count.

**What is NOT in the window:** 2008 GFC (~−60%), 2011 (~−25%), the 2013 taper/INR
devaluation, the 2015–16 China-deval slide (~−22%), Nov-2016 demonetization, and any
multi-year secular bear. Honest assessment of whether that absence matters:

- **For a NAKED short-vol book it would matter enormously** — a 2008 replay is exactly the
  scenario that kills naked premium sellers, and no 2019-start test could claim tail safety.
- **For THIS book — defined-risk credit spreads — the per-trade tail is capped by
  construction**, not by backtest evidence: max loss = width − credit = the margin the broker
  blocks (~₹10k/trade at 1 lot in v2). A 2008-type event cannot make a single spread lose more
  than that. What longer history would inform is not per-trade tail but **loss frequency and
  clustering** (Section 3) and **regime mix** — and on regime mix, note that 2008/2011/2013
  were *high-fear, high-IV* environments, i.e. the environment where the c/w ≥ 0.40 gate
  passes rich credit, which the in-window crash analogue (Mar 2020) handled positively.
  The unrepresented scenario that would genuinely hurt is a *multi-year* 2023-style grind —
  the window shows one such year (−4.5%w for v1), so we know the sign, not the depth of a
  longer one.

Verdict on regimes: **adequate breadth, thin depth.** Five-plus distinct regimes including the
strategy's true worst-case *type*, but only ~1 sample of each — 7 years is maybe 5–6
independent regime draws, so year-level statistics (5/6 positive, 8/8 positive) have wide
uncertainty even when per-trade t-stats look huge.

## 2. Can we even go further back? (Mostly no — and what a longer test could/couldn't measure)

**What data exists:**

| Layer | Depth | Usable for |
|---|---|---|
| Real intraday option premiums (Upstox) | ~3–4 weeks | fills/liquidity sanity only |
| Real daily option close+OI (NSE bhavcopy) | **2019 → date** (the current IS+OOS spine) | the actual deployed backtests |
| 5-min underlying (Kite) | ~2019 → date | direction proxies (`BUY_STRATEGIES_2019_REALTEST.md`) |
| Daily underlying | 1990s → date | direction/reversion proxy only |

Stock option premium history before ~2019–2020 does not exist at usable granularity — and
even where index bhavcopy rows exist further back, **the market itself did not**:

- **Weekly index options** (the 0DTE books' instrument) launched on BANKNIFTY only in 2016
  and NIFTY in Feb 2019; SENSEX weeklies date from 2023 (hence 0DTE SENSEX is "3 yrs only").
  There is no 2008 or 2013 version of a 0DTE weekly spread to test — the product did not
  exist. (And market structure keeps moving under us: SEBI's late-2024 framework cut weekly
  expiries back to one index per exchange — the 2019 market is already not today's market.)
- **Stock options pre-~2015 were too illiquid** for a 4-leg mid-cap spread to be a realistic
  trade at modeled prices; the universe selection (intraday movers), lot sizes, strike grids,
  and settlement rules (physical delivery phased in 2018–19) all differ. A pre-2015 "backtest"
  would model trades that could not have been executed.

**What a longer test COULD measure:** the underlying-only reversion tendency — "after a
Donchian breakout, does price stay OTM of an assumed short strike?" — back to the 1990s for
the index. That is Part 9's proxy methodology extended.

**What it could NOT measure — which is the part that matters:** real premiums, IV spike/crush,
and above all the **credit/width ≥ 0.40 gate — which IS the edge**. `STOCK_OPTIONS_NO_EDGE.md`
Part 10 is unambiguous: same signals, same geometry, no gate = **−1.1%w** (loses); gated =
**+5.3%w** (the durable edge). c/w is unobservable without real option prices, so a pre-2019
proxy cannot even *select* the trades the live book takes, let alone price them. It would
validate a strategy this repo does not run (the ungated fade — which loses). This repo has
also already been burned by exactly this class of inference: the Part 11 index-fade gates were
positive 6/6 *years* on 2019–24 data and still failed OOS, and Part 9's proxy overstated win
rates 68–75% vs the real 54%. **More proxy years would add confidence-theater, not evidence.**

The only genuine extension would be a paid deep-history vendor (TrueData/GDFL/NSE dump) for
index options back to ~2011–2016 — real premiums, but for products (monthlies, different
microstructure) that are not what the books trade. Possibly worth it someday for the index
books; it would still say nothing about the stock fade (the ★ book) before stock-option
liquidity existed.

## 3. The real residual risk: correlated clustering — did 2019–26 stress it?

For a defined-risk book the tail is not one blowup; it is **many spreads hitting max loss in
the same week** while gap-throughs make the 2–3× premium stops unattainable (the wing still
caps the loss; the stop does not save you). Two aggravators are specific to this book:

1. **The gate concentrates entries into stress.** High IV → rich credit → *more* signals clear
   c/w ≥ 0.40 exactly when correlations go to 1. The book is structurally busiest in crash
   weeks. (That is also where its compensation is — the two are inseparable.)
2. **Fill assumptions are weakest exactly then.** All pre-Oct'24 results assume daily-close
   fills; March-2020-width spreads on 4 legs of mid-cap stock options would fill far worse
   than modeled. The 2020 in-sample numbers (90% win, +27%w) should be read as "the *signals*
   survived the crash," not "the *fills* were proven."

What the window actually showed about clustering:
- Mar 2020 is IN-sample and the books stayed positive through it (v2 +27%w in 2020; v1 +0.4%w
  — i.e., approximately breakeven through the worst market in the sample: the honest read is
  "did not blow up," not "thrived").
- The measured worst clusters landed *outside* crashes: Nov-2023 (−208 %w-units month, loss
  cluster, streak of 4) and Feb-2021 (−₹2.28L month at 1 lot — pre-cap; the ₹40k exposure
  cap now deployed cuts the same history's worst month to **−₹26.4k** and worst single loss to
  −₹21.6k at 1 lot).
- But: only ~40 in-sample losses exist in v2's 405 trades. Tail-cluster statistics estimated
  from 40 events over one 7-year path are wide. The window stressed clustering *once* at
  crash-grade severity. That is a sample of one, and it is daily-close-modeled.

**What this implies for sizing on a ₹5L account (arithmetic, not advice):** the defined-risk
property makes worst cases computable in advance rather than estimable from history —
which is precisely why a 7-year window can be workable here when it never could be for naked
short vol. At 1 lot across the books, deployed margin is ~₹2–2.5L (`CONSOLIDATED_PNL.md`);
v2 alone budgets ~6 concurrent trades × ~₹10k margin ≈ ₹1L. The absolute worst theoretical
week — *every* open spread gapped to max loss simultaneously, stops never filled — loses the
blocked margin and nothing more: ~₹60k for the v2 book, ~₹2–2.5L (≈40–50% of ₹5L) if every
book's every position maxed at once. Severe, survivable, and knowable *ex ante*. That
computability, plus keeping roughly half the account as undeployed dry powder (the current
1-lot configuration does this automatically at ₹5L), is the structural answer to the
missing-2008 problem. Two live-only tails the backtest cannot see: **physical settlement** of
ITM stock-option legs at expiry (delivery obligations if one leg is exercised/assigned
asymmetrically — an operational risk, manage by closing before expiry week when ITM), and
the **stale, non-functional election-blackout list** flagged in CLAUDE.md.

## 4. Verdict

**Is 7 years sufficient?** For *this* risk structure, the honest answer is: **7 years is
sufficient-as-available — it is nearly all the history that exists for these instruments, it
contains the strategy's true failure mode (grind years) and one crash-grade stress, and the
defined-risk cap substitutes computation for the missing tail history.** The same 7 years
would NOT be sufficient grounds for a naked short-vol book, for removing the wings, for
raising lots, or for trusting the model's ₹/month magnitude.

**Its honest limits, plainly:**
1. One 7-year path ≈ 5–6 regime draws; "positive every year" has wide uncertainty.
2. Pre-Oct'24 fills are daily-close-modeled; this repo's own track record says realized ≈
   ⅓–½ of optimistic backtests (min-prem +1.5%→−1.0%; v1 +16–25%→+5.3%w). Plan on the
   PRACTICAL column (~50% haircut), per `STOCK_FADE_TP50_UPGRADE.md`.
3. v2's geometry came out of a 96-config grid on the in-sample years — IS years are partially
   fit by construction; the untouched evidence is the 21-month OOS era (132 trades, 88%) plus
   the both-era house rule. 21 months is still one broad regime.
4. Crash-week clustering was stressed once (Mar 2020), at daily-close granularity.
5. No amount of additional backtest length can close limits 2–4. **Only the live-fill forward
   test can** — which is why the ~2-month runway is genuinely valuable rather than dead time.

**What the evidence supports a "live in ~2 months" plan including (methodology, not advice):**
- **Do not spend the 2 months extending the lookback** — extend the *forward* test. The repo's
  own gate (a 20–30-trade live-fill vs model comparison) is the right admission criterion:
  LIVE ≥ 60% of MODEL → the thesis holds; LIVE ≤ PRACTICAL → stay paper and investigate fills.
- Enter, if at all, at the already-deployed risk configuration: 1 lot, ₹40k exposure cap,
  concurrency caps, c/w ≥ 0.40 untouched (the gate is the edge — loosening it to get more
  signals re-admits the −1.1% book), ~half the account as dry powder.
- Watch specifically for: worst-*week* (not worst-trade) P&L vs the computed max; fill
  slippage vs model on the 4 stock-option legs; ITM positions approaching physical
  settlement; the c/w gate's signal rate as IV regime shifts; and the model-vs-live ledger.
- Treat the first live months as the continuation of the experiment, not its reward.

*Sources: `STOCK_OPTIONS_NO_EDGE.md` Parts 8–11 · `STOCK_FADE_TP50_UPGRADE.md` ·
`STOCK_FADE_V2_UNION_VS_D10.md` · `DATA_AVAILABILITY_LIMITS.md` · `CONSOLIDATED_PNL.md` ·
`ZERO_DTE_EVENT_DAYS.md` / `ZERO_DTE_EARNINGS_SHOCKS.md` · `README.md` house rules ·
root `CLAUDE.md` deployed-books table. Market-structure dates (weekly-option launches,
physical-settlement phase-in, SEBI expiry framework) are outside-repo facts stated
approximately.*
