# 0DTE pre-open signals — can we tell before 09:15 that today is a bad day? (2026-07-19)

Companion to `ZERO_DTE_EVENT_DAYS.md`. That study rejected a *calendar* filter (RBI/Budget/FOMC).
This one asks the broader version of the user's question: **of everything knowable before 09:15 —
overnight global cues, geopolitical shocks, volatility regime — does anything reliably tell us to
stand aside?**

## The instrument: the overnight gap

Rather than assemble a news feed, use the number the market computes for us. The **overnight gap**
(`open / prev_close − 1`) is a weighted summary of *every* overnight input — a Wall Street selloff,
a weekend military escalation, a crude spike, an Asian-market rout, a heavyweight result announced
pre-market. If "bad news before the open" hurts this book, a gap filter has to show it.

**No lookahead:** these books enter at ~09:16, *after* the 09:15 open prints. The gap is genuinely
known before entry. Same for `rv5` (5-day realized vol) and the prior day's move — closed bars only.

This also cleanly separates the two categories the user asked about. A geopolitical shock is
*unpredictable as an event* but *fully observable at the open* — so it is *avoidable as a rule*.
The test for "avoidable" is *observable pre-open*, not *predictable in advance*.

## Headline — no pre-open filter survives. Every candidate fails the era split.

Swept over 448 expiries 2019→Jul'26, most thresholds simply **cost money**, consistent with the
calendar study. A few extreme thresholds looked promising on the pooled sample — and all of them
collapse when tested on the two eras independently:

| Candidate rule | Era A 2019→Jul'24 | Era B Oct'24→date | Verdict |
|---|---|---|---|
| skip `rv5 ≥ 1.10` | **+₹47,605** | −₹17,988 | ✗ fails |
| skip `rv5 ≥ 1.30` | **+₹35,345** | −₹789 | ✗ fails |
| skip gap-UP ≥ 0.75% | +₹2,035 | −₹743 | ✗ fails |
| skip `|gap| ≥ 0.75%` | −₹879 | −₹14,083 | ✗ dead in both |
| skip gap-UP≥0.75 **or** `rv5≥1.10` | **+₹37,450** | −₹19,366 | ✗ fails |

Every rule that helps in Era A hurts in Era B. **The pooled result was in-sample threshold
optimisation** — found by sweeping, then flattered by one regime. This is precisely the failure mode
that killed the index fade ("6 positive years in ONE regime ≠ out-of-sample"), so it gets the same
verdict.

## The asymmetry that looked real — and reversed

On the pooled sample the signed-gap buckets told a clean, mechanistically appealing story: these are
predominantly **short-call** books, so a gap *up* runs toward the short strike (danger) while a gap
*down* runs away from it and hands us fear-inflated premium (ideal).

| Signed gap | n | Win % | Avg %margin | Total ₹ |
|---|---|---|---|---|
| gap DOWN >0.75% | 19 | 78.9% | +1.07% | +₹16,254 |
| gap down 0.25-0.75% | 62 | **93.5%** | **+12.73%** | +₹72,227 |
| flat ±0.25% | 229 | 88.2% | +4.18% | +₹1,08,975 |
| gap up 0.25-0.75% | 110 | 84.5% | +3.54% | +₹37,283 |
| **gap UP >0.75%** | 28 | **71.4%** | **−4.78%** | **−₹1,292** |

The only negative bucket was large up-gaps. Tidy. **But split by era it inverts:**

| Signed gap | Era A win / avg | Era B win / avg |
|---|---|---|
| gap DOWN >0.75% | 63.6% / **−12.51%m** | 100% / **+19.74%m** |
| gap UP >0.75% | 68.2% / **−6.18%m** | 83.3% / **+0.34%m** |

Down-gaps were the *worst* bucket in Era A and the *best* in Era B. Up-gaps were bad in Era A and
harmless in Era B. **The asymmetry is not structural — it is a read on which regime you were in.**
Era A contains COVID, the 2020 crash and the 2022 drawdown, where a big gap meant genuine trend
continuation; Era B has been calm, where a big gap meant an overreaction that mean-reverted and
crushed vol.

