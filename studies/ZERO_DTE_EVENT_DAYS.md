# 0DTE event-day avoidance — does skipping RBI/Budget/FOMC days help? (2026-07-19)

**User question:** for all three 0DTE books (NIFTY, BANKNIFTY, SENSEX), Oct'24→date — if we had
known in advance that a scheduled event (RBI monetary policy, Budget, FOMC) fell on that expiry
date and **avoided taking the position**, what would win rate and net % return be, versus not
avoiding?

## Verdict — NO. Avoiding event days COSTS money on every definition tested.

Pooled across all three books (182 expiries that pass the deployed filters):

| Strategy | n | Win % | Avg % of margin | Total ₹ (1 lot) |
|---|---|---|---|---|
| **Trade everything (deployed baseline)** | 182 | **90.7%** | **+7.28%** | **+₹1,32,278** |
| Avoid RBI MPC days | 180 | 91.1% (+0.5pp) | +7.52% | +₹1,36,672 (**+₹4,394**) ⚠ n=2 |
| Avoid FOMC-spillover days | 166 | 89.8% (−0.9pp) | +6.54% | +₹1,09,277 (**−₹23,001**) |
| Avoid ANY core event | 164 | 90.2% (−0.4pp) | +6.79% | +₹1,13,672 (**−₹18,606**) |
| Avoid everything incl. CPI/elections | 154 | 90.3% (−0.4pp) | +7.07% | +₹1,06,440 (**−₹25,837**) |

Avoiding events **lowers win rate slightly and destroys ₹19–26k of profit** over 21 months.
The only "helps" row is RBI-only, and it rests on **two trades** — see below.

## Why: the events you'd avoid are the *best* days for short premium

The event subset (18 of 182 expiries) returned **94.4% win / +11.82% of margin** — far *better*
than the +7.28% baseline. Sixteen of those eighteen were **FOMC-spillover** days (the Indian
session *after* a Fed decision, since the statement lands ~23:30 IST) and they went **16/16, 100%
win, +15.05% of margin, +₹23,001**.

That is not luck, it's mechanism: **post-event implied-vol crush**. Once the announcement is out,
uncertainty premium drains from options — which is exactly what a short credit spread is paid to
capture. "Event day" in the sense that matters here means *the day the market exhales*, and
selling premium into that exhale is the single best thing these books do.

## The tail risk is NOT on event days

The worst trade in the whole sample (**−₹14,298**, BANKNIFTY) landed on an ordinary non-event day.
Excluding every event day leaves that worst case completely untouched (EX-EVENT worst = −₹14,298,
identical to baseline), while event-only worst was just −₹5,482.

So an event filter **gives up profitable vol-crush days and buys no tail protection** — it removes
return without removing risk. That's the whole argument in one line.

## Per-book detail

| Book | Baseline n / win / avg | Event expiries | Event-only result | Avoid ANY core → total ₹ |
|---|---|---|---|---|
| **NIFTY** (weekly, FLIP + rv5 + credit gates) | 73 · 93.2% · +6.54%m | 6 (8%) | 100% win, +11.41%m | −₹6,320 (costs) |
| **SENSEX** (weekly, CE-always) | 91 · 89.0% · +7.62%m | 10 (11%) | 90.0% win, +9.98%m | −₹8,086 (costs) |
| **BANKNIFTY** (monthly, CE-always) | 18 · 88.9% · +8.60%m | 2 (11%) | 100% win, +22.24%m | −₹4,199 (costs) |

## The RBI caveat — the one place to stay honest

RBI MPC is the only category with genuine *intraday* risk: the decision drops ~10:00 IST while
you are already short, unlike FOMC/CPI which release after the close. And the single worst event
trade in the study was an RBI day — **2025-10-01 SENSEX, −46.97% of margin (−₹5,482)**.

But across 21 months **only 2 of 182 expiries ever landed on an MPC decision day** (11 MPC days
occurred; they rarely coincide with a Tue/Thu weekly expiry). Those two were +₹1,087 and −₹5,482.
**n=2 cannot support a trading rule** — the "+₹4,394 benefit" of avoiding RBI is one bad trade,
not an edge. Flagging it as a *watch item*, not a filter.

Budget days produced **zero** overlap: both 2025-02-01 and 2026-02-01 fell on a weekend
(Sat/Sun special live sessions), so no weekly expiry coincided.

## Method

- Books reproduced at deployed geometry (`engine/zero_dte.py`, `engine/dte_multi.py` BOOKS):
  NIFTY short CE 0.5% OTM / wing +200pts fixed / lot 75 / FLIP ret5≥1.0 → PE / filters rv5<0.9 +
  credit ≥0.02% of spot; SENSEX & BANKNIFTY 0.5% OTM / wing 0.83% of spot / CE-always / no extra
  filters; BANKNIFTY monthly expiries only.
- Entry = expiry-day **OPEN**, settle **intrinsic** vs that index's daily close. Costs 2.5% of
  (short+long) + ₹20×4 legs/lot — identical to `ndte7`/`ndte8`/`sensex_flip`.
- Real Upstox expired-instrument premiums, Oct'24→19 Jul 2026.
- **Cross-checks passed:** SENSEX 89.0% win / +7.62%m vs documented **88.8% / +7.6%m**; BANKNIFTY
  88.9%; NIFTY filtered n=73 matches the documented rv5-filtered sample.
- Event calendar verified against primary sources (rbi.org.in, federalreserve.gov, NSE circular
  CMTR72349). Includes the **rescheduled Aug'25 MPC (decision 2025-08-06, not 08-07)**.
- FOMC and CPI release after the 15:30 IST close, so they are mapped to the **next** trading day.
- CPI dates are largely **inferred** from MOSPI's "12th or next working day" rule (only 3 verified)
  and elections are a judgment call — both are reported separately and excluded from the headline.

## Honest limits

- **Single regime** (Oct'24→Jul'26, 21 months) — the same caveat that killed the index-fade
  "6 positive years in one regime" result. 2019-24 bhavcopy has expiry-day OPEN prints only, so
  this cannot be extended backwards without redoing the collection.
- **Event subsets are small by construction** (~6 RBI/yr, and most never touch an expiry). Any
  per-category conclusion below n≈10 is noise and is labelled as such above.
- Entry uses the daily OPEN rather than a 1-min fill, so absolute levels run slightly optimistic
  (NIFTY prints 93.2% here vs 90.4% on 1-min in `ndte11`). This does **not** affect the verdict:
  event and non-event days are measured with identical methodology, so the *comparison* is valid.

## Disposition

**REPORT-ONLY — no engine change.** Do not add an event filter to any 0DTE book. If anything the
data argues the opposite (FOMC-spillover expiries are the best-performing subset), but 16 trades
is not enough to justify *up*-weighting them either. Keep trading the full calendar.

Scripts: `studies/ndte/ndte13_events.py` (collector, results persisted in-repo at
`ndte13_trades.json`), `studies/ndte/build_event_calendar.py` (calendar + next-trading-day
mapping), `studies/ndte/ndte13_report.py` (analysis).
