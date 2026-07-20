# 0DTE event-day avoidance — does skipping RBI/Budget/FOMC days help? (2026-07-19)

**User question:** for all three 0DTE books (NIFTY, BANKNIFTY, SENSEX) — if we had known in advance
that a scheduled event (RBI monetary policy, Budget, FOMC) fell on that expiry date and **avoided
taking the position**, what would win rate and net % return be, versus not avoiding?
Extended on request to the **longest testable history: 2019 → date**.

## Verdict — NO. Avoiding event days costs money, and it now holds across BOTH regimes.

Pooled, all three books, **448 expiries 2019 → Jul 2026**:

| Strategy | n | Win % | Avg % of margin | Total ₹ (1 lot) |
|---|---|---|---|---|
| **Trade everything (deployed baseline)** | 448 | **86.6%** | **+4.51%** | **+₹2,33,447** |
| Avoid RBI MPC (scheduled) | 439 | 86.8% (+0.2pp) | +4.58% | +₹2,32,633 (**−₹814**) ⚠ n=9 |
| Avoid FOMC-spillover | 389 | 86.6% (+0.0pp) | +4.33% | +₹2,01,168 (**−₹32,279**) |
| **Avoid ANY core event** | 380 | 86.8% (+0.2pp) | +4.40% | +₹2,00,354 (**−₹33,093**) |
| Avoid everything incl. CPI/elections | 370 | 86.8% (+0.1pp) | +4.45% | +₹1,93,123 (**−₹40,324**) |

Avoiding events moves win rate by **±0.2pp — statistical nothing — while destroying ₹33k of
profit.** You give up 68 trades to gain nothing.

### The two eras agree independently — this is no longer a single-regime finding

The earlier Oct'24-only study carried the caveat "single regime, could be an artifact." It isn't:

| Era | Baseline | Avoid ANY core | Δ total ₹ |
|---|---|---|---|
| **A · bhavcopy 2019 → Jul'24** (n=266, incl. COVID) | 83.8% · +2.62%m · +₹1,01,169 | 84.3% · +2.59%m · +₹86,683 | **−₹14,487** |
| **B · Upstox Oct'24 → date** (n=182) | 90.7% · +7.28%m · +₹1,32,278 | 90.2% · +6.79%m · +₹1,13,672 | **−₹18,606** |

Both eras: win rate essentially unchanged, total ₹ meaningfully **worse**. Two independent
regimes, seven and a half years, same answer.

## Why: you'd be skipping the vol-crush days

The core-event subset returned **85.3% win / +5.14% of margin** — *better* than the +4.51%
baseline. FOMC-spillover alone (59 trades) ran **+5.74%m vs +4.51% baseline**.

Mechanism: the Fed statement lands ~23:30 IST, so the *next* Indian session collects the
**post-event implied-vol crush** — precisely what a short credit spread is paid to capture. In
Era B those days went 16/16. "Event day" in the sense that matters here is the day the market
exhales, and selling premium into that exhale is the best thing these books do.

## The tail risk is on ordinary days — the filter buys no protection

Worst 12 trades, 2019 → date, tagged:

| Date | Book | % margin | ₹ | Day type |
|---|---|---|---|---|
| 2020-03-26 | BANKNIFTY | −122.9% | −3,190 | ordinary |
| 2021-01-28 | BANKNIFTY | −106.5% | −4,094 | FOMC spillover |
| 2020-06-25 | BANKNIFTY | −105.4% | −4,535 | ordinary |
| 2019-09-26 | BANKNIFTY | −105.2% | −4,292 | ordinary |
| 2022-01-27 | BANKNIFTY | −104.6% | −6,688 | FOMC spillover |
| 2024-01-31 | BANKNIFTY | −102.2% | −9,477 | ordinary |
| 2026-01-27 | BANKNIFTY | −101.1% | **−14,298** | ordinary |
| 2025-01-02 | NIFTY | −101.8% | −11,629 | ordinary |
| 2020-10-15 | NIFTY | −101.1% | −12,975 | ordinary |

**10 of the 12 worst trades were ordinary days**, including the single worst (−₹14,298). Excluding
every event day leaves the worst case untouched. The filter removes return without removing risk.

## Per-book, 2019 → date

| Book | n | Win % | Avg %m | Total ₹ | Avoid ANY core → Δ₹ |
|---|---|---|---|---|---|
| **NIFTY** (weekly, FLIP + rv5 + credit gates) | 273 | 88.3% | +4.69% | +₹1,52,267 | −₹24,524 (costs) |
| **SENSEX** (weekly, CE-always) | 91 | 89.0% | +7.62% | +₹69,356 | −₹8,086 (costs) |
| **BANKNIFTY** (monthly, CE-always) | 84 | 78.6% | +0.55% | +₹11,824 | −₹482 (costs) |

## The RBI caveat — still the one honest exception, still too thin to act on

