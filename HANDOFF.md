# Handoff — institutional-trader

## 17-Aug LIVE ENGINE + VIEWER AUDIT - 5 BLOCKERS. Engine safe to run with 2 rules.
B1 Settlement has NO DATE GUARD on the price. from_date=to_date=expiry returns empty (no same-day
   daily bar), so it falls through to _spot() = today's LTP every time. On the catch-up path a fetch
   failure settles a days-old expiry at TODAY's price, silently. THREE OPEN v1 POSITIONS SETTLE
   THROUGH THIS ON 25-AUG. Works today only because SETTLE_AFTER 15:40 > CAS_END 15:35 makes LTP the
   auction print - load-bearing and undocumented. Fix: 3 lines each at stock_credit.py:348,
   stock_credit_v2.py:506, swing_credit.py:329 - require the bar dated the expiry, else refuse.
B2 todays_close() stale-bar guard + direction audit are on all three SCAN paths but NO resolve path.
B3 THE VIEWER IS NOT READ-ONLY: ui_terminal.py:1226 -> signal_db.py:101 writes
   data/signals_export.csv on the first refresh each day. Only caller in the system.
B4 STOCK_CREDIT_MAX_NEW_PER_DAY is per SCAN INVOCATION, not per day. A restart 15:36-15:40 can open
   5+5+3 MORE positions. Did not fire today.
B5 *** BAJAJ-AUTO-2026-07-29 carries a REACHABLE STOP under a no-stop book. stop_cost 241.8 frozen
   from when STOP_MULT was 2.0 = 0.81x width; current cost 211.22, so 30.58 POINTS FROM FIRING,
   realising -Rs9,068 on a policy that says no stops. USER DECISION NEEDED. ***
MINE, FROM TODAY: signal_recheck OI floor ALWAYS collapses to 100 units (d has no "lot" key - use
   p.get("lot")); the v2 Telegram line hardcodes "10 of 17 candidates on 17-Aug", stale tomorrow;
   UI still shows OI>=100 at :869 and withdrawn OOS figures at :454/:435/:580.