That is not tradeable, because it requires knowing the regime in advance — which is the same thing
as knowing whether the gap will follow through.

## What this says about "news parameters" generally

The user asked to analyse the factors that hit a given day — geopolitical news, results, global
cues. The gap test covers all of them **in aggregate**, and its answer is that pre-open information
about *magnitude* does not separate good days from bad days in a regime-stable way.

The reason is the same one that sank the calendar filter: this is a **short-volatility** book, and
big news cuts both ways. Elevated pre-open uncertainty inflates the premium we collect. Sometimes
the move follows through and we lose; sometimes it exhales and we collect an unusually rich credit.
Across 448 trades, those two effects roughly cancel — and *which one dominates is a property of the
regime, not of the news*.

## Why this happens — the release-window taxonomy

An independent design pass (Fable 5) produced the structural explanation, and it subsumes both
studies. What matters is not *whether* there is an event but **where the release lands relative to
the 09:16→15:30 holding window**:

| Release timing | Examples | Effect on a short-premium 0DTE book |
|---|---|---|
| **Inside the window** | RBI 10:00, Budget 11:00, election counting all day | Vol *expansion* while short — the only genuine risk class |
| **Just before the window** | FOMC 23:30 IST, US close, overnight geopolitics, post-market results | Move already realized, strikes set off post-shock spot, we sell the exhale — **good** |
| **After the window** | India CPI/WPI 17:30, US CPI/NFP 18:00+ | **Irrelevant to today's position.** Reaches us only via tomorrow's gap |

This reframes the earlier FOMC finding as a *prediction* rather than a curiosity: any scheduled event
releasing outside the holding window is **not an event for this strategy at all**. A large part of a
naive "event calendar" dissolves on inspection — Indian and US macro prints release after the 15:30
close, so testing them as same-day filters is a category error, not an empirical question.

It also explains why only the *inside-window* categories (RBI, Budget, elections) are even
candidates — and RBI/Budget were already measured and rejected.

## A methodological trap worth recording: retrospective event lists

A tempting way to answer "what about geopolitical news?" is to compile a list of major shocks
(COVID, Ukraine, Balakot, Hindenburg, tariffs) and test avoiding them. **That list is inadmissible as
a trading rule**, because it was selected *for having moved the market* — survivorship-of-the-scary.
Every entry is on it precisely because it was consequential, which guarantees a flattering backtest
and zero real-world transferability. You cannot subscribe in 2019 to a list written in 2026.

The legitimate instrument for the same question is the one used above: **the gap**, which prices
every overnight geopolitical shock in index points, was available in real time throughout, and
requires no hindsight. Balakot (03:30 IST), the Ukraine invasion open, and any overnight escalation
all enter the study *through their gap footprint* — which is the honest way for them to enter. That
test was run, and it failed the era split.

## Honest limits

- Threshold sweeps on 448 trades are **in-sample optimisation**. That is exactly why the era split
  is the headline here rather than the pooled table — treat any pooled "HELPS" row as unproven.
- Extreme buckets are small (n=19-35). The era-split cells are smaller still (n=6-22). None of these
  would support deployment even if they had agreed.
- The gap is a *proxy* for overnight news, not a decomposition of it. It cannot say *which* input
  drove a day, only how much the market repriced overnight. A dedicated earnings / geopolitical
  date-set is tested separately (see below).
- Era A vs Era B differ in data source (bhavcopy vs Upstox) and in market structure (BANKNIFTY lost
  weekly expiries), so some era divergence is expected on top of genuine regime differences.

## Disposition

**REPORT-ONLY — no engine change.** Do not add a gap filter, and do not extend the NIFTY `rv5<0.9`
filter to SENSEX or BANKNIFTY: on SENSEX, adding `rv5` gating costs money at every threshold in both
eras; on BANKNIFTY it helps only in Era A.

Combined with `ZERO_DTE_EVENT_DAYS.md`, the standing conclusion for all three 0DTE books is: **trade
the full calendar; neither scheduled events nor pre-open magnitude signals earn their keep.**

Script: `studies/ndte/ndte15_preopen.py` (sweeps + era-split robustness + signed-gap diagnostic).