RBI MPC is the only category with genuine *intraday* risk: the decision drops ~10:00 IST while you
are already short, unlike FOMC/CPI which release after the close. Over 7.5 years, **only 9 of 448
expiries ever landed on an MPC decision day** (43 MPC days occurred; they rarely coincide with a
weekly expiry). Those 9 ran 77.8% win / +1.19%m — weaker than baseline but *still net positive*
(+₹814), so avoiding them would have **cost** money over the full history.

The Era-B-only "avoiding RBI helps +₹4,394" figure was **two trades**, one of them the
2025-10-01 SENSEX −47%m. The full history dissolves it. Watch item, not a filter.

Budget days: **zero overlap** in either era — Budget is 1 February (or a post-election July), which
essentially never coincides with a weekly expiry, and 2020/2025/2026 fell on weekend special sessions.

## What could NOT have been avoided (and why that matters)

The 2019-24 window contains the COVID era, where several of the largest RBI moves were **off-cycle
and unknowable in advance**: 2020-03-27, 2020-05-22, the May'22 surprise hike, plus four emergency
Fed actions (incl. the Sunday 2020-03-15 cut). These are held in a separate `UNAVOIDABLE` bucket and
are **never** included in the avoidable set — folding them in would be hindsight cheating that
flatters the filter.

As it happens **not one of them coincided with an expiry** in this sample (n=0), so they change
nothing here. But the distinction is what makes the "avoid" number honest: a real-world event filter
can only dodge scheduled events, and the genuinely violent surprises are exactly the ones it can't.

## Method

- Deployed geometry (`engine/zero_dte.py`, `engine/dte_multi.py` BOOKS): NIFTY short CE 0.5% OTM /
  wing +200pts fixed / FLIP ret5≥1.0 → PE / rv5<0.9 + credit ≥0.02% of spot; SENSEX & BANKNIFTY
  0.5% OTM / wing 0.83% of spot / CE-always; BANKNIFTY monthly expiries only.
- Entry = expiry-day **OPEN**, settle **intrinsic** vs that index's daily close. Costs 2.5% of
  (short+long) + ₹20×4 legs/lot. Bhav era adds the prior-study liquidity floor (short CONTRACTS ≥ 100).
- Era A = NSE bhavcopy (real premiums, full OHLC); Era B = Upstox expired-instrument premiums.
- **Cross-checks passed:** NIFTY 2019→date 88.3% / +4.69%m vs the config's documented
  **87.8% / +4.0%m (2019-26, rv5 filter)**; SENSEX 89.0% / +7.62%m vs documented **88.8% / +7.6%m**.
- Event calendar verified against rbi.org.in, federalreserve.gov, NSE circular CMTR72349, ECI.
  Includes the rescheduled Aug'25 MPC (06 Aug, not 07) and the three rescheduled 2020-22 meetings.
- FOMC and CPI release after the 15:30 IST close → mapped to the **next** trading day.

## Honest limits

- **SENSEX contributes only Era B, by necessity** — BSE SENSEX weekly options launched in 2023 and
  are absent from NSE bhavcopy entirely. Pre-Oct'24 is NIFTY + BANKNIFTY only.
- **2016 is not testable.** NIFTY weekly options launched Feb 2019; before that only monthly
  expiries existed, so there is no 0DTE weekly book to measure. 2019 is the true floor.
- **Data gap Jul-Sep 2024:** NSE discontinued the legacy `foDDMMMYYYYbhav.csv.zip` format around
  July 2024, so Era A ends 2024-07-04 and Era B starts 2024-10-01. ~3 months missing.
- **Event subsets remain small by construction** (~6 RBI/yr, most never touching an expiry). Any
  per-category row under n≈10 is labelled NOISE above and should not drive a decision.
- Entry uses the daily OPEN rather than a 1-min fill, so absolute levels run mildly optimistic.
  This does not affect the verdict — event and non-event days use identical methodology, so the
  *comparison* is valid even if the levels are not exact.
- **Side-finding worth its own study:** BANKNIFTY monthly on the full history is much weaker than
  its recent slice (Era A 75.8% win / **−1.64%m** on 66 trades, vs Era B 88.9% / +8.60%m on 18).
  The book's documented "91% win" rests on a small recent sample. Not this study's question, but
  it should be looked at before that book is sized up.

## Disposition

**REPORT-ONLY — no engine change.** Do not add an event filter to any 0DTE book. The result is now
robust across two independent regimes and 448 trades, so this question can be considered closed.
Keep trading the full calendar.

Scripts: `ndte13_events.py` (Era B collector), `ndte14_events_2019.py` (Era A collector),
`bhav_dl_0dte_idx.py` (bhavcopy downloader), `build_event_calendar.py` (verified calendar +
next-session mapping), `ndte14_report.py` (full-history analysis). Trade rows persisted in-repo
(`ndte13_trades.json`, `ndte14_trades_2019.json`) because /tmp is periodically purged.
