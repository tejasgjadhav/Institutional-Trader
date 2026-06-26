# Study: No NSE option strategy tested survives real costs (definitive)

> **Scope grew over the project.** This started as "find the best intraday stock-option *buying*
> strategy" (Parts 1–3 below). When that failed structurally, the search was widened — to
> intraday spreads, to multi-day holds, and finally to multi-day **credit spreads** (selling
> premium / harvesting theta), which was the single most promising idea. **Part 4 records the
> decisive real-cost verdict on the credit spread: it loses too.** One structural cause explains
> every negative — see "The unifying conclusion".

## Mandate
Find the highest-performing NSE stock-/index-options strategy on real option data, net of
realistic costs, validated out-of-sample. Reject anything that isn't robust. No exceptions made
for a strategy because it "looked good" on an estimate — every survivor had to clear *measured*
costs on a held-out sample.

## Data (the upgrade that made this honest)
Upstox Plus **expired-instruments API** (`engine/expired_options.py`) provides real historical
premiums for expired contracts (~18 months). So everything below is on **actual option P&L**,
not the underlying proxy. Underlying 5-min limits the window to ~1 year; this study uses 180
days of ORB+alpha signals (rich feature set) + 18 months of gap-reversal signals.

## Cost model (NSE options, round-trip, per trade)
Brokerage (Rs20×2) + STT (0.0625% on sell premium) + exchange txn (~0.035%) + GST (18% on
brokerage+txn) + stamp (0.003%) + **premium-dependent bid-ask/slippage** (≈ clamp(60/premium,
1%, 6%) — rich options ~1–1.7%, cheap options ~5–6%). This is realistic-to-generous.

## Gate 2 (ORB) — verified applied
All 485 ORB+alpha signals are ORB-confirmed: 0 below the 1.2× volume-surge threshold,
vol-ratio 1.2–145, every microstructure non-zero. The poor results are NOT a missing-gate bug.

## Part 1 — Intraday stock-option BUYING (all NET of costs, 120d train / 60d holdout)

| Strategy | Trades | Best holdout NET | Verdict |
|---|---|---|---|
| Alpha+ORB+gates+min-premium (deployed) | 59–289 | ~breakeven, **neg. expectancy**, <100 tr | ❌ |
| **Mix-and-match: 3,312 filter combos** (z, momentum, trend-quality, vol-surge, ORB-width, VIX, day-range, time, alignment, min-premium × exits) | ≥100 each | **0 of 3,312 cleared the bar** | ❌ |
| Oops gap-reversal — stocks (1,656 trades) | 1,656 | **−2.2%** (best), PF<1 | ❌ |
| Oops gap-reversal — index (130) | 130 | negative / noise | ❌ |

**Robustness bar** (mandate's own rules): train net>0 AND holdout net>0 AND ≥100 trades AND
holdout PF>1. **Nothing met it.** Several configs were positive on train and sharply negative on
holdout (textbook overfit); a tempting "1-bar confirmation" pattern was look-ahead and failed.
The min-premium config looked like **+1.5% (64% win) on 180 days** but came in at **−1.0% (55%
win) over a full year** — the canonical overfit caught by the longer window.

## Part 2 — Intraday vertical SPREADS (buy + sell a leg to cut cost)
Buying a debit spread halves directional cost but caps payoff; the extra leg adds a second
bid-ask crossing. Net result across the combinations tested: **−10% to −20%** — the capped
upside no longer covers two legs of slippage. ❌

## Part 3 — MULTI-DAY buying (Donchian-20 breakout, hold days)
Holding a *bought* option overnight to capture a multi-day move runs straight into **theta**:
the option bleeds time value every day it's held. Net-negative across exits. ❌

## Part 4 — MULTI-DAY CREDIT SPREADS (sell premium, harvest theta) — the decisive test
This was the most promising structure and the reason the mandate's "no selling" rule was set
aside to *measure* it. The idea inverts the cost problem: instead of paying the spread + theta,
you **collect** them (sell the near leg, buy a further leg as defined-risk protection). On an
**estimated** 6%-of-capital cost it looked genuinely good — hold-to-expiry **+8.8% gross**,
**+6.9% holdout, PF 1.19**. So we did NOT deploy on the estimate — we collected the *real*
per-leg premiums (`/tmp/swing_credit2.json`, 2,387 trades, 18 months) and measured the actual
4-transaction cost.

**Real measured cost: ₹1,137 / trade. Result — every exit net-negative:**

| Exit rule | Win % | NET / cap | PF | Holdout | Worst trade / max lose-streak |
|---|---|---|---|---|---|
| take 50% / stop 2× | 58% | **−12.6%** | 0.59 | −14.2% | −198% / 14 |
| take 75% / stop 2× | 54% | −7.3% | 0.79 | −6.9% | −198% / 11 |
| hold-exp / stop 2× | 48% | −8.8% | 0.77 | −8.0% | −198% / 13 |
| **hold to expiry (best)** | 50% | **−4.7%** | 0.87 | **−2.4% / PF 0.94** | −186% / 13 |

The +6.9% estimate was a **cost mirage**: the real 4-leg bid-ask cost is far above 6% of capital
and **erases the theta edge entirely** (gross +8.8% → net −4.7% best case). The tail is also
brutal — worst trade −198%, losing streaks to 14. **Rejected. Not deployed.** ❌

> The discipline that mattered: had we built the parallel engine on the +6.9% *estimate* (as
> requested), a confirmed money-loser would now be wired into the system. The "measure real costs
> before deploying" gate stopped exactly that.

## The unifying conclusion — one structural cause
**No NSE option strategy tested — intraday buying, spreads, multi-day buying, or multi-day credit
spreads — produces a net-positive, out-of-sample, ≥100-trade edge after *measured* costs.** The
single cause: as a **retail taker you cross the bid-ask on every leg** (~2–4% of premium each),
and:
- *buying* adds **theta** working against you (Parts 1–3);
- *selling* (credit spreads) flips theta in your favour but pays **4 legs of slippage** that
  outweigh the small premium collected (Part 4).
A ~50–58% hit rate on either side cannot consistently cover that toll. More parameter iteration
only manufactures overfit — proven repeatedly (3,312 configs; +1.5%→−1.0%; +6.9%→−4.7%).

## Recommendation
- **Do not allocate capital to any of the option structures tested here.** Each is structurally
  negative-EV net of measured costs — documented, rigorously-tested, not a tuning gap.
- The only durable signal in the whole system is the **thin index trend-ride** (+0.9% *gross*
  over 18 months — and real costs thin even that). It stays a paper forward-test, not a money-maker.
- Treat the system as what it is: a disciplined research engine whose real value is **honestly
  disproving losing ideas before they cost money** — which it did, most importantly on the credit
  spread that looked like a winner until real costs were measured.

## Method note for the record
These negative results are strong *because* of the discipline: real/measured option premiums,
full costs, held-out validation, a ≥100-trade floor, a 3,312-config systematic search, and — the
decisive one — refusing to deploy the credit spread on an estimate and instead measuring the real
per-leg cost. A less rigorous study would have shipped an in-sample "winner" (+1.5% on 180 days,
or +6.9% on estimated cost) and been wrong with real money.

## Reproduce
- Credit-spread real-cost verdict: `/tmp/swing_credit_real.py` over `/tmp/swing_credit2.json`
  (2,387 trades w/ per-leg premiums) → prints the Part-4 table (`DONE-CREDITREAL`).
- Collector: `/tmp/swing_credit_collect.py` (Donchian-20 scan → bull-put/bear-call legs, real
  expired-instrument premiums for both legs).