OTHER MAJORS: signal_recheck rebuilds messages every 5s 09:30-15:40 (~66k extra API calls/day - the
   proximate cause of today's DNS failure); market_is_trading_today cannot tell a network failure
   from a holiday (fix: never cache a negative from an empty frame, fail OPEN - todays_close already
   fails closed per stock); once-a-day markers burnt BEFORE the work, no success check; one bad
   signal kills the whole Telegram batch; a failed book write reports success; TP/stop bookings have
   no spread gate (5 of 19 closes in the first 10 min, one 22s after the open);
   _stock_settlement_due opens the resolve gate 24/7 for ALL books if ANY position expired;
   disabling STOCK_CREDIT_ENABLED strands open positions forever.
VERIFIED CLEAN: no double-settle, P&L arithmetic dimensionally correct, no duplicate ids,
   engine_runner integrity fine after the corruption revert, v0 inherits the OI floor, watchlist and
   trading floors identical, phantom stop correctly neutralised.
RULES UNTIL FIXED: (a) do NOT restart the engine 15:15-15:40; (b) watch BAJAJ-AUTO.

## 17-Aug USER: no evidence OI gating helps win rate/ROM — CONCEDED, bucket study now running
He is right. The OI gate was justified as a FIDELITY fix (a bhavcopy close on a zero-OI contract is
NSE theoretical settlement, not a fillable price) and it LOWERED IS ROM by half. That is a
measurement correction, NOT evidence the gate improves trading. No OI threshold above zero has ever
been tested for win rate or ROM in either window. I deployed 10 lots then 5 lots on SIGNAL COUNTS
and called it measured, twice. Live it is inert anyway - spread binds first (blocks all 4 names OI
blocks, plus 6 more).
NOW MEASURING: every row carries oi_units + oi_lots, and both windows print an OI-BUCKET table
(0 / 1-2 / 2-5 / 5-10 / 10-25 / 25+ lots) with win rate, ROM-Rs and Rs/trade. If buckets are flat
above zero, the only defensible gate is exclude-zero and any lot threshold is arbitrary.
OOS NOTE: Upstox candles always carried OI at index 6, but leg() cached only the close, so OOS
needs a FULL REFETCH (hours) into a new cache /tmp/oos_legcache_oi.json. The OOS walk is now gated
on OI too, matching IS - which also closes audit MAJOR #3 (windows were not like-for-like).

## 17-Aug OI GATE VERDICT: redundant LIVE, essential in the BACKTEST (user was right)
He challenged whether the OI gate matters given the engine already runs a bid-ask check. Evidence
from todays 17-name watchlist: the OI gate blocks 4 names (ASIANPAINT/CIPLA/IOC/DLF) and the SPREAD
gate already blocks all 4; OI blocks ZERO that spread does not. Spread blocks 6 MORE that OI passes
(COLPAL 59%, HEROMOTOCO 9.1%, NESTLEIND, AMBUJACEM, BHEL, SUNPHARMA). => LIVE the OI floor is inert;
bid-ask <= 6% is the binding constraint. Left at 5 lots as a harmless backstop; not worth another
config change either way.
BUT bhavcopy has NO bid/ask - only CLOSE and OPEN_INT - so the HARNESS cannot run the spread gate.
There OI is the ONLY liquidity proxy and stands in for it. That is why gating it halved IS ROM.
*** THE BIG UNMODELLED GAP, now the honest headline caveat: the live SPREAD gate blocked 10 of 17
candidates TODAY (59%). The backtest models none of it. Every ROM figure is computed on a
population that includes names live would refuse. Larger source of optimism than any OI threshold. ***
ALSO ADMITTED: the 10-lot and 5-lot deploys were made on a SIGNAL-COUNT measurement, not a P&L
backtest. No OI threshold above ~zero has ever been backtested for win rate or ROM.
RUNNING: dte_sweep.py IS (floors 3/5/7/10/15/20/25, reports rejections on premium AND OI per DTE,
~2-3h) -> /tmp/dte_is.log; code audit agent on the OI gate + rupee columns + expiry settlement.

## 17-Aug STUDY UPDATED with final IS+OOS+ROM (six corrections documented)
studies/DEPLOYED_EVIDENCE_AUDIT.md SS5/SS6 rewritten. FINAL median-cohort numbers:
  IS  v2 77.5%/+25.3% ROM-Rs/Rs5,427/6-6yrs (n=191) · v1 80.1%/+14.1%/Rs2,828/5-6 (n=322) ·
      v0 81.9%/+13.6%/Rs3,412/6-6 (n=216)
  OOS v2 82.8%/+27.3%/Rs3,477/2-3 (n=58) · v1 80.2%/+10.4%/Rs1,145/3-3 (n=192) ·
      v0 80.4%/+4.1%/Rs565/2-3 (n=97)
  Rs/mo: v2 9,040 · v1 9,733 · v0 2,430 = ~21,200 stock; ~27,000 with index; 80% rule = ~21,600
Six corrections listed in SS5: leg alignment, v1 population, corporate-action scale (parity),
one-open-position, OI>=100 both legs (THE BLOCKER - halved IS ROM), expiry settlement from the
options own closes (users fix). Plus the phantom 3x stop removed everywhere.
CONVERGENCE CAVEAT recorded in the study: IS and OOS agree now, but NOT independently - two
different fixes moved two different windows toward each other. Encouraging, not proof.
OPEN + NOW DOCUMENTED: STOCK_CREDIT_MIN_DTE=10 has NO study behind it. Every study holds it fixed
at 10 while sweeping something else; the only DTE sweep on record belongs to the rejected low-c/w
rescue. It pushes the books into far expiries where strikes are thin - possibly CREATING the
illiquidity the new OI gate then removes. Sweep 5/10/15/20/25 both windows is the next test.
STILL OWED: UI + Telegram still carry pre-OI-gate numbers = STALE.

## 17-Aug FINAL BOTH-WINDOW TABLE (OI-gated IS + money-weighted ROM) — THE GAP CLOSED
              IS ROM-Rs   n    yrs |  OOS ROM-Rs   n    yrs   Rs/trade
  v2            +26.1%   200   6/6 |    +24.9%    58   2/3    Rs3,180
  v1            +12.1%   336   6/6 |     +9.1%   192   3/3    Rs1,003
  v0            +13.7%   223   5/6 |     +2.4%    97   2/3      Rs335
This morning the same comparison read +30.7% vs +3.7%. Two changes closed it: the OI gate cut the
untraded contracts out of IS, and money-weighting lifted OOS (v2 +3.7 -> +24.9 from weighting by
rupee margin instead of strike points; v0 SIGN FLIPPED -0.7 -> +2.4).
*** CAVEAT TO CARRY: the convergence is NOT independent confirmation. I applied a different fix to
each window and they moved toward each other. Both fixes are defensible on first principles (match
live gate; rupee margin is what an account commits) and neither was chosen to make them agree - but
I predicted IS would FALL to OOS, and instead OOS ROSE to IS via a different mechanism. Treat the
agreement as encouraging, not as proof. ***
STILL OPEN (audit): settle() falls back to the ADJUSTED close (~4-5% of trades, catastrophic per
trade on a corporate-action name); parity returns the FORWARD not spot (25-39% of chains pick a
different strike, needs discounting); OOS has NO OI gate so the two windows are still not the same
experiment; caps unmodelled; IS window is 2019-01-01 to 2024-07-05 so 6 years is 5 + a stub; v2 stop
skippable only in the profitable direction; cost model thinner than the repo standard 2.5%+Rs20x4.
AND: the OI-gate + money-weighting code is itself UNREVIEWED - no audit since it was added.
UI/studies/Telegram still carry the pre-OI-gate numbers = STALE. Correction pass owed.

## 17-Aug 10:49 DEPLOYED: size-aware OI floor (10 lots) on all three stock books
config STOCK_CREDIT_MIN_OI_LOTS=10; gate is max(100, 10*lot) on the SHORT leg in stock_credit.py
and stock_credit_v2.py (v0 inherits); watchlist liq_ok uses the same floor. Engine restarted 10:49,
clean. Ledger + engine.db recorded it. Revert: git checkout 4db9563~1 -- engine/config.py
engine/stock_credit_v2.py engine/stock_credit.py
MEASURED FIRST (bhavcopy 2019->Jul-2024, deployed geometry): of signals passing the old 100-unit
gate, 85% survive at v2/v0 geometry and 89% at v1 - removes ~1 signal in 8, the thinnest contracts.
Underlying number that matters more: only 25-34% of raw candidates carry ANY meaningful OI.
CORRECTION I MADE IN-TURN: I wrote "markets closed" in the deploy note and commit message. It was
MONDAY 10:49 and markets were OPEN. Safe (freeze window is 15:15-15:40) but the change is live for
TODAY 15:36 scan, not idle. Commit message on 4db9563 carries the wrong claim - do not repeat it.
STILL SHORT-LEG ONLY: the long wing is the illiquid leg (it drove the 70% IS cut). Gating both legs
is the open decision the user has not answered.
OOS backtest (OI gate + money-weighted ROM) still running -> /tmp/dbt8_oos.log, 85/113 at 11:23.
UI/studies/Telegram still carry PRE-OI-GATE numbers = stale; correction pass owed after OOS lands.

## 16-Aug BLOCKER FIXED (OI gate) + money-weighted ROM. IS HALVED. OOS RUNNING.
OI UNITS SETTLED (user challenged this): bhavcopy OPEN_INT and Upstox `oi` are BOTH in UNITS
(shares), not contracts. Proof: HAL/INFY/ACC OI 100% divisible by lot; OFSS live oi 34,300 / lot
100 = 343 lots. So harness MIN_OI=100 matches live STOCK_CREDIT_MIN_OI=100 exactly.
*** FINDING ABOUT THE LIVE ENGINE: 100 units is LESS THAN ONE LOT for every name (lots 125-1000),
so the live "OI >= 100" gate is effectively "OI > 0". It is not a liquidity filter; the bid-ask
<= 6% check does all the real work. Raising it to ~10 lots is a config change, user's call. ***
IS WITH THE GATE (median cohort, both weightings now printed by the harness of record itself):
  v2 n 667->200  WIN 82.2->78.5%  ROM-pts +30.7->+16.9%  ROM-Rs +26.1%  Rs5,428/tr  6/6 yrs
  v1 n 477->336  WIN 79.9->80.7%  ROM-pts +19.9->+11.5%  ROM-Rs +12.1%  Rs2,338/tr  6/6->5/6
  v0 n 569->223  WIN 83.1->83.4%  ROM-pts +17.8->+16.9%  ROM-Rs +13.7%  Rs3,331/tr  6/6->5/6
The audit's theory was RIGHT: IS ROM roughly halved. Gap to OOS narrows but does not close.
70% of v2's trades were cut, not the 30% the audit measured, because the audit counted only the
SHORT leg - BOTH legs must clear and the LONG WING is the illiquid one.
Money vs points weighting genuinely differs: v2 +16.9 pts vs +26.1 Rs; v0 +16.9 pts vs +13.7 Rs.
USE THE RUPEE COLUMN.
Also fixed: deployed_backtest.py now prints MEDIAN COHORT + FULL BAND itself (audit MAJOR #2 - it
previously could not reproduce its own published headline).
STILL OPEN from the audit: settle() adjusted-close fallback -> should be `continue` (MAJOR #4);
parity returns forward not spot, needs discounting (MAJOR #3); OOS has no OI gate (its candles only
exist if traded, so largely redundant but NOT identical); caps unmodelled; IS window is really
2019-01-01 to 2024-07-05 so "6 years" is 5 + a stub.
OOS run in flight -> /tmp/dbt8_oos.log. NOTHING deployed. Published UI/study/Telegram numbers are
now STALE AGAIN (they carry the pre-OI-gate figures) and must be updated after OOS lands.

## 16-Aug HARNESS AUDIT (post-parity, post-open_until) — 1 BLOCKER, 5 MAJOR. IS ROM IS AN UPPER BOUND.
The four completed fixes were attacked directly and HELD: parity_spot maths + CE/PE arg order at
both call sites, open_until string compare and max(), the date-keyed leg join, Donchian/gap/DTE all
match live, and tp_sweep has NO logic drift from deployed_backtest.
NEW FINDINGS:
1 BLOCKER - IS prices 24% (1-OTM) to 30% (2-OTM) of its SHORT legs off contracts with OPEN_INT==0.
  Bhavcopy CLOSE for an untraded contract is NSE THEORETICAL SETTLEMENT, not a print. Live refuses
  OI<100 (stock_credit_v2.py:411); OOS structurally cannot include them (a candle exists only if it
  traded). This is the most likely single cause of IS +30.7% vs OOS +3.7%. FIX = one line: gate
  OPEN_INT>=100 on both legs at entry in the IS path. bhavcopy already carries the column.
2 MAJOR - deployed_backtest.py has NO median-cohort filter; it prints the FULL band (IS v2 +51.1%).
  The published 667/+30.7% figures come from tp_sweep.py. The harness of record cannot reproduce
  its own headline. Fix: add the cohort print to deployed_backtest.py.
3 MAJOR - parity_spot returns the FORWARD not spot (S = K + C - P omits discounting). Measured
  +0.20..+0.30% bias on 5 liquid names; ATM strike differs from the true-close ATM in 25-39% of
  chains, tilted one strike UP. Fix: S = K*exp(-r*T) + C - P.
4 MAJOR - settle() silently falls back to the ADJUSTED close when expiry-day parity is unavailable,
  reintroducing bug 3 at settlement. Pickle ends 2024-07-05 so all later expiries hit it (~4-5% of
  each cohort). Catastrophic per trade on a corporate-action name. Fix: `continue`, never fall back.
5 MAJOR - ROM pools in strike POINTS not money. Lot-weighted: OOS v2 +3.7 -> +24.9%, v1 +4.8 ->
  +9.2%, v0 -0.7 -> +2.4% (SIGN FLIPS). The published ROM is not what an account earns.
6 MAJOR - IS and OOS are not the same experiment (5 differences incl. OOS dropping ALL
  corporate-action names via ATM_MAX_DRIFT). "OOS confirms IS" is not supported by construction.
7-11 MINOR - v2 stop skippable in the profitable direction only; cost model thinner than the repo's
  own 2.5%+Rs20x4 standard; IS window is 2019-01-01 to 2024-07-05 NOT Sep-2024 (so "6/6 years" is
  5 years + a 6-month stub); caps/liquidity gate unmodelled; tp_sweep exits[bk] trap if a deployed
  TP ever leaves SWEEP_TPS.
AUDITOR RATING: 6/10. PRIORITY ORDER: (a) OI>=100 gate in IS, (b) cohort print in the harness of
record, (c) settle() fallback -> continue, (d) lot-weighted ROM, (e) discounted parity.
NOTHING deployed. Published numbers stand as an UPPER BOUND until (a) is run.

## 16-Aug CONSOLIDATED UPDATE SHIPPED (studies + UI + Telegram + CLAUDE.md)
Final numbers everywhere = production harness after 4 corrections, MEDIAN COHORT c/w 0.40-0.50:
  IS  v2 82.2%/+30.7% (n=667, 6/6) · v1 79.9%/+19.9% (n=477, 6/6) · v0 83.1%/+17.8% (n=569, 6/6)
  OOS v2 82.8%/+3.7% (n=58, 2/3) · v1 79.8%/+4.8% (n=193, 3/3) · v0 80.4%/-0.7% (n=97, 2/3)
  Rs/mo: v2 8,198 (2.6/mo) · v1 8,711 (8.6/mo) · v0 1,443 (4.3/mo); +index = ~24,159; 80% = 19,327
Updated: studies/DEPLOYED_EVIDENCE_AUDIT.md SS5+SS6 rewritten · studies/README.md index ·
UI LIVE STRATEGIES + PROFIT AND LOSS + WORK BEHIND tables + 4 STUDIES cards + PM/trade-log v0
headers · Telegram _TG_ANALYSIS v2/v1/v0 evidence blocks · CLAUDE.md live-books table + a new
block on what the two windows can and cannot say + TP-is-settled note. Viewer AND engine restarted.
ENGINE LOGIC UNTOUCHED throughout: config.py unchanged since 6-Aug; only display strings edited.
Remaining disclosed gaps: daily caps ~5%, todays lot sizes on old trades, margin proxy vs SPAN,
no bid-ask/OI gate, OOS on guards not parity, harness not re-audited since the parity fix.

## 16-Aug FIX #1 COMPLETE — BOTH WINDOWS. v2 lifts off zero; all three books now ~flat OOS.
OOS with the one-open-position rule (median cohort, deployed TP):
  v2 n=58  +3.7% ROM (was -0.3%)  2/3 yrs  Rs8,198/mo  90% CI [-27.8%, +39.7%]
  v1 n=193 +4.8% ROM (was +5.4%)  3/3 yrs  Rs8,711/mo  90% CI [-5.0%, +13.3%]
  v0 n=97  -0.7% ROM (was -3.9%)  2/3 yrs  Rs1,443/mo  90% CI [-14.8%, +12.5%]
IS with the rule: v2 +30.7% 6/6 · v1 +19.9% 6/6 · v0 +17.8% 6/6.
READING: the fix moved v2 and v0 UP in both windows, confirming the removed re-entries were
adverse. v2 is no longer negative OOS. BUT all three CIs still span zero and v2 n=58 with a
4-trade 2024 stub, so the OOS window STILL cannot rank the books. The v1-over-v2 lean from 15-Aug
is WEAKER now - point estimates are +4.8 vs +3.7, effectively tied.
TP verdict UNCHANGED and now firmer: v2 flat across 30-70 both windows; v1 slope still INVERTS
(IS falls +20.0->+13.2, OOS rises +1.8->+11.1) = noise, do not move off TP-40; v0 negative-to-flat
at every TP. KEEP v2 TP-50, v1 TP-40, v0 TP-40. NOTHING TO DEPLOY.
Remaining audit gaps (unfixed, disclosed): daily caps ~5%, todays lot sizes on 2019-26 trades,
margin proxy not SPAN, no bid-ask/OI gate, OOS uses guards not parity, harness not re-audited
since the parity fix.
STILL PENDING: consolidated correction across studies SS5/SS6 + UI + Telegram + CLAUDE.md table.

## 16-Aug FIX #1 LANDED: one-open-position-per-symbol rule now modelled (IS done, OOS running)
Audit gap #1 (biggest): live each book skips a name it already holds OPEN until it closes
(stock_credit.py:223, stock_credit_v2.py:372). Harness only had the 3-day gap, so 59% IS / 31% OOS
of trades were same-book re-entries inside 35 days that live could never take. Bias had a
direction: winners exit fast and free the name, losers stay open, so the extra trades were drawn
from names STILL GOING AGAINST the book.
Implemented as per-symbol `open_until` {book: exit_day}; it now drives self-blocking, v1 deferring
to an open v2, and the same-day clash from ONE piece of state (v2_hold_until removed).
Both deployed_backtest.py and tp_sweep.py carry it.
IS RESULT (median cohort) - REMOVING THOSE TRADES IMPROVED EVERY BOOK:
  v2 n 1041->667, TP50 ROM +24.0% -> +30.7%, years 5/6 -> 6/6, win 80.3% -> 82.2%
  v1 n  566->477, TP40 ROM +23.5% -> +19.9%, years 6/6 (unchanged), win 79.7% -> 79.9%
  v0 n  724->569, TP40 ROM +18.8% -> +17.8%, years 6/6 (unchanged), win 81.5% -> 83.1%
=> v2 is the biggest beneficiary: the re-entries were concentrated in its book and they were
adverse. v2 now 6/6 years IS. v1/v0 slightly lower but unchanged in shape. TP still flat for v2
(+28.8..+31.4 across 30-70) and still decaying with higher TP for v1 - same verdict, keep TPs.
OOS in flight /tmp/tp2_oos.log. IS rows /tmp/tpsweep_is_rows.json.

## 16-Aug TP SWEEP COMPLETE — lowering TP does NOT help; the two windows DISAGREE on direction
studies/ndte/tp_sweep.py, median cohort, hierarchy timing held at deployed TP-50 so every level
scores the SAME trades.
IS  ROM by TP (30/40/50/60/70): v2 +23.5/+23.4/+24.0/+24.1/+24.0 · v1 +23.5/+23.5/+20.8/+20.4/+19.5
    · v0 +19.7/+18.8/+18.7/+18.5/+19.4   -> essentially FLAT for v2 and v0; v1 decays ABOVE TP-50.
OOS ROM by TP: v2 -3.4/+0.0/-0.3/+2.4/+2.4 (2/3 yrs at every level) · v1 +3.8/+5.4/+6.8/+10.5/+12.3
    (3/3 yrs at every level) · v0 -5.4/-3.9/-1.4/-2.0/-0.8 (never positive).
VERDICT: (1) The user's idea of cutting TP to 40 or 30 to force a positive net is REFUTED - lower
TP buys win rate and gives back average win size, and the two cancel. v2 at TP-30 is the WORST OOS
cell (-3.4%). (2) v1 IS->OOS DISAGREE ON SLOPE: in-sample lower TP is better (+23.5 at 30 vs +19.5
at 70), out-of-sample HIGHER is better (+3.8 at 30 vs +12.3 at 70). A parameter whose slope
inverts between windows is noise, so DO NOT move v1 off TP-40. (3) v0 is negative at every TP.
NOTHING TO DEPLOY from this sweep. Deployed settings stay: v2 TP-50, v1 TP-40, v0 TP-40.
STILL PENDING: one consolidated correction across studies SS5/SS6 + UI tables/cards + Telegram
evidence lines + CLAUDE.md book table, all of which still carry pre-parity numbers.

## 16-Aug FINAL CLEAN BASELINE (both windows, corporate-action fixed) — v1 IS THE BOOK
Method: IS uses PUT-CALL PARITY spot (bhavcopy has every strike). OOS cannot - Upstox expired
candles exist only for strikes that traded, so a parity OOS returned v2 n=0 / v1 n=9; OOS therefore
uses the drift + ladder-edge guards and is headlined on the MEDIAN COHORT (c/w 0.40-0.50).

HEADLINE (median cohort, which is where all 21 live fills sit at c/w 0.39-0.47):
  IS 2019-Sep24: v2 80.3% / +24.0% ROM (n=1041) · v1 79.7% / +23.5% (n=566) · v0 81.5% / +18.8% (n=726, 6/6 yrs)
  OOS Oct24-Aug26: v2 77.1% / -0.3% (n=70, 2/3) · v1 80.2% / +5.4% (n=227, 3/3) · v0 76.8% / -3.9% (n=99, 2/3)
  Rupees OOS cohort: v2 3.1 sig/mo Rs2,111/tr = Rs6,567/mo · v1 10.1 sig/mo Rs1,019 = Rs10,276/mo · v0 -Rs842/mo
=> v1 IS THE ONLY BOOK POSITIVE IN BOTH WINDOWS AND ALL 3 OOS YEARS. v2's OOS edge is ZERO at the
c/w it actually trades (its whole-sample +4.1% comes from the high-c/w tail). v0 negative OOS.
This REVERSES the entire history of this repo, which has always called v2 the leader.
ALL published numbers (UI, studies SS5/SS6, Telegram lines, CLAUDE.md book table) are WRONG and
must be replaced with the above. NOTHING deployed; engine untouched; v0 stays paper per user.
PENDING: TP sweep 30/40/50 on this clean baseline (user asked; must be judged IS->OOS, not tuned
until positive), then one consolidated correction across study + UI + Telegram + both remotes.

## 15-Aug ~19:00 PARITY FIX WORKED; ROM decomposition shows the tail still dominates
Root cause was adjusted-spot vs unadjusted-strikes. Two heuristic guards FAILED (median c/w
0.78->0.56->0.54). REAL FIX: derive spot from the option chain by put-call parity (S = K + C - P at
the strike where |CE-PE| is least) - both quotes carry the same unadjusted scale as the strikes so
a split cannot desync them. Adjusted equity series still used for the Donchian breakout only.
IS (parity, /tmp/deployed_bt_is_rows_PARITY.json): v2 n=1706 82.4%/+41.3% 6/6 median cw 0.47 ·
v1 n=874 83.2%/+42.0% 6/6 median 0.45 · v0 n=726 81.5%/+18.8% 6/6. Acceptance test PASSED
(median cw 0.44-0.49, matching the 21 live trades at 0.39-0.47). n ROSE (1025->1706).
USER THEN ASKED: is ROM computed on the median c/w? Decomposition says NO, the tail still carries
it: v2 gets 33.4% of all its profit from cw>=0.65 (n=330, ROM +253.7%) and v1 gets 38.8% from the
same bucket. AT THE MEDIAN COHORT (cw 0.40-0.50) the honest numbers are v2 80.3% win/+24.0% ROM
(n=1041) and v1 79.7%/+23.5% (n=566). v0 has no tail at all (band caps 0.40) so its +18.8% is
already clean - v0 is the only book whose headline needs no discount, and it is now 6/6 years.
=> REPORT THE MEDIAN-COHORT ROM as the headline going forward; the high-cw tail on high-priced
dense-ladder names (MARUTI 0.73, LT 0.60) is structurally real but is NOT what the live book trades.
OOS parity run in flight: /tmp/dbt6_oos.log (extra chain fetches per signal, slow).

## 15-Aug ~17:30 ROOT CAUSE FOUND: corporate-action scale mismatch (NOT a c/w cap issue)
User challenged +182.8% ROM and 1.92:1 win:loss (both impossible for a vertical) and then refused
an arbitrary c/w cap, asking for evidence. He was right. Audit + probe root-caused it:
fetch_upstox_historical returns split/bonus-ADJUSTED closes; bhavcopy STRIKE_PR and Upstox expired
strikes are UNADJUSTED as-listed. On split/bonus names the scales diverge, atm pins to the far end
of the ladder, legs are picked DEEP ITM, credit~width, margin~0, and settlement vs the same
adjusted price books a fabricated full-credit win. Evidence: IS median c/w per symbol - HCLTECH
0.96 PIDILITIND 0.95 DRREDDY 0.95 HDFCBANK 0.91 RELIANCE 0.91 WIPRO 0.90 (all split/bonus); names
with NO corporate action sit 0.44-0.49, matching all 21 live trades (0.39-0.47). c/w NEVER
genuinely exceeds ~0.50.
FIX (deployed in harness, not engine): ATM_MAX_DRIFT=0.05 - reject the name-day when the nearest
strike is >5% from the close. A DATA guard, no upper c/w bound, so a real high-c/w quote would
still trade. Runs in flight: /tmp/dbt4_is.log, /tmp/dbt4_oos.log.
Audit clean-subset preview: OOS v2 +32.5% -> +0.4% ROM, Rs14,956 -> Rs2,224/trade; OOS v1 +14.6%
-> +7.7%, Rs1,428; v0 -4.0% unchanged. IS v2 +182.8% -> +40.6%, v1 +84.5% -> +31.1%.
=> v1 likely the STRONGER book OOS, reversing every prior version of this study. ALL UI/study/
telegram numbers pushed 15-Aug are WRONG pending these runs.
Audit also flagged (open, not yet fixed): live one-open-position-per-symbol rule not modelled
(59% IS / 31% OOS same-book re-entries within 35d); MAX_NEW_PER_DAY/MAX_OPEN not applied (~5%);
lot sizes are todays applied to 2019-2026 trades; OOS 3/3 years is really 3mo+12mo+8mo.
USER ALSO ASKED: sweep v2 TP 50->40->30 to find a positive net. Do it ONLY on the fixed harness
and judge IS->OOS; tuning until positive is curve-fitting and must be called out.

## 15-Aug DONE: corrected harness + rupee calibration + UI/Telegram/studies refreshed
Numbers of record (deployed_backtest.py, live hierarchy modelled: v1=D10 only, v1 defers to open
v2, v0 defers to v1): IS v2 95.4/+182.8 (2526,6/6) · v1 89.4/+84.5 (805,6/6) · v0 80.1/+12.4 (322,5/6).
OOS v2 81.2/+32.5 (96,3/3) · v1 81.7/+14.6 (268,3/3) · v0 76.8/-3.9 (99,2/3).
Rupees (OOS only, per-symbol lot sizes /tmp/lotmap.json): v2 4.3 sig/mo Rs14,956/tr = Rs64,311/mo ·
v1 11.9 sig/mo Rs3,149 = Rs37,509/mo · v0 4.4 sig/mo -Rs191 = -Rs842/mo. Total ~Rs106.7k, plan 80% = Rs85.4k.
Shipped: study SS5+SS6 rewritten, UI (LIVE STRATEGIES, P&L, WORK BEHIND, STUDIES cards, PM+tab v0
headers) all stale numbers purged, Telegram evidence lines updated, engine+viewer restarted, pushed.
v0 STAYS LIVE as paper forward-test per user 15-Aug. PENDING: relaunch harness audit agent (the
2nd one confirmed the D10/defer findings then hit the usage limit; a full pass on the fixed
harness has not completed).

## PRODUCTION BACKTEST COMPLETE (15-Aug morning) — the numbers of record

studies/ndte/deployed_backtest.py, full universe, date-aligned, engine rules (cross-book gap,
v1-wins-clash, exit costs, fake-stop filter):
- IS 2019-Sep24:  v2 95.5%/+183% (n=2497, 6/6) · v1 92.9%/+160% (n=3078, 6/6) · v0 81.7%/+11.2% (n=191, 5/6)
- OOS Oct24-Aug26: v2 80.2%/+31.8% (n=91, 3/3) · v1 79.0%/+18.0% (n=443, 3/3) · v0 76.4%/-11.5% (n=55, 1/3)
GATE BOOKS CONFIRMED both windows. v0 NEGATIVE OOS - regime-flip signature; every corrected
measurement agrees the 0.35-0.40 band pays nothing after 2024. v0 OFF/KEEP is the USER'S open
decision - do not touch config without his explicit sign-off. All in DEPLOYED_EVIDENCE_AUDIT.md
§5 + UI STUDIES tab, pushed both remotes. Rows: /tmp/deployed_bt_is_rows.json, /tmp/deployed_bt_oos_rows.json.

## AUDIT OF DEPLOYED BOOKS — RESULTS (14-Aug) + corrected re-measurement IN FLIGHT

Audit agent verdicts (full text in studies/DEPLOYED_EVIDENCE_AUDIT.md once written):
- 0DTE NIFTY FLIP + 0DTE SENSEX: SURVIVE. Single-day real-trade prints, no path walk, intrinsic
  settle, 4-leg costs. Structurally immune to both bug classes. (SENSEX caveat: no volume floor.)
- v2/v1/v0 stock credit OOS: ALL BUGGED - every Upstox OOS validation (v2 87%/+41.2%/margin,
  v1 86%, v0 90.7%/+19.4%) used POSITIONAL leg alignment (stkfade_oos_union.py:69-78,
  stkfade_v1_oos_exits.py:72-76, stkfade_lowcw_oos2.py:162-190). UNPROVEN until re-run.
  v0 already has a corrected cell: 83.3% / +4.7% ROM (was 90.7% / +19.4%) - its OOS case collapsed.
- v2/v1 stock credit IS (bhavcopy): date-aligned CLEAN, direction real (6/6 yrs), but priced on
  85%-OI=0 settlement prints with entry-only costs -> magnitude soft.
- Forward record since 6-Aug restart: 4 resolved, 4 wins - statistically empty.
RESULTS (both landed 14-Aug ~17:05, clean runs):
- Date-aligned OOS >=0.40: v2 91.7% win / +237% ROM (n=24, 2/2 yrs) · v1 84.4% / +54% (n=109,
  3/3 yrs) · v0-geometry 91.7% / +217%. THE DEPLOYED GATE SURVIVES ITS CORRECTED TEST; the cliff
  at 0.40 (+54..237% above vs -12..+1% below) is the sharpest feature in the data.
- IS forensics (full universe, OI tracked, exit costs charged): v2 +176->+172% ROM, 18% of exits
  on an OI=0 leg, 120 impossible stop marks (5%); v1 +173->+169%, 9%, 0. IS magnitude soft, not
  hollow. Win rates unchanged.
- v0's live band corrected OOS: 83.8% / +5.2% (claimed 90.7% / +19.4%) - weakest book, slot is
  the user's decision. Stop sweep: no stop rescues 0.25-0.35.
Study: studies/DEPLOYED_EVIDENCE_AUDIT.md + addendum in CW_BAND_BY_BOOK.md, both pushed.

## AUDIT 14-Aug: the c/w band study has TWO BLOCKERS — OOS re-run in flight

An adversarial audit agent (user-requested) reviewed studies/CW_BAND_BY_BOOK.md before any
deployment decision. Verified findings:
1. **BLOCKER — OOS legs date-misaligned.** `leg()` in studies/ndte/cw_band_sweep.py drops candle
   timestamps and the walk indexes positionally (`sp[k]-lp[k]`); 47% of multi-leg windows have
   unequal candle counts, so spreads compare different DATES and even entry credit can pair
   mismatched days. The +11.6%/82.6% OOS cell (v1 0.30-0.35) is invalid as measured.
2. **BLOCKER — stop triggers on impossible prices.** 17/17 stop triggers at >=0.40 and 17/26
   in-band fired on marks where spread cost EXCEEDED width (stale settlement prints). The
   "no-stop beats 3x stop everywhere" claim is an ARTIFACT — do not touch v2's live stop.
3. MAJOR: IS charges no exit costs (OOS does) → IS +9.6% is really ~+8.1-8.7%; bhavcopy >=0.40
   comparator is stale-print fiction (85% of prem>=50 rows have OI=0) — honest comparator is
   live v2's +41%/margin; winning cell is best-of-12 selected after both windows, OOS
   equal-weighted mean +3.2% ± 5.1% (z≈0.6); live gates absent; OOS window is a favorable regime.
4. **User's correction, accepted:** entering at the option's daily CLOSE is FAITHFUL to the live
   system — since 3-Aug the engine scans 15:36 on the official close and places 15:36-15:40 while
   derivatives trade to 15:40. The audit's "entry price ≠ entry time" point is answered by design;
   the residual caveat is stale last-trades on illiquid strikes, not timing.
RESULT of the date-aligned re-run (14-Aug, /tmp/cw_dated2.log, clean, no fetch failures):
the headline cell v1@0.30-0.35 COLLAPSED from +11.6% ROM to +1.2% (n=103, 1/3 years). All other
low cells flat or negative (v2 0.30-0.35: -10.9%). THE LOW BANDS ARE DEAD OOS — LOWCW_BAND_RESCUE's
original verdict re-confirmed by a corrected route. Study rewritten with an audit-correction box at
the top of studies/CW_BAND_BY_BOOK.md; do not touch v2's live stop on this study. User confirmed no
deployment intended. Question CLOSED.

## c/w BANDS 0.25-0.35 measured (13-Aug) — information only, NOTHING deployed

OOS Oct-24->date, 38-name slice, each band priced at each book's OWN geometry+exit:

| band | v2 (S2W4 TP50 stop3x) | v1 (S1W3 TP40 no-stop) | v0 (S2W4 TP40 no-stop) |
|---|---|---|---|
| 0.25-0.30 | 78.1% / +2.6% ROM (n=64) | **85.7% / +5.1%** (n=70, +ve 3/3) | 84.4% / +4.9% (n=64) |
| 0.30-0.35 | 74.1% / **0.0%** (n=58) | **82.6% / +11.6%** (n=92, +ve 3/3) | 77.6% / +3.1% (n=58) |
| 0.35-0.40 (v0's live band) | 74.3% / +11.2% (n=35) | 74.8% / -1.0% (n=103) | **88.6% / +22.5%** (n=35) |
| >=0.40 deployed v2 | **95.8% / +219%** | | |

FINDINGS: (1) v1's TP-40/no-stop is the only exit that stays positive in ALL THREE low bands and
+ve 3/3 years — 0.30-0.35 at v1 shows 82.6% / +11.6%, which CONTRADICTS the LOWCW_BAND_RESCUE
verdict that the band is dead (that study scored it at v2/v0 geometry, not v1's S1/W3). (2) v2's
stop-3x is what kills the low bands (0.0% ROM at 0.30-0.35) — the stop binds when credit is thin.
(3) ROM at every low band is 2-12% against +219% at the gate: 20-100x less money per rupee of
margin. The win rates look fine; the money is the point.
CAVEATS: n=58-92 per cell, OOS-only (IS leg needs the bhavcopy option pickle rebuilt ~40 min),
38-name slice not the full 113. NOT actionable without the IS leg.

---

## RUNNING 13-Aug: win rates for c/w bands 0.25-0.30 and 0.30-0.35 at v0/v1/v2 exits

User request (information only, no deployment). Bands below the deployed gates, priced at each
book's OWN geometry+exit: v2 = S2/W4 TP-50 stop-3x · v1 = S1/W3 TP-40 no-stop · v0 = S2/W4 TP-40
no-stop. IS = bhavcopy 2019->Sep-24, OOS = Upstox Oct-24->date. Script studies/ndte/cw_band_sweep.py.
Known prior (LOWCW_BAND_RESCUE): 0.30-0.40 blended OOS TP-40 = 81.7% win / +2.2% ROM; 0.30-0.35 half
is dead (+0.2% IS, -5.2% OOS). 0.25-0.30 has never been measured.

---

## 13-Aug: watchlist polish round — user screenshot shows GATES ticks wrapping raggedly,
## SIGNAL header clipped to "IGNAL→LIV". Fix: compact one-line gates, deliberate 2-line legs,
## header renamed PRICE. See ui_terminal WATCH_COLS + _watch_weights.

---

## ⛔ T-1 CLOSE ENTRY — REJECTED IN FULL (11-Aug). Cadence killed it; user caught it.

BANKNIFTY weeklies are GONE. Expiries/yr in the data: 2019-2023 ~52-58, 2024 40, then **12**. The
Rs575-801/trade edge was priced on ~52 expiries/yr; at 12 it is Rs6,900-9,612/yr — against deployed
0DTE SENSEX Rs37,836 and NIFTY Rs21,252, with extra margin and overnight gap risk they do not carry.
NIFTY: rejected (Rs6,180/yr at 1%, 3 of 8 years negative, direction flips IS->OOS).
SENSEX: untestable — BSE index, absent from NSE bhavcopy, weeklies only from Oct-2024, entire history
is one falling regime.
DO NOT RE-MINE unless BANKNIFTY weeklies return; then revisit BEAR CALL 0.75-1.0% w6 (0 negative
years in 6). studies/T1_CLOSE_ENTRY.md carries the full record. Nothing was ever deployed.

---

## 1% OTM BEATS 0.5% (11-Aug) · SENSEX CANNOT be tested pre-Oct-2024 — hard data limit

**SENSEX: no in-sample window exists.** It is a BSE index — absent from NSE's F&O bhavcopy entirely
(confirmed: only NIFTY/BANKNIFTY present) — and SENSEX weekly options only began Oct-2024. So its
ENTIRE history is the falling regime, and the regime-artifact criticism that killed NIFTY cannot be
tested away. Treat any SENSEX T-1 number as single-regime and unproven, permanently, until more time
passes.

**1% OTM is materially better than 0.5% on NIFTY** (IS 2019-2024, 288 trades):
 0.5% w6: 71.5% win · Rs72/tr · worst year -39,007
 1.0% w6: **89.6% win · Rs123/tr · worst year -15,816** — better win, better money, 60% smaller worst
 year. The user's gap intuition was right: gaps breach 0.5% on 9.8% of sessions but 1.0% on 3.3%.
BANKNIFTY 0.75% w6 is the standout: 81.4% · Rs575/tr · **0 negative years of 6** (0.5% has 1).

REVISED CANDIDATE: BANKNIFTY 0.75-1.0% w6, not 0.5%. NIFTY at 1.0% is no longer an outright reject —
re-examine, but its direction still flipped IS->OOS, which 1% does not fix.

---

## T-1 CLOSE 2019->2026 SETTLED (11-Aug): NIFTY REJECTED · BANKNIFTY is the real candidate

1,405 trades. IS = bhavcopy 2019->Sep-24 (1,359 sessions, has BULL regimes), OOS = Upstox Oct-24->
Aug-26. BEAR CALL 0.5% w6.
NIFTY: +Rs72/tr IS vs +Rs556 OOS · 71.5% IS win (not 87%) · **-Rs39,007 in 2020** · and the DIRECTION
FLIPS (puts +226 IS / -176 OOS). Regime artifact — CLAUDE.md Part 11 repeating. REJECT.
BANKNIFTY: +Rs801/tr over 293 IS trades, +Rs2,137 over 25 OOS, positive 5 of 6 IS years, and the sign
does NOT flip (calls + in both, puts - in both). Its 0DTE book was rejected, so this slot is EMPTY =
genuinely additive. THE candidate.
Still unmodelled: spreads are spf()-MODELLED not real; no live liquidity/c-w gate; 2020 shows what
clustered gaps do. NOT DEPLOYED — approval-first.

---

## RUNNING 11-Aug: T-1 close entry over 2019->2026, IS + OOS, year by year

Downloading NSE F&O bhavcopy 2019->Sep-2024 (OPTIDX NIFTY/BANKNIFTY closes per strike) -> /tmp/
bhav_opt_idx.pkl, then a full T-1 close backtest. TRUE IS/OOS this time: IS = 2019->Sep-2024
(bhavcopy, contains BULL regimes), OOS = Oct-2024->Aug-2026 (Upstox, the falling regime already
tested). This is the test that decides it — the earlier "IS/OOS" split was two halves of one
downtrend. GAP RISK quantified: a 0.5% OTM short call is breached AT THE OPEN on 9.8% of NIFTY
sessions (12.5% BANKNIFTY), worst +4.86%; 0DTE enters 09:16 AFTER the open and knows the gap, T-1
wears it blind. Spreads are spf()-MODELLED, not real — P&L shown is optimistic by an unmeasured
amount.

---

## ⚠ T-1 CLOSE ENTRY — DO NOT DEPLOY. It is a directional bet on a falling market.

Follow-up check (11-Aug) overturns the earlier optimism. EVERY surviving cell is BEAR_CALL; the put
side loses on all three indices (NIFTY -176, SENSEX -233, BANKNIFTY -943 Rs/trade). The tape: NIFTY
-4.1% then -1.1%, SENSEX -4.2% then -3.2% — the WHOLE sample is a falling market. Selling calls into
a one-way decline is short delta in a credit-spread costume; the 87% win rate is the market going
down, not premium harvested.

The IS/OOS split does NOT save it: both windows are the SAME falling regime, so splitting a downtrend
gives two downtrends. This is precisely the failure recorded in CLAUDE.md Part 11 (down-only fade
gate: +15.1%/78%/6 positive years, then FAILED OOS when the asymmetry reversed).

NEXT STEP if pursued: test on a RISING regime — bhavcopy 2019->Sep-2024 has both. Until a bull window
is tested, this is unproven. studies/T1_CLOSE_ENTRY.md carries the finding.

---

## T-1 CLOSE ENTRY — IS/OOS VALIDATED on 3 indices · studies/T1_CLOSE_ENTRY.md · NOT DEPLOYED

BEAR CALL 0.5% OTM w6 is the ONLY geometry holding in both windows on all three:
NIFTY 84.6%IS/90.7%OOS · SENSEX 85.7%/85.7% · BANKNIFTY 93.3%/90.0%. Rs/yr at 1 lot: NIFTY 28,827 ·
SENSEX 27,249 · BANKNIFTY 29,143 = Rs85,219 vs deployed 0DTE Rs59,088.
COMPLEMENTARY IN TIME (T-1 = overnight-gap risk; 0DTE = intraday drift) but CORRELATED IN RISK —
both open simultaneously on expiry morning, same index, same direction; worst case is the SUM.
BANKNIFTY is the only truly additive slot (its 0DTE book was rejected).
WEAKNESSES: BANKNIFTY n=25 (~2 losses); NIFTY IS leg is +Rs32/trade ~= zero, carried by OOS; no live
liquidity/c-w gate applied; entry collides with the 15:36-15:40 stock-scan window; one regime.
RECOMMENDATION: SENSEX first (only index with a real sample consistent in both windows), NIFTY small,
BANKNIFTY last. Approval-first rule — nothing deployed, no engine file touched.

---

## T-1 CLOSE ENTRY (11-Aug) — the promising variant. NIFTY: Rs30,140/yr vs live 0DTE Rs21,252

Selling at the T-1 CLOSE (not 09:16) beats both the deployed 0DTE book (+42%) and the 09:16 T-1
entry, with a far healthier shape: BEAR 0.5% OTM w6, 87.5% win, credit Rs32.9, 6.5 losses/yr, one
loss erases 5 wins (vs 30 at 09:16 2.5%). Mechanism: closer strikes hold real premium, and the close
entry skips the day of drift the 09:16 entry sits through while keeping the overnight gap.
CAVEAT: NIFTY only, n=96, ONE window, no IS/OOS split. Script /tmp/t1_close.py, rows
/tmp/t1close_nifty.json. NOW RUNNING: IS/OOS split + SENSEX + BANKNIFTY monthly.

---

## T-1 loss profile (11-Aug) — the payoff shape is why it is rejected, not the win rate

1 lot, Oct-24->Aug-26 annualised. ONE loss erases: **30 wins** (NIFTY 2.5% w4), 10 (SENSEX 2.0% w6),
4 (BANKNIFTY 1.0% w6). NIFTY 2.5%: avg win Rs246 vs avg loss Rs-7,432, worst Rs-14,860, net only
Rs3,415/yr. Losses are RARE (1-6/yr) but each is 10-30x a win — pennies in front of a steamroller.

Best NET/yr vs the DEPLOYED books (annualised): NIFTY T-1 1.5% w6 Rs17,013 vs live 0DTE Rs21,252 ·
SENSEX T-1 1.0% w6 Rs21,214 vs live 0DTE Rs37,836. Both LOSE to what is already running.

⚠ THE ONE GENUINELY OPEN SLOT: **BANKNIFTY**, whose 0DTE book was REJECTED (t=+0.10), so nothing
occupies it. T-1 BANKNIFTY 1.0% w6 = 92% win, Rs22,089/yr, 1.1 losses/yr, one loss erases 4 wins —
the best payoff SHAPE in the whole sweep and ADDITIVE rather than a replacement. But n=25 monthlies
with ~2 losses total: far too thin to deploy. If T-1 is ever revisited, this is the only cell worth
the compute, and it needs a bigger sample (extend before Oct-24 via bhavcopy) before any decision.

---

## T-1 EXPIRY-EVE: REJECTED (11-Aug) — 95-100% win rates, but Rs3.7 credits · studies/T1_EXPIRY_EVE.md

4,000+ trades, Oct-24->Aug-26. Win target smashed (NIFTY 97.7%, SENSEX 97.8%, BANKNIFTY 100%) and
MEANINGLESS: avg credit Rs3.7 at NIFTY 2.5% OTM, c/w 0.01-0.10 vs the proven >=0.40 gate. User's
"much larger premiums" premise REFUTED at 2%+ OTM. Money: best SENSEX T-1 Rs1,768/mo vs the LIVE
0DTE SENSEX book's Rs3,153 — 44% less for double the risk window. Nothing beats what is deployed.
Only 1.0-1.5% OTM holds real premium (and 88-92% win) — the opposite of the hypothesis — still
inferior on money. BANKNIFTY n=25 monthlies, book already rejected on t=+0.10; 100% is noise.
NOT deployed, no engine file touched.

---

## T-1 backtest RUNNING (11-Aug 07:09): NIFTY done, SENSEX 50/96, BANKNIFTY pending

studies/ndte/t1_expiry_eve.py · log /tmp/t1_run.log · results /tmp/t1_expiry_eve_results.json ·
leg cache /tmp/t1_leg_cache.json (resumable — rerun picks up cached legs). 4,033 trades priced so
far. Rate ~13s/expiry (API-throttled). ETA ~10-15 min for SENSEX remainder + BANKNIFTY monthlies.
Report on completion: win rate FIRST (user), ROM + avg credit + c/w beside it, per index/geometry,
benchmarked against deployed 0DTE (NIFTY 88.3%, SENSEX 89.0%).

---

## RESEARCH LOOP started 11-Aug (/loop, dynamic pacing): T-1 EXPIRY-EVE ENTRY

User hypothesis: enter NIFTY/SENSEX/BANKNIFTY credit spreads at 09:16 on the day BEFORE expiry
(T-1), ~2% OTM, holding through expiry — bigger premium to harvest across two days. Target: maximise
WIN RATE, 80%+. Data: Upstox expired-options OOS, Oct-2024 -> date. Goal is a validated config or an
honest rejection, written to studies/ either way.

---

## 11-Aug verification: no trade legitimate · index closes EXACT · swing is DISABLED (flag it)

**No trade today is real:** 23 breakouts, top c/w 0.31 — below even v0's 0.35 floor, so 0 passed.
Yesterday (10-Aug) v0 DID fire GRASIM 3420/3500 c/w 0.39 — the cross-book gap rule working.

**Index closes verified against NSE's official index file** (NOT the CM bhavcopy — that is EQUITIES
only, no NIFTY row; index closes live at nsearchives.nseindia.com/content/indices/ind_close_all_
DDMMYYYY.csv). All three EXACT to the paisa: NIFTY 24,471.70 · FINNIFTY 26,432.40 · BANKNIFTY
57,446.25. So `todays_close()` is correct for indices as well as stocks.

⚠ **SWING_CREDIT_ENABLED = False** — the swing book has been OFF. Its 3 positions are all from July
(NIFTY WIN, FINNIFTY LOSS, NIFTY WIN) and predate the stale-bar fix, so they carry signal_px=None
and are T-1-era trades. No swing signal can fire until the flag flips; the index fade also failed
OOS (-1.4% of width), so leaving it off is defensible — but the user should know it is off.

---

## IN PROGRESS 10-Aug eve: Telegram wording — outcome line + "intraday" not "0DTE"

User spec: RESULT messages must read "This is the outcome of the Signal we gave for execution on
24th July." (ordinal date, not ISO); and NIFTY/SENSEX books must say INTRADAY, never 0DTE, in all
user-facing messages. Implement for future messages, send nothing now; show samples in chat
(result-swing, result-intraday, intraday signal).

---

## 10-Aug: v0 GRASIM fired under the cross-book gap rule · watchlist column widths rebalanced

Screenshot from the user (10-Aug 15:51): v0 fired GRASIM 3420/3500 CE (new levels vs the 4-Aug v1
3140/3200) — the 7-Aug cross-book 3-day-gap rule working as designed on its first opportunity.
UI issue reported: watchlist columns truncate (C/W shows "✗ …", LOT "15…", BRK "D…", SIGNAL→LIVE
cut on 4-digit prices). Fix: rebalance the 13 fixed widths — C/W must show tick+value fully
(user: premium column is fine as is). Deploying after close.

---

## ✅ 7-Aug verified vs bhavcopy: watchlist 14/14 EXACT, GRASIM exact (3,323.00)

Second consecutive session verified against the exchange. The 15:31 watchlist's signal_px matched
official ClsPric on ALL 14 names, zero mismatches (6-Aug was 19/20; the one thin-name miss did not
recur). GRASIM specifically: signal_px 3,323.00 == official close 3,323.00, LONG D20, c/w 0.38,
gate=BLOCKED (below v2/v1's 0.40; v0 was blocked by the old exclusion rule, since replaced by the
cross-book 3-day gap). Forward verification record: 2 sessions, 33/34 exact, GRASIM+HAL both exact.

---

## DEPLOYED 7-Aug 16:15 (after close, per freeze rule): 3-day gap is now CROSS-BOOK, all of v0/v1/v2

User rule: the re-entry gap applies across ALL books — no book fires on a name ANY book entered
within STOCK_CREDIT_REENTRY_GAP_DAYS (3). `data_utils.recent_entry_symbols()` is the one source of
truth (reads all three book files); v2's scan consults it (v0 inherits via importlib) and v1's scan
gained the same check beside its own gap. Same-day tie-break preserved (v1 scans first; its entry is
in the file when v0 scans, 0 < 3 blocks). Matches the backtests' per-symbol REENTRY=3, which never
had separate books. Current gap set: {HAL} (entered 6-Aug). Engine restarted after close; pushed.

---

## 7-Aug close-out: freeze rule pushed · NO backfill of the missed GRASIM v0

Deployment-freeze rule (15:15-15:40) pushed to both remotes after the close. User confirmed the
missed GRASIM v0 signal (7-Aug D20 breakout, c/w 0.38, blocked by the old exclusion rule) is NOT to
be backfilled into PM DECISIONS or the trade log — the paper book records what the engine actually
signalled, never what it would have signalled; a retroactive entry on day 2 of the restarted forward
record would corrupt it. The 4-Aug GRASIM v1 position stays as-is (real, still OPEN). The new 3-day
gap rule takes first live effect at the next session's 15:36 scan.

---

## DEPLOYED 7-Aug ~15:45 (user decision): v0 cross-book exclusion is now the 3-DAY GAP, not OPEN

User's reasoning, confirmed correct: a repeat signal at NEW levels is a different trade; only
CONSECUTIVE-day repeats are chasing one continuing move. This exactly matches the backtests —
REENTRY=3 per symbol in every lowcw/stkfade script, with NO open-position blocking — so the old
"blocked while v1 holds the name OPEN" rule was stricter than anything validated.

`stock_credit_v0._v1_recent_symbols()` now excludes v1 names ENTERED within
STOCK_CREDIT_REENTRY_GAP_DAYS (3). Same-day tie-break (v1 wins) preserved automatically (0 < 3).
Effect at deploy time: exclusion shrank from {BAJAJ-AUTO, GRASIM, HAL, TCS} to {HAL}. GRASIM's fresh
7-Aug breakout (D20, 3,323, c/w 0.38) would have fired under the new rule — today's 15:36 scan had
already run on the old rule, so first effect is the NEXT session.

---

## 7-Aug: GRASIM in watchlist at c/w 0.38, no signal — WORKING AS DESIGNED, rule question open

GRASIM broke out fresh on 7-Aug (LONG D20, signal_px 3,323 = live, fresh close). c/w 0.38 → v2/v1
gate (>=0.40) blocks. v0's band (0.35-0.40) would take it, BUT v0 excludes v1's OPEN names and
GRASIM is OPEN in v1 (4-Aug bear call 3140/3200, cost 43.05 vs credit 24.85 — losing). So v0 stood
down per the user's tie-break rule (2026-07-31). NOT a bug.

OPEN QUESTION for the user: the tie-break was designed for same-DAY clashes; here a 3-day-old v1
position blocked a fresh v0 entry. Trade-off if relaxed: v0 would sell a NEW bear call at higher
strikes (spot 3,323) on a name already moving against the v1 position — doubles same-name
same-direction exposure. Do not change without his call (approval-first rule).

---

> **ADDED (2026-08-07 ~11:15): replay is now self-extending.** calc_vs_print_recorder also dumps
> each day's minute path to `replay_days.json` (upsert, sorted); server serves it at **/replay**;
> UI merges it over the embedded data and builds day tabs dynamically (falls back to embedded
> 3 days without the server). 6-Aug backfilled — 4 tabs verified. Each 15:50 run adds the day.
>
> **ARMED (2026-08-07 ~11:05):** who prints first at 15:28–29, the exchange index or our
> constituent calc? Not answerable from 1-min bars (both land in the same bar; no poll logs
> existed). Added `race_logger()` to live_calc_server: 15:26–15:34 weekdays it samples /live
> once a second → `studies/CAS_NIFTY_SENSEX_DATA/race_log.jsonl`. Server restarted, thread
> armed. **Read the jsonl after today's 15:34** — first ts where each side leaves its frozen
> level answers it. Expectation to verify, not assert: exchange index likely leads (internal ms
> feed vs our 5s-cadence REST LTPs); our only possible lead is stocks' auction prints reaching
> LTP before the index recomputes.

> **DONE (2026-08-07 ~10:55):** auction-print model trained Mon–Wed, tested Thu — **every model
> lost to naive**. The NIFTY auction lift DECAYED +201→+152→+54→+8 pts: a regime-change transient,
> gone by day 4. Naive (calc@15:15) was −8 pts on Thursday's print; trained models +133…+145 off.
> SENSEX exception: +168-pt auction jump on its OWN EXPIRY day after 3 inert days. Exact CAS price
> is order-book-determined (max executable volume) — not reproducible from public feeds, ever.
> → CROSS_EXCHANGE_AUCTION_GAP.md Addendum 4. **Ops fix:** scheduled calc-vs-print failed 6-Aug
> (no same-day daily bar → no official close at 15:50); now uses intraday last print for today +
> default run re-records the prior session (self-healing). Thu row backfilled: NIFTY gap +8.33,
> SENSEX +167.63.

> **DONE (2026-08-06 ~13:50):** stock futures do NOT predict the cash auction print —
> corr −0.017 (n=100 train Mon+Tue), futures-implied predictor loses to naive out-of-sample on
> Wed (22/50, MAE 0.319% vs 0.292%); futures stayed FLAT while auctions moved +0.74%, and don't
> converge even after the print (+0.21% gap at 15:39). Regression fitted on Mon+Tue only learns
> the mean lift and does WORSE on Wed — magnitude unstable, only the positive SIGN persists.
> → CROSS_EXCHANGE_AUCTION_GAP.md Addendum 3. Thursday scores itself once today's data lands.

## DONE (6-Aug eve): stale-bar incident recorded per RESULTS→STUDIES→UI→GITHUB

studies/STALE_BAR_INCIDENT.md (full record: defect, GRASIM proof, 19/19 T-1 reconstruction, 4-layer
lesson, fixes, bhavcopy-verified first session, restart of the forward record). studies/README.md
banner points to it and flags the superseded "+44%" claim; NSE_SESSION_CHANGE study carries a
CORRECTION header (audit findings: cost-table convention, spf 1.2%, v1 OOS 73.4%, bhavcopy match
proved nothing). STUDIES tab card added in the same format; viewer restarted. All pushed.

---

## ✅ VERIFIED vs bhavcopy (06-Aug 18:18) — the first corrected session checks out

**HAL (the day's only fired call, v1 BEAR_CALL 4950/5100):** scan's signal_px 4,920.00 == official
bhavcopy ClsPric 4,920.00, EXACT. Breakout genuine on today's close (+4.28% over the D10 band),
direction right (HAL +5.92% on the day — bear call ON the up-day, the GRASIM inverse). The scan read
the AUCTION print (bars 15:10/15:15/15:20 frozen at 4,934; last bar 4,920 = the auction crossing).

**Whole 15:31 watchlist vs bhavcopy: 19/20 exact.** One mismatch: NAVINFLUOR scan 8,619 vs official
8,650 (-0.36%) — consistent with a thin name whose auction print landed after the 15:31 rebuild
sampled it (UBL/ATUL showed the same pattern on 3-4 Aug). The 15:36 SCAN itself fired nothing off
NAVINFLUOR, so no trade was affected. Watch whether the same names recur; if so, thin names may need
a later read or a tolerance note in the digest.

Also proven live today: the stale guard fired for RELIANCE at 15:36:40 (skipped, not scanned stale) —
first production firing; 15:31 digest went out on time (20 breakouts, 2 candidates).

Remaining cosmetic: signal_auction field is v2-only, shows None on v1 positions — extend to v1/swing.

**The verification chain the plan demanded is now CLOSED: same-day close -> genuine breakout ->
correct direction -> exact official-close match, on the first corrected session.**

---

> **DONE (2026-08-06 ~12:10):** (a) NIFTY live-mismatch diagnosed: **~75% was day-old weights**
> (yday-weights −1.31 pts vs today-weights −0.30 at 12:00); server now **auto-refits every 30 min**
> in market hours. Verified after fix: NIFTY diff +0.10…+0.88 pts, SENSEX −0.36…+0.71 (from −2/+3).
> Per-stock weight-shift table is COLLINEARITY NOISE, not corporate actions — documented in
> CROSS_EXCHANGE_AUCTION_GAP.md Addendum 2; do not read single-name lstsq weights as real weights.
> Minor: TMPV/ETERNAL LTPs lag ~0.2%. (b) Desktop app shipped: launchd agent
> **`com.sayali.cas-calc`** (RunAtLoad+KeepAlive, all-day, logs `logs/cas_calc_server.*.log`) +
> **`~/Applications/CAS Calculator.app`** (kickstarts agent, opens http://localhost:8787;
> Desktop shortcut symlinked at `~/Desktop/CAS Calculator`).
> `.claude/launch.json` `cas-live` entry is now ATTACH-ONLY (url) so preview can't double-start
> the server. The live calc is pure Σ(wᵢ·LTPᵢ) over the 80 stocks — the index print is only used
> once a day to calibrate weights, never in the live number.
>
> **ADDED (2026-08-06 ~13:20): daily calc-vs-print record.**
> `studies/CAS_NIFTY_SENSEX_DATA/calc_vs_print_recorder.py` → engine.db table
> **`cas_calc_vs_print`** (date, idx, print_1515, calc_1515, calc_1518, official_close,
> auction_gap, fit_rmse, recorded_at; upsert on date+idx) + `cas_calc_vs_print.csv`.
> Scheduled by CHAINING into `com.sayali.cas-recorder` (bash -c runs engine.cas_recorder then
> this, 15:50 + 16:20 retry — plist reloaded). Backfilled 3/4/5-Aug, values match the study
> exactly. UI summary table now fetches **/summary** from the live server (falls back to embedded
> data in static-file mode) and shows the recorded_at timestamp — grows a row per index per
> trading day, starting with today 6-Aug at 15:50.

> **DONE (2026-08-06 ~11:45):** "Calculated Constituents" UI shipped and VERIFIED LIVE in-market.
> `studies/CAS_NIFTY_SENSEX_DATA/live_calc_server.py` (stdlib HTTP, port 8787) serves
> `calculated_constituents.html`: replay tabs (SENSEX/NIFTY × 3/4/5-Aug, close window
> calc-vs-published chart) + a **LIVE tab polling /live every 5s** — one batched Upstox LTP call
> for 82 instruments, calc = lstsq weights (fit on latest session 09:20–15:09, POST /refit to
> refit) dotted with live prices. Live at 11:44 IST 6-Aug: SENSEX live−calc **+3.0 pts (0.004%)**,
> NIFTY **−2.0 pts (0.008%)**. Out-of-sample 15:10–15:15 match (fit ends 15:09): NIFTY ≤2.1 pts,
> SENSEX ≤11.3 pts (≤0.014%) across the 3 sessions. Launch: `.claude/launch.json` entry
> `cas-live` (worktree), or
> `cd ~/files/institutional-trader && ./.venv/bin/python studies/CAS_NIFTY_SENSEX_DATA/live_calc_server.py`.
> Gotcha fixed: livePanel div was nested inside replayPanel (hidden in live mode) — moved out.

## Alignment summary (2026-08-06, user confirmation request)

Signal input now aligns with the full 2019-2026 backtest series: IS used bhavcopy official closes,
OOS used Upstox daily closes (verified == bhavcopy 113/113), live now reads the auction close
(verified == bhavcopy exactly). Two residual gaps, stated: (1) close CONSTRUCTION changed 3-Aug
(VWAP -> auction) — same field, different mechanism, untested; (2) entry premium — backtest fills at
the option's daily close, live fills at 15:36-40 quotes. Alignment of inputs is now true; alignment
of RESULTS is what the forward record starting today measures.

---

## Post-mortem note (2026-08-06): why repeated bug sweeps missed the stale-bar bug

User asked directly. Honest answer recorded for future sessions:
1. The defect was in the DATA, not the code — `df["Close"].iloc[-1]` is correct-looking code; the
   Upstox daily endpoint simply omits the current day's bar during the session. No amount of code
   reading can reveal what an external feed returns at 15:36.
2. Every verification ran OUTSIDE the window that matters. Checks made after hours or next day saw
   the bar present and matching bhavcopy, and concluded the feed was fine (the 5-Aug "Test 2" did
   exactly this).
3. The evidence WAS captured and not connected — the study's own data-feed note (18:15 on 4-Aug, no
   4-Aug data) was written down by the model without joining it to the scan path. The adversarial
   critic flagged the connection; the session observer then proved it.
4. Long-standing behaviour read as baseline. The bug predates every change; sweeps focused on what
   had just changed. The user's domain instinct ("why a bear call after a fall?") was the detector.
LESSON (binding): code review finds code bugs; only RUNTIME observation at the actual decision time
finds data bugs. The fix-class is instrumentation + invariants (session observer, stale guard,
direction audit, SIGNAL→LIVE column) — all now in place; any recurrence is visible same-day.

---

## CONFIRMED from the books (2026-08-06): EVERY live trade was a previous-day breakout

User asked whether the old 15:10 scan represented the same day or the previous day. Reconstructed the
Donchian verdict for all 19 v1+v2 positions ever booked, on T (entry day) and T-1, from daily bars:

**PREV-DAY only: 14 · both days (consecutive breakouts, ambiguous): 5 · SAME-DAY only: 0 · neither: 0**

All 19 are consistent with the signal being T-1's close; ZERO require T's. The 5 "both" cases are
names that broke out two days running — exactly what a stale bar would also book. So the old system
traded the PREVIOUS day's breakout every single time; 15:10 never represented the current day.

Consequence for the record: the 15 closed v1 trades (11W/4L, 73%) are a sample of the T-1-DELAYED
strategy, not the backtested one. Do not compare them to the 84-87% backtest figures. Interesting
honest note: even delayed a day, the fade still went 11/4 — the edge may be forgiving of delay, but
that is an observation, not a measurement (n=15). The T-vs-T+1 backtest remains the way to answer it.

---

## TODAY 6-Aug-2026 — FIRST LIVE RUN of the corrected chain. Watch these checkpoints.

Everything from 5-Aug is committed+pushed. Today is the first session where the scan reads TODAY's
close (todays_close via intraday), the direction audit gates every signal, and the UI shows the
signal price with the AUC tag.

Timeline + what PROVES each piece:
1. **09:30 re-check → must send NOTHING.** 5-Aug produced zero calls (0/15 passed c/w). Silence is
   the correct output; a message today = bug in _last_session/no-signal gating.
2. **14:45 observer baseline**, then **15:15–15:40 sampling** — legs must now stay the SAME contract
   all window (fixed), targets constant.
3. **15:17 watchlist + digest** — rows must carry signal_px with src=intraday and SIGNAL→LIVE col
   filled. Breakout set must be TODAY's, not 5-Aug's (under the old bug they'd be identical).
4. **15:36 scan** — log must show current-day closes; any DIRECTION AUDIT FAILED line = data bug
   caught (good), but investigate. New positions must carry signal_px/signal_src/signal_auction.
5. **15:40 settle + grace window** — RESULT telegrams land ~15:40-15:42, not 15:45.
6. **~18:00 bhavcopy check** — compare what todays_close returned at 15:36 vs official ClsPric
   (expect exact for most, ≤0.3% thin names). THE decisive verification, plan §Verification-2.
7. TCS + BAJAJ-AUTO + GRASIM (v1, exp 25-Aug) keep marking, no early settle.

If something misfires mid-session: engine restart is `launchctl kickstart -k
gui/$(id -u)/com.sayali.institutionaltrader.engine` — config_ledger records any tunable change.

---

## IN PROGRESS (2026-08-06 early) — bug sweep round 2 + stale UI time strings

All of round 1's 8 fixes are COMMITTED AND PUSHED (see git log). Engine + viewer ALIVE, zero
tracebacks, open positions marking. Now: (a) fresh bug sweep, (b) purge stale time literals from the
UI — known offenders: "engine builds it at 3:05 PM" in _refresh_union_watch (twice; real time is
config.WATCHLIST_AFTER = 15:17), and any other hardcoded session time that survived the NSE retiming.
Rule: UI times must READ config, never restate it.

---

## Strategy semantics — direction vs trigger (user asked 2026-08-05)

**Direction: user's understanding is CORRECT.** Up-break → sell a BEAR CALL (fade the up-move).
Down-break → sell a BULL PUT. The book always fades the breakout; it never follows it. (The follow
version was tested and wins ~40% — see CLAUDE.md.)

**Trigger: it is a LEVEL, not a percentage.** The gate is "today's close is beyond the prior N-day
Donchian high/low", not "the stock moved X%". So a name can rise 3% and NOT signal (still inside the
band), or rise 0.4% and signal (band was tight). There is **no minimum breakout size for stocks** —
`SWING_MIN_BREAKOUT_PCT` is index-only and defaults 0.0, and the flush gate that used it FAILED
out-of-sample (CLAUDE.md Part 11).

GRASIM on Mon 03-Aug, the numbers behind the call:
| | |
|---|---|
| previous close (31-Jul) | 3,100.80 |
| D10 prior HIGH (the level) | 3,195.10 |
| 03-Aug close | 3,260.00 |
| daily move | **+5.13%** (not what the gate reads) |
| distance beyond the band | **+2.03%** (this is the breakout) |

So the BEAR CALL was the RIGHT call for Monday — a decisive 2% break on a 5% day. The only defect was
delivery: it fired on Tuesday, by which point the move had given back 3.74%.

**Open, untested:** whether breakout MAGNITUDE predicts fade quality for STOCKS. It was tested for the
INDEX and failed OOS, but never for the stock books. Cheap to test on existing daily data.

---

> **DONE (2026-08-06):** entry-time sweep + call-side decay profile, NIFTY + SENSEX, 3/4/5-Aug →
> [`studies/CAS_NIFTY_SENSEX_DATA/ENTRY_TIME_AND_DECAY.md`](studies/CAS_NIFTY_SENSEX_DATA/ENTRY_TIME_AND_DECAY.md).
> Result: **No entry time gained on any non-expiry session**; best in the grid is +₹91/lot, negative
> after costs. Only the 4-Aug 0DTE session paid. Discard the 09:15 row — the opening-auction print
> is recorded as the bar open and sits at the bar low, so it is not transactable.
>
> ⚠ **The first version of that study over-stated auction decay (−72 pts) by measuring against the
> INDEX. Corrected in-place the same day.** The index is unusable as an underlying after 15:15: it
> freezes at its last continuous value, then prints the auction equilibrium as one tick at 15:29.
> On NIFTY 3-Aug that print (24774.30) sat **190 points above the put-call-parity forward**
> (24583.7) — the options never priced it. 4-Aug and 5-Aug the print did match the forward.
>
> ✅ **RESOLVED 2026-08-06 by constituent test →
> [`studies/CAS_NIFTY_SENSEX_DATA/CROSS_EXCHANGE_AUCTION_GAP.md`](studies/CAS_NIFTY_SENSEX_DATA/CROSS_EXCHANGE_AUCTION_GAP.md).
> The NIFTY index print was NOT wrong — I called that wrong.** Pulled all 50 NIFTY and 30 SENSEX
> constituents at 15:16 vs their official closes on both NSE_EQ and BSE_EQ keys. NIFTY's move
> matches its NSE constituents to **0.006pp**; SENSEX matches its BSE constituents to 0.046pp. Both
> indices are internally correct. **The dislocation is between the EXCHANGES: BSE's closing auction
> barely moves prices (median SENSEX-30 stock 0.00% on all three days) while NSE's repriced the same
> names +0.79% on 3-Aug** — TITAN closed 5000 on NSE and 4900 on BSE, a 2.04% gap on the same share.
> SENSEX then opened +0.63% the next day, closing most of the gap, so BSE's auction looks like the
> stale one. **Consequence for the option work: the post-15:15 divergence is CASH vs DERIVATIVES,
> not an index error.** Anything settling on a cash close and anything settling on a derivatives
> VWAP can differ ~0.8% the same day.
> **Always derive the post-15:15 underlying from parity on the recorded CE/PE pair, never the
> index.** Correct answer: ATM time value is FLAT 09:30→15:00 (96–105% of the 09:30 level), bottoms
> at **15:30 at 83%**, recovers to 88% by 15:40 — about −21 premium points, not −72. All P&L numbers
> were computed from traded premiums and are unaffected.
>
> **Two bugs found and FIXED in `engine/cas_recorder.py` while doing this** — see the CAS section
> below. One had already corrupted a DB row; it is repaired and verified.

## 15:31 PROPOSAL — adjudicated by 3 agents (2026-08-05). Verdict: watchlist YES, scan move NO.

User proposed a 15:31 watchlist to pre-stage, then execute off the 15:36 scan. Ran a FOR agent, an
adversarial critic, and an independent reviewer.

**VERIFIED by two agents independently:** for all 14 observed names, the 15:29→15:39 spot equals the
official NSE bhavcopy `ClsPric` **exactly**; 0/14 at 15:17–15:25 (median error 0.392%). The auction
price flipped at **15:29** — inside the 15:28–15:30 random-close window, i.e. an EARLY draw.

**THE HOLE IN MY OWN EVIDENCE (reviewer, confirmed).** The observer records `_spot()` →
`get_cached_ltp` (stock_credit_v2.py:85-90) — that is the **strike-selection** feed. The breakout gate
reads `todays_close()` → `fetch_upstox_intraday(5m)` (data_utils.py:168), a DIFFERENT pipeline.
`_daily_bar_probe` deliberately hits the daily endpoint. **So nothing has ever observed what the
scan's actual breakout input returns at 15:31.** My "spot equals the close at 15:31" validates strike
selection only. Do not repeat this claim as support for moving the scan.

**THE DECIDING ASYMMETRY.** `todays_close` accepts any 5-min bar dated today (data_utils.py:169) —
trivially true during the session. On a LATE auction a 15:31 call returns the frozen ~15:15
continuous price: a real number, dated today, ~0.39% off the close. `_todays_breakout` then evaluates
the Donchian band against it and fires. **The failure is a silent WRONG signal, not a skipped scan** —
the exact defect `todays_close` was written to kill. 15:36 risks a rushed fill; 15:31 risks trading a
breakout that did not happen.

**Also: the accuracy argument was measured on names that could not fire.** All 14 had c/w 0.109–0.273
against a 0.40 gate. And the observer re-resolves legs each sample, so 4/14 carry different strikes
at 15:17 vs 15:38 — same-strike only, the 15:17-vs-15:31 edge shrinks to 0.004 vs 0.002.

**WHAT THE 15:31 WATCHLIST GENUINELY FIXES (this is the real win, and it is proven):** the current
15:17 digest is built on pre-auction spot, so it **stages the WRONG STRIKES 29% of the time** (4/14).
At 15:31 spot is final, so the ticket — symbol, expiry, both legs, lots — cannot change.

**DECISION: keep `STOCK_CREDIT_SCAN_AFTER = "15:36"`; add a 15:31 watchlist.** Not yet implemented.

**Before the scan could ever move, in order:**
1. Log `todays_close()` price AND source minute-by-minute 15:25→15:40 vs bhavcopy, on names with c/w
   near 0.40. Nothing else matters until this exists.
2. Record the actual auction-match timestamp daily; ≥10 sessions to catch a LATE draw.
3. Add a post-auction guard to `todays_close`: reject a bar whose close still equals the frozen 15:15
   print. This de-risks any later move.
4. Evidence of a signal actually lost to the 4-minute window. None exists.
5. `KILL_SWITCH_TIME` (15:36) must move with the scan if it ever does.

**SEPARATE BUG found by the critic:** `morning recheck: exchange holiday — no message` logs every
~5 min through the afternoon on a TRADING day. `market_is_trading_today()` returns False once past
FNO_CLOSE, so the message is misleading; harmless today but it is a safety net reporting nonsense.

---

## THE GRASIM TIMELINE — user spotted the bug from the trade itself (2026-08-05)

The user asked "why on earth would you give a bear call" when GRASIM had just fallen. He was right,
and his trading instinct caught the stale-bar bug before any log did. Verified against bhavcopy:

| | close | note |
|---|---|---|
| Mon 03-Aug | **3,260.00** | breaks the D10 prior high of 3,195.10 → **CE breakout. THIS was the signal.** |
| Tue 04-Aug | **3,138.00** | −3.74% vs Monday. **NOT a breakout** — sits inside the D10 band [3,066.40, 3,260.00]. **We fired the bear call HERE.** |
| Wed 05-Aug | 3,224.00 | +2.74%, back through the 3,140 short strike |

So the engine faded Monday's up-move on Tuesday, by which point the move had already given back 3.74%.
Selling a bear call into a stock that has just fallen is exactly what it looks like: wrong. The signal
was a day old.

**CORRECTION to an earlier note in this file:** I previously wrote that GRASIM "kept running" after
entry. It did not — it FELL 3.74% on Tuesday, then rose 2.74% on Wednesday. The failure mode is not
"the fade kept extending", it is "we faded a move that had already partly reverted, then it turned
again". Same conclusion, wrong mechanism.

**Scope: MOSTLY, not all.** The audit found 14 of 19 positions since June match the PRIOR day's close
breakout, 5 the same day's. The 5 are likely days where the name broke out on both sessions
(persistent breakouts), not evidence the bar was fresh. GRASIM is the clean proof: 04-Aug was not a
breakout on any price, so its signal could ONLY have come from 03-Aug.

**Not a configuration error.** Donchian windows, c/w gate, geometry, targets were all correct. The
PRICE fed into them was one session stale. Fixing the price fixes the strategy; no tunable changes.

---

## IN PROGRESS (2026-08-05 eve) — stale-bar fix IMPLEMENTED, not yet restarted/committed

Plan approved: `/Users/sayali/.claude/plans/there-is-a-change-sparkling-badger.md`.

**Done so far:**
- `engine/data_utils.todays_close(ticker) -> (price, source)` — intraday 5-min first (the ONLY source
  carrying today during the session), daily as after-hours fallback, **never a bar not dated today**.
  Verified live: RELIANCE 1280.0, GRASIM 3224.0, SIEMENS 3980.0, all source `intraday`, all equal to
  the 15:25 auction print.
- Wired into all three books (`stock_credit_v2._todays_breakout`, `stock_credit`, `swing_credit`).
  Each now skips the name and logs a WARNING rather than falling back to a stale bar. **The
  `.shift(1)` on the Donchian band was dropped** — `prior` now excludes today explicitly, so
  yesterday's bar belongs IN the lookback, not outside it. v0 inherits via importlib.
- Verified the fixed scan: 14 breakouts in the first 60 names on TODAY's close, a different set from
  the stale watchlist (which had 15 across the whole universe on yesterday's close).

**Still to do:** observer artifacts (§3: legs re-resolved per sample → contract switch; targets
re-read per sample → names vanish at the 15:17 rebuild), study corrections (§4), CLAUDE.md
track-record note (§5), restart, commit, push.

## Settled — hourly vs daily (user asked 2026-08-05)

**The breakout has ALWAYS been DAILY Donchian**, never hourly: all three books read
`unit="days", interval=1` (lookbacks 5/10/15/20 for v2 union, 10 for v1 and swing).

The hourly work the user remembers is `studies/HOURLY_VS_CLOSE_ENTRY.md` (2026-07-24), and it is about
something else: whether to evaluate the **c/w gate on OPTION premiums** at hourly marks and enter on
first touch of c/w>=0.40, instead of once at the close. **REJECTED — "NOISE, not edge. Keep the CLOSE
rule."** +32.8%→+25.7% of width (v2), +16.9%→+11.2% (v1), every calendar year worse, and many extra
signals unexecutable. Do not re-mine.

Likely source of the confusion: that study calls the 15:10 evaluation "the 15:10 **close**", because
pre-3-Aug the engine treated its 15:10 daily-bar read as the day's close.

## Also settled — cash, not futures

Signals read the **CASH** series (`GRASIM.NS -> NSE_EQ|INE047A01021`; NSE_EQ = cash segment), which is
correct: the backtests use NSE bhavcopy cash closes. NEW SEAM since 3-Aug worth watching: we signal
off a cash close struck by auction at 15:35, but execute in options that trade on to 15:40. Under the
old session both were 15:30. Nothing measures that 4-minute gap yet; the observer captures it.

---

## ⚠ CONFIRMED BUG (2026-08-05 15:36) — the scan reads YESTERDAY's close. The retiming bought nothing.

`engine/session_observer.py` ran its first live session and settled Q2 empirically. At **every** sample
from 14:45 through 15:38, including 15:36 (the scan instant), the last daily bar the scanner would
read was dated **2026-08-04** — the previous session. `stale=True` throughout.

Root cause, verified: **the Upstox feed has no same-day daily bar during the session.** At 15:41 on
5-Aug, `fetch_upstox_historical('RELIANCE.NS', unit='days')` returned bars ending 2026-08-04
(close 1290.9), while the 5-min intraday series had 5-Aug data to 15:25 (close 1280.0).

Consequences:
1. **The 15:36 retiming achieved nothing on signal fidelity.** It reads the same stale bar 15:10 did.
   The "+44% more breakouts" was a counterfactual the system never ran. The audit called this and it
   is now confirmed on live data.
2. **Moving the scan cannot fix it.** No time of day works — the bar does not exist intraday.
3. **The system has been trading a 1-DAY-DELAYED strategy all along** — breakout computed on T-1's
   close, traded on T. The backtests assume T's breakout entered at T's close. This is untested, and
   it predates the session change; it is NOT caused by CAS.
4. `stock_credit_v2.py:116-121` (+ `stock_credit.py:100-102`, `swing_credit.py:106-108`) take
   `df["Close"].iloc[-1]` with no freshness check, so this failed silently and always has.

**Options to fix (none implemented, user not yet consulted):**
  (a) construct today's close from the intraday 5-min series (last bar ~15:25) — a PRE-auction price,
      not the official close, but same-day;
  (b) pull NSE bhavcopy after it publishes (~18:00) — the true official close, but too late to trade
      that session, so it becomes a next-morning signal;
  (c) accept the 1-day delay and RE-BACKTEST the strategy as T-1-signal/T-entry, which is what is
      actually running.
Whatever is chosen, add the freshness guard: a scan that cannot get today's close must refuse to fire
and log loudly, not silently trade a day-old breakout.

**Today 5-Aug: no calls, legitimately.** Watchlist built 15:17 held 15 breakout names, **0 passed
c/w >= 0.40** (top SIEMENS 0.31). Nothing fired in any book.

Also noted: `market_is_trading_today()` returns False after FNO_CLOSE, so the morning re-check logs
"exchange holiday — no message" post-15:40. Misleading log text, not a gating bug.

---

## ⚠️ OPEN / UNRESOLVED (2026-08-06) — third-party audit found a possible STALE-BAR bug. Nothing fixed yet.

Two independent agents (auditor + adversarial critic) reviewed the 15:36 retiming. **No code was
changed — user said report first.** Findings that matter:

**1. THE SCAN MAY BE READING THE PREVIOUS SESSION'S CLOSE.** `engine/stock_credit_v2.py:113-121`
takes `df["Close"].iloc[-1]` with **no check that the last daily bar is today's**; same in
`stock_credit.py:100-102`, `swing_credit.py:106-108`; `data_fetcher.py` has no freshness check.
Hard evidence: `data/union_watchlist.json` built **4-Aug 14:45 contains exactly the 46 breakouts of
3-Aug's close (46/46 identical set)** and only 8 of 15 that broke out on 4-Aug; **14 of 19 live
positions since June match the PRIOR day's close breakout**, 5 the same day's. Our own study note
(no 4-Aug data in the feed at 18:15 on 4-Aug) supports it and was never connected to the scanner.
**If true, the whole retiming analysis is moot and live has been trading day-old breakouts.**
CHEAP TEST: log at 15:36:00 the DATE of the last daily bar the scanner reads + whether its close
matches that day's bhavcopy.

**2. My cost table was wrong (convention).** Compared a full quoted spread to a one-way charge.
`spf()` charges 1.00% short / 1.51% long on the real GRASIM legs (blended 1.20%), NOT "~1%/leg".
Corrected extra cost −₹51/+₹79/+₹210 at 2/3/4%, not ₹210/₹470/₹730. **The 2–4% spread figure has NO
artifact in the repo** — no script, no data, no log. Only persisted sample: 14:45 4-Aug, median 1.20%.

**3. +44% becomes ≈+20% after the live spread gate** (`STOCK_CREDIT_MAX_SPREAD_PCT=6`, rejects 3/18
at 15:36) — right at v0's break-even. The break-even table omitted that gate.

**4. PRO 2 may be backwards.** If the option daily `C` is a closing VWAP, fill-vs-VWAP variance is
minimised at the window CENTRE: old 15:15 in 15:00–15:30 = centre; new 15:38 in 15:10–15:40 = tail,
**2.6–3.3× the variance**. Never checked which construct `C` is.

**5. "84–87% win rate" is v2 ONLY.** v1 OOS 73.4% (346 trades); v0 90.9% on n=44.

**6. CLAIM 2 proved nothing.** Upstox==bhavcopy 113/113 on 3-Aug AND 4-Aug — but ALSO 113/113 on
31-Jul (pre-change). Upstox always carried the official close.

**SURVIVED:** settlement fix (pure correctness); the principle that backtests are close-based so a
close-based scan is the faithful variant; CLAIM 3 reproduced exactly (32/46, PNB, 0.680% drift).

**VERDICT (critic): NOT YET KNOWABLE, closer to break-even than claimed. Do not quote the
₹39k/₹54k monthly figures.** Order of work: (a) settle the stale-bar question, (b) measure GATED
FIRED SIGNALS/month before vs after (v2 3.7, v1 12, v0 5.8) over ~a quarter, not breakout counts.

Agents (resumable): auditor `a3a815eeb581d0165`, critic `ab42b56aada679aee`.

---

## DONE (2026-08-05 16:20) — CAS NIFTY AND SENSEX DATA recorder, built + deployed + backfilled

**Goal:** nothing was capturing the new 15:15–15:40 close window, which is exactly where
`KILL_SWITCH_TIME` (15:36) and the 15:36 scan operate. It is now recorded every session.

**What it records**, per session per index (NIFTY, SENSEX):
index OHLC, prev close, %chg, 15:15 spot, 15:15→close move, close-vs-high, last-60m move, India VIX
at close · the **ATM CALL and ATM PUT** for the nearest expiry on/after the day, strike picked off
the **15:15 spot** so both legs share it · premium marks at **15:15 / 15:30 / 15:36 / close** ·
window hi/lo · **gross P&L per 1 lot** at each exit · traded volume before/after 15:30 · full 1-min
OHLCV from 15:00 for the index and both legs.

**Fill convention:** a mark at T is that minute bar's **OPEN** (what you'd pay entering at T); the
closing mark is the last bar's **CLOSE**. P&L is GROSS — no brokerage/STT/exchange/spread. Budget
~₹55–65 per round trip per lot on top.

**Writes to BOTH:**
  * `data/engine.db` → new tables `cas_index_close` (PK date,idx) and `cas_option_close`
    (PK date,idx,opt_type). `INSERT OR REPLACE`, so re-running any day is safe — verified, a second
    run left 6 index / 12 option rows unchanged, no duplicates.
  * `studies/CAS_NIFTY_SENSEX_DATA/` → `cas_index.csv`, `cas_options.csv` (full-table dumps,
    rewritten from the DB each run), `raw/<date>_<index>.json` (1-min series), `README.md`.

**Deployed:** `com.sayali.cas-recorder` — weekdays **15:50** with a **16:20** retry pass. Plist in
`deploy/`, copied to `~/Library/LaunchAgents/`, **loaded and force-run successfully under launchd**
(so it does not fail on launchd's stripped environment). Logs `logs/cas_recorder.{out,err}.log`.
Holidays return an empty intraday feed and it exits clean.

**Backfilled 3/4/5-Aug-2026 — the entire regime.** There is no earlier CAS data to fetch; before
3-Aug the derivatives close was 15:30 and 15:36 did not exist. All three fetch paths exercised and
recorded in the `src` column: `expired-api` (4-Aug NIFTY, expiry-day contract), `historical`
(SENSEX), `intraday` (same-day).

**Gotchas baked in:**
  * Same-day index/option data MUST come from `fetch_upstox_intraday` — the historical feed has no
    same-session bar. This is the same stale-bar trap documented at the top of this file; the
    recorder is a working instance of fix option (a) and confirms the intraday endpoint serves
    same-day 1-min data reliably at 15:50.
  * SENSEX options are **not** in `options._load_index()` (that master is NSE_FO only). They come
    from `dte_multi._bse_sensex_options()`. `_master()` in the recorder handles the split.
  * `EO.get_expiries()` rate-limits and returns [] silently — do **not** rely on it to resolve an
    expiry. The recorder resolves strike/expiry off the live master and uses the expired API only
    to fetch premiums, retrying both steps. An earlier version that trusted `get_expiries()` fell
    through to the live master and silently produced no premium data.
  * NIFTY lot size is **65**, SENSEX **20** — read from the instrument master, never hardcoded.
  * **BUG 1, FIXED 6-Aug — backfill resolved the WRONG EXPIRY.** `_resolve_atm` read only the live
    master, which purges expired contracts *some days after* they expire. On 5-Aug the 4-Aug weekly
    was still listed; by 6-Aug it was gone, so re-recording 4-Aug silently resolved to the 11-Aug
    weekly (entry 182.05, 7DTE) instead of the 4-Aug 0DTE (entry 75.55) — **and overwrote a correct
    row**. The answer depended on WHEN you backfilled. Now consults both masters and takes the
    earliest expiry on/after the day, resolving strikes from `EO.get_contracts` when that expiry has
    expired. Corrupted row re-recorded and verified byte-identical to the original.
  * **BUG 2, FIXED 6-Aug — `from==to` loses the newest session.** `fetch_upstox_historical` returned
    0 bars for NIFTY 5-Aug with `from=to=2026-08-05` on 6-Aug, while `from=05,to=06` returned all 25;
    SENSEX served the same request fine. Instrument-specific and silent. All past-day fetches now go
    through `_hist_day()`, which asks day..day+1 and filters to the day.
  * **The 1-min and 5-min historical feeds lag ~1 session** (no 5-Aug 1-min data on 6-Aug); 15-min
    and coarser publish sooner. This does NOT affect live recording (15:50 uses the intraday
    endpoint) but it means **a 1-min backfill of yesterday will find nothing** — use 15-min for
    recent-day studies, or wait a session.
  * The index goes dark after 15:30, so `mv_1515_close` is 15:15→15:30 only. Premium moves between
    15:30 and 15:40 track futures/the auction and have no index to explain them.

**Finding worth testing (n=3, NOT a result):** buying the ATM call at 15:15 and exiting 15:36 lost
on 4 of 6 index-days, three of them with spot UP — theta/IV crush outran delta. On 5-Aug the PUT
made money on both indices while the CALL lost (NIFTY −₹1,160 / +₹335, SENSEX −₹1,581 / +₹472),
spot up on both. The only large winner was 4-Aug NIFTY 0DTE (+₹5,792), an expiry-day gamma payoff
carrying 150% of the total P&L — strip it and the other five lose ₹1,983. **The recorder exists to
settle this properly; do not act on the n=3.**

**Next step if resumed:** the expired-instruments API reaches back months, so the same 15:15→15:36
ATM study can be run over 6–12 months *for the OLD regime's 15:15→15:30 window* to get a baseline,
splitting expiry-day from non-expiry-day. The CAS-specific 15:36 leg can only accumulate forward.

Manual run: `./.venv/bin/python -m engine.cas_recorder [YYYY-MM-DD [YYYY-MM-DD]]`

⚠ **Uncommitted.** `git status` also shows a pre-existing modified `engine/data_utils.py` and an
untracked `assets/` that are NOT from this work — check them before staging anything.

---

## VERIFIED (2026-08-05) — backtest granularity, and an honest read on the new timing

**Every v0/v1/v2 backtest is END-OF-DAY, both legs of the discipline.** Checked in the scripts, not
from memory:
  * IS (bhavcopy 2019→Sep'24): `pivot_table(values="CLOSE")`, entry premium `P["C"][di, si]` — the
    option's DAILY CLOSE on the signal day.
  * OOS (Upstox Oct'24→Jul'26): `/expired-instruments/historical-candle/.../day/...`, entry `sp[0]`
    = the option's daily close; underlying `unit="days", interval=1`.
So the backtest assumes **entry at the option's closing price on the breakout day** — an
idealisation you cannot actually transact at, under either the old or the new timing.

**Is the new timing better? Mixed — do not report it as a clean win.**
  * BETTER, signal fidelity: 15:36 reads the official close (verified == NSE bhavcopy, 6/6 exact).
    15:10 did not, and disagreed on ~1/3 of names. This is the big one.
  * BETTER, entry premium: the backtest prices entry off the CLOSING underlying. A 15:15 fill was
    priced off a pre-drift underlying (median 0.68% away); a 15:36–15:40 fill is priced off the
    close. More faithful.
  * WORSE, cost: spreads 2–4% vs the ~1%/leg the `spf()` cost model charges. On the GRASIM trade
    that is **₹470/trade extra at a 3% spread — 6% of v2's measured net, 17% of v0's.**
  * UNMEASURED: whether the +44% extra breakouts clear the c/w gate; the net of more trades at
    worse fills. +44% is also ONE day (3-Aug).

Added to CLAUDE.md: a standing rule not to be carried along by the user's framing (distinct from
"honesty over optimism", which is about reporting results).

---

## DONE (2026-08-05) — morning re-check: LAST TRADING DAY only, silent when that session had no call

`engine/signal_recheck.py` used "the most recent entry_date in any book", which reaches back days —
if yesterday produced nothing it would surface a call from three sessions ago as though it were
fresh. Now it resolves the previous session explicitly and sends NOTHING when that session produced
no signal (user, 2026-08-05).

`_last_session()` takes the LATEST of three independent witnesses, because no single one is safe:
  1. **NIFTY daily bar** before today — holiday-aware by construction (a bar exists only for a day
     the exchange traded; this repo has no hardcoded holiday calendar on purpose). BUT the Upstox
     feed publishes it late — at 18:15 on 4-Aug it still carried no 4-Aug data — so at 09:30 it can
     be a session behind.
  2. **newest entry_date in any book** before today — the engine opens positions on trading days
     only, so such a date IS a trading day. Fails when the session produced no signal.
  3. **mtime of union_watchlist.json** — rebuilt at WATCHLIST_AFTER every session, the only witness
     that survives a session with NO signal.
Max is safe both ways: a witness can only ever be a real session, and if the winner produced no call
the caller sends nothing anyway. Holiday failure mode is benign for the same reason.

Verified: with the last session at 04-Aug and every position dated 31-Jul, build_message() returns
"" and nothing is sent.

---

## DONE (2026-08-05) — 09:30 morning re-check LIVE (engine/signal_recheck.py)

Read-only re-validation of the PREVIOUS session's stock-credit calls. Writes NO book, NO trade-log
row — only `data/recheck_notified.json` (per-day de-dup). Fires from `engine_runner._morning_recheck`
in `cycle()`, gated on `config.SIGNAL_RECHECK_AT` (09:30), `SIGNAL_RECHECK_ENABLED`, weekday AND
`market_is_trading_today()` (holiday gate added on user note — weekday alone was not enough).

**Gates re-run live on the SAME strikes:** two-sided market both legs · premium ≥ ₹50 · bid-ask ≤ 6% ·
OI ≥ 100 · c/w inside that book's band · **short strike still OTM vs live spot** (new; no scan
counterpart — overnight a gap through the strike turns the fade into an already-losing trade).

**ONE template for both verdicts** (user): same 5 lines, only the verdict line + "Reason:" text
change, both from scan output; buy case gets one extra target line. Closes with the SAME separator +
"📚 Why this signal" block (pulled from `EngineRunner._TG_ANALYSIS`, so it cannot drift) + disclaimer.
Stamp reads `SIGNAL_RECHECK_AT`, not the wall clock.

⚠ **KNOWN: today's 09:30 send went out in the OLD template** — the engine fired at 09:30 before the
restart picked up the unified template, and the de-dup then blocked a resend. User was offered a
resend and said do not push. From 6-Aug it uses the unified template automatically.

**Why c/w ALONE is not enough (the GRASIM lesson, 5-Aug):** c/w rose 0.41 → 0.486 and looked better,
but spot had gone ₹16.60 THROUGH the 3,140 short strike. Of the ₹29.17 credit only ₹12.58 was time
value vs ₹24.85 at entry — **c/w rose 18% while the actual edge input halved**. Deeper ITM drives c/w
toward 1.0 with no edge at all. The gate is a proxy for elevated IV *on an OTM strike*; it stops
meaning that the moment the strike is ITM. This is why the OTM gate exists — do not remove it.

---

## IN PROGRESS (2026-08-05) — 09:30 morning re-check: message covers BUY *and* DON'T-BUY

`engine/signal_recheck.py` (read-only; never writes the trade log or any book). Re-runs every gate
live on yesterday's SAME strikes. User revision: it must ALWAYS send — "Good morning, in case you are
buying yesterday's calls … please don't buy today" WITH the reason when a gate fails, not just stay
silent. Naming the signals either way.

First live run 05-Aug: v1 GRASIM 3140/3200 DROPPED — spot 3,150.30 through the 3,140 short strike
(all premium gates passed: c/w 0.488, spread 1.7%, OI 89,000). The OTM gate is doing real work.

TODO: verify 09:30 is the right hour (opening spreads are widest), wire the trigger into
engine_runner.cycle(), commit + push.

---

## IN PROGRESS (2026-08-05 morning) — 09:30 morning re-check engine (AWAITING USER APPROVAL TO SEND)

New module `engine/signal_recheck.py`. Purpose: the signal fires 15:36 and the window shuts 15:40; if
the user missed it, at 09:30 next morning **re-run every gate live on the SAME strikes** and only if
they ALL still pass, send ONE reminder. **Read-only** — never opens/closes/edits a position, never
touches the trade log, writes only `data/recheck_notified.json` (per-day de-dup).

Gates re-run: two-sided market both legs · short prem ≥ ₹50 · bid-ask ≤ 6% · OI ≥ 100 · c/w still in
THAT BOOK's band (v2/v1 ≥0.40, v0 0.35–0.40) · **short strike still OTM vs live spot** (new gate — no
scan counterpart, because overnight a gap through the short strike turns the fade into an
already-losing trade).

**First live run (05-Aug 09:18) correctly sent NOTHING.** Yesterday's only call was v1 GRASIM BEAR_CALL
3140/3200. Spot 3,150.30 had gone **through** the 3,140 short strike, so it was dropped. Every other
gate passed (c/w 0.488, spread 1.7%, OI 89,000) — proof the OTM gate is doing real work.

**NOT YET DONE — next steps:**
1. User must approve the message format (shown in chat, nothing sent).
2. Wire the 09:30 daily trigger. Decide: a hook in `engine_runner.cycle()` (preferred — the engine is
   already KeepAlive) vs a separate launchd job. NOT wired yet.
3. Commit + push both remotes.

---

## DONE (2026-08-04 late) — target-book audit + Telegram summary reformat

**Target → WIN/LOSS → Telegram sequence VERIFIED end to end.** Planted a booked target in all eight
outcome books with `send_telegram` stubbed: **9 RESULT messages** (WIN and LOSS), **exactly 1**
portfolio summary, **0** on a second pass. Books covered: v2, v1, v0, swing, 0DTE NIFTY, SENSEX,
BANKNIFTY, monthly futures.

**Non-bug, do not "fix" it again:** the TP and stop branches in the credit books do not set
`changed = True`. It is unreachable — `bookable` requires the same fresh two-sided quote that sets
`changed` in the MTM block above. A target can only fire on a quote that already marked the book
dirty.

**Real bug found and FIXED (pushed):** `is_market_open()` is inclusive only to 15:40:00, so the cycle
that settles at `SETTLE_AFTER` was the LAST fast cycle, and `_outcomes()` (throttled 60 s) had almost
always just run — so it skipped, the loop dropped to its 300 s idle sleep, and every WIN/LOSS RESULT
+ portfolio summary landed **~15:45 instead of ~15:40**. Introduced by moving settle to 15:40 (at the
old 15:30 settle there were still 10 min of fast ticking). Fix: `SETTLE_GRACE_MIN = 6` in config +
`_in_settle_grace()` in the runner keeps the 5 s tick alive 6 min past the F&O close. Boundary tested:
15:39 F / 15:40–15:46 T / 15:47 F / weekend F.

**Portfolio summary reformatted (user, twice):** no ticks/crosses in either the intraday or month-end
block; each section is one sentence — **"Total trades = 8 out of which our system achieved 8 Wins and
0 Losses."** (user corrected "predicted" → "achieved"); win-rate and money on their own indented line;
OVERALL in the same form with wins, win-rate and realized in bold; blank lines between blocks.
Singular/plural handled; empty section prints "No closed trades yet."

⚠ **Still unverified LIVE:** no target has fired since any of this changed. First real test is the
next 0DTE expiry — it exercises the 15:40 settle, the 95% early close and this message together.

---

## IN PROGRESS (2026-08-04 evening) — verifying target-book → WIN/LOSS → Telegram sequence

User ask: "ensure once targets are booked you close the trade with win/loss and do the telegram
sequence". Checking every book's take-profit path end to end.

### Settled this session (no action needed)

**v0 is NOT broken.** It has never opened a position, so there is nothing in the trade log and no
`data/stock_credit_v0_positions.json`. Proof it runs: `data/stock_credit_v0.json` written 15:26 on
4-Aug with `rows: []`; zero `stock_credit_v0 scan/resolve` exceptions in the whole log. In 3 live
sessions (31-Jul, 3-Aug, 4-Aug) at 5.8 sig/mo (~0.28/session) the expectation is 0.8 — zero is normal.
Today's only band candidates were GRASIM 0.350 and HCLTECH 0.350; **GRASIM went to v1 at c/w 0.41 and
v0 stood down** per the user's tie-break rule (working as designed).

⚠ **Structural note worth revisiting:** v1 (1-OTM/width-3) produces HIGHER c/w than v0 (2-OTM/width-4)
on the same underlying, so the names landing in v0's 0.35–0.40 band tend to clear v1's 0.40 gate and
get taken by v1 first. v0 will therefore fire less than its 5.8/mo model. Not a bug — a consequence of
the tie-break — but it means v0's live record will accumulate slowly.

**Bug found and FIXED (pushed):** `_update_pm_now_hint` still pivoted on 15:10 after the scan moved to
15:36, so the banner announced the scan 26 min early and then showed **"Market closed"** from 15:36 —
during the only window in which a signal can be placed. Phases now 09:15 / 15:17 / 15:36 / 15:41.
Also `MARKET_CLOSE` (cash 15:30) → `FNO_CLOSE` on the 3-Family hours line, plus 11 stale copy strings.

**Engine health:** engine + viewer ALIVE. All 214 errors since 3-Aug are DNS/network
(`Failed to resolve api.upstox.com`, Yahoo timeouts) — machine losing connectivity, not code. No
tracebacks from any book.

---

## DONE (2026-08-04) — NSE 3-Aug session change: engine retimed, pushed to both remotes

**Nothing outstanding on this. It is deployed, committed and pushed (origin + private).**

NSE moved the equity-derivatives close to **15:40** and added a **Closing Auction Session
15:15–15:35**. F&O stocks stop continuous trading at 15:15 and their official close is now the
**auction equilibrium price**. Every name in `UNIVERSE` is an F&O stock.

**What was broken:** the close was a bare literal in **seven** places (`agent.py` hardcoded 15:30 and
ignored config entirely; `monthly_fut` at 15:25; `monthly_call` had **no time gate at all**), and
swing/stock books preferred **live spot over the official close** — so every expiry settled on a
guaranteed pre-auction print.

**What changed:** one session model in `config.py` — `CASH_CLOSE` 15:30 · `CAS_END` 15:35 ·
`FNO_CLOSE` 15:40 · **`SETTLE_AFTER` 15:40** (the single settle knob). Settlement inverted to
official-close-first. Schedule: watchlist+digest **15:17**, scans **15:36**, kill switch 15:36, EOD
15:40. 0DTE books close early at **95% of max profit** (`ZERO_DTE_EARLY_CLOSE_FRAC`), wired for all
three expiries.

**Evidence** (3-Aug replay, 113 names): 32 breakouts on the 15:10 price vs **46 on the official
close = +44%**, 15 gained, 1 false signal (PNB) removed, median drift 0.68%. Post-auction book
(4-Aug, 18 names): 17/18 two-sided, 15/17 clear the liquidity gate, c/w stable, but **spreads roughly
double** (~1% → 2–4%).

⚠ **The 95% early-close rule is UNMEASURED** — intraday option premium history does not exist, so it
cannot be backtested. Set `ZERO_DTE_EARLY_CLOSE_FRAC = 0` to revert to hold-to-expiry.

⚠ **Research caveat:** daily closes before 3-Aug-2026 are a 15:00–15:30 VWAP; after, auction
equilibrium prices. Not the same construct — do not splice without noting it.

Record: `studies/NSE_SESSION_CHANGE_2026_08_03.md`. STUDIES tab carries a notice; CLAUDE.md and
studies/README.md carry the standing rule. "IMPORTANT NOTIFICATION" Telegram sent 4-Aug.

**NEXT SESSION — the checks that actually prove it:**
1. Watch the **15:36 scan fire** and compare its list against the 15:17 watchlist — names the auction
   moved in or out are the whole point.
2. On the next NIFTY (Tue) or SENSEX (Thu) expiry, confirm settlement lands **15:40–15:42** on the
   published index close, not a 15:30 print.
3. Confirm the 95% early close fires and sends its RESULT message.
4. Instrument daily: log the breakout set at 15:10 vs the official close, and option bid-ask/OI at
   15:36. After ~10 sessions that decides whether +44% holds and whether the window stays liquid.

---

## DONE (2026-07-31 night) — 0.30-0.40 c/w BAND RESCUE: **REJECTED on OOS** (commits bc3801d, 6872345, 3da95c5 — LOCAL ONLY, not pushed)

User goal: the union watchlist blocks a lot of names at c/w ~0.30 — can any config (geometry,
target, "any other config") make them tradeable at better win rate + net? Answer delivered: **NO.
Nothing deployed, no engine file touched.** Study: `studies/LOWCW_BAND_RESCUE.md`.

**IS (bhavcopy 2019->Sep'24, 113 names, 2,254 priced UNION signals; band 0.30-0.40 = 782 = 34.7%):**
swept 432 cells — geometry strike-step (S0-3 x W1-5) AND percent-of-spot (S1-4% x W2-6%), TP
{40,50,75,hold}, stop {none,2x,3x} — plus a DTE sweep {5..55} and adaptive-width rules. Band at
deployed S2/W4 TP-50 stop-3x = 74.3% win / **-1.1% ROM** / +ve 3/6 (dead). Re-cut to **width 1**:
87.8% win / **+18.1% ROM** / +ve 6/6 on 680 trades, avg c/w rising 0.34 -> 0.42 (mechanism: c/w is
a function of how far the wing sits, so a FIXED width-4 rejects coarse-strike-ladder names, not
thin-premium ones). Best composite ADAPT-41 (W4 if clears 0.40 else W1 if IT clears): 11.5 tr/mo
vs 4.9, 89.9% win, +50% total net. Separately IS said v2's 3x stop costs ~21% of net (TP-40/no-stop
89.4%/+70.4% vs deployed 82.9%/+58.1% on the same 340 signals).

**OOS (Upstox expired options Oct'24->Jul'26, 38 of 113 names = UNIVERSE[::3]; 48 gate / 109 band /
198 below): BOTH CLAIMS FAIL.**
  band do-nothing W4      n=109  76.1% win  +1.9% ROM   (2024 +38 / 2025 -1 / 2026 -2)
  band S2/W1 TP-40 (IS winner) n=101  **74.3% win  +1.4% ROM**  (2026 **-7%**)
  band S2/W1 TP-50        n=101  75.2% win  +4.0% ROM   (2026 -3%)
  gate deployed / TP40-nostop / TP50-nostop / TP75-nostop, all n=48:
        95.8%/+219.4% · 97.9%/+204.5% · 97.9%/+221.0% · 95.8%/+229.1% — indistinguishable; at 96%
        win the 3x stop never binds, so removing it saves nothing. NOT evidence either way.
**Verdict: CW_BUCKET_ANALYSIS reinstated — below 0.40 win% holds (TP books small winners early) and
money does not follow. The gate IS the edge; leave it. v1's 30-Jul TP-40/no-stop (242 OOS trades)
is unaffected and stays.**

**Why IS lied:** every in-regime guard PASSED and none detected it — 20 adjacent W1 cells all +ve,
6/6 yrs, matched-sample bias check (the 102 signals W1 can't price are equally bad: -2.2% ROM),
month-block bootstrap p5 +26%, 32/34 symbols +ve, 58/68 months +ve, live liquidity probe fine
(W1 long leg carries 23k-8.5M OI at 0.4-2.5% spread; only BAJAJHLDNG rejects). Those test
consistency WITHIN a regime. Same lesson as the index-fade salvage (CLAUDE.md Part 11).

**SUB-BAND SPLIT — DONE, and it FOUND something the pooled test buried (commit 8f466f6).**
User pushed back ("we checked everything for 0.3 to 0.4?"). Split the band in half. Scripts
`ndte/stkfade_lowcw_subband.py` (OOS, reuses /tmp/lowcw_legcache.pkl so nearly free) +
`_subband_is.py`.

  OOS Oct'24->Jul'26 (upper n=43, lower n=66)      | do-nothing W4 | **W4 TP-40 no-stop** | W1 TP-40
    upper 0.35-0.40                                | 79.1%/+12.1%  | **90.7%/+19.4% 3/3yr** | 75.0%/+0.3%
    lower 0.30-0.35                                | 74.2%/-2.6%   | 75.8%/**-5.2%**      | 73.8%/+1.8%
  IS 2019->Sep'24 (upper n=310, lower n=472)
    upper 0.35-0.40                                | 72.9%/-1.4%   | **77.4%/+1.9% 4/6yr**  | 88.6%/+23.6% 6/6
    lower 0.30-0.35                                | 75.2%/-0.9%   | 79.4%/+0.2%          | 87.3%/+15.5% 6/6

1. **W1 width re-cut REJECTED, now more strongly** — strong IS in BOTH halves (6/6 yrs each), dead
   OOS in BOTH. 2. **0.30-0.35 is dead everywhere** — that is the half filling the watchlist; keep
   blocking. 3. **ONE live cell, and it is NOT a geometry change: 0.35-0.40 at the DEPLOYED width
   with TP-40/no-stop.** Positive both windows. Matches CW_BUCKET_ANALYSIS OOS (+9.2%w; this run
   +12.2%w). **This SETTLES the two-tier gate deferred 2026-07-16** (couldn't be validated on
   2019-24 then). Verdict: real but MARGINAL — +1.9% ROM IS with 2/6 yrs negative vs the core
   book's +58-70%; added trades earn ~1/30th the core's ROM; only works paired with TP-40/no-stop
   (which OOS says is neutral on the core). Recommended: **paper forward-test a 0.35 tier, do NOT
   deploy.**

**BUILT & LIVE — stock credit "v0" EXPERIMENTAL book (commit fcf9ecc, user-approved after being
shown it is a bad capital trade).** User was told three times, with numbers, that v0 adds ~+9% net
for ~+99% capital and that one more CORE lot returns 82% more on the same margin. He chose to run
it to build a live record. Built in full:
- `engine/stock_credit_v0.py` — loads a SECOND independent instance of `stock_credit_v2.py` via
  importlib and rebinds its constants (ONE copy of scan/resolve, no 400-line fork). Exports only
  scan_signals/resolve_positions/rows_for_ui — build_watchlist & notify_nearmiss are deliberately
  NOT re-exported (they own union_watchlist.json).
- `stock_credit_v2.py` gained TWO hooks that are NO-OPS for v2: `STOCK_CREDIT_MAX_CW` (None) and
  `EXCLUDE_SYMBOLS` (empty). VERIFIED v2 still = band 0.40 / ceiling None / TP-50 / stop-3x / own book.
- config `STOCK_CREDIT_V0_*`: band 0.35-0.40 (MAX_CW exclusive), TP 0.40, STOP 99 (none), geometry
  inherited from v2 (S2/W4), 1 lot, max 3 new/day, max 10 open (tighter than v2's 5/20).
- runner: v0 resolves after v2 and scans LAST of the three; skips any name v1 or v2 holds OPEN
  (extends the cross-book one-position-per-stock rule). Own Telegram EXECUTE signal with the
  standard IS/OOS-with-dates block, led by ⚠️ EXPERIMENTAL + the 4-of-6-years and n=43 caveats.
- UI: separate PM DECISIONS section + separate SWING TRADE LOG section, both dashed RED (NOT v2's
  gold), placed LAST so it can never be mistaken for the leader book. Tracked as "v0".
- CLAUDE.md live-books table has a v0 row with the honest weak-evidence note.
Engine (pid 352) + viewer (pid 597) restarted, both alive, no errors. v0 snapshot written; book
empty until the next 15:10 scan. v1 (3 open: TCS/BAJAJFINSV/BAJAJ-AUTO) and v2 books verified
unmodified. **v0 will skip those 3 names by design.**

**LABEL CHANGE (commit b0175ae, pushed):** user rejected "EXPERIMENTAL" on v0 — fair, since the OOS
numbers (91%/+19.4% ROM/3-of-3 yrs) are decent and the word was framing not fact. Removed everywhere
(0 occurrences). All numbers kept. Sizing argument MOVED OUT of the per-signal Telegram into the
STUDIES card + CLAUDE.md (a signal states its own evidence, not portfolio allocation). UI dashed-red
-> solid cyan. STUDIES tab gained 2 cards (v0 deployment + REJECTED width-1 re-cut). **All pushed to
BOTH remotes (origin + private), 0 unpushed.**

**EXPECTED MONTHLY FROM CADENCE (commit e14d590):** model **Rs39,799/mo at 1 lot across ~42 sig/mo** —
v2 Rs20,000 (7.6/mo x Rs2,632) · v1 Rs13,000 (16/mo x Rs812) · SENSEX Rs3,153 · NIFTY Rs1,771 ·
v0 Rs1,875 (6.8/mo x Rs276). Sober = half (~Rs19,900). LIVE July 2026 = 20W/4L, 83.3%, **Rs44,789
realised** (113% of model, one hot month). v0 = Rs0 so far, book empty. **v1 is 86% of all realised
P&L.** Key sizing fact: v0 fires almost as often as v2 (6.8 vs 7.6/mo) for a TENTH of the money per
trade (Rs276 vs Rs2,632).

**V2 SIGNAL-SHORTFALL DIAGNOSED (2026-07-31 night) — the Rs20,000/mo v2 model is NOT reachable live.**
July 2026: v1 fired 12 (model 16/mo, fine) but **v2 fired ONCE** (model 7.6/mo). Cause is structural,
not luck — TWO live-only filters the backtest never modelled hit v2's wider geometry much harder:
  (a) **c/w gate x geometry** — v1 is short-1-OTM/**width 3**, v2 is short-2-OTM/**width 4**. A wider
      wing mechanically LOWERS credit/width (the same mechanism the band study proved), so v1 clears
      0.40 far more often. v1's live c/w range is 0.40-0.47, i.e. it only just clears.
  (b) **the Rs40k exposure cap** (`width_pts*lot <= 40000`, v2-only risk limit): measured live on the
      113-name universe — blocks **33% of names for v2 vs 10% for v1**; 22 names blocked for v2 but
      not v1 (ABB, AXISBANK, DIVISLAB, M&M, APOLLOHOSP, ...).
OFFSET: v1 realised **Rs2,737/trade vs its Rs812 model** — fewer trades, much bigger ones.
**NOT ACTIONED (needs user):** either correct v2's Rs20,000/mo in CLAUDE.md/README to the ~1/mo live
cadence, or raise the exposure cap (a risk-appetite call — the cap cut worst single loss from
-Rs84.7k to -Rs21.6k). Offered a cap-sensitivity run (60k/80k vs signal count and worst loss);
user did NOT take it up.

**v0 SHIPPED + ECONOMICS CORRECTED (commits 09e7605, faae476, 89ebb3e — all pushed both remotes).**
I had v0's economics WRONG TWICE and corrected them: first "+9% net / Rs276 per trade" (compared the
books in POINTS not rupees — v0 trades big-lot names ADANIGREEN 600 / COFORGE 475 / LUPIN 425), then
ignored the live Rs40k exposure cap (backtests have NO cap, so they count trades the engine can never
take). Re-measured on real Upstox premiums Oct'24->Jul'26, 38 names, 1 lot, WITH the cap:
    v2 core (c/w>=0.40, TP-50/stop-3x = its REAL config) : 3.5/mo · 92.3% · +41.2% margin · Rs6,267/tr · ~Rs22,000/mo
    v0      (0.35-0.40, TP-40/no-stop)                   : 5.5/mo · 90.2% · +18.7% margin · Rs2,408/tr · ~Rs13,300/mo
Cap blocks 17 of v2's 43 OOS trades but only 2 of v0's -> **v0 fires MORE often live than v2 and adds
~+61% on top.** Per rupee of margin v2 still wins (+41.2 vs +18.7) but it is signal-starved.
v0 IS/OOS: 77% (+ve 4/6 yrs, n=310) / 91% (+ve 3/3, n=43). Telegram quotes the MEASURED 91% (an
80% cap was added then reverted at user request).
**TIE-BREAK RULE (user):** v1/v2/v0 + watchlist scan in PARALLEL and INDEPENDENTLY, EXCEPT if v0 and
v1 would both trade the SAME stock -> **v1 wins, v0 stands down, ONE signal only**. v0 scans last so
it sees v1's new entries. v0 vs v2 can never clash (same geometry, mutually exclusive c/w bands), so
v2 is NOT consulted. Implemented in `stock_credit_v0._v1_open_symbols()`.
**STUDIES tab** rebuilt on FULL-WINDOW AVERAGES (user: never quote a single month) — LIVE STRATEGIES
table + TIER A now carry v0, signals/mo, model Rs/mo and a cap-applied Rs/mo column.

**KNOWN GAP:** v1's own geometry (short-1-OTM/width-3, TP-40/no-stop) was NEVER re-measured with the
cap — its Rs13,000 model figure sits in the totals as an ESTIMATE next to two measurements. The cap
blocks only ~10% of v1's names (measured live) so it should be close. Offered to run it; not yet done.

**EXPOSURE CAP REMOVED (commit 4632cd0, pushed).** `STOCK_CREDIT_MAX_EXPOSURE` is now a config
constant; hardcoded 40k -> 60k -> **0 (NO CAP)**, all on 2026-07-31 at the user's instruction.
Applies to v2 AND v0 (v0 runs a second instance of the same module). Measured first, OOS, v2 @1 lot:
40k = 26 tr/Rs22.0k mo · 60k = 27 tr/Rs28.6k mo · no cap = 43 tr @ Rs47,824 avg.
HONEST CAVEATS recorded in config + STUDIES: no-cap is NOT unbounded (largest live width x lot is
HEROMOTOCO Rs90,000 = ~Rs45k max loss; median Rs30,000; 60k already allowed 87/92 names so removal
adds ~5) BUT it removes the ceiling for any future high-priced listing. The ~Rs278k/mo no-cap figure
is NOT credible (>100%/mo on deployed margin, n=43) and was deliberately kept OUT of the totals.
Real risk = whale profile: big-exposure trades won 95.3% in this window; the one that loses cost
-Rs84.7k, worst MONTH -Rs2.28L, on the longer window that produced the original 40k limit (~17% of
a Rs5L account). **BUG I CAUSED AND FIXED:** the first config patch DELETED the constant instead of
replacing it -> ImportError that would have crashed the engine on next restart. Caught pre-restart.
**PLAN-ON is 80% of model** (was 50%; UI had used 80% before I wrongly changed it). CLAUDE.md updated.
**Take-profits confirmed distinct: v2 = TP-50 + stop-3x · v1 = TP-40 no stop · v0 = TP-40 no stop.**
The "TP-40 no-stop" row in the earlier v2 comparison was v2 GEOMETRY with v1 EXITS (a hypothetical to
isolate the stop) — NOT v1.

**STUDIES TAB REBUILT (commit 454768b, pushed).** Stripped to what works + a real execution guide.
REMOVED: the stale auto-generated "THE LIVE STRATEGIES — SUMMARY" table (still said 4 live books /
Rs37,924, no v0, no cap columns) and its orphaned builder `_strategy_summary_table()` (97 lines,
nothing else called it), plus 646 tail lines (superseded 3-Family/ORB+VWAP gate studies, old worked
example, per-study logs 1-9, duplicate 0DTE narrative, shelved long-call). NOTHING LOST — all of it
still lives in studies/*.md and on GitHub; only the dashboard copy went. ui_terminal.py 2141 -> 2044.
ADDED: "HOW TO EXECUTE — step by step" — stock books as 9 numbered steps (15:10 scan · fade not
follow · exact strikes per book · liquidity floor · place before 15:30 · exits v2 TP-50 vs v1/v0
TP-40-no-stop · settlement · the v1-wins rule) and expiry-day books as 5 steps (09:16 off the open ·
0.5% OTM + 200pt wing · rv5 calm skip · hold to 3:30 · why entry time IS the edge), plus "THE FOUR
RULES". KEPT: the full-window LIVE STRATEGIES table, REJECTED/OFF table, six surviving results, and
a "do not re-mine these" list (kept deliberately against the user's "delete most" — it is the repo's
guard against re-exploring dead ends; user was told and can still cut it).

**BREAKTHROUGH — SELLING BOTH SIDES WORKS ON THE DEAD BAND (commit 91e437c, pushed).** After the
calm-regime filter was refuted, the last untested idea was STRUCTURAL rather than parametric: every
previous attempt moved WHERE the single spread sits or WHEN it is taken; none fixed the actual defect,
which is that at c/w 0.30 one side does not collect enough premium for its risk. A condor fixes it —
sell the fade side AND the opposite side, credit roughly doubles, width barely moves (only ONE side
can finish ITM when wings do not overlap). Pre-registered on the in-house precedent of the DEPLOYED
0DTE FLIP-CONDOR HYBRID. `ndte/lowcw_condor.py`, IS 2019->Jul'24, band 0.30-0.35, TP-40:
    one side (baseline)              n=506  81.4% win   +3.5% ROM  5/6 yrs  c/w 0.32
    + opposite side c/w >= 0.10      n=336  64.3% win  +24.8% ROM  5/6 yrs  c/w 0.65
    + opposite side c/w >= 0.30      n=236  62.7% win  +34.6% ROM  5/6 yrs  c/w 0.68
Combined c/w 0.32 -> 0.65 clears the 0.40 level that IS the edge. Stable across the whole floor
0.10-0.30. Win rate FALLS 81->64% while net rises ~7x — every other candidate did the reverse, so
this is the payoff ratio finally being right rather than a flattering win rate.
**NOT DEPLOYED.** Caveats in study §9: (1) the width-1 re-cut looked STRONGER (6/6 yrs, bootstrap
p5 +26%) and still died OOS, so IS only buys the OOS run; (2) costed as ONE-SIDED margin (correct
for the structure, normally what SPAN gives a condor) — if the broker charges both sides ROM roughly
HALVES to ~12-17%; verify in Upstox.

**CONDOR OOS DONE — THE DEAD BAND IS RESCUED (commit ecd9192, pushed). First candidate in this
entire study to survive the held-out window.** `ndte/lowcw_condor_oos.py`, real Upstox premiums
Oct'24->Jul'26, 38 names, 1 lot, TP-40 of TOTAL credit.
  BAND 0.30-0.35   one side          n=67  76.1% win   -4.1% ROM  1/3 yrs
                   + opp >= 0.10     n=47  63.8% win  +18.4% ROM  3/3 yrs   (IS +24.8%)
                   + opp >= 0.20     n=46  63.0% win  +18.2% ROM  3/3 yrs   (IS +25.3%)
                   + opp >= 0.30     n=29  55.2% win   -5.2% ROM  1/2 yrs   (IS +34.6%)  <-- FAILS
  BAND 0.35-0.40   one side (v0)     n=44  90.9% win  +20.5% ROM  3/3 yrs
                   + opp 0.10/0.20   n=32/28  +25.9% / +19.4%     2/3 yrs
CONCLUSIONS: (1) 0.30-0.35 IS tradeable as a condor at floors 0.10-0.20; IS+24.8% -> OOS+18.4% is
consistent, unlike the width-1 re-cut (+18.1% -> +1.4%). Combined c/w 0.33 -> 0.64 clears the level
that IS the edge. (2) The >=0.30 floor FAILS OOS despite being the BEST IS cell — the neighbourhood
is NOT uniform, use 0.10-0.20. (3) **The "upgrade v0 to two-sided" claim is WITHDRAWN** — one-sided
is +20.5%/3-of-3 there and the condor does not beat it. v0 stays one-sided. (4) It does NOT do what
was literally asked: net -4.1% -> +18.4% but WIN RATE FALLS 76% -> 64%; it buys net by fixing the
payoff ratio.
**NOT DEPLOYED.** Gates: n=46-47 thin; one neighbouring floor already failed; four legs = double
slippage/fill risk on mid-caps; and above all **the MARGIN CONVENTION — costed as one-sided risk
(one width - total credit = true max loss, what SPAN normally grants a condor). If Upstox blocks
both spreads separately, +18.4% becomes ~+9%.**

**BUG FIXED mid-run (worth remembering):** `m = min(len(q["sp"]) ...)` took the min over SHORT legs
only then indexed the LONG legs at the same k -> IndexError on any side whose long-leg series is
shorter. It killed the whole ThreadPool, and the supervisor restarted straight back into it (a crash
loop at 36/38 stocks). Fixed to min over BOTH legs, and the per-signal block is now try/guarded so one
malformed series cannot take a multi-hour run down. Per-stock checkpoints meant zero work was lost.

**CONDOR REJECTED ON SIZE (user's call 2026-08-01: "246 is nothing per lot ignore it, keep it in
studies"). CORRECT CALL — recorded, not deployed.** The edge is REAL and it is the only thing in this
whole study to survive OOS, but it is too small to be worth four legs. Cost sensitivity (leg-cache
re-run at 2x cost, no new API calls):
    avg margin (max loss)                          Rs9,893/trade
    net at modelled cost                           +Rs805/trade   (n=43)
    the MODELLED 4-leg cost                        Rs578/trade
    breakeven if real cost is                      Rs1,383/trade
    repo's MEASURED 4-leg stock cost               Rs1,137/trade  (STOCK_OPTIONS_NO_EDGE Part 4)
    => net at that measured cost                   +Rs246/trade ~ Rs1,400/mo at 1 lot
At 2x modelled cost it STILL returns +17.0% ROM, 3/3 yrs — so it is not statistically fragile. It is
just small, and breakeven sits only 21% above the cost that KILLED the previous 4-leg stock book
(which also looked good on ESTIMATED cost: +6.9% holdout -> -4.7% net on real). Rs246/lot does not
pay for four legs of mid-cap fill risk.
**THE 0.30-0.40 BAND IS NOW CLOSED. Do NOT re-mine it a fourth time.** One-sided: dead (432 configs,
DTE sweep, adaptive width, regime filter). Two-sided: works, too small. Only 0.35-0.40 one-sided
(= v0, deployed) is worth trading.
Recorded in studies/LOWCW_BAND_RESCUE.md §9-10 + a STUDIES-tab card. Viewer restarted.

**WHAT WOULD REOPEN IT:** v0's live fills. If they come in near model, the Rs246 floor is
conservative and the condor is worth revisiting. That evidence arrives free from a book already
running — **v0 has fired ZERO live trades so far**, which is also why no second unproven book should
be added before the first produces evidence.

**STUDIES TAB REBUILT (commits 7dd05a9 + this one).** LIVE STRATEGIES table restored with both
windows NAMED IN FULL ("1-Jan-2019 -> 30-Sep-2024" / "1-Oct-2024 -> 1-Aug-2026") instead of
in-sample/out-of-sample; SENSEX's first window says WHY it is empty (SENSEX weekly options only
began Oct 2024). Below it a PROFIT AND LOSS table showing trades/month and the expectancy
ARITHMETIC written out per the user's request (win% x avg win - loss% x avg loss):
  v2      ~7.6/mo  83.2%  +Rs13,219 / -Rs11,645  = Rs10,998 - Rs1,956 = +Rs9,042/trade
  v1      ~16/mo   85.1%  +Rs5,557  / -Rs7,571   = Rs4,729  - Rs1,128 = +Rs3,601/trade
  v0      ~5.8/mo  76.5%  +Rs3,986  / -Rs11,505  = Rs3,049  - Rs2,704 = +Rs346/trade
  NIFTY   ~4/mo    93.2%  +Rs1,202  / -Rs6,274   = Rs1,120  - Rs427   = +Rs694/trade
  SENSEX  ~4/mo    88.8%  +Rs1,427  / -Rs4,549   = Rs1,267  - Rs509   = +Rs758/trade
Source: `studies/ndte/book_win_loss_sizes.py` (local pickle, no API).

**IMPORTANT — expectancy x cadence does NOT reconcile with the Rs54,224 model, and the tab now says
why, with evidence rather than assertion.** Rupees use TODAY's lot sizes applied to old trades, so
every book measured on older years runs hot:
  SENSEX (measured Oct'24->now, i.e. CURRENT lots)  Rs3,031 vs model Rs3,153  = 1.0x  <-- the control
  NIFTY  (2019->Sep'24)                             Rs2,775 vs Rs1,771        = 1.6x
  v2     (2019->Jul'24)                             Rs68,718 vs Rs20,000      = 3.4x
  v1     (2019->Jul'24)                             Rs57,615 vs Rs13,000      = 4.4x
  v0     (2019->Jul'24)                             Rs2,005 vs Rs16,300       = 0.1x (mirror image:
         its model comes from the 2024-26 window at Rs2,808/trade, the table shows 2019-24 at Rs346)
SENSEX being the ONLY post-Oct-2024 book AND the only 1.0x is the proof. **Plan on Rs54,224 / 80% =
Rs43,379, NOT on that column.** The table is for the ARITHMETIC and the win:loss shape, which are sound.

**CORRECTION SHIPPED:** v2 previously showed +Rs50,749 / -Rs12,147 and 4.2:1 win:loss. WRONG — a
lot-size mix artifact, and structurally impossible for a defined-risk spread (winner capped at the
credit, loser at width-credit). Re-measured on the same basis as every other row: **1.1:1**. v1 and
v0 rows moved to the same basis too.

**Rs20,000 vs Rs9,042 CONFUSION RESOLVED — there is now exactly ONE money table in the tab.**
User was rightly confused: Rs9,042 is PER TRADE, Rs20,000 was PER MONTH, and they were computed on
different signal rates. Rs20,000/mo assumed **7.6 signals/mo for v2, which this session already
proved wrong** (v2 really fires ~3.5/mo — the width-4 geometry both clears the 0.40 gate less often
than v1's width-3 AND used to be blocked 33% of the time by the exposure cap). The rupees were never
the problem; the cadence was.
FIX: the LIVE STRATEGIES table no longer carries a Rs/mo column at all (it shows modelled vs REAL
signal rates only), and ALL rupees live in one PROFIT AND LOSS table that shows the arithmetic and
multiplies by MEASURED cadence:
  v2      ~3.5/mo  83.2%  +Rs13,219/-Rs11,645  exp +Rs9,042  = Rs31,646/mo
  v1      ~12/mo   85.1%  +Rs5,557 /-Rs7,571   exp +Rs3,601  = Rs43,211/mo
  v0      ~5.8/mo  76.5%  +Rs3,986 /-Rs11,505  exp +Rs346    = Rs2,005/mo
  NIFTY   ~4/mo    93.2%  +Rs1,202 /-Rs6,274   exp +Rs694    = Rs2,775/mo
  SENSEX  ~4/mo    88.8%  +Rs1,427 /-Rs4,549   exp +Rs758    = Rs3,031/mo
  TOTAL   ~29/mo                                             = Rs82,667/mo · 80% = Rs66,134
**The old Rs54,224 / Rs43,379 model figures are GONE from the tab** — they were built on smaller
historic lot sizes and understate current economics (v1's model said Rs13,000/mo; v1 realised
Rs38,312 live in July). Sanity anchor stated in the tab: July 2026 live = 24 closed, Rs44,789 —
BELOW Rs82,667 because live fired fewer trades than the signal rates assume, not because per-trade
was wrong (v1 realised Rs2,737/trade live vs Rs3,601 modelled). Ceiling Rs66,134, floor one live month.

**BUG SWEEP 2026-08-01 — 1 real bug found and FIXED, 1 counting error corrected, 15 assertions pass.**

*BUG FIXED — monthly futures resolved SILENTLY.* `monthly_fut_positions.json` was in NEITHER
`_OUTCOME_BOOKS` nor `_BOOK_TAG`. It is REGIME_OFF today (NIFTY under its 200DMA) so nothing was
lost, but the moment the regime turns it trades again and every WIN/LOSS would have gone out with
NO Telegram result and been ABSENT from the running portfolio summary. Added to both. Safe because
the watcher only fires on status WIN/LOSS, so this book's REGIME_OFF placeholder rows are ignored.
Engine restarted, alive.

*COUNTING ERROR CORRECTED — July signals are 23, not 25.* The two "monthly futures" July rows
(2026-07-10, 2026-07-31) are `status=REGIME_OFF` markers with null symbol/side/entry — they are the
book recording that it STOOD ASIDE, not trades. July 2026 actual entries:
    v1 12 · v2 1 · 0DTE SENSEX 4 · 0DTE NIFTY 3 · index swing 3 · v0 0  = **23 on 17 distinct days**
(v0 was only deployed 31-Jul so zero is expected; index swing's 3 all predate its 07-24 disable.)

*CHECKED AND CLEAN:* engine + viewer alive, no tracebacks; no stale/expired-but-OPEN positions (4
open, all marked); v0 runs a genuinely separate module instance from v2 with separate book files,
and v2's two hooks (`STOCK_CREDIT_MAX_CW`, `EXCLUDE_SYMBOLS`) verified no-ops for v2 itself; v0's
EXCLUDE_SYMBOLS is set in a try/finally so a scan exception cannot leak the exclusion into the next
run; exposure-cap guard short-circuits correctly at 0; v0 scans AFTER v1 in the runner (so the
v1-wins tie-break actually sees v1's new entries); v0 does not re-export build_watchlist /
notify_nearmiss (which own union_watchlist.json).

*NOT a bug (checked, false alarm):* "0DTE BANKNIFTY" has no Telegram evidence block ON PURPOSE —
`_analysis` deliberately excludes it so a REJECTED book cannot inherit NIFTY's 88/90% stats via the
"NIFTY" substring. And the 0DTE/SWING labels look absent from the outcome watcher only because that
list keys on FILES with its own display labels ("0DTE NIFTY (same-day)"), not on the _tg() labels.

**TELEGRAM BUG FIXES 2026-08-03 (user sent screenshots) — 3 bugs, all fixed, engine restarted.**

*BUG 1 — raw `<b>` tags in every watchlist digest. ROOT CAUSE FOUND.* `stock_credit_v2.py:261` built
`prob = "<76%"` for c/w < 0.30 — a LITERAL '<'. Telegram's HTML parser reads it as an opening tag and
returns 400, so the WHOLE digest fell through to the plain-text fallback with every `<b>` visible.
Visible in the screenshot on the MARUTI line ("backtest win <76%"). Fixed to `&lt;76%`. Validated:
the rebuilt digest now has ZERO stray `<`/`>`.

*BUG 2 — the fallback made it worse, and silently.* `notifications.send_telegram` resent the body
VERBATIM on a 400 ("so it still reaches the user, tags and all"), which is exactly why the reader saw
markup; and because the retry succeeded it `continue`d WITHOUT LOGGING, so a broken message left no
trace anywhere (that is why nothing appeared in the logs). Now: new `_strip_html()` removes tags and
unescapes entities before the plain retry, AND a WARNING is logged naming the first 120 chars so the
next escaping bug is visible immediately.

*BUG 3 — phantom "2 futures trades" in the portfolio summary. THIS WAS MY REGRESSION from the
2026-08-01 sweep.* `_portfolio_summary_text` used a bare `else: openn += 1`, so ANY status that was
not WIN/LOSS counted as an open trade. Harmless until I added monthly_fut to `_BOOK_TAG`, which then
surfaced its two REGIME_OFF marker rows (null symbol, null expiry — the book recording that it STOOD
ASIDE) as "?: 2 trades — ? (MONTHLY FUT), ? (MONTHLY FUT)". Now only `st == "OPEN"` counts; any other
status is neither open nor closed. Verified: summary now reads **Open: 3 trades** (NIFTY swing, TCS,
BAJAJ-AUTO) — correct.

*VERIFIED (user asked): targets tracked and results sent for ALL books.* Result/WIN-LOSS Telegram
coverage is now 8/8 position files with NONE missing (v2, v1, v0, swing, 0DTE NIFTY, SENSEX, BNF,
monthly fut). Take-profit is applied inside resolve_positions for v2 (50% of credit, stop 3x), v1
(40%, no stop) and v0 (40%, no stop) — all three confirmed by source inspection. Every signal states
its own target and stop: v2 "book at 50% of credit"/3x · v1 & v0 "book 40% of credit"/none ·
swing "hold to expiry"/2x · 0DTE NIFTY & SENSEX "hold to same-day expiry"/none.

**PUSH BLOCKED — 1 commit sits LOCAL ONLY: `f079b61` (the 3 Telegram fixes).** `git push` fails with
`could not read Username for 'https://github.com': Device not configured`. Diagnosed: the osxkeychain
helper returns NOTHING for github.com, `gh` CLI is not installed, no GH_TOKEN/GITHUB_TOKEN env, no
SSH key. Earlier pushes THIS SAME DAY succeeded, so the credential was reachable before the session
restarted and is not now, and git has no TTY to prompt on. Remotes are correct (origin =
Institutional-Trader, private = Institutional-Trader-private-). **The user must run it themselves:**
`cd ~/files/institutional-trader && git push origin main && git push private main` (GitHub needs a
Personal Access Token, not an account password). NOTE: the fixes are LIVE in the running engine
regardless — the push only affects the repos.

**TARGET-TRACKING MECHANISM — verified from source + live quotes 2026-08-03 (user asked "are you
running live prices").** For the stock credit books (v0/v1/v2), every 15 min
(`STOCK_CREDIT_RESOLVE_INTERVAL = 900`):
  1. fetch a LIVE Upstox quote for BOTH option legs — NOT the underlying;
  2. price = MID of bid/ask (`_quote`), falling back to LTP if there is no two-sided market;
  3. cost to close = short mid - long mid;
  4. TARGET when `cost <= credit * (1 - TP)` -> WIN  (v2 TP-50, v1/v0 TP-40);
  5. STOP when `cost >= credit * stop_mult` -> LOSS  (v2 3x; v1/v0 99x = never, wing caps it);
  6. the UNDERLYING price is used ONLY at expiry (expiry day past 15:30) for intrinsic settlement,
     via live spot then the expiry-day daily close — the 07-21 fix against fabricated wins.
Live-verified: both legs of both open v1 spreads (TCS 2420/2480, BAJAJ-AUTO 11400/11700) have real
two-sided markets, so the fallback is not currently firing.

**TWO OF THE THREE LIMITATIONS ARE NOW FIXED (user: "keep it on only during market hours" then
"do what is right, you are the decision maker"). Engine restarted, verified live.**

*(a) MTM/TARGET LOOP IS NOW MARKET-HOURS ONLY.* `_stock_credit`'s resolve is gated on
`is_market_open()`. **CRITICAL SUBTLETY — do not "simplify" this gate:** `is_market_open()` is
9:15-15:30, but the expiry branch inside resolve_positions only fires once `now >= 15:30`. A naive
market-hours gate therefore gives settlement a ONE-MINUTE window against a 15-MINUTE timer and
expired positions would sit OPEN forever — the same freeze that stranded the NIFTY bull-put in July
(653d3c9). So the gate is `is_market_open() OR _stock_settlement_due()`, where the new
`EngineRunner._stock_settlement_due()` scans the three stock-credit books for any OPEN position whose
expiry <= today. Verified: runs now (market open), idle after 15:30 when nothing is expiring,
always allowed on an expiry day.

*(b) A STALE QUOTE CAN NO LONGER BOOK A TRADE.* `_quote` falls back to last-traded price when a leg
has no bid/ask, and on an illiquid strike that print can be hours old — booking a WIN/LOSS off it is
the same defect class that once fabricated 0DTE wins. ENTRY already required a two-sided market (the
MPHASIS fix); RESOLVE did not. Both resolvers (`stock_credit_v2.py` which v0 also runs, and
`stock_credit.py` for v1) now compute `bookable` = BOTH legs returned bid>0 AND ask>0 THIS cycle, and
skip the TP/stop decision unless it is True. **MTM still updates on a fallback quote — only the
DECISION is gated.** Verified live: both open v1 spreads quote two-sided, and MTM marked correctly
after the restart (TCS 29.33, BAJAJ-AUTO 139.03).

*(c) STILL OPEN, accepted:* mid-price is optimistic (closing means crossing the spread) and the
15-min poll books at the next poll rather than at the touch. Both are inherent to polling a mid;
neither is a correctness bug.

**STATE 2026-08-03 ~11:50 — 3 COMMITS STILL UNPUSHED, VIEWER HAD DIED.**
Unpushed (local only): `f079b61` Telegram fixes · `1351c03` handoff/mechanism · `6392c2b` market-hours
gate + stale-quote booking guard. Push needs the user's own terminal for the PAT prompt (keychain
returns nothing for github.com in this session; no gh CLI, no token env, no SSH key).

**VIEWER DIED AND DID NOT COME BACK — restarted manually (pid 6590).** app.log shows only Upstox
connection failures at 11:46 (Max retries exceeded) and NO traceback; memory was fine at the time
(~350 MB free, swap 873 MB of 2 GB), so this was NOT the jetsam kill that took the backtests earlier
— most likely a network blip. **ROOT ISSUE: the viewer's launchd job has NO KeepAlive** — it only
auto-launches 9:00 on weekdays, so unlike the engine (KeepAlive=true) it never self-heals and a
dashboard can sit stale until someone notices. Trading is unaffected (the engine is decoupled and
kept marking throughout). OFFERED to add KeepAlive to `deploy/` + setup.sh plist for the viewer;
awaiting the user.

**TICKER % BUG FIXED 2026-08-04 (user: "sensex should be 0.18%-0.2% but showing so much more").**
The top ticker on PM DECISIONS showed **SENSEX +0.88%** while NIFTY was −0.64% — impossible, they are
~95% correlated. ROOT CAUSE: `_index_live_or_close` derived the % from the DAILY HISTORY feed ("the
last close not dated today"). **BSE publishes SENSEX's daily bar later than NSE publishes NIFTY's**,
so at snapshot time SENSEX's series still ended at FRIDAY 31-Jul (78,094.64) and the change was
measured against a session-stale reference: 78,780.08 − 78,094.64 = +685.44 = +0.88%. NIFTY's NSE bar
had already landed, so NIFTY was correct — which is why only SENSEX looked wrong.
FIX: use the exchange's OWN day change. The raw Upstox quote carries `net_change` (the wrapper
`fetch_upstox_quote` was discarding it — it only returns ask/bid/ltp/oi/volume). Added
`_batch_index_net_change()` (one batched /v2/market-quote/quotes call for all four indices) and
`_index_live_or_close(..., net_change=)`, which when present computes prev = price − net_change and
returns that change/pct directly. net_change cannot be a session stale. Falls back to the old derived
path if the field is missing. Verified: SENSEX ref is now **78,639.03 = Monday's close** (was Friday's)
and reads +0.08…+0.19% through the session instead of +0.88%. Applies to ALL FOUR tickers, not just
SENSEX — the same staleness could have hit any of them.

**STILL OPEN (user's, ~5 min):** price a two-sided stock condor in Upstox and see whether blocked
margin is ~ONE width or ~TWO. Only matters if the condor is ever revisited. Asked 3x, unanswered.

**STILL NOT COVERED for the band** (conditional filters, not configs): IV/VIX regime at entry (most
promising — the failure was regime-driven), breakout size, which Donchian window fired, per-name IV
rank/sector, calendar time-exit. OOS covered 38/113 names. WARNING given to user: 432 cells already
searched and the winner died OOS; more mining on the same 782 IS signals risks another mirage —
pre-register ONE hypothesis and test it OOS-first.

**Scripts (all committed):** `ndte/bhav_stk_parquet.py` (one-time compaction of the 1,500-file
bhavcopy CSV cache -> /tmp/bhav_stk.pkl; the old per-row pd.to_datetime loader cost ~75 min PER RUN,
this is 45 s once — reuse it in future studies), `ndte/stkfade_lowcw_geometry.py` (432-cell IS),
`_controls.py` (faithfulness: harness reproduces the deployed book 82.9%/+24.6%w vs known
84.1%/+25.7%w), `_matched.py`, `_dte.py`, `_adaptive.py`, `_robust.py`, `_oos2.py` (OOS, resumable),
`lowcw_live_liquidity.py`.

**GOTCHAS hit this session (read before re-running):**
- `/tmp/bhav_cache_stk` (1.3 GB of raw CSVs) was DELETED to free disk — machine had only 5.3 GiB
  free and swap was 8.75/10 GB. Re-download via `ndte/bhav_dl_stk.py` if needed; `/tmp/bhav_stk.pkl`
  (486 MB, universe-filtered) is what every lowcw script actually reads.
- **Machine is memory-starved.** A 12-worker OOS run was silently killed by macOS jetsam (no
  traceback, process just gone). Use 6 workers. `_oos2.py` now checkpoints per stock to
  `/tmp/lowcw_oos2_bysym.json` and resumes, and writes the leg cache ATOMICALLY (an earlier kill
  mid-`pickle.dump` truncated it -> EOFError on next load).
- The expired-instruments endpoint throttles to ~7 s/call; full 113-name OOS = ~30k legs = ~10 h.
  Hence the 38-name subset. ~80% of calls go on pricing the reference geometry just to bucket a
  signal — short leg is fetched first now so sub-Rs50 signals bail before paying for the long leg.
- pyarrow is NOT installed -> use `to_pickle`, not `to_parquet`.
- **Another Claude session (fable-5) is committing to this same repo concurrently** (e.g. 73e725c
  "handoff: search loops stopped"). Check `git log` before pushing; a push carries its commits too.

**NOT DONE / awaiting user:** (a) the PM DECISIONS tier-2 scope choice above, (b) push to both
remotes — 6 local commits: bc3801d, 6872345, 3da95c5, handoff, 8f466f6 (+ this one), (c) STUDIES-tab
card recording the rejection (repo convention documents rejections, cf. BANKNIFTY_0DTE_REJECTION.md).
_Updated: 2026-07-31 by Claude Code_

## DONE (2026-07-30 night) — BOOK column · swing-MTM fix · UI renames · Saavi branding (653d3c9→1bb1f6d)
Four commits, all pushed both remotes, viewer relaunched stable after each (final PID 58816), engine
restarted once (57214):
1. **BOOK column (653d3c9)** — SWING TRADE LOG's two stock-credit tables now carry an explicit BOOK
   column ("v2"/"v1") after ENTERED on both leg rows: SWING_TAB_BOOK_COLS + book_label param on
   _fill_swing_table (engine/ui_terminal.py). Other tables untouched (8 cols).
2. **Stale-MTM root cause + fix (653d3c9)** — SWING_CREDIT_ENABLED=False (07-24) sat BEFORE
   resolve_swing_positions in both engine_runner._swing and the resolver itself, so the OPEN NIFTY
   2026-08-04 BULL_PUT (opened 07-24 15:10, just before the disable) froze at Jul 24 16:35 marks and
   would never have settled. Flag now gates NEW entries only; resolve runs while OPEN positions exist
   (double-gated: scan_swing_signals keeps its own flag check). Verified: book re-marked 19:43,
   short PE 155.65→7.50, position near max profit (+48.68 of 51.3 credit) — engine TP/expiry books it.
3. **Per-figure P&L colours (30424b1)** — stats lines coloured the WHOLE line by booked's sign, so v1's
   negative open MTM (−₹1,031) rendered green. Now booked and MTM each get their own green/red span
   (MTM math itself verified correct: credit − current cost per trade).
4. **Renames + branding (73dfb0b, 1bb1f6d)** — TRADE LOG tab → "INTRADAY TRADE LOG"; "0DTE" stripped
   from ALL UI chrome (tab, titles, section labels → "EXPIRY-DAY"/"INTRADAY", stats, status strip) but
   KEPT in STUDIES/README research prose (quotes study filenames). App renamed SAAVI INSTITUTIONAL
   TRADER (window title, Dock name, header) with a circular gold-ring logo of the user's daughter at
   data/saavi_logo.png — data/ is GITIGNORED on purpose: the child's photo must NEVER be pushed to the
   public repo. All logo uses fall back cleanly if the file is absent. Regenerate: crop (250,520,510,780)
   of ~/Downloads/SAAVI.jpg, gold gradient ring (script was in session scratchpad).

## DONE (2026-07-30 evening) — SENSEX ticker + README LIVE/REJECTED restructure (4c7121b)
SENSEX in top ticker strip (BSE_INDEX|SENSEX in _batch_index_ltp, ^BSESN Yahoo fallback, snapshot key
"sensex", UI sensex_lbl; verified live 77,772.70). README: plain-English narrative + 2 sprawling tables
replaced by two crisp tables — LIVE (win IS/OOS+dates, signals/mo, ₹/mo) & REJECTED/OFF (status+why).
Also this session: bold win rates in TG signals, profit-calc table (live month 21tr/+₹45,488 after user
removed index-swing row), stale totals fixed (30,340/75,848). All pushed both remotes; engine+viewer alive.

## DONE (2026-07-30) — Telegram signal format v2 LIVE (commit 37bccb3, both remotes)
User-designed format deployed in _tg(): "🟢 EXECUTE NOW — MULTIDAY/INTRADAY SIGNAL" · no 0DTE jargon
("Expires TODAY at 3:30 PM") · target ₹ + max P/L · "📚 Why this signal — Tejas Jadhav, CFA…" with effort
funnel (v2 32,852→609; v1 25,978→997) + SEPARATE IS/OOS lines with full dates ({TODAY} auto-fills via
datetime.now(IST)) · SENSEX says in-sample CANNOT be captured · SEBI disclaimer every signal · removed
"Execute with your broker" + "7 of 8 years". BUGFIX: 0DTE BANKNIFTY inherited NIFTY stats ("NIFTY" substring)
— excluded. Dead _TG_WIN/_TG_WIN_SYM removed. STUDIES card documents format. 2 samples sent to Telegram
(🧪-prefixed). Engine+viewer restarted, alive. NOTE: shell env can carry stale TELEGRAM_BOT_TOKEN — use
load_dotenv(.env, override=True) for manual sends; launchd engine unaffected.

## DONE (2026-07-30) — v1 exit TP-40/no-stop DEPLOYED (goal: raise win rate, zero signal loss)
Sweep (V1_WINRATE_SWEEP.md) + OOS path-replay (242 real-premium trades, stkfade_v1_oos_exits.py): TP-40/no-stop
= 85.0% IS / 86.0% OOS win, net +18.2/+17.6%w vs deployed TP-75/stop-2× 64.0/73.6% & +10.3/+15.1%w — SAME
trades, zero signal change. User approved ("then deploy tp-40"). Deployed: config TP 0.75→0.40, STOP_MULT
2.0→99.0 (none; wing caps risk). Labels updated (PM header, STUDIES card, TARGET_STOP_TABLE, _TG_WIN "85% IS /
86% OOS"). v1 is NO LONGER the TP-75 control. NOTE: the 3 existing open v1 positions keep their STORED 2×
stop_cost (baked at entry) but get the new TP-40 immediately (favorable). Commit 8d2aa66, both remotes.
Engine+viewer restarted, alive. Loop goal met → wakeup stopped.

## (prior) ACTIVE (2026-07-30) — /loop GOAL: raise v1 WIN RATE without cutting signals (all technical params)
User goal (dynamic /loop + ScheduleWakeup armed): better v1's win rate (64% IS / 73% OOS), signal count must
NOT drop. Levers = n-preserving only: TP fraction {0.40,0.50,0.60,0.75dep,0.90,hold} × stop {1.5,2,2.5,3,none}
× geometry {(1,3)dep,(2,4),(2,3),(1,4)} — entry gates FIXED. IS SWEEP DONE (log /tmp/v1sweep.log, json in scratchpad
v1sweep_results.json; both faithfulness checks reproduced: v2 85.3%, v1 755/64.0%/+10.3%w). KEY IS RESULT —
only s1w3 keeps n=755 (s2w4→286, s2w3→390, s1w4→571 = signal cuts, violate constraint). n-preserving winners:
TP.40/no-stop 85.0%/+18.2%w · TP.50/no-stop 82.4%/+18.8%w · TP.40/stop3 82.0%/+15.9%w vs deployed 64.0%/+10.3%w
— all 0 neg yrs. Same mechanism as v2 (early booking + stop was realizing recoverable losses; no-stop still
defined-risk). Time-exit overlay marginal (~73-74%). NOW RUNNING: OOS confirmation — NEW script
studies/ndte/stkfade_v1_oos_exits.py (pid 88624, log /tmp/v1oos_exits.log, json /tmp/v1_oos_exits.json):
fetches each v1-geometry trade's daily path ONCE from Upstox (Oct'24→date), evaluates all 4 exits on the SAME
trades. Watcher bv80ungyf fires on exit. PACE WARNING (10:05 IST): 10/113 stocks in ~29min — market-hours Upstox
throttling (engine shares the API) → full pass ~4-5h; interim read possible at ~50-stock checkpoint
(/tmp/v1_oos_exits.json refreshes every 10 stocks — evaluate the 4 exits on partial recs with the walk() in
the script). User told; default = let it grind, interim at ~50. WHEN DONE: if OOS confirms (win%↑ AND net%w ≥
deployed OOS +17.9%w), write studies/V1_WINRATE_SWEEP.md, show user, get approval BEFORE changing
STOCK_CREDIT_TAKE_PROFIT/STOP_MULT in config (v1 is the CONTROL book — flag that changing it loses the
TP-75 control benchmark), commit+push BOTH remotes. WHEN DONE: relay table + honest verdict (TP-earlier
win% gains partly cosmetic — judge on net%w + per-year), get approval BEFORE deploying any param change; commit
+ push BOTH remotes. NOTE: model switched to Fable 5 this session by user (/model claude-fable-5).
_Updated: 2026-07-29 by Claude Code_

## ACTIVE (2026-07-29) — GOAL /loop: MORE swing trades @85% + put/call + timing + stop-loss + size ₹1L/mo on ₹5L
User goal (Stop hook active): expand the swing book — more trades while holding ~85% win — analyse put-vs-call,
entry-timing, stop-loss limits; size to ~₹1 lakh/month for a retail trader with **₹5L margin** (updated from ₹2L).
STATUS: GOAL #1 COMPLETE. Backtest done → studies/SWING_PUTCALL_STOP_ANALYSIS.md (committed). VERDICT:
 (1) PUT vs CALL = NO stable edge. IS puts looked better (92.5%win/+24.9%w vs calls 80.8%/+25.0%w) but OOS the
     put NET COLLAPSED (+9.1%w) while calls held (+23.7%w) — the reversal CLAUDE.md warned of. Trade BOTH sides,
     no tilt. (2) STOP: looser is better-or-equal in BOTH windows, never worse (IS no-stop +30.4%w vs 3.0x +25%w;
     OOS no-stop +18.4%w vs 3.0x +18.0%w), worst loss bounded ~−62 to −65%w by defined risk. Widen 3.0x→3.5x/no-stop
     = marginal + and harmless, but SMALL & OOS-thin. My earlier prelim "-199%w on 3x stop" was a quick-sim artifact
     (intraday path-walk); authoritative close-sim caps ~−65%w. (3) TIMING: no DOW edge (inconsistent IS vs OOS);
     entering at breakout CLOSE (deployed) is optimal — waiting one session drops ~40% of trades for no net gain.
 NET: none of these ADD trades — they're quality/risk tweaks. Only a deploy-worthy OPTIONAL: widen stop 3.0x→3.5x.
 NOT deployed — needs user approval. "More trades @85%" answer = universe expansion (Goal #2, next).
DONE (on-disk, delivered to user):
 - Frequency ceiling CONFIRMED: v2 UNION already = the 85% swing book (~5.8/mo, 84–87% OOS, +26–29%w). "More trades
   at 85%" is CAPPED by the c/w≥0.40 gate (the edge). Below gate: 0.35–0.40→82%win but only +9%w; 0.30–0.35→76%/+1%w
   (breakeven). Win% stays high (mirage, TP-50 books early); MONEY collapses. Sources: UNION_DONCHIAN_FREQUENCY.md,
   CW_BUCKET_ANALYSIS.md.
 - ₹5L sizing (from LIVE forward-test economics): margin ~₹6–13k/trade (defined risk), blended net ~₹2,700/trade,
   ~20–22 trades/mo @1 lot. ₹1L/mo needs ~3 lots at favorable/model rate (~₹300k peak margin, fits ₹5L) but ~6 lots
   at the sober 50%-haircut rate (~₹500k, fully deployed). Verdict: ₹1L/mo = good-regime CEILING; durable base ~₹50–70k/mo
   at 3–4 lots. UNION losses CLUSTER on same down-days (−55% avg loss) → keep dry powder.
IN FLIGHT: a detached backtest `studies/ndte/stkfade_putcall_stop.py` (pid was 91107) is RUNNING on the freshly
 re-downloaded /tmp/bhav_cache_stk (1500 files). It computes, IS(2019→Sep24)+OOS(Oct24→now): (1) BEAR-CALL vs
 BULL-PUT win%/net split; (2) stop-loss sweep {2.0/2.5/3.0(deployed)/3.5/hold}; (3) day-of-week + close-vs-next-open
 timing. Output PENDING: studies/SWING_PUTCALL_STOP_ANALYSIS.md. The spawning subagent (id a38bf824d62b60730) ALREADY
 STOPPED before results landed — resume it via SendMessage OR just wait for the script + read the .md.
NEXT: read SWING_PUTCALL_STOP_ANALYSIS.md when done → relay put/call + stop + timing numbers to user → if any finding
 is deploy-worthy, show numbers & get user approval BEFORE touching engine (never deploy on a hunch). Then commit
 studies + push BOTH remotes (origin + private). Goal Stop hook auto-clears when condition met.
RE-RUN NOTE: the agent-launched detached run died silently mid-collection (no md, no /tmp jsons). Relaunched by me
 (pid tracked, log /tmp/pcs_run.log). Script studies/ndte/stkfade_putcall_stop.py writes /tmp/stkfade_pcs_is.json +
 _oos.json then studies/SWING_PUTCALL_STOP_ANALYSIS.md. Cache load of 1500 full FO-bhavcopy CSVs is SLOW (~mins).
GOTCHA: NSE bhav cache in /tmp is wiped on reboot — re-download via studies/ndte/bhav_dl_stk.py. Don't push .env.

## QUEUED GOAL #2 (2026-07-29, Stop hook) — EXPAND the F&O universe without diluting signal count
User: "look at all fno options band and work on enhancing and increasing the universe without compromising on the
number of signals — do this AFTER you finish the first test." Interpretation: current universe = ~100 hand-picked
names (config.UNIVERSE, chosen by intraday movement; beat a mcap-top-100 67% vs 61%). NSE F&O has ~180–220 stock
underlyings. Take the F&O names NOT already in UNIVERSE, run v2 UNION fade + c/w≥0.40 gate on them, keep those that
ADD signals at ≥~85% quality (the gate self-selects rich-IV higher-priced names — see FUNDAMENTAL_TECHNICAL_FINDING).
"Without compromising signals" = additive only; must not lower the 85% win / +26%w. NEEDS bhav option data for the
EXTRA names too (current /tmp/bhav_cache_stk only has the ~100 universe) → download via bhav_dl_stk.py variant with
the expanded symbol list. Deliverable: studies/UNIVERSE_EXPANSION.md + proposed additions; show user numbers &
get approval BEFORE editing config.UNIVERSE. Do ONLY after Goal #1's backtest is reported.
STATUS 2026-07-29: DONE (subagent). Deliverable studies/UNIVERSE_EXPANSION.md (149 lines) + scripts
 studies/ndte/expand_phase0_enum.py / expand_phase1_screen.py / expand_phase2_dl.py / expand_split_bysym.py /
 expand_phase2_bt.py + /tmp/expand_phase2.json. VERIFIED against raw JSON (not prose): baseline reproduced
 370tr/84.1%/+25.7%w/+ve6/6yr (matches known target → sim faithful). RESULT: universe CAN expand additively.
 Screened 180 F&O underlyings → 88 candidates not in UNIVERSE → 37 clear c/w≥0.40 gate, ALL net-+ve IS. Options:
  • STRICT (2: MRF,DEEPAKNTR, n≥15): 5.78→6.39/mo, 84.1→84.4%win, +25.7→+28.0%w
  • TIER-5 (13: COLPAL,ASTRAL,INDIAMART,ALKEM,DALBHARAT,UBL,NAVINFLUOR,MRF,ATUL,CUMMINSIND,DEEPAKNTR,HAL,BOSCHLTD)
    recommended: 5.78→7.56/mo (+31%), 84.1→85.5%win, +25.7→+27.6%w
  • ALL-GATED (37): 5.78→8.89/mo (+54%), 84.1→84.9%win, +25.7→+26.4%w
 ALL keep win% & net%w at/above baseline. CAVEAT: IS-only (no per-name OOS — Upstox premium hist ~1mo);
 mid-cap live fills erode net more than shown; small per-name n = noise (trust pooled). config NOT edited.
 DEPLOYED 2026-07-29 (user approved "yes go for Tier-5"): config.UNIVERSE 100->113 (+13 Tier-5 names), assert
 ->113, engine restarted (all 13 resolve live spots). Commit b042a13, pushed BOTH remotes. ALSO in same commit:
  - Telegram _tg(): every signal now shows 🎯 Target + 🛑 Stop the win% is conditioned on, grouped w/ max
    profit/loss; win% stated once "at the target/stop below" (per user: winrate subject to target+stop).
    Map _TG_TGT_STOP + _tgt_stop() in engine_runner.py.
  - UI STUDIES tab: universe-expansion card + put/call/stop/timing card + target/stop card; v2 sig/mo 5.8->7.6*.
  - UI PM DECISIONS: TARGET+STOP on v2/v1/monthly headers. studies/TARGET_STOP_TABLE.md (new).
 BUG CHECK done (user asked): 13 names resolve live, no stale size-assert, _tg label coverage verified, engine+
 viewer healthy @113. Minor cosmetic: '94-stock' descriptive comments in agent.py/orb_vwap_live.py now stale
 (pre-existing, left per surgical rule). BOTH GOAL STOP HOOKS should now be satisfied.
NOTE: origin push of Goal-#1 commit eedcc00 TIMED OUT (github unreachable ~2min) — PRIVATE remote has it; retry
 origin when network recovers (`git push origin main`). Upstox+github both flaky this session.

## DONE (2026-07-30) — v1 TP-75 IN-SAMPLE measured + backtest-lookback assessment
v1 TP-75 IS = **64.0% win / +10.3%w / 755 tr (2019→Sep'24), +ve every yr (2023 weak 54.8%)**. Harness validated
(v2 config reproduced 85.3% DC10 baseline). OOS(73%)>IS(64%) → deployed 73% was optimistic end, not overfit;
honest = 64% IS / 73% OOS (~67% pooled). Hold-to-expiry base 55.1% (confirms the "~54%"). Script
studies/ndte/stkfade_v1_is.py, doc studies/STOCK_V1_IS_MEASURED.md. UI v1 header + _TG_WIN corrected from
"NOT MEASURED" → "64% IS / 73% OOS". Lookback: studies/BACKTEST_LOOKBACK_ASSESSMENT.md (Fable) — 7yr is
sufficient-as-available, can't go usefully further back for stock option premiums, defined-risk caps the tail,
extend the FORWARD test not the lookback. Committed 94bb8e6, pushed BOTH remotes. Engine+viewer restarted, alive.

## (prior) ACTIVE (2026-07-29) — measuring v1 TP-75 IN-SAMPLE (closing a label gap)
User caught: UI says v1 in-sample "NOT MEASURED" but v2 IS was measured — why? Honest answer: no data/method
reason, just a gap (same bhavcopy, same daily-close TP detection; only v1's hold-to-expiry base 54% IS + TP-75
OOS 73% were ever run). Subagent a646796a6ce3cbd25 FAILED — hit the WEEKLY usage limit (resets 4:30am Asia/Calcutta) before writing
anything. NOT re-run this session (shared account limit). QUEUED for a fresh session after reset: measure v1's
DEPLOYED config (D10, short-1-OTM, width-3, TP-75=book@0.25×credit cost, stop-2×, c/w≥0.40, prem≥50) on
/tmp/bhav_cache_stk (2019→Sep'24) — reuse studies/ndte/stkfade_union.py loader + studies/stkfade_oos_v1.py
exit logic; cross-check v2 config reproduces ~84% IS first. Deliverable studies/STOCK_V1_IS_MEASURED.md. WHEN DONE: update the v1 PM DECISIONS header in ui_terminal.py (currently
"in-sample NOT MEASURED for the TP-75 exit... 54%") to the real IS win%/net; update _TG_WIN if needed; commit
+ push BOTH remotes. Latest pushed commit: f570c3a. Recent telegram/UI edits all live (universe 113, target/stop
honest, Multiday/Intraday labels, WIN/Loss summary, watchlist win-prob).

## ACTIVE (2026-07-24) — HOURLY first-touch c/w>=0.40 entry vs CLOSE entry (stock v2 UNION + v1) — VALIDATION ONLY
User Q: the live engine evaluates c/w ONCE at the 15:10 close; if instead we entered the FIRST intraday
hour c/w touches >=0.40 we'd catch MORE signals (user's example: OFSS touched 0.43 at 14:45, back <0.40
by 15:10, so close skipped it). Does hourly add EDGE or NOISE? Hypothesis (flip side): hourly fills on
transient IV spikes that revert = more signals, lower quality. REPORT-ONLY, do NOT touch the live engine.
FILES: studies/ndte/hvc_backtest.py (fetch+sim, resumable/cached/checkpointed → /tmp/hvc/hvc_results.json),
studies/ndte/hvc_report.py (tables), hvc_probe.py (breakout counter). Deliverables PENDING:
studies/HOURLY_VS_CLOSE_ENTRY.md + a UI STUDIES res() card + commit/push BOTH remotes.
METHOD: same breakout universe (v2 UNION D5/10/15/20; v1 D10) + same strikes (off breakout-day close ATM)
+ same gate (c/w>=0.40 & prem>=50) + same daily-close exit walk (TP/stop/intrinsic). Only ENTRY differs:
CLOSE uses 15:10 daily-close premiums; HOURLY steps hourly marks [09:15,10:00..15:00] on the breakout-day
1-min expired-option candles, enters at first mark c/w>=0.40, else falls back to close (HOURLY ⊇ CLOSE).
Flip-side metric = of HOURLY intraday entries, fraction that are "reverting spikes" (c/w back <0.40 by
close = the extra signals CLOSE skips) and their win%/net vs the held ones.
**CRITICAL BUG FOUND + FIXED (do NOT reintroduce):** bar_at() called _mins() on a bare "HH:MM" mark but
_mins sliced ts[11:13] (full-ISO only) → ValueError → swallowed by do_stock try/except → the WHOLE record
dropped. It only fired when the short leg HAD intraday data (`if bs:`), so EVERY breakout whose short
trades intraday was silently dropped, leaving only illiquid-short survivors (74 v2/60 v1) with 0 intraday
— which falsely looked like "hourly==close, no data". FIX: split _mins_ts (ISO) vs _mins_hm (HH:MM).
After fix, record counts jumped (v1 78 by stock 21 alone). MUST re-run fresh (run2). LESSON: the buggy
run REPRODUCED documented close numbers (v2 86.5%/+35.2%w vs doc 200/87.5%/+31.5%w; v1 71.7%/+16.9%w vs
73.4%/+17.9%w) so close-sim is validated — the bug only hit the HOURLY branch.
**DATA FINDING (real, not the bug):** liquid low-priced stocks (RELIANCE/ICICIBANK ~1420) have FULL
intraday data (375 bars) at ATM/2-OTM/6-OTM but c/w hovers 0.22-0.29 → rarely hit the 0.40 gate. The
gate structurally selects rich-IV wide-strike options on HIGHER-priced stocks (OFSS/COFORGE/BAJFINANCE)
whose fade shorts produce FEW/NO intraday TRADE candles (user saw OFSS's path via LIVE QUOTES; historical
expired-instrument candles record TRADES only). So hourly is partly unmeasurable/unexecutable on exactly
the gated names — a genuine finding to report alongside whatever the re-run yields.
FETCH BOUND (documented, conservative): intraday fetched only when close c/w>=0.30 & prem>=40 (band around
the gate). Deeper reverters excluded → biases TOWARD hourly (against the noise hypothesis). ~26k daily +
~3k intraday calls; API throttles HARD (a mid-run DNS blip dropped some too — leg fetchers now 6/5 retries
w/ backoff). Caches in /tmp/hvc/{daily,intra,under}; results /tmp/hvc/hvc_results.json (per-breakout recs).
RESULT (run2, post-fix, DONE): **HOURLY = NOISE, keep CLOSE.** v2 UNION CLOSE 183·87.4%·+32.8%w vs HOURLY
253·84.6%·+25.7%w; extra 70 signals (3.3/mo) only +4.5%w/74% (a 7th of core). v1 CLOSE 331·72.2%·+16.9%w
vs HOURLY 500·69.0%·+11.2%w; extra 169 signals LOSE −2.5%w/61%. FLIP-SIDE confirmed: 63%/47% of intraday
entries are reverting spikes; reverting vs held = v2 +4.5 vs +33.5%w, v1 −2.3 vs +4.7%w. Total edge/mo flat
(v1 identical) → more trades+lower win+more variance for no gain. CLOSE reproduced docs (v2 87.4≡87.5,
v1 72.2≡73.4). Exec caveat: both legs traded intraday on only 30%/62% of trades (gate picks rich-IV
wide-strike names that don't print sub-day). FOLLOW-UP Q "does hourly make sense for v2 (its extra signals
were +4.5%w, not negative)?": NO — the v2 extra-70 net is 2026-ONLY: 2024 −1.8%w(n3), 2025 −5.5%w(n30),
2026 +11.6%w(n37); the +4.5%w aggregate is a single favorable year, negative in the two prior. Plus you
can't cherry-pick the good (held +33.5%w) half ex-ante — held-vs-reverting is defined by the close you're
front-running. So keep CLOSE for BOTH books. (The v2 extra signals ARE executable — 70/70 both legs intraday
— so the barrier is durability, not liquidity, unlike the deep gated trades.) v2-per-year + the follow-up
folded into studies/HOURLY_VS_CLOSE_ENTRY.md + the UI HOURLY card.

## DONE (2026-07-24) — STUDIES TAB RESTRUCTURED (user request) + v2 follow-up added
User: "fix the ui studies tab. it should not have audit. it should have strategies live first table and
then pnl and then each strategy which is live and backtesting involved." REMOVED the top AUDIT block
(_studies_html: the "⚠ RECOMMENDATION — NO strategy change" 18px header + the ①/①b/②/③ actions table +
the 2 audit res() blocks "SHOULD NIFTY BE REMOVED"/"WHY ① MATTERED", old lines ~812-857). Tab now opens
directly on THE LIVE STRATEGIES — SUMMARY table → plain-English → CONSOLIDATED MONTHLY P&L → per-strategy
research (each with its backtest) — which was already the order from line 859 on; only the audit preamble
was in the way. Also appended the v2 "does hourly make sense? NO, +4.5%w is 2026-only" nuance to the
HOURLY res() card. Verified: ast OK, viewer relaunched, PID 5138 stable (no crash). Commit + push both. DELIVERABLES DONE: studies/HOURLY_VS_CLOSE_ENTRY.md, UI res()
card after the DONCHIAN card (viewer relaunched, PID stable), committed + pushed origin & private. Engine
NOT touched. Scripts: studies/ndte/hvc_{probe,backtest,report}.py; data cache /tmp/hvc (gitignored, not committed).

## DONE (2026-07-19 cont.) — PRE-OPEN SIGNALS all REJECTED (studies/ZERO_DTE_PREOPEN_SIGNALS.md, e09f294)
Broader "what's knowable before 9:15" test. INSTRUMENT = the overnight GAP (market's own weighted
summary of every overnight input — no news API needed; entry is 09:16 AFTER the 09:15 open prints so
there is NO lookahead). Swept gap / rv5 / prior-day-move thresholds on 448 trades.
RESULT: nothing survives. Pooled sweeps show some extreme thresholds "helping" but EVERY candidate
FAILS THE ERA SPLIT: skip rv5>=1.10 = +₹47.6k Era A / −₹18.0k Era B; same reversal for rv5>=1.30,
gap-up>=0.75%, and the combined rule. The signed-gap asymmetry that looked structural (short-call book
should fear UP-gaps) INVERTS: down-gaps worst bucket in Era A (−12.5%m), best in Era B (+19.7%m).
Regime read, not an edge. → do NOT extend NIFTY's rv5<0.9 filter to SENSEX/BANKNIFTY.
FRAMEWORK (from Fable 5 design pass, folded into the study):
  * RELEASE-WINDOW TAXONOMY — what matters is where a release lands vs the 09:16→15:30 hold window.
    INSIDE (RBI 10:00, Budget 11:00, election counting) = the only real risk class. JUST BEFORE
    (FOMC 23:30, US close, overnight geopolitics, post-market results) = we sell the exhale = GOOD.
    AFTER (India CPI 17:30, US CPI 18:00+) = IRRELEVANT to today's position — testing them same-day is
    a CATEGORY ERROR, not an empirical question. This PREDICTS the earlier FOMC finding.
  * RETROSPECTIVE-EVENT-LIST TRAP — a "major geopolitical shocks" list compiled today is selected FOR
    having moved the market (survivorship-of-the-scary); inadmissible as a rule. The gap is the
    admissible instrument for the same question. DO NOT build a hand-list avoid-rule.
  * Other Fable cautions to honour: multiple testing (~90 tests → 4-5 false positives expected);
    one-day dominance (report results ex-worst-day); test filters CONDITIONAL on the c/w gate;
    prefer HALF-SIZING over full skip if any effect is ever found.

## DONE (2026-07-19) — STOCK AUDIT PASSED + NIFTY KEPT + studies/README.md index added
STOCK AUDIT (ndte22): BOTH books PASS decisively. v2 t=+13.78 CI[+60.6,+80.7] 8/8 yrs, drop 10 best
-> 83% survives. v1 t=+7.09 CI[+19.8,+34.9] 3/3 yrs, 69% survives. Worst trade = 8 and 12 TRADES of
profit (BANKNIFTY was 102 MONTHS). The Rs32,000 is NOT fabricated.
BUT MAGNITUDE still optimistic: v2 implies ~97%/mo on deployed capital; 24/569 trades print c/W>0.95
(stale marks). KEEP THE BOOKS, DISTRUST THE NUMBER. Plan-on ~50% vs 80% still recommended, NOT changed.
NIFTY 0DTE: **DO NOT REMOVE** — 2nd-strongest book. n=273/8yrs, +ve 7/8, t=+4.43, CI[+2.62,+6.77]
excludes 0, p=0.0002, drop 5 best -> 87% survives. Small Rs/mo is a SIZE question not a VALIDITY one;
per day of capital it is +4.7%/day vs v2 +4.3%/day. Opposite of BANKNIFTY (t=+0.10, p=0.33).
OPEN GAPS: v1 in-sample era (718 trades) still has NO per-trade file — only its 346-trade OOS era was
audited. v2 capital rests on approximated per-stock lot sizes.
Added studies/README.md — index of all 40 studies + current book state + the 6 house rules.

## (superseded) RECOMMENDATION — validate, do not modify. See studies/NEXT_ACTIONS.md
Asked "any change in strategy?" Honest answer: **the evidence supports NO geometry/gate change.** Every
modification tested this session was rejected on data (events, gap, VIX, earnings, shocks, Donchian
window, rv5-extension). The two things deployed were RISK exclusions, not edges.
**The real finding is a VALIDATION GAP, not a strategy gap:**
  * ₹32,000 of the ₹36,924 monthly model (**87%**) is the two STOCK books, NOT re-measured this session.
  * Every stale number checked this session came in OPTIMISTIC — BANKNIFTY worst: claimed 91%/₹1,500 →
    measured 78.6%/₹141 (**~10× overstated**). NIFTY ₹2,500→₹1,771.
  * v2's own numbers imply ≈97%/month on deployed capital — not credible; corroborates the standing
    "backtest is OPTIMISTIC" warning.
→ #1 PRIORITY: audit stock v2 + v1 the same way the 0DTE books were audited (per-trade file, per-
  calendar-year win, RoC per lot, holding period, adversarial checks). v1 has NO per-trade file at all.
→ #2: plan-on haircut of 80% is TOO GENEROUS on numbers that may themselves be 2-3× high. Suggest
  planning on ~50% of model until the stock audit lands. (UI still SHOWS 80% — flagged, not changed,
  because changing a planning assumption needs user sign-off.)
→ DO NOT: add filters, resize up, or add books. Nothing in the evidence supports it.

## DONE (2026-07-19) — RETURN ON CAPITAL per lot + holding period added to strategy table
User: "add net returns considering loss rate per trade... return on capital which is max loss amount...
mention holding period" then "this is per lot".
CAPITAL = margin blocked = (width − credit) × lot = MAX LOSS. Returns below are ALREADY net of the
loss rate (mean taken across ALL trades incl. losers).
**PER LOT, MEASURED:**
| book | lot | capital/trade | credit | net/trade | RoC | avg WIN | avg LOSS | worst |
| NIFTY 0DTE | 75 | ₹13,577 | ₹1,423 | +₹558 | +4.11% | +₹1,168 | −₹4,038 | −₹12,975 |
| SENSEX 0DTE | 20 | ₹11,519 | ₹1,755 | +₹762 | +6.62% | +₹1,418 | −₹4,549 | −₹8,963 |
| BANKNIFTY (rejected) | 30 | ₹8,308 | ₹1,871 | +₹141 | +1.69% | +₹1,635 | −₹5,336 | −₹14,298 |
Cross-check OK: NIFTY ₹558×3.2/mo=₹1,786≈₹1,771 · SENSEX ₹762×4.1=₹3,124≈₹3,153.
KEY SHAPE: a LOSS costs 3–7× what a WIN pays (NIFTY −₹4,038 vs +₹1,168) — that is WHY ~88% win is
required and why BANKNIFTY at 78.6% could not carry itself.
**BUG CAUGHT — do not repeat:** naive mean-of-ratios gave v2 UNION **+302%/trade**, impossible for a
credit spread (max gain = the credit). Cause: **16 of 569 trades print c/W>0.95** → margin collapses to
~0.5 pts and the ratio explodes; those are stale/illiquid prints (a spread paying 99.5% of width is
free money). FIX: exclude c/W>0.90 AND report CAPITAL-WEIGHTED sum(net)/sum(margin), never mean-of-
ratios. Clean v2 (n=545): **capital-wtd +52.3%**, median +56.6%, win 84.8%, avgW +101.7%, avgL −101.8%.
(v2 ₹ per lot NOT derivable from d5 jsons — no per-stock lot size; UI keeps prior study's ~₹10,500
margin / +₹4,069 expectancy and marks it as carried-forward.)
HOLDING PERIOD — **MEASURED** (ndte21_roc_holding.py; SLOW ~25min, reloads 1,359 bhav files + refetches
underlyings; add flush=True if re-running, prints are buffered):
  0DTE NIFTY/SENSEX : SAME DAY (09:16→15:30, ~6h, ZERO overnight gap risk) — certain
  v2 UNION (369 bhav-era trades): **avg 12.1 cal days · median 9 · p90 27 · max 38**
      TP     279 (75.6%) avg  8.9d median  6d   ← 3 of 4 exits are early TP-50, not expiry
      STOP    23 ( 6.2%) avg 17.9d median 20d
      EXPIRY  67 (18.2%) avg 23.6d median 24d
**DERIVED — RoC PER DAY OF CAPITAL (makes books comparable):** v2 +52.3%/12.1d = **+4.3%/day** ·
NIFTY 0DTE +4.69%/1d = **+4.7%/day** · SENSEX +7.62%/1d = **+7.6%/day**. So per DAY of capital the
0DTE books MATCH OR BEAT v2 — v2 only wins on ₹/month because its capital is continuously deployed
(~5.5 sig/mo × 12.1d ≈ 2.2 concurrent positions) while 0DTE sits IDLE ~90% of the month.
**HONESTY FLAG:** v2's numbers imply ≈97%/month on deployed capital (₹22.4k profit on ~₹23.1k avg
tied up). That is NOT credible for a live strategy and independently corroborates the repo's standing
warning that the v2 backtest is OPTIMISTIC — KEEP LOTS AT 1. Do not present +52%/trade without this.

## DONE (2026-07-21) — BUG SWEEP: 3 parallel audit agents + grep; fixed all live CRITICAL/HIGH
Two settlement bugs + one CRITICAL Telegram bug fixed. Agents audited resolvers, notifications, scan/data.
**FIXED (live):**
1. 0DTE FABRICATION (HIGH) — zero_dte.py + dte_multi.py STILL had `spot = _spot() or entry_spot or 0`
   in settlement (the swing fix hadn't reached them). A settle-time quote failure → intrinsic 0 →
   full credit → FAKE WIN + wrong Telegram; `or 0` on a bear-call ALWAYS fakes a win. FIXED: settle on
   the EXPIRY-DAY DAILY CLOSE first (correct on T+1 too, where live spot is the wrong day), live spot
   only as exp-day fallback, else leave OPEN + retry. Never entry/0. New helper dte_multi._expiry_close.
2. monthly_fut.py (MED) — `today >= exp` fired at 00:00; now `(today>exp) or (today==exp and >=15:25)`
   so it books at the close (MOC), matching its backtest. (Not a notifier book; can't send wrong msg.)
3. **TELEGRAM M&M (CRITICAL)** — "M&M.NS" IS in universe, stored "M&M". The `&` breaks Telegram HTML
   parse_mode → send 400 → BUT `seen.add(pid)` ran BEFORE the send and the return was ignored →
   M&M results/entries silently lost FOREVER, no retry. Same vector = ANY transient send failure.
   FIXED 3 ways: (a) notifications.send_telegram retries as PLAIN TEXT on a 400; (b) html.escape all
   dynamic fields (sym/side/label) in _tg + _outcomes; (c) _outcomes marks seen ONLY after send
   returns True (seeding path still silent). import html added.
**NOTED, NOT FIXED (low / disabled path):** agent.py/signals.py `current_price` never set + fetch_nifty_pct
returns 0.0 on failure (blocks trades) — but 3-Family is DISABLED, latent. options.py tz-naive expiry
(daemon runs IST). fetch_ltp_batch dead code. HTTPAdapter max_retries=0 despite docstring (fail-safe).
credit books (swing/stock) have the same T+1-settles-on-next-day-spot vector but agent judged minor for
multi-day monthly books (they already don't fabricate) — left to limit blast radius.
All verified: ast+import OK, M&M escapes to M&amp;M, engine cycle clean, engine+viewer stable.

## DONE (2026-07-21) — SWING Telegram RELABELLED (user chose relabel over silence)
Telegram now distinguishes multi-day from same-day so an index credit spread entered days ago can't
read as a same-day 0DTE call:
  * `_MULTIDAY_BOOKS` set → every held-to-expiry book (stock v2/v1, swing, monthly) prepends
    "⏳ MULTI-DAY — strikes fixed at entry TODAY, HELD to expiry (this is NOT a same-day 0DTE call)".
  * swing signal label: "SWING CREDIT (NIFTY/FINNIFTY)" → "SWING CREDIT · multi-day (NIFTY/FINNIFTY)".
  * outcome labels: swing → "SWING CREDIT · multi-day"; 0DTE NIFTY/SENSEX → "… (same-day)".
  * result message already leads with entry-date + expiry, so a settle reads unambiguously.
ALSO fixed stale win% labels in _TG_WIN: 0DTE NIFTY "90% (calm-filtered)"→"88.3% (measured)",
SENSEX "89%"→"89.0% (measured)"; REMOVED BANKNIFTY 0DTE entries (book rejected/disabled 07-19).
Verified by rendering the actual swing + 0DTE messages (no send) — tags correct, contrast clean.
Engine cycle clean, engine+viewer restarted stable. User did NOT silence swing — kept broadcasting,
just clearer. (Earlier "VIEWER CRASHED" reads this session were the stability check racing the restart
and catching a transient PID — verified stable on a settled PID both times.)

## (resolved) OPEN THREAD — SWING vs 0DTE Telegram confusion
User read the correction message (SWING NIFTY 24500/24650, expiry 21-Jul) as a same-day 0DTE call and
objected: "our logic is check 9:16 levels then decide on Tuesday for NIFTY." That is the 0DTE book.
The message was the SWING book: entered MON 6-Jul on a Donchian breakout (~15:10 scan), strikes chosen
1-OTM AT ENTRY off 6-Jul close (~24440), held 15 days, expiry TUE 21-Jul. So the levels were NOT a
today-call — they were locked 2 weeks ago. Coincidence worsening it: 21-Jul is BOTH the swing expiry
AND a 0DTE Tuesday, so both books touch NIFTY today.
ROOT UX PROBLEM: two NIFTY books both Telegram "NIFTY bear-call" results; swing broadcasts strikes
decided at entry, which reads like a fresh same-day call. PENDING user decision (asked twice, not yet
answered): (a) relabel swing _tg as "SWING · multi-day · entered <date> · held to expiry" so it can't
be mistaken for 0DTE, and/or (b) SILENCE the swing book on Telegram entirely — it is an unproven paper
fwd-test (54% win, failed OOS) and arguably should not broadcast beside the validated books.
Do NOT change _tg labels or silence swing without the user picking — it is their group.

## DONE (2026-07-21) — FIXED: premature-settlement bug that sent a WRONG Telegram WIN
User got a wrong Telegram at ~00:06 on NIFTY expiry night declaring a WIN before settlement.
ROOT CAUSE: swing_credit.resolve used `expired = today >= exp`, TRUE from 00:00 on expiry day. At
midnight the market is shut so `_spot()` returned None and it fell back to `entry_spot` (the price
from ENTRY, 2 weeks earlier). Against the 24500 short strike that gave intrinsic 0 → full credit →
fake "WIN", which the _outcomes notifier then Telegrammed 15.5h before the 15:30 settlement.
FIX (3 notifier books had the same latent defect — all fixed):
  swing_credit.py (the culprit), stock_credit.py, stock_credit_v2.py:
  `expired = (today > exp) or (today == exp and past_settle)` where past_settle = IST time >= 15:30,
  AND never settle on entry_spot — use live spot, else expiry-day daily CLOSE, else leave OPEN + retry.
  (zero_dte + dte_multi/sensex/bnf ALREADY had the correct past_settle guard — verified.)
STATE REPAIRED: reverted NIFTY-2026-07-06 swing pos to OPEN (backup /tmp/swing_backup.json), removed
it from data/outcome_notified.json so the REAL result notifies after 15:30 today.
CORRECTION TELEGRAM SENT (send_telegram → True): apologised, explained the position is still open,
settles today 15:30. NOTE: send_telegram reads token at import — a bare `python -c` needs
`load_dotenv()` + re-inject n.TELEGRAM_BOT_TOKEN/CHAT_ID, else it returns False silently.
STILL LATENT (not a notifier book, so no wrong-message risk; REGIME-OFF anyway): monthly_fut.py:245
has the same `today >= exp` pattern. Fix it the same way if that book is ever re-enabled.

## DONE (2026-07-19) — UI restructure: STRATEGY TABLE to top w/ per-CALENDAR-YEAR win rates, then P&L
User: "clean the table, win rate IS and OOS and calendar year, structured, keep it top then pnl."
MEASURED per-calendar-year win rates (all from real per-trade data, NOT estimates):
  v2 UNION (D5, merged both eras, n=569): 19:96 · 20:88 · 21:85 · 22:90 · 23:79 · 24:81 · 25:85 · 26:89
    → worst year 79%, positive/8 yrs covered
  NIFTY 0DTE (n=273): 19:85 · 20:85 · 21:76 · 22:87 · 23:94 · 24:91 · 25:94 · 26:94 → worst 76%
  SENSEX 0DTE (n=91):  24:75 · 25:90 · 26:93 → worst 75% (3 yrs only, Era-B book)
  BANKNIFTY (REJECTED, n=84): 19:67 · 20:67 · 21:83 · 22:64 · 23:92 · 24:89 · 25:90 · 26:83
v1 per-year NOT available — studies/stkfade_oos_v1.json is a dict, not per-trade rows. Left as
IS/OOS only and marked as such; DO NOT fabricate a per-year series for it.
Sources: /tmp/d5_10_15_20_{bhav,oct24}.json (v2), studies/ndte/ndte1{3,4}_trades*.json (0DTE).
NOTE /tmp may be purged — the 0DTE ones are in-repo, the v2 ones are NOT (regenerate via
studies/ndte/stkfade_d5_10_15_20_{bhav,oct24}.py if needed).

## DONE (2026-07-19, 1e05f1f) — BANKNIFTY 0DTE **REJECTED & DISABLED** (user decision)
`DTE_MULTI_BANKNIFTY_ENABLED=False` in config; dte_multi.scan_signals skips it. Open positions STILL
RESOLVE (only new entries stop). Fully reversible.
NOT because it loses — MEDIAN trade is +14.1%m. Because edge ≈ zero and tail swamps it (84 monthly
expiries 2019-01→2026-06, 1 lot, net): avg +0.55%m · **t=+0.10** · 95% CI [−9.98%,+11.09%] · bootstrap
p(mean≤0)=0.33 · **ENTIRE profit is 3 trades — drop 3 best → −₹8** · +₹141/mo vs worst day −₹14,298
(≈102 months of profit in one session) · the "91%/₹1,500" it was carried on was NEVER supported.
Both rescues tested & failed: monthly-pinning (ndte19: monthly 76.1% vs weekly 80.4% WITHIN Era A,
z=−0.75) and "recent era proves it" (n=18; EVERY book rose in Era B, NIFTY 86.5%→93.2%).
ADVERSARIAL AUDIT `ndte20_bnf_audit.py` written to FALSIFY the rejection: clean on bad prints, monthly
tagging, lot-size artifact, survivorship. **One real gap: CONTRACTS>=100 floor was applied to the SHORT
leg only, not the long wing — a dead wing would FLATTER the book, so the bias runs AGAINST rejecting
= conservative.** No bug flips the sign.
NOT claiming proven-unprofitable (CI spans 0 → UNPROVEN). At ~12 trades/yr it can never accumulate
evidence fast enough. REVERSAL BAR: ≥30 new monthly expiries with 95% CI excluding zero.
Draft rationale: studies/BANKNIFTY_0DTE_REJECTION.md.

## ACTIVE (2026-07-19) — STALE UI NUMBERS FOUND + layman explainer requested
User asked to explain the 0DTE strategy in plain English and CORRECT STALE VALUES / update monthly
profit calcs. Measured from the 448-expiry dataset (1 lot, net of costs, months = distinct YYYY-MM):
| book | full history | recent era (Oct'24→date) | UI CLAIMED |
| NIFTY 0DTE | 88.3% win · ₹1,771/mo (n=273, 86mo) | 93.2% · ₹2,290/mo | 87% · ₹2,500 |
| SENSEX 0DTE | (Era-B only) 89.0% · ₹3,153/mo (n=91) | same | 89% · ₹3,200 ✓accurate |
| BANKNIFTY 0DTE | **78.6% win · ₹141/mo** (n=84, 84mo) | 88.9% · ₹696/mo | **91% · ₹1,500 ✗STALE** |
BANKNIFTY is the big one: claimed 91%/₹1,500 vs measured 78.6%/₹141 full-history (even the generous
recent-era read is ₹696 = under half the claim). Era A alone was −₹711 total (−₹11/mo). CAVEAT that
must ride with it: weekly→monthly expiry break confounds the era comparison, so this is "the claim is
unsupported", NOT "the book is proven bad".
DEPLOYED c/W>=0.04 FLOOR IS ~NEUTRAL on recent data (SENSEX +₹77/mo, BANKNIFTY unchanged — no sub-0.04
trades in Era B). That is EXPECTED and fine: Fable deployed it for TAIL protection, not profit. Do not
re-sell it as a profit booster.
DO NOT TOUCH the stock-book rows (v2 UNION ₹20k, v1 ₹12k) — not re-measured this session, no new
evidence; only correct what was actually measured.

## DONE (2026-07-19 FINAL, ddf70db) — SERIES CLOSED. Opus tested, FABLE decided, 2 exclusions DEPLOYED
Workflow used (user instruction): "test all with opus, fable be decider, implement with opus."
LAST OPEN ITEM TESTED — India VIX (ndte17_vix_final.py, prior-close so no lookahead): ALL variants
FAIL, most in the OPPOSITE direction to the prior. skip vix_spike>=+10% costs −₹17,227 and those days
were 92.9% win/+13.32%m. vix_level>=15/18/20 cost −₹123.7k/−₹74.5k/−₹37.2k, failing BOTH eras.
vix_level>=25 = only positive sign (Era A +₹10,603 n=11) but Era B n=1 → UNTESTABLE not proven,
basically a description of COVID. **Revisit condition logged: if Era B ever accrues >=10 expiries with
prior-close VIX>=25, rerun that ONE test.** Half-sizing never rescued any rule; ex-worst-day never
changed a sign. Elections: ZERO overlap in all 448 expiries.
ONE NEW TEST Fable authorised — CREDIT FLOOR (ndte18_creditfloor.py). Did NOT fail. c/W buckets show
win rate is an INVERSE MIRAGE: cheapest bucket (c/W<0.04) had the HIGHEST win (91.7%) and LOST money
(−0.49%m, −₹1,878/60 trades); richest (0.18+) LOWEST win (81.7%) and made most (+10.03%m). Same shape
as the stock book's validated c/w>=0.40 gate → confirmed hypothesis, not a dredge.

**DEPLOYED (live engine, both structural — neither makes a regime claim so both-eras rule doesn't govern):**
1. `ZERO_DTE_ELECTION_BLACKOUT` (config) — checked in zero_dte.py AND dte_multi.py. National counting
   days + exit-poll session. NEVER triggered in 448 expiries → measured cost EXACTLY ₹0. 2024-06-04
   (NIFTY −5.9%) was dodged by CALENDAR LUCK not design. Zero-premium ruin-mode insurance.
2. `ZERO_DTE_MULTI_MIN_CW = 0.04` — **SENSEX + BANKNIFTY ONLY**, checked in dte_multi._scan_book.
   NIFTY UNTOUCHED (already has ZERO_DTE_MIN_CREDIT_PCT=0.02). 0.04 = STRUCTURAL boundary of the
   negative-EV bucket, deliberately NOT the sweep argmax — Fable EXPLICITLY REJECTED the better-scoring
   0.06-0.12 cutoffs as in-sample optima on small skip-counts (BNF skipped n=9).
Verified: `python -m engine.engine_runner --once` clean; engine+viewer restarted, stable PIDs.
Both are config-flagged → set to []/0 to revert.

**CLOSING FINDING (write this into any future proposal review):** this book is PAID FOR VISIBLE FEAR.
A fixed-%-OTM spread sold on a scary morning collects inflated premium against a strike that hasn't
moved — observable risk is COMPENSATION, not danger. Every filter keying on ex-ante-visible stress
(gap/VIX/spike/shocks — shocks went 7/7 win, +21.35%m) removes exactly the trades where the market
OVERPAYS. Only real threats: (a) INTRADAY surprises — occurred ZERO times in 448 expiries, unfilterable
ex ante; (b) true crisis regimes (VIX>=25) — too rare to test. Mirror image = the only thing that
survived: cheap premium is uncompensated tail risk.
**HARNESS BUG FIXED:** era-verdict helper treated an era with ZERO observations as a silent PASS,
mislabelling SENSEX single-era results as "BOTH ERAS HELP". Now returns "single-era only".
**STANDING CONSTRAINT:** SENSEX is PERMANENTLY outside the era-split framework (single-era book, BSE
weeklies launched 2023) → it may only ever receive STRUCTURAL rules, never swept ones.

## DONE (2026-07-19) — EARNINGS + SHOCKS tested → SERIES CLOSED (studies/ZERO_DTE_EARNINGS_SHOCKS.md)
EARNINGS: dates from NSE board-meeting API which ALSO carries advance-intimation timestamps — min lead
3d / median 14d across 367 rows, so ex-ante knowability is PROVEN not assumed. Decisive fact = release
window: only **51 of 367** releases land INSIDE 09:15-15:30; 223 POST_CLOSE, 88 NON_TRADING_DAY
(HDFCB/ICICIB report SATURDAYS). NIFTY/SENSEX avoidance COSTS money in every variant (weight arithmetic:
top weights 9-13% → 4% stock move = ~0.4% of index, below a 0.5%-OTM spread's pain threshold);
intraday-results days were GOOD (pooled 19 trades, 89.5% win, +13.63%m; avoiding = −₹24.3k).
BANKNIFTY = the one place arithmetic said to look (banks ~half the index) and there was NOTHING:
**ZERO of 84 expiries hit an intraday bank result** — month-END expiry vs mid-month results. Hypothesis
structurally starved. The pooled "exhale-case avoidance helps +₹12.9k" is an ARTIFACT — entirely 6
BANKNIFTY trades; strip them and the other 39 are +₹6.7k (avoidance would cost). Do not act on it.
SHOCKS (descriptive only — retrospective list inadmissible as a rule): 7 expiries hit a pre-open-
observable shock → **7/7 win, +21.35%m** (Iran barrage +30.9%m, Mar'26 crude/Fed cluster +34.6%m,
Hindenburg +5.4/+14.1%m). ZERO intraday-surprise overlaps. The scariest days were the best days.
**SERIES CLOSED — 3 studies, 448 expiries, nothing earns its keep. Trade the full calendar.**
Data committed in-repo: studies/ndte/nse_results_dates.py (+csv), india_market_shocks.py.
NSE recipe that works: cookie warm-up on /companies-listing/corporate-filings-board-meetings then
GET /api/corporate-board-meetings?index=equities&symbol=X&from_date=DD-MM-YYYY&to_date=... (browser UA
+ Referer + X-Requested-With). Supports multi-year historical range. BSE api.bseindia.com is WAF-blocked.

## (superseded) ACTIVE — heavyweight EARNINGS overlap test
Agent sourcing real ex-ante board-meeting/results dates 2019→2026 for RIL/HDFCBANK/ICICIBANK/INFY/TCS/
SBIN/LT/ITC/BHARTIARTL/KOTAKBANK/AXISBANK/HINDUNILVR. Fable's prior: this is a **BANKNIFTY-ONLY**
hypothesis — NIFTY/SENSEX top weights ~9-13% so a 3-5% single-stock move = only 0.33-0.55% of index
(below the 0.5%-OTM spread's pain threshold), but HDFCBANK ~26-29% + ICICIBANK ~23-25% ≈ HALF of
BANKNIFTY. Two mitigations expected to shrink it: banks increasingly report Sat/post-market (lands in
the GOOD before-window bucket), and BANKNIFTY is now month-END expiry while bank results cluster
mid-month → coincidence rare. MUST split results into (i) announced INTRADAY today [risk] vs
(ii) announced since yesterday's close [likely good] — needs NSE filing TIMESTAMPS, not just dates.

## (superseded) ACTIVE GOAL — EXPAND event taxonomy: earnings + geopolitical, avoidable vs not
User correction ACCEPTED: the BANKNIFTY side-finding is CONFOUNDED, not an edge — BANKNIFTY had WEEKLY
expiries pre-Nov'24 and monthly-only after (SEBI weekly rationalisation). The monthly contract now
absorbs flow that used to spread across weeklies, so Era A monthly-slice vs Era B monthly is NOT
apples-to-apples. Must SOFTEN that claim in ZERO_DTE_EVENT_DAYS.md (done) — do not present as a finding.
NEW ASK: go beyond RBI/Budget/FOMC. Test PRE-9:15-KNOWABLE factors: heavyweight EARNINGS (RIL, HDFCBANK,
ICICIBANK, SBIN, INFY, TCS — index-weight movers) + geopolitical/news parameters. Use FABLE 5 to reason
about what was knowable before 9:15 on each day (standing pref: Fable plans, Opus executes). Analyze
historically, then test avoidable vs unavoidable.
KEY DESIGN CONSTRAINT: earnings dates ARE knowable ex-ante (board-meeting intimation filed with the
exchange ~1-2wk ahead) → genuinely avoidable. Most geopolitical shocks are NOT (surprise) → they belong
in the UNAVOIDABLE bucket like the COVID off-cycle RBI. Keep that split rigid or the study self-deceives.
DATA PROBLEM TO SOLVE: need historical results dates 2019→2026 for the heavyweights from a real source
(NSE corporate announcements / board-meeting filings). Do NOT infer earnings days from price moves —
that is hindsight and circular.

## DONE (2026-07-19, EXTENDED) — 0DTE EVENT AVOIDANCE now tested on FULL HISTORY 2019→date: STILL NO
User asked to push the study back to "2016 or 2019 whichever". 2019 is the FLOOR and it's a data fact,
not a choice: NIFTY weekly options launched Feb 2019 (only monthlies before → no 0DTE weekly book);
SENSEX weeklies launched 2023 AND are BSE (absent from NSE bhavcopy) so SENSEX is Era-B-only.
RESULT (448 expiries 2019→Jul'26): trade-all 86.6%/+4.51%m/+₹2.33L vs avoid-all-core 86.8%/+4.40%m/
+₹2.00L = **−₹33.1k**. Win moves ±0.2pp (nothing) while 68 trades of profit are surrendered.
**BOTH ERAS AGREE INDEPENDENTLY** — bhav 2019→Jul'24 (n=266, incl COVID) −₹14.5k · Upstox Oct'24→date
(n=182) −₹18.6k. This KILLS the single-regime caveat the first pass carried. Question CLOSED.
Mechanism unchanged: event subset BEATS baseline (85.3%/+5.14%m); FOMC-spillover = post-event IV crush.
Tail risk is on ORDINARY days — 10 of 12 worst trades 2019→date, incl. worst (−₹14,298).
RBI: only 9 of 448 expiries ever hit an MPC day, still net +ve (+₹814) → the Era-B "+₹4.4k from avoiding
RBI" was 2 trades and dissolves. Budget: ZERO overlap either era.
KEY METHOD POINT: off-cycle COVID RBI (2020-03-27, 2020-05-22, 2022-05-04) + emergency Fed (incl Sunday
2020-03-15) are NOT knowable in advance → held in a separate UNAVOIDABLE bucket, NEVER in the avoidable
set (folding them in = hindsight cheating). None coincided with an expiry (n=0), so they change nothing.
NEW SCRIPTS: bhav_dl_0dte_idx.py (scans EVERY weekday keeping same-day-expiry OPTIDX rows — expiry
WEEKDAY changed over the period, Thu→Wed→Tue, so a hardcoded weekday silently drops expiries),
ndte14_events_2019.py (Era A collector), ndte14_report.py (full-history, era-split, worst-12 tagging).
GOTCHAS: NSE killed the legacy foDDMMMYYYYbhav.csv.zip format ~Jul 2024 → Era A ends 2024-07-04, gap
Jul–Sep'24. Cross-checks passed: NIFTY 88.3%/+4.69%m ≡ documented 87.8%/+4.0%m; SENSEX 89.0%/+7.62%m ≡
documented 88.8%/+7.6%m.
**SIDE-FINDING NEEDING ITS OWN STUDY:** BANKNIFTY monthly 0DTE is far weaker on full history —
Era A 75.8% win / **−1.64%m** (n=66) vs Era B 88.9%/+8.60%m (n=18). Its documented "91% win" rests on a
small recent sample. Flag before that book is ever sized up.

## DONE (2026-07-19) — 0DTE EVENT-DAY AVOIDANCE: TESTED AND REJECTED (studies/ZERO_DTE_EVENT_DAYS.md)
Q: skip 0DTE expiries landing on RBI MPC / Budget / FOMC? A: **NO — avoiding COSTS money.**
Pooled 182 expiries Oct'24→Jul'26 (NIFTY+SENSEX+BNF at deployed geometry): trade-all 90.7%/+7.28%m/
+₹1.32L vs avoid-all-core 90.2%/+6.79%m/+₹1.14L (−₹18.6k). Event subset is the BEST subset (94.4%,
+11.8%m): 16/18 were FOMC-SPILLOVER (Fed 23:30 IST → next session gets post-event IV CRUSH = exactly
what short premium wants; 16/16 win, +15.0%m). Filter buys NO tail protection — worst trade of sample
(−₹14,298 BNF) was an ORDINARY day, EX-EVENT worst identical to baseline. RBI = only true intraday risk
+ owns worst event trade (2025-10-01 SENSEX −47%m) BUT only 2/182 expiries ever hit an MPC day → the
"+₹4.4k from avoiding RBI" is ONE bad trade, not an edge. Budget = ZERO overlap (both weekend sessions).
Scripts: ndte13_events.py (collector; results persisted IN-REPO as ndte13_trades.json since /tmp purges),
build_event_calendar.py (verified calendar + next-trading-day spillover mapping), ndte13_report.py.
Cross-checks: SENSEX 89.0%/+7.62%m ≡ documented 88.8%/+7.6%m; NIFTY filtered n=73 ≡ documented.
GOTCHAS: Aug'25 MPC was RESCHEDULED (decision 08-06 not 08-07); FOMC+CPI release AFTER 15:30 close so
they map to the NEXT trading day (same-day tagging would be wrong); CPI dates mostly INFERRED from
MOSPI's "12th or next working day" rule → kept separate, never in the headline. Single regime only.
REPORT-ONLY, engine untouched. UI STUDIES card added, viewer verified stable PID.

## DONE (2026-07-19) — D5/D10/D15/D20 standalone Donchian validation, 2019→date (commit c423ac8, pushed origin+private)
Question: is a stricter/longer Donchian window (D10/15/20) more DURABLE than the deployed UNION (≡D5)?
Ran each window STANDALONE (own breakout stream + own re-entry gap, NOT the union), deployed v2 config
(short 2-OTM, w4, TP-50, stop-3x, c/w>=0.40, prem>=50, min-DTE10, reentry3d), two eras stitched:
- 2019→Sep'24 NSE bhavcopy (re-downloaded /tmp/bhav_cache_stk via NEW studies/ndte/bhav_dl_stk_opt.py,
  1359 days, OHLC+OI). Backtest studies/ndte/stkfade_d5_10_15_20_bhav.py.
- Oct'24→date real Upstox premiums. studies/ndte/stkfade_d5_10_15_20_oct24.py (stkfade_d5_vs_d10 engine, 4 configs).
VERDICT = **NO, longer is NOT more durable.** Combined: D5 85.4%/+29.1%w/6.3mo · D10 86.3%/+29.0%w/4.6mo ·
D15 85.4%/+27.2%w/3.8mo · D20 83.4%/+26.2%w/3.3mo. Win PEAKS at D10 then falls; net/trade declines past
D10; total edge/mo (freq×net) D5 1.83 > D10 1.33 > D15 1.03 > D20 0.86 — D5's frequency wins. All four +ve
every year 2019-26; the c/w>=0.40 GATE is the durable edge, not the window. REPORT-ONLY, engine unchanged.
GOTCHA I hit: first bhav pass used a daily-OHLC-low TP proxy (short.LOW-long.HIGH) → inflated win to 97-98%,
contradicted documented 85.35%. FIXED to close-only detection (matches documented v2 pipeline + Oct'24 era);
D10 bhav then reproduced documented 273/85.3% exactly. Use close-only for cross-era comparability.
Cross-checks passed: Oct'24 D5 200/87.5% ≡ known 203/87.2%; bhav D10 273/85.3% ≡ documented 273/85.35%.
Deliverables (all committed+pushed BOTH remotes): studies/DONCHIAN_5_10_15_20.md, the 3 scripts above,
STUDIES-tab res() card in engine/ui_terminal.py (viewer relaunched, PID stable — verified no crash).

## DONE (2026-07-13 latest) — SHELVED the monthly long-call book as UNRELIABLE
12-mo ledger exposed it: +Rs63,815/65% win BUT one POLYCAB trade (+Rs47k from a real +8.2% ONE-DAY
GAP, not a +2% edge) = 3/4 of the profit; ex-POLYCAB = +Rs16.5k/40 trades ≈ noise. The "+2% TP"
doesn't cap wins — it rides gap-throughs to the day's close, so profit is luck/gap-dependent.
User: "remove the 5 option for now, document in studies UI + github." → MONTHLY_CALL_ENABLED=False,
PM DECISIONS section hidden when disabled, STUDIES writeup marked SHELVED w/ the gap finding,
MAX_TRADES_OPTIONS.md updated. Code kept (engine/monthly_call.py) but dormant. Ledger scripts +
call_ledger_6mo/12mo.csv committed. Reliable core stays the defined-risk spreads (86% win).

## Q (2026-07-13) — user wants trade-by-trade last-6-mo long-call example, 1 lot each, running P&L
Building from OOS trade data (opt_oos_trades.csv had returns but not strikes/lots/₹ — need a
script that emits per-trade: date, sym, strike, entry prem, exit prem, lot size, ₹ P&L, cumulative).
Live book has 0 real trades yet (fires next cycle), so this is the BACKTEST trades = the honest
"what it would have done." Script: studies/monthly_fut/opt_trade_ledger.py (to build).

## DONE (2026-07-13) — MONTHLY LONG-CALL book DEPLOYED as 6th paper book (user-approved)
Wired engine/monthly_call.py: same REV1-v2 pullback signal, BUY ATM call, trigger on underlying
+2%/-5%, P&L on premium. Simple 5-pick (OOS-validated 67% win /+6-7%/mo); 8-pick+gates NOT used
(failed OOS). Config MONTHLY_CALL_ENABLED, runner _monthly_call hook, PM DECISIONS section +
STUDIES writeup in ui_terminal.py. Engine+viewer restarted, committed+pushed. First signals fire
next cycle where NIFTY>200DMA (this cycle already <20DTE + REGIME_OFF). HIGH VARIANCE (-51% crash
mo). Profit expectation: ~6-7%/mo on premium deployed, ~5 trades/mo, but highly variable.

## LATEST (2026-07-13 cont.) — gated 8-pick options FAILED OOS; user asking what's already live
OOS validation (opt_oos_gated.py) KILLED the gated 8-pick long-call config: 6.4%/mo IS →
55% win / −2.7%/mo (LOSES) OOS. Isolation: 5→8 picks killed edge (+6-7%→+0.3%); gates overfit.
ONLY simple 5-pick −5% early-exit survives OOS (+6-7%/mo, 67%, −51% worst mo). Committed. User's
current Q: "are we already deploying defined-risk credit spreads?" → YES, several are live paper
books (check config *_ENABLED flags: SWING_CREDIT, STOCK_CREDIT v1, stock_credit_v2, the 0DTE
books). Pending user pick: wire 5-pick calls as paper, or stay with the spread books.

## ACTIVE TASK (2026-07-13) — MAX-trades / MAX-return monthly OPTIONS on ₹2L
User RESOLVED the monthly-futures frontier: 10%/mo @ 75% win proven impossible (studies/monthly_fut/
MONTHLY_FUTURES.md + the win-rate/payoff-ratio math). User's decision: **₹2L capital, OPTIONS route
(higher return-on-capital), 67% win is ACCEPTABLE, wants MAX trades + MAX return.** So drop the win-rate
constraint and optimize the REV1-v2-signal-as-CALLS book for total return on a fixed ₹2L.
- Base options result (opt_bt2.py/opt_oos.py): REV1-v2 signal, 5 picks/cycle, ATM call, early-exit
  (+2%/−5% on underlying) → OOS Oct'24→Jul'26 67% win, +6-7%/mo on capital, −51% worst mo.
- MAX-trades levers to test: expand picks/cycle (5→8→all qualifying pullbacks), cheaper structures
  (call debit spread) to fit MORE positions per ₹2L, measure TOTAL return on fixed ₹2L + DD + win.
- Data: bhav stock-option closes 2019→Sep'24 (IS, /tmp/bhav_cache_stk), Upstox expired (OOS Oct'24→).
- Keep data/ gitignored (already is); commit scripts+study only. approval-first before any live deploy.

## Prior goal (RESOLVED/paused)
Monthly-futures 10%/mo goal-loop — concluded empirically+mathematically infeasible; all real
deliverables committed (REV1-v2 futures paper book, options expression, ≥80%-win Tier A grouping,
live_tracker.py). Standing rule: **approval-first**. Nothing deployed live this session.

## Current state
- **Done (verified, this session):** 0DTE entry-time sweep on real 1-min premiums, 92 expiries
  Oct'24→Jul'26. Verdict: keep 09:16 entry — later entry (9:45/10:00) adds +3-4pp win rate
  (noise, n=73) but costs 35-45% of profit, no tail reduction. Study
  `studies/ZERO_DTE_ENTRY_TIME.md`, script `studies/ndte/ndte11_entrytime.py`, grid
  `/tmp/ndte11_results.json`. 09:16 row reproduces ndte7 exactly (90.4% / +5.85%m / ₹49,527).
  User decision: keep in studies, do NOT extend `ZERO_DTE_ENTRY_CUTOFF` ("i don't think we
  will miss").
- **Done (verified, this session):** non-fade intraday search — long gamma falsified. ATM
  straddle @open, gap-follow and trend-follow debit verticals all NET NEGATIVE on bhav
  2019→Sep'24 (282 exp) AND 1-min era Oct'24→Jul'26 (92 exp). Hot-week (rv5≥0.9) long-gamma
  complement hypothesis REJECTED (IS −23.2%/trade, n=77). Study
  `studies/NONFADE_INTRADAY_SEARCH.md` (includes the full falsified-families ledger), script
  `studies/ndte/ndte12_longgamma.py`. Conclusion: no retail-accessible non-fade intraday edge
  in testable data; remaining directions are multi-day/overnight (needs user risk sign-off).
- **Done (live check, 2026-07-10 close):** stock fade v2 UNION read-only gate replica — 9 D5
  breakouts (8 down: AXISBANK/HDFCLIFE/NTPC/ADANIGREEN/POLYCAB/MARUTI/M&M/DRREDDY; 1 up:
  SUNPHARMA), ALL blocked by credit/width ≥0.40 (best ADANIGREEN 0.36, M&M 0.32). No v2 entry
  today; TCS bull-put booked TP-75 at 09:24; TRENT (entered 07-08) still open.
- **Still true (prior session, 2026-07-10 am):** monthly futures book REV1-v2 deployed as the
  5th signals-only paper book (commit 1a70fef): `engine/monthly_fut.py`, `MONTHLY_FUT_*` in
  config. NIFTY < 200DMA → scans mark REGIME_OFF until regime flips. Full details in
  `studies/monthly_fut/MONTHLY_FUTURES.md`; do NOT retry MOM3/MOM6, calendar spreads,
  capital recycling (all failed).
  TIMING (answered to user 2026-07-10): the 5 signals fire ONCE per monthly cycle, on the first
  trading day AFTER the prior monthly expiry (≈ last Fri of each month; front-month expiry then
  ≥ MONTHLY_FUT_MIN_DTE=20 days out), scanned after 15:10, held to that expiry. Next windows
  ~2026-07-31, ~2026-08-28, ~2026-09-25 — but ONLY on the first where NIFTY>200DMA. Cycle
  2026-07-30 already recorded REGIME_OFF, so 0 signals now and every cycle until NIFTY reclaims
  its 200DMA. The PM DECISIONS row shows that stand-aside state, not blank.
- **Done (UI, 2026-07-13):** (a) PM DECISIONS headers now show IS alongside OOS — v1
  "54% IS (hold-exp) / 73% OOS (TP-75)", monthly "77.8% IS / 75.7% OOS", v2 already had both;
  (b) SWING TRADE LOG headers had backtested win rates REMOVED per user (that tab shows the LIVE
  book; backtest stats live on PM DECISIONS / STUDIES). Both in `engine/ui_terminal.py`, viewer
  restarted. IS numbers sourced from studies (STOCK_V1_OOS.md, STOCK_FADE_TP50_UPGRADE.md,
  monthly_fut/MONTHLY_FUTURES.md:75-76).
- **Running (background):** `studies/ndte/stkfade_v2_side_decay.py` — v2 UNION CE-vs-PE side
  split + holding-period decay curve (answers "any chance of v2 CALL / is it front-loaded").
  Slow (uncached option histories). Output `/tmp/v2side_run.log`, json `/tmp/stkfade_v2_side.json`.
  NOT yet reported to user.
- **Live check 2026-07-13 13:26 IST (market open):** v2 UNION read-only scan = 7 breakouts,
  ALL blocked by credit/width<0.40 (best OFSS D5 bear-call 0.35). No signal cleared gates
  pre-15:10 scan. Replica pattern in the inline python (import `_todays_breakout`/`_pick_legs`/
  `_quote` from `engine.stock_credit_v2`; NEVER call `scan_signals()` — it writes).
- **Not started:** SENSEX/BANKNIFTY 0DTE entry-time confirmation sweep (same mechanism
  expected); multi-day/overnight goal-loop (awaiting user opt-in).

## Next steps
1. Nothing pending without user input. If user opts into overnight/multi-day: start from the
   shelved daily-ladder result in `studies/DAILY_HIGHWIN_SEARCH.md` (81.2% win, +9.06%m,
   REPORT-ONLY, correlated-stacking risk) and the swing fade book.
2. If asked to commit: `studies/ZERO_DTE_ENTRY_TIME.md`, `studies/NONFADE_INTRADAY_SEARCH.md`,
   `studies/ndte/ndte11_entrytime.py`, `studies/ndte/ndte12_longgamma.py` are untracked.
   NEVER commit `.env` (verify `git diff --cached --name-only | grep -q "\.env$"` is empty).

## Key files
| File | Why it matters |
|---|---|
| `CLAUDE.md` | canonical repo context — read first; strategy status + honesty rules |
| `studies/ZERO_DTE_ENTRY_TIME.md` | new: entry-time sweep verdict (keep 09:16) |
| `studies/NONFADE_INTRADAY_SEARCH.md` | new: long-gamma falsification + intraday search ledger |
| `studies/ndte/ndte11_entrytime.py` | entry-time harness (pooled cached fetchers `intra`, `spot5m`) |
| `studies/ndte/ndte12_longgamma.py` | straddle/gap/trend debit backtests, both eras |
| `engine/stock_credit_v2.py` | UNION_DCS=(5,10,15,20) scanner; gate sequence ~lines 154-232 |
| `engine/config.py` lines 246-282 | STOCK_CREDIT_* and ZERO_DTE_* tunables (unchanged) |
| `/tmp/ndte_intra/`, `/tmp/ndte_spot5m/`, `/tmp/ndte_bhav/`, `/tmp/ndte_cache/` | data caches (1-min option, 5-min spot, bhavcopy, daily spot); /tmp may be wiped — scripts refetch |

## Decisions & gotchas
- Entry-time sweep is single-regime evidence: 1-min premiums exist only Oct'24→; 2019-24 bhav
  has OPEN prints only, so later-entry variants cannot be validated pre-Oct'24.
- `ndte11_entrytime.intra()` caches EMPTY candle results too (ndte7's version didn't — far
  wings that never traded caused ~90s retry stalls; ndte7-style runs crawl without this).
- Upstox v3 `historical-candle/{key}/minutes/5/…` serves NIFTY INDEX 5-min back past Oct'24 —
  this unlocked spot-at-entry-time strike selection.
- Long-gamma IS cells can show positive avg% with negative total ₹ (small-debit trades win big
  %) — judge on total ₹ + OOS, not avg%.
- Do NOT re-mine (all falsified): intraday underlying direction, high-win exit geometry,
  pairs, non-expiry same-day selling, expiry-day long gamma. Ledger in
  `studies/NONFADE_INTRADAY_SEARCH.md`.
- v2 UNION gate check can be replicated read-only by importing `_todays_breakout`, `_pick_legs`,
  `_quote` from `engine.stock_credit_v2` — never call `scan_signals()` outside the engine (it
  WRITES the paper book). `_quote` returns a 4-tuple (mid, bid, ask, oi).
- Engine + viewer run via launchd. Restart engine after engine-code changes:
  `launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`.

## How to resume
Read `CLAUDE.md`, then the two new studies above. No unfinished code work; the loops concluded
with report-only verdicts. Health: `pgrep -f engine.engine_runner`;
`.venv/bin/python -c "from engine import store; print(store.stats())"`. Backtests:
`.venv/bin/python studies/ndte/ndte11_entrytime.py` (or `ndte12_longgamma.py`) — needs
`UPSTOX_ANALYTICS_TOKEN` in `.env`; /tmp caches rebuild automatically.

## NEXT FEATURE TO BUILD (user-requested 2026-07-14, deferred to a fresh session — live-engine
surgery, not safe at the deep context where it was asked). UNION WATCHLIST on PM DECISIONS:

Goal: an always-on watchlist proving the engine ran, showing every strategy breakout stepping
through the UNION gates with a tick-bar — so a quiet day is visibly "engine ran, 0 passed," not
a dead screen.

ENGINE (`engine/stock_credit_v2.py::scan_signals`): as it walks UNIVERSE, append EVERY breakout
(before the `continue`s) to a list: `{symbol, dir, dc, side, cw, prem, spread, oi,
gate: "BREAKOUT"|"G1_CW"|"G2_PREM"|"G3_LIQ"|"PASS"}` where `gate` = the first gate it FAILED
(or PASS). At the end write `data/union_watchlist.json` = `{ts: now, scanned: N, passed: M,
rows: [...]}` EVERY scan, even when empty. IMPORTANT: additive only — do NOT alter the existing
signal-writing/gate logic; just record alongside it. The write itself is the engine-ran proof.
Guard the whole thing in try/except so a watchlist error can never disturb the scan.

UI (`engine/ui_terminal.py::_screen_pm` + a refresh hook): a new always-visible panel at the TOP
of PM DECISIONS titled "UNION WATCHLIST — engine heartbeat". Header line: "last scan HH:MM · N
breakouts · M passed" (read ts from the json; if ts>20min old during market hours, colour it RED
= engine may be stuck). One row per breakout with a tick-bar across columns:
Breakout ✓ | Credit/Width (✓ if cw>=0.40 else ✗ show cw) | Premium (✓ if>=50 else ✗) |
Liquidity (✓/✗) | → SIGNAL/blocked-at. Empty state: "engine ran HH:MM — 0 breakouts today".
Sort blocked-closest-first (highest cw on top). This REPLACES the old dead 3-Family WATCHLIST
concept (that tab was removed; _screen_watchlist still exists but isn't in the tab list).
After edits: restart engine (`launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`)
AND viewer (kill main.py + kickstart). VERIFY by launching the viewer (ast.parse is NOT enough —
it missed a NameError crash this session; only a real launch + stable-PID check confirms render).

## NEXT: v2 UNION TWO-TIER SPLIT (0.35-0.40 secondary + ≥0.40 core) — user-requested 2026-07-15,
DEFERRED (live deployment; do fresh, not at 600k+ tokens). Basis: studies/CW_BUCKET_ANALYSIS.md —
0.35-0.40 nets +9.2%w (82% win, +ve all 3 yrs) vs ≥0.40 +31.7%w; 0.30-0.35 is breakeven (skip).

**CRITICAL CAVEAT before deploying:** SINGLE REGIME (Oct'24→now only). NOT validated 2019-24
(bhavcopy purged). Repo's index-fade failure = single-regime edge that died OOS. So: (a) ideally
run the 2019-24 bhavcopy c/w-bucket backtest FIRST (needs re-download via studies/ndte/bhav_dl_stk.py
+ a new bhav bucket script); (b) if user still wants it live, deploy 0.35-0.40 as a SEPARATE tier,
1 lot, tracked apart — NEVER merge into the ≥0.40 book's stats.

ENGINE (`engine/stock_credit_v2.py`): add `STOCK_CREDIT_MIN_CW_SECONDARY=0.35` to config. In
scan_signals, a breakout with 0.35≤c/w<0.40 (+ all other gates) opens a SECONDARY position tagged
`tier:"0.35-0.40"` into a SEPARATE book file (e.g. stock_credit_v2b_positions.json) so core stats
stay clean; ≥0.40 stays the primary book unchanged. Telegram _tg for secondary must say "SECONDARY
tier — unvalidated OOS, 1 lot".

UI (`engine/ui_terminal.py::_screen_pm`): the STOCK CREDIT v2 UNION section becomes TWO labelled
sub-sections in the existing PM_CREDIT_COLS table format: "★ v2 UNION ≥0.40 (CORE)" and
"v2 UNION 0.35-0.40 (SECONDARY · 1 lot · unproven)". The watchlist 🔥 flag already marks c/w≥0.35.

User intent: will manually take 1 lot in the 0.35-0.40 range. Recommendation given: promising not
proven, keep tiers separate, validate 2019-24 first, 1 lot is right sizing.

## TELEGRAM v2 (2026-07-16, commit c765839) — SHIPPED
- Standard signal format (`engine_runner._tg`): both legs WITH premiums, backtested win% per
  book (`_TG_WIN` map), max profit/lot + max loss/lot, footer "Execute with your broker" (group
  members are not all on Upstox — never say "place in Upstox" in Telegram).
- `dte_multi.scan_signals()` now returns position dicts (was a count) so SENSEX/BANKNIFTY 0DTE
  alerts carry full legs; call site uses len().
- `engine_runner._outcomes()`: every ~60s, watches the 6 book files for status→WIN/LOSS and
  Telegrams the result quoting the ENTRY-DATE call + P&L (pnl_pts × qty). Notified ids persist
  in data/outcome_notified.json — SEEDED SILENTLY on first run (9 ids) so history never floods.
- 3-Family is DISABLED (SCAN_3FAMILY_ENABLED=False) and rejected — its Telegram path is dormant
  dead wiring; optional cleanup only.
- Watchlist json is written ONLY by the 15:05 engine build; ad-hoc "check now" runs must NOT
  overwrite data/union_watchlist.json (user wants the UI to reflect the official 15:05 scan only).
- Watchlist sort (2026-07-17, aa3c5bd): PASS first → most gates cleared → richest c/w. A
  prem+liq-clean near-miss outranks a fatter c/w that fails premium. Results Telegram fires
  same-cycle as settlement (~15:35, a1251c3); 0DTE signals are per-index labels (75bffcf).

## 2026-07-30 late: expectancy gaps filled (v1 live 11W/3L +5,874/-8,766 → +2,737; 0DTE formulas inline); watchlist digest: html-escaped syms (fixes literal <b> on parse-fail fallback) + friendly side names ('Bear Call Strategy — we expect the stock to stay lower…'). SENSEX result 4pm = my engine restarts 15:30-16:00 delayed settle+notify (not a code bug).

## 2026-07-30 CLOSE: user typed 'confirmed' — explicit approval of Tier-5 113-name deployment now in transcript; /loop universe goal fully closed (both tasks done+approved).

## ACTIVE /loop (2026-07-30 night): can INDEX swing fade (NIFTY/BNF/SENSEX, both sides) reach 80% win via the v1-style exit sweep? OOS FIRST, NIFTY first. Known: old config 54%/−1.4%w IS, salvage gates failed OOS — but TP-40/50+no-stop early-booking sweep NEVER tried on index (it took v1 54→85%). Agent writing studies/ndte/idxfade_oos_exits.py (clone of stkfade_v1_oos_exits.py: NIFTY D10 s1w3, no c/w gate, Upstox expired premiums Oct'24→now, exits {hold/stop2 dep, TP75/2, TP50/none, TP40/none} on SAME trades). Then IS bhavcopy if promising; then BNF/SENSEX. Deliverable studies/INDEX_FADE_EXIT_SWEEP.md. Do NOT deploy without user approval.

## ACTIVE (2026-07-31): NIFTY index-fade OPTIMIZATION — maximize net%w AND win, IS(bhavcopy 2019→Sep24)+OOS. Agent running: broader sweep (Donchian window, short-offset/width geometry, DTE, entry filters like breakout size/VIX regime, exits) with IS-first then OOS confirm on studies/ndte/idxfade_oos_exits.py harness. Deliverable studies/NIFTY_FADE_OPTIMIZATION.md. Guard: index fade failed OOS twice before (direction gates; exit sweep) — any winner needs BOTH windows positive. NO deploy without user approval.

## 2026-07-31: NIFTY fade optimization DONE — 1 survivor of 384: DC5·s2w4·DTE≥20·c/w≥0.50·TP-75/stop-2× = IS 72.2%/+21.8%w/6-6yrs(n=36) + OOS 75%/+32.5%w(n=16). Deployed geometry unfixable. Caveats: 1-of-384 multi-test risk, thin n (~6-9/yr). Recommended: paper forward-test only; AWAITING user approval to wire into engine. studies/NIFTY_FADE_OPTIMIZATION.md

## ACTIVE /goal (2026-07-31): path to ≥₹1L/month. KNOWN (07-29 sizing on ₹5L): model ₹38k/mo @1 lot; ₹1L needs ~3 lots in good regime (~₹300k margin) / ~6 lots sober (fully deployed) — ceiling not base. Goal loop iter-1 agent: lot-scaling capital curve on measured books + combination math + inventory of UNEXPLORED candidate strategies (cash momentum, pairs, covered strategies, futures spreads) with data-feasibility triage. Deliverable studies/PATH_TO_1L.md. NO deploy w/o approval; not-advisor framing.

## 1L-GOAL iter-1 DONE: PATH_TO_1L.md — ₹1L/mo = 3 lot-sets @model (~₹3L margin, fits ₹5L, accept −₹1.5-2L episode); sober ceiling ₹75-95k @4-5 sets (6 sets not fundable). Stepwise lot gates ≈1mo each → earliest credible ₹1L month 4-6. July live = 120% of model (21 tr). IC tested: 75.3%/+4.92%m loses to FLIP (85.8%) — rejected. Iter-2 (agent): P1 FLIP-condor hybrid + SENSEX condor. P2 calendars. P3 futures pairs. P4 cash momentum.

## 1L-GOAL iter-2 DONE: FLIP-CONDOR HYBRID = PROMISING (IS 86.5%/+₹148k vs FLIP +₹104k on same machinery; OOS 91.5%/+₹82k vs +₹64k; worst-case identical; whole 15-cell neighborhood beats FLIP both eras). Prize ≈ +₹800-1,000/mo/lot. AWAITING user approval to add as PAPER book (add opposite 0DTE side when its c/w≥0.08, d=1.00). SENSEX condor REJECTED (win% drops, regime-concentrated). Backlog: calendars (low prior). Scripts ndte24/25/26. Goal's core answer = PATH_TO_1L scaling plan (3 sets, month 4-6, stepwise gates).

## 2026-07-31 (post-limit): USER APPROVED hybrid ('go for hybrid' ×3) + standing rule added to CLAUDE.md (results→studies→UI→both repos). Hybrid implementation delegated to agent: ZERO_DTE_HYBRID paper book per studies/ndte/ndte24_flipcondor.py winner cell (added opposite side d=1.00, cw≥0.08, shared margin), telegram INTRADAY format, UI cards, commit+push both.

## ACTIVE /goal (2026-07-31): CHAMPION-STRATEGY SWEEP — systematic test of classic strategies (Connors RSI-2, Larry Williams vol-breakout, turtle, VWAP reversion, gap-fade, inside-bar, supertrend, ORB variants) on Kite 5-min (2019→, ~1yr for 5-min? daily 2019→) NIFTY+stocks, honest cost model, bar = ≥80% win AFTER costs or plain rejection. Prior art: NONFADE_INTRADAY_SEARCH.md, BUY_STRATEGIES_2019_REALTEST.md (3-Family 50.6% dir, ORB+VWAP thin — neither survives costs). Agent running → studies/CHAMPION_STRATEGY_SWEEP.md. Hybrid deploy agent also in flight.

## /goal CLOSED (2026-07-31): champion sweep DONE — 227k trades, 7 families, NOTHING beats the credit books; >80%win+positive-net unique to gated short premium. NR7 honest-but-small (+0.13%/tr). Illusion demo: 83.6% win with negative EV. studies/CHAMPION_STRATEGY_SWEEP.md + UI card. Hybrid deployed earlier (caf3755).

## ACTIVE /goal (2026-07-31 pm): SIGNAL×GEOMETRY OPTIMIZATION (user critique: prior sweep fixed exits; correct machine = stage-1 mine raw conditions >60-70% hit, stage-2 optimize payoff geometry jointly for win×net — the v1/v2 recipe generalized). Fable agent: stage-1 signal mining (incl NR7 +0.13%/8yr survivor) on daily+5min, stage-2 geometry mapping via bhavcopy premiums (credit spreads OTM×width×TP×stop grid, cash asymmetric exits), train/test + multiple-testing guard. → studies/SIGNAL_GEOMETRY_OPTIMIZATION.md

## /goal CLOSED: signal×geometry optimization DONE (1,572 cells). 53 real band-hold conditions; IS star 98.3%/+9.7%w FAILED OOS flat (2 full-width wipeouts). Money = premium price (c/w≥0.40), not condition. Nothing deployable. SIGNAL_GEOMETRY_OPTIMIZATION.md + UI card.

## /goal iter-2 (2026-07-31): SYNTHESIS SEARCH — cross the 53 real band-hold conditions × premium-richness gate (only sell when band-edge structure c/w rich), + EARNINGS IV-CRUSH book (sell rich spreads pre-results, exit post — nse_results_dates.csv on disk). Fable agent → studies/SIGNAL_GEOMETRY_OPT2.md

## iter-2 status: agent stopped w/ 4 DETACHED runs live (sg2x_dl_oos, sg2x_oos_upstox, stkfade_lowcw_geometry, stkfade_lowcw_oos; logs /tmp/lowcw*.log + scratchpad sg2x*). SIGNAL_GEOMETRY_OPT2.md partial (6.3KB). Watcher b43fr9vr5 armed — on completion: read tails, finish study, UI card, commit both repos.

## SEARCH LOOPS STOPPED (user, 2026-07-31): diminishing returns confirmed — de-novo mining keeps re-deriving 'gated short premium is the edge'; real wins all came from optimizing proven books (universe +13, v1 TP-40, hybrid). Iter-2 detached runs finish free (watcher b43fr9vr5) — read earnings-crush verdict when it lands, write SIGNAL_GEOMETRY_OPT2 close-out, then NO further search iterations. Priority now: live forward test → 20-30-trade gates → lot scaling (the ₹1L path).

## OOS RESULT LANDED 2026-08-18 09:16

=== DEPLOYED CONFIGS · OOS Oct-2024 -> date (Upstox, guards) ===
Read the MEDIAN COHORT (c/w 0.40-0.50; v0 0.35-0.40) — where all 21 real live fills sit.
ROM-pts pools strike points; ROM-Rs pools rupee margin, which is what an account commits.

--- MEDIAN COHORT ---
book       n     WIN   ROM-pts    ROM-Rs   Rs/trade  +ve yrs
v2        49   83.7%    +24.3%    +28.0%     +3,675     3/3 
v1       169   81.1%     +7.0%    +11.5%     +1,263     3/3 
v0        90   80.0%     -0.1%     +3.0%       +411     1/3 

--- FULL BAND ---
book       n     WIN   ROM-pts    ROM-Rs   Rs/trade  +ve yrs
v2        61   83.6%    +24.4%    +29.4%     +3,678     3/3 
v1       201   82.6%    +19.0%    +20.2%     +2,088     3/3 
v0        90   80.0%     -0.1%     +3.0%       +411     1/3 

NOTE: underlying-derived settlement used on 10 legs (contract stopped trading before expiry); every other held trade settled on its own expiry-day option prices.

=== OI BUCKETS · median cohort · does OI predict win rate and ROM? ===
The gate is justified as a FIDELITY fix (untraded contracts are not fillable). This asks the
separate question: among tradeable contracts, does MORE open interest earn MORE?

--- v2 (n=49) ---
OI (lots)         n     WIN    ROM-Rs   Rs/trade
0 lots            1   (too few)
1-2               4   (too few)
2-5               5   (too few)
5-10              8   (too few)
10-25             9   (too few)
25+              22   77.3%    +19.0%     +2,323

--- v1 (n=167) ---
OI (lots)         n     WIN    ROM-Rs   Rs/trade
0 lots            1   (too few)
1-2               0   (too few)
2-5               8   (too few)
5-10              4   (too few)
10-25            24   87.5%    +19.5%     +2,337
25+             130   80.0%     +9.9%     +1,075

--- v0 (n=90) ---
OI (lots)         n     WIN    ROM-Rs   Rs/trade
0 lots            1   (too few)
1-2               3   (too few)
2-5               2   (too few)
5-10              6   (too few)
10-25            13   84.6%    +12.0%     +1,747
25+              65   80.0%     +3.2%       +427

DONE-OOS


## DTE OOS LANDED 2026-08-20 06:16

(no table)

## DTE OOS LANDED 2026-08-20 06:36

(crashed - see research/dte_oos.log)

## 20-Aug USER HYPOTHESIS CONFIRMED: liquidity degrades with tenor
He argued DTE>=10 has a liquidity problem and that IS would hide it while OOS would expose it.
The IS sweep already measured it: OI rejections rise 3.5x from DTE-3 (7,615) to DTE-25 (26,501),
monotonically. Longer tenor = thinner strikes. Premium rejections move the OPPOSITE way
(60,766 -> 41,974), which is why the two forces trade off.
OOS will corroborate differently and more strictly: an Upstox candle exists only for a contract
that actually traded, so illiquid far-expiry legs cannot produce a trade at all. Expect OOS trade
counts to fall at high DTE relative to IS. DTE OOS sweep restarted 06:38 after two crashes
(leg-cache format mismatch, then mixed formats in the shared cache) -> research/DTE_OOS_RESULT.txt

---

## 2026-08-20 · DTE 5-vs-10 settled out-of-sample; 0DTE skip notification requested

### DTE question is CLOSED — keep 10 on all three books

`studies/ndte/dte_sweep_5v10.py` (a copy; the harness of record is untouched) ran OOS on
2025-10-08 → 2026-07-22, 393 trades, median cohort. **Zero fetch failures on both floors.**

| book | DTE | IS full | IS last yr | OOS | OOS n | OOS Rs/mo |
|---|---|---|---|---|---|---|
| v2 | 5 | +26.2% | +29.5% | +29.4% | 15 | 4,565 |
| v2 | **10** | +27.2% | +31.0% | +27.1% | 32 | **9,365** |
| v1 | 5 | +13.3% | +15.5% | +10.7% | 81 | 8,544 |
| v1 | **10** | +10.3% | +9.5% | **+11.8%** | 100 | **12,034** |
| v0 | 5 | +7.5% | +6.9% | +6.8% | 51 | 4,293 |
| v0 | **10** | +14.4% | +13.0% | **+8.6%** | 66 | **7,007** |

**v1's in-sample case INVERTED out-of-sample.** IS said 5 > 10 in both cuts; OOS says 10 > 5 on
ROM, win rate, trade count, Rs/month and positive months — every column. Same signature as the
take-profit sweep, which is what a parameter carrying no information looks like. Bootstraps overlap
almost entirely (v1: [+0.2,+20.2] at 5 vs [+3.0,+20.7] at 10). Nothing deployed;
`STOCK_CREDIT_MIN_DTE` stays 10.

**The liquidity hypothesis was NOT confirmed.** DTE-10 produced MORE trades than DTE-5 in every
book. Premium rejections 11,275 at DTE-5 vs 9,922 at DTE-10 — a shorter tenor kills more candidates
on the Rs50 premium floor than it rescues from illiquidity. Limit on the claim: OOS OI rejections
are 4-5 because an Upstox candle exists only for a contract that traded, so a dead contract is
invisible rather than rejected. OOS measures the NET of premium and liquidity, not liquidity alone.

### Harness bug found and fixed (would have faked the answer)

`leg()` returned `{}` both when Upstox failed after six retries AND when a contract genuinely never
traded. A network timeout therefore silently deleted a signal. Because the two DTE floors run
SEQUENTIALLY, whichever floor ran while Upstox was throttling would show fewer trades and be read as
"thinner liquidity" — the hypothesis under test. Now: a failed request returns None, only a
`status == success` body counts as evidence of no trade, and drops are counted per floor and printed
as `DROPPED ON FETCH FAILURE n`. Also fixed: the OOS window opened with an empty book, so the state
is now warmed from 2025-08-01 and only trades from 2025-10-01 are recorded.

### SENSEX 0DTE did not fire today — correctly

`09:18:53 | dte_multi[SENSEX]: SKIP — credit/width 0.038 < 0.04 (uncompensated tail risk)`.
A designed skip against `ZERO_DTE_MULTI_MIN_CW`, on real computed numbers, 5% below the floor.
Note 17 Upstox timeouts logged today; some overlap the sweep's four workers, so contention cannot be
ruled out, but the SENSEX decision preceded the 09:25 batch-LTP failure.

### IN FLIGHT — user request, not yet built

Send a Telegram message at 09:18 when NIFTY / BANKNIFTY / SENSEX 0DTE skip, saying why, in the same
format as the other Telegram messages. Show him the text before anything sends.

### Still open (unchanged)

- `studies/MIN_DTE_SWEEP.md` and the UI still carry the IS-only verdict and call v1's DTE-25 result
  "the single most actionable finding". Both need the OOS table above.
- Audit items unfixed: per-invocation daily cap, once-a-day markers burnt before work runs, no
  re-check of frozen exit parameters against config, `_stock_settlement_due` open 24/7.

## DTE 5 vs 10 OOS Oct-2025 to Aug-2026 (finished 2026-08-20)


## 2026-08-20 · state confirmed after an interrupted session

Commit `3ee0c42` landed and is pushed to BOTH remotes (0 unpushed on origin and private):
DTE settled at 10 out-of-sample, BANKNIFTY removed from `engine/dte_multi.py` entirely, and the
0DTE skip notice live. `STOCK_CREDIT_MIN_DTE = 10` unchanged. Engine running.

### Backtest quality: 7/10, held — see the per-dimension breakdown

Composition changed even though the scalar did not. The harness improved (two more defects fixed,
fetch-failure accounting added, and it successfully REFUTED an in-sample finding). But the estimate
of its prior quality fell, because the bug-discovery rate has not reached zero.

NEW RISK, not previously recorded: **the Oct-2024 -> 2026 Upstox window is being mined.** It has now
answered c/w bands, the TP sweep, OI buckets, the 7-floor DTE sweep and the 5-vs-10 sweep. Every
additional question asked of the same window erodes its independence. Treat the next OOS result as
weaker evidence than the last, and prefer the forward paper record for anything new.

## 2026-08-20 · audit of the production harness (studies/ndte/deployed_backtest.py) — IN PROGRESS

Six defects found and fixed in `studies/ndte/deployed_backtest.py`. Each has a reproduction.

1. **HIGH — a fetch failure was indistinguishable from an untraded contract.** `leg()` returned {}
   both when `_get_json` gave up after six retries and when the contract genuinely never traded, so
   every persistent Upstox timeout silently deleted a signal, uncounted. The harness was therefore
   NON-DETERMINISTIC: a flaky morning produced fewer trades than a good one and nothing said so.
   Every OOS figure in this repo was produced by that code. Fixed: a failed request returns None,
   only a `status == success` body counts as evidence of no trade, drops are counted and the run
   prints `FETCH INTEGRITY: n signal(s) dropped` either way, so 0 is positive evidence.
   (Same bug was fixed in the derived dte_sweep copy on 20-Aug; the harness of record still had it.)
2. **MEDIUM — open interest leaked across books.** `oi` was assigned in the gate loop and read in
   the exit loop, so it held whatever the LAST book evaluated left behind. v0 and v2 share a
   geometry so they were unaffected, but **every v1 row recorded v2's open interest**, not its own.
   The gate always used the right value; only the recorded column was wrong — which matters because
   the OI-bucket table is what justified `MIN_OI = 1`. Reproduced against the pre-fix copy
   (v1 row carried 222 when its own legs held 777) and confirmed fixed.
3. **MEDIUM — importing the module ran the whole backtest.** No `__main__` guard, so `import
   deployed_backtest` started a multi-hour run, and the `json.dump` overwrites
   `research/deployed_bt_<window>_rows.json` — a stray import could destroy the stored record. Also
   made the file impossible to unit-test. Fixed, plus an unknown WINDOW argument now exits with a
   usage message instead of silently running OOS.
4. **MEDIUM — the leg cache was written non-atomically.** `json.dump(LEGC, open(CACHE,"w"))`
   truncates on open, so a killed run leaves a fragment. This ALREADY happened on 20-Aug: the cache
   ended up holding a mix of [close, oi] pairs and bare floats. Now writes to a temp file and
   renames.
5. **LOW/MEDIUM — the most recent bar never produced a signal.** `range(20, len(u) - 1)` dropped the
   final bar although nothing looks ahead to i+1, so out-of-sample the newest breakout on every
   symbol was silently discarded. Fixed to `range(20, len(u))`; verified a final-bar breakout is now
   detected.
6. **LOW — the settlement-fallback counter was incremented from four worker threads** without a
   lock, so it under-reported. Now locked.

**CONSEQUENCE: the stored rows files are STALE.** Fixes 1 and 5 both change trade counts. Nothing has
been re-run; `research/deployed_bt_is_rows.json` (17-Aug) and `_oos_rows.json` (18-Aug) still hold
pre-fix results, and so does every number quoted in the UI and studies. A re-run is needed before any
of those figures are quoted again.

### Re-run of both windows on the fixed harness — launched 2026-08-20

Pre-fix rows preserved as `research/prefix_bt_is_rows.json` and `research/prefix_bt_oos_rows.json`
so the impact of the six fixes can be measured rather than assumed. Logs:
`research/rerun_is.log`, `research/rerun_oos.log`. The OOS run now prints `FETCH INTEGRITY: n`,
which is the first direct measurement of whether past OOS runs were losing trades to the network.

### OOS re-run started 20-Aug 15:46 (user instruction)

Started after the 15:40 derivatives close, so there is no contention with the live engine and no
freeze window is needed. Log: `research/rerun_oos.log`; result auto-appended here.

## Fixed-harness OOS finished


### 20-Aug evening: the OOS re-run CRASHED, and why it matters

`TypeError: 'float' object is not subscriptable` at deployed_backtest.py px(). ROOT CAUSE: three
scripts share ONE cache file, `research/cache/oos_legcache_oi.json`, with two different formats.
`deployed_backtest.py` writes and reads `[close, open_interest]`; `dte_sweep.py` and
`dte_sweep_5v10.py` wrote a BARE FLOAT. 6,476 of 37,258 entries (17%) carried the wrong shape.

Two consequences, not one:
1. The harness of record could not run at all. No rows were written, so nothing was corrupted —
   `research/deployed_bt_oos_rows.json` is still the 18-Aug file.
2. **The DTE 5-vs-10 result reported on 20-Aug had the OI gate weakened.** That sweep reads
   tolerantly, treating a bare float as "open interest unknown, let it pass". Practical impact is
   small — OOS OI rejections were only 4-5 because an Upstox candle exists only if the contract
   traded — but the gate was not fully applied and that was not stated at the time.

FIXES: both sweeps now write the pair format, and the harness SANITISES its cache on load, dropping
malformed entries so they refetch with real open interest. Tolerating a bare float was rejected on
purpose: it would silently disable a fidelity gate in the harness of record.

LESSON for the record: a shared mutable cache with no format version is a coupling defect. Any
future script writing into this cache must write `[close, open_interest]`.

## 2026-08-21 · why the measurement kept being re-run, and what changes

User, frustrated and correct: "why u always go back to backtesting sweeps why u dont do it once for
all without error". The honest cause, stated plainly.

**It was never done once. It was copied five times.** 60 commits touch `studies/ndte/`. Each new
question (c/w bands, TP sweep, OI buckets, DTE 7-floor, DTE 5-vs-10) got a COPY of the harness, and
every copy inherited the parent's defects and added its own. The leg-misalignment bug, the
fetch-failure bug and the cache-format bug all propagated exactly this way. A backtest bug does not
crash — it prints a plausible number — so each copy's bug was only found by the next audit.

**And the forward record cannot yet replace it.** Of 18 closed paper trades, 17 were entered BEFORE
the 6-Aug stale-bar fix and are T-1 signals, not this strategy. **The deployed strategy has exactly
ONE closed trade (+Rs3,490) and four open.** That is why the backtest kept being the only instrument
with data in it.

### The change, proposed 21-Aug

1. **This OOS run is the last sweep.** The backtest is closed at ~7/10, ceiling ~8 (no bid/ask, the
   live spread gate is unmodellable). More polishing does not raise it.
2. **ONE harness, imported, never copied.** `deployed_backtest.py` becomes the only source; any new
   question imports its functions instead of duplicating them. The `__main__` guard added 20-Aug
   makes this possible for the first time.
3. **A regression test that locks the answer.** IS must reproduce 1,270 rows and v2 +27.2% /
   v1 +10.3% / v0 +14.4% on the median cohort. Any future edit that moves those fails loudly.
4. **The decision instrument becomes the forward paper record.** At ~8 v1 signals/month it needs
   months, and that is the honest timeline — not another sweep.

### 21-Aug: items 2, 3 and 4 done

- **`studies/ndte/test_harness.py`** — 19 checks, runs in seconds, no network. Covers the live
  hierarchy, both gates, the OI attribution that leaked, TP and expiry exits, `leg()` failure
  semantics, the final-bar breakout, and a GOLDEN FILE locking the in-sample answer
  (v2 217/+27.2%, v1 359/+10.3%, v0 237/+14.4%). **Mutation-tested**: reintroducing the OI leak and
  the silent fetch failure each turn the suite red, and the real file stays green. Run it after ANY
  edit to the harness.
- **The two sweep copies are frozen** with a DO-NOT-COPY banner. `deployed_backtest.py` is the
  single harness of record; new questions import it (the `__main__` guard makes that safe).
- **`studies/ndte/forward_record.py`** — reports the paper record split at the 6-Aug stale-bar fix.
  Deployed strategy: **1 closed trade, +Rs3,490**, 4 open. The 17 earlier trades (+Rs34,162) are
  T-1 signals and must never be pooled with it.
- Item 1 stands: this OOS run is the last sweep.

Open position to watch: **BAJAJ-AUTO is now -125.62 pts** (was -99.35 this morning), entered 29-Jul,
no stop by policy.

### Pushed 21-Aug 08:34 — commits ea7d05c, 4a04c34, d1b116e, ee9f4ac to origin + private
The six-defect harness audit, the shared-cache format fix, the corrected MIN_OI justification, and
the regression suite / freeze / forward-record work. OOS re-run was at 100/113 at push time.

## 2026-08-21 · FINAL OOS re-run landed; every surface reconciled to one set of numbers

`studies/ndte/deployed_backtest.py` OOS finished on the fixed harness. Median cohort:

| book | IS | OOS | agreement |
|---|---|---|---|
| v2 | 78.8% · **+27.2%** [+18.4,+34.7] · 6/6 · n=217 | 83.6% · **+27.2%** [+16.4,+37.2] · 3/3 · n=55 | identical |
| v1 | 79.1% · **+10.3%** [+2.9,+17.1] · 6/6 · n=359 | 79.3% · **+9.5%** [+2.5,+15.9] · 3/3 · n=179 | within a point |
| v0 | 83.1% · +14.4% [+5.9,+21.9] · 5/6 · n=237 | 79.6% · **+3.0%** [−6.2,+11.5] · **1/3** · n=93 | does NOT agree |

**v1's OOS interval now EXCLUDES zero** ([+2.5,+15.9]); the previous run's [−5.0,+13.3] did not.
The six-defect audit did NOT move the result — IS bit-identical, OOS moved at most two points.

**THE BINDING LIMIT IS NOW THE DATA FEED, NOT SAMPLE SIZE.**
`FETCH INTEGRITY: 293 signal(s) dropped` — book-level evaluations abandoned because Upstox would not
answer after six retries (~100-150 unique signal days) against 374 trades kept. Earlier runs lost the
same way and never counted it. **Every OOS n is a FLOOR and the run is NOT reproducible.** No further
sweep fixes this; the cause is vendor availability. Backtest rating drops to 6/10 on that basis.

Reconciled surfaces (the stale +3.7%/+4.8%/−0.7% pair is GONE from the repo): `CLAUDE.md` book table
and evidence paragraph, `studies/README.md`, `engine/ui_terminal.py` (8 figures), and the three stock
`_TG_ANALYSIS` blocks in `engine/engine_runner.py`. **Telegram format verified byte-identical apart
from digits** (3 lines differ, zero wording changes) per the append-only rule. Regression suite green.
Nothing sent to Telegram — user will say when.

### 21-Aug: UI studies tab restructured

New order: **PROFIT AND LOSS (money + signals/mo) FIRST**, then LIVE STRATEGIES, THE WORK BEHIND
THOSE NUMBERS, HOW TO EXECUTE, FULL STUDIES. **Removed from the UI entirely** (kept in git and
memory, per user): the NSE Closing-Auction-Session block and the incident record — a one-line
pointer to studies/NSE_SESSION_CHANGE_2026_08_03.md, STALE_BAR_INCIDENT.md and
DEPLOYED_EVIDENCE_AUDIT.md replaces them. 26 lines dropped. Every stale figure swept from all tabs
(0 remaining).

**Wording corrected in CLAUDE.md and the UI**: v2's IS/OOS match is +27.20% vs +27.24%, a rounding
coincidence, NOT "the same number". Both bootstrap intervals are ~18pp wide. The user caught this
and was right to — presenting it as confirmation reads noise as signal.

### 21-Aug: second harness audit + UI improvement

**One more real defect found and fixed: `+ve yrs` counted a stub year as a full year.**
Out-of-sample 2024 is an Oct-Dec stub holding ONE v2 trade and ONE v0 trade, yet it was reported as
a third confirming year — turning "positive 2 of 2 years plus a single observation" into the much
stronger-sounding "positive 3 of 3 years". Added `MIN_YR_N = 10`; years under it are now printed
as `(+1 stub yr: 2024 n=1)` rather than folded into the ratio. Checked and NOT bugs: no `lot==0`
rows exist in either window, and the 45-day leg-fetch cap never truncates (monthly expiries land
at most ~41 days out).

**UI: the forward paper record is now the FIRST thing on the studies tab**, computed live from the
position files on every refresh. It splits at the 6-Aug fix and refuses to pool the two eras:
deployed strategy 1 closed (+Rs3,490), pre-fix T-1 signals 17 closed (+Rs34,162), plus the open
positions with live points. Verified by rendering the method directly.

### 21-Aug: yfinance fallback was DEAD, now fixed; freeze rule extended

**`yfinance==0.2.32` returned ZERO rows for every ticker** — ^NSEI, ^NSEBANK, ^INDIAVIX, ^BSESN and
even AAPL and ^GSPC. Yahoo changed their API and the pinned version broke, so the engine has had **no
working fallback at all** during Upstox outages (like yesterday's 40-minute one). It failed loudly in
the log every cycle and nobody connected the ERROR lines to "the safety net does not exist".
Upgraded to **1.2.0**; all three call sites re-tested and correct (`_yahoo_intraday_fallback`,
`_yahoo_historical_fallback`, `_yahoo_index_prices`), columns intact, values matching live Upstox.
requirements.txt now pins `>=1.2.0` with the reason.

**Also fixed:** SENSEX silently dropped out of `_yahoo_index_prices` because `^BSESN` carries no
5-minute series for much of the day. Falls back to daily now — SENSEX drives the 0DTE book.

**FREEZE RULE EXTENDED — there are TWO windows, not one.** 09:16–09:45 (0DTE entry) as well as
15:15–15:40 (stock credit). Same mechanism: in-memory once-a-day markers reset on restart. I breached
the morning one at 09:17 today; harmless only because Friday carries no index expiry (NIFTY=Tue,
SENSEX=Thu) and no book was eligible. Verified: 0 positions opened today in either 0DTE book.

**Stub-year correction propagated** to Telegram, UI and CLAUDE.md: OOS "positive every year" is now
"positive in both full years (2024 is a 3-month stub)", and v0 is "1 of 2 full years" not "1 of 3".

## 2026-08-21 · forward record is LIVE, and the 30-trade rule is pre-registered

`data/forward_record.db` (`engine/forward_record.py`), wired into the engine cycle. 34 positions
backfilled. **The 30-trade counter starts at 0** — v2+v1 entered on/after the 6-Aug stale-bar fix
and closed. At ~8 v1 signals/month that is 3-4 months.

**Criteria fixed BEFORE any data** in `studies/FORWARD_RECORD_DECISION_RULE.md`: win rate >=70%,
ROM bootstrap lower bound > -5%, take rate >=40%, no single trade eating >25% of net. ALL FOUR
required. v0 excluded from the lot decision (its OOS interval spans zero).

**What it records that nothing else did:** every REJECTION at the live gates (the take rate — the
fraction of backtest trades actually fillable, unmeasured until now; 7 of 17 on 17-Aug), and
`spread_pct` at entry. P&L stays on MIDS, same basis as both backtest windows — the user was right
that switching to crossing prices would break comparability, since bhavcopy has no bid/ask.

Daily report: `.venv/bin/python studies/ndte/daily_record.py [YYYY-MM-DD]`.

### Correction the user made, and he was right

I described every 0DTE loss as a full-width event. **Measured average loss is well below max**:
NIFTY avg win +Rs1,202 vs avg loss -Rs6,274 (93.2% win, expectancy +Rs693/trade); SENSEX +Rs1,427
vs -Rs4,549 (88.8%, +Rs758/trade). A loss only reaches full width if the index settles beyond the
long strike. The honest concern is narrower: a loss costs ~5 average wins on NIFTY, and at a 6.8%
loss rate one loss per ~15 trades is expected, so 6 winners with no loser is the BASE RATE and
carries no information either way.

### 0DTE forward record — untouched by the stale-bar bug

That bug was about the daily CLOSE for stock breakouts; 0DTE enters at 09:16 off the OPEN. So all
12 closed 0DTE paper trades are valid history: NIFTY 6/6 +Rs4,196, SENSEX 6/6 +Rs6,667.

### 21-Aug: realised loss everywhere, and a sync-timing bug the user's question exposed

**BUG FOUND BY THE USER'S QUESTION** ("hope for intraday on engine you will record actual loss end of
the day"). `sync()` was called inside the 15:36 stock scan, but the 0DTE books settle at **15:40**
(`SETTLE_AFTER`) — four minutes later. An intraday loss would not have reached the DB until the NEXT
trading day. Moved to the MAIN CYCLE, so any settlement lands within seconds. Idempotent, cheap.

**REALISED loss, never max loss** (his correction, and it is right — a credit spread only loses full
width if the underlying settles beyond the long strike):
- **UI**: the forward-record block now has an "Avg loss (REALISED)" column per book, showing
  "no loss yet" where none has occurred, plus the 30-trade counter and rejection count.
- **Telegram**: the portfolio summary now carries `Average win X · average loss Y` per bucket.
  Currently intraday 12/12 avg win Rs+905, no loss yet; month-end 16W/5L avg win Rs+5,040 avg loss
  Rs-8,168. Per-trade RESULT messages with realised P&L already existed.

### 21-Aug: losses can only be realised at expiry — now enforced, not merely configured

User's model, confirmed correct: **no stop on v1/v0/v2, so a loss can only crystallise at expiry
settlement (15:40); profit books any day via take-profit.** Verified on all three surfaces —
harness `BOOKS` has `stop=None` for all three, config carries the unreachable 99.0, and every open
position has `stop_cost=None`. The backtested numbers being decided on ARE no-stop numbers.

**Checking his model against the data found a real hole.** Three historical losses were booked
22–28 days EARLY: GODREJPROP (closed 06-Jul vs 28-Jul expiry), BAJAJ-AUTO (28-Jul vs 25-Aug),
BAJAJFINSV (03-Aug vs 25-Aug). All three carry `stop_cost` = 2x credit, FROZEN IN AT ENTRY when a
reachable stop still existed. Config had removed it; the positions had not. That is the standing
unfixed audit item — no book re-checks frozen exit parameters against current config — and it had
already cost real closes.

**Fixed:** the stop branch in both books now calls `_stop_allowed()`, which refuses unconditionally
and logs a WARNING naming the position. A stale frozen parameter can never again realise a loss
before the underlying has settled. Verified False on both books; no open position carries a stop.

Also this session: `sync()` moved to the main cycle (it ran at 15:36, four minutes before 0DTE
settles at 15:40, so an intraday loss would have reached the DB only the NEXT day); UI and Telegram
now report **average REALISED loss**, never max loss.

### 21-Aug: READMEs de-staled (repo + UI tab)

`README.md` was last touched 17-Aug and still listed **0DTE BANKNIFTY as a live book at 91%**,
deleted from `engine/dte_multi.py` on 20-Aug. Also carried v2 at 87%/~5-6-per-month and v1 at
73%/~16-per-month, both superseded, and omitted v0 entirely. Corrected to the measured OOS figures
(v2 83.6% ~2.4/mo, v1 79.3% ~8/mo, v0 79.6% ~4/mo) and a new **"Where the evidence stands"** section
carries the full IS/OOS table with intervals, the FETCH INTEGRITY caveat, the no-stop enforcement and
the pointer to the forward record and its pre-registered criteria.

The in-app README tab described "THREE 0DTE expiry-day spreads (NIFTY / SENSEX / BANKNIFTY monthly)"
and listed BANKNIFTY among the wired Telegram sources. Both corrected; zero stale BANKNIFTY-as-live
references remain anywhere.

### 21-Aug: every study now says why it exists

Audit: 45 of 64 already stated a **Question** or **Goal** (my first pass grepped only for "why" and
wrongly reported 60 missing — corrected). 16 genuinely lacked one and now carry a
**"Why this study exists."** line written from each file's own content, not templated. Seven
index/summary docs (README, LIVE_STRATEGIES, CONSOLIDATED_PNL, NEXT_ACTIONS, OBJECTIVE_SPEC,
STRATEGY_SUMMARY, WIN_RATE_RESEARCH_LOG) are not studies and are exempt.

Also updated `studies/DEPLOYED_EVIDENCE_AUDIT.md` to the 21-Aug re-run: the 18-Aug figures it
carried (v2 +28.0% n=49, v1 +11.5% n=169, v0 +3.0% n=90, all "3/3 yrs") are superseded, the
"3/3 years" claim corrected to "2/2 full years" (OOS 2024 is a stub with ONE v2 trade), the
FETCH INTEGRITY caveat added, and the v2 cross-window match documented as a rounding coincidence.

**Measured 21-Aug:** parity is NOT a hidden filter — on 6,916 sampled symbol-expiry chains it
derives spot on 98.8%, dropping 1.2% on the 2%-span guard and 0% for want of common strikes. It runs
on EVERY in-sample candidate, so it is the universal spot source, not a patch applied to some.

**Clarified:** bhavcopy DOES carry premiums (`CLOSE`) and open interest (`OPEN_INT`), both 100%
populated. The ONLY thing it lacks is the order book — bid/ask. Earlier wording that implied
"no premium or OI" was loose and the user was right to challenge it.

## 2026-08-21 · IN FLIGHT: universe expansion study, name by name (user request)

PAGEIND-type moves are being missed. NSE F&O has ~206 stock underlyings; UNIVERSE holds 113. Task:
IS + OOS per candidate name (WIN + NET, v2/v1/v0 at deployed configs) for the ~93 outsiders, then
decide which come inside. Note: user wrote "v3" — reading as v2 (no v3 exists). Prior art:
studies/UNIVERSE_EXPANSION.md (2026-07-29 screen that added 13 names) — reuse its shape. The
IS pickle (research/bhav_optstk.pkl) holds ONLY current-universe symbols, so outsiders need a
bhavcopy re-extract from research/cache/bhav_days/ (raw days on disk) before the IS leg can run.
