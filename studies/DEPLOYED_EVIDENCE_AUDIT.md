# The deployed books' evidence, audited and re-measured (14-Aug-2026)

**Why this study exists.** The deployed books were re-measured because an adversarial audit found the harness itself was wrong, not the strategy. Every out-of-sample validation had paired the two option legs BY POSITION rather than by date, so roughly 47% of multi-leg windows compared prices from different calendar days. The bug survived dozens of runs because it crashes nothing and prints plausible numbers, and because each new study copy-pasted the same harness, so the cross-checks were the same bug agreeing with itself. This file is the re-measurement, and the running record of every defect found since.


The user asked for the same adversarial audit that killed the low-c/w band study to be run on the
DEPLOYED strategy. An audit agent read every validating script behind the live books, checked each
for the two bug classes found on 13–14 Aug (positional leg alignment, stale settlement marks), and
the two numbers it flagged as unproven were then re-measured with corrected code the same day.

## 1. What the audit found

| Book | Validating evidence | Verdict |
|---|---|---|
| 0DTE NIFTY FLIP | single-day real-trade prints, volume-gated, intrinsic settle, 4-leg costs | **SURVIVES** — immune to both bug classes by construction |
| 0DTE SENSEX | same harness | **SURVIVES** (no volume floor applied — minor caveat) |
| v2 stock credit IS | `stkfade_union.py`, date-keyed by day | CLEAN alignment; but marks are settlement prints (85% of ₹50+ bhavcopy rows carry OI=0) and costs were entry-only |
| v2 stock credit OOS | `stkfade_oos_union.py:69-78` | **BUGGED** — positional leg walk, the same defect that collapsed the band study |
| v1 OOS | `stkfade_v1_oos_exits.py:72-76` | **BUGGED** — same defect |
| v0 OOS | `stkfade_lowcw_oos2.py:162-190` | **BUGGED** — same defect, and the c/w band classification itself was computed on misaligned candles |
| Swing NIFTY/FINNIFTY | already ruled regime-dependent by its own studies | unchanged |

The forward record since the 6-Aug stale-bar restart held 4 resolved trades, all wins — a sample
that proves nothing either way.

## 2. The re-measurement — date-aligned OOS, Oct-2024 → Aug-2026

`cw_band_sweep_dated.py` extended to the deployed band. Both legs must trade on entry day; the
path marks only on days both legs traded; 38-name slice; each book at its own geometry and exit.

| band | v2 (S2/W4 TP-50 stop-3×) | v1 (S1/W3 TP-40 no-stop) | v0 (S2/W4 TP-40 no-stop) |
|---|---|---|---|
| **≥0.40 (deployed)** | **91.7% · +237% ROM** (n=24, 2/2 yrs) | **84.4% · +54% ROM** (n=109, **3/3 yrs**) | 91.7% · +217% (n=24, 2/2) |
| 0.35–0.40 (v0's live band) | 75.7% · +2.7% (n=37) | 71.1% · −11.1% (n=121) | **83.8% · +5.2%** (n=37, 1/2 yrs) |
| 0.30–0.35 | 72.1% · −11.7% | 76.7% · +1.2% | 78.7% · −1.8% |
| 0.25–0.30 | 71.6% · −5.5% | 77.6% · −7.5% | 79.1% · −1.9% |

**The deployed gate survives its corrected test.** v2 at ≥0.40 comes back 91.7% win and +237% ROM
on the corrected code, against the 87% and +41%/margin claimed from the bugged script. v1 comes
back 84.4% against the claimed 86%. The cliff at 0.40 is the sharpest feature in the table: the
same code, the same names and the same window pay +54% to +237% above the gate and −12% to +1%
below it. The c/w gate is the edge, measured clean for the first time.

**v0's live band did not recover.** Its corrected OOS cell is 83.8% win and +5.2% ROM against the
deployed claim of 90.7% and +19.4%. Its IS leg was always marginal (+1.9% ROM, 4 of 6 years), so
v0 now runs on the weakest corrected evidence of the three stock books. Whether it keeps its slot
is the user's decision; nothing was changed.

## 3. The IS forensics — how much of the bhavcopy edge is artifact

Re-walked from `/tmp/bhav_optstk.pkl` (1,358 sessions, full universe) at the deployed band with
OI tracked per exit and exit-side costs charged:

| book | WIN | ROM entry-only → with exit costs | exits on an OI=0 leg | impossible stop marks |
|---|---|---|---|---|
| v2 | 91.6% (unchanged) | +176.3% → **+172.1%** | 443 of 2,406 (18%) | 120 |
| v1 | 93.1% (unchanged) | +173.0% → **+168.8%** | 267 of 2,918 (9%) | 0 |

Exit costs move the IS ROM by about 4 points and the win rates by nothing. The artifact share is
real but bounded: roughly one exit in ten (v1) to one in five (v2) prices off an OI=0 print, and
v2's 120 impossible stop marks are 5% of its trades. The IS magnitude is soft by that much, not
hollow.

## 4. Standing conclusions

1. **The deployed c/w ≥ 0.40 edge is confirmed on corrected code, in both windows.** Direction
   and cliff are real; magnitudes remain backtest-grade (settlement prints IS, thin n OOS, no
   live liquidity gates in either), so the 80%-of-model planning rule stays.
2. **The 0DTE index books were already clean.** Nothing to change.
3. **v0 is the weakest book after correction** (+5.2% OOS, +1.9% IS in its band) and its slot is
   an open user decision.
4. **Every future OOS script joins legs BY DATE.** The positional pattern is banned; three
   deployed-book validations carried it silently for weeks.
5. Stops cannot rescue the sub-0.35 bands (20-cell sweep, `CW_BAND_BY_BOOK.md` addendum): every
   stop multiple in 0.30–0.35 is worse than no stop, and the lone positive cell (S2/W4, 2.0×,
   +3.6%) is a one-parameter spike between negative neighbours.

Scripts: audit agent transcript summarised here; re-measurement `cw_band_sweep_dated.py` (bands
extended to ≥0.40); forensics `/tmp/is_forensics.py` → `studies/ndte/is_forensics_deployed.py`.

## 5. The production harness — the numbers of record (17-Aug-2026, final)

`studies/ndte/deployed_backtest.py` is the single harness of record. It reached these numbers
through SIX corrections. Each one changed the answer, and each was found either by an adversarial
audit or by the user reading a figure that could not be true.

1. **Leg alignment.** Option legs were paired by list position, so ~47% of multi-leg windows
   compared prices from different calendar days. Legs are now keyed by date, and both must trade on
   the entry day.
2. **Signal population.** v1 was fed the Donchian UNION while live v1 scans **D10 only**
   (`STOCK_CREDIT_DONCHIAN = 10`), and the harness never modelled v1 standing down while v2 holds a
   name.
3. **Corporate-action scale.** `fetch_upstox_historical` returns split-adjusted closes while the
   strike ladders are unadjusted, so on any split or bonus name the harness picked deep-ITM legs,
   collected near-full width and booked fabricated wins. It printed +182.8% ROM and a 1.92:1
   win:loss, both arithmetically impossible for a defined-risk vertical, and the user caught both.
   In-sample now derives spot from the option chain by put-call parity.
4. **One open position per symbol.** Live, each book skips a name it already holds open. The
   harness had only the 3-day gap, so **59% of in-sample and 31% of out-of-sample trades were
   same-book re-entries inside 35 days**. Winners exit fast and free the name while losers stay
   open, so the extra trades came from names still moving against the fade. Modelling the rule
   raised every book in both windows.
5. **Open interest (the audit's blocker).** Bhavcopy publishes a CLOSE for every listed contract,
   and for one that never traded that CLOSE is NSE's theoretical settlement price, not a print.
   **24% of 1-OTM and 30% of 2-OTM short legs carried zero open interest.** Both legs must now clear
   `OI >= 100` units, matching the live gate. This removed 70% of v2's in-sample trades, because
   both legs must pass and the long wing is the illiquid one. **It roughly halved in-sample ROM,
   which is the single largest correction in this document.**
6. **Expiry settlement (the user's fix).** Settlement derived intrinsic from the underlying close,
   which reintroduced correction 3 at settlement whenever the parity lookup failed. His point: at
   expiry an option IS its intrinsic value, so read the two legs' own expiry-day closing prices and
   skip the underlying entirely. The old path is now last resort and counts itself — it was needed
   on **19 legs in-sample and 8 out-of-sample** across the whole history.

Also corrected on 17-Aug: **no book has a working stop, and none can.** A stop priced as a multiple
of the credit is unreachable above c/w 1/3, because a vertical can never cost more than its width.
At the deployed c/w 0.40 a 3x-credit stop sits at 1.2x the width while full loss arrives at 1.0x.
Live already had `STOCK_CREDIT_STOP_MULT = 99.0`, but the UI advertised a "3x stop, almost never
reached" and the harness modelled `stop=3.0`. Both were wrong; both were fixed. All three books are
take-profit only, with risk capped by the bought wing.

**Read on the MEDIAN COHORT — c/w 0.40–0.50, where every one of the 21 real live fills sits
(0.39–0.47).** ROM is reported two ways: pooled in strike POINTS, and pooled in RUPEE margin, which
is what an account actually commits. Lot sizes vary roughly twentyfold inversely with price, so the
two differ materially and **the rupee column is the one to use**.

| book | IS 2019-01-01 → 2024-07-05 | OOS Oct-2024 → Aug-2026 |
|---|---|---|
| v2 | 77.5% · **+25.3% ROM-₹** · ₹5,427/trade · 6/6 yrs (n=191) | 82.8% · **+27.3% ROM-₹** · ₹3,477/trade · 2/3 yrs (n=58) |
| v1 | 80.1% · **+14.1%** · ₹2,828/trade · 5/6 yrs (n=322) | 80.2% · **+10.4%** · ₹1,145/trade · **3/3 yrs** (n=192) |
| v0 | 81.9% · **+13.6%** · ₹3,412/trade · 6/6 yrs (n=216) | 80.4% · **+4.1%** · ₹565/trade · 2/3 yrs (n=97) |

**The two windows now agree**, at +25.3% against +27.3% for v2 and +14.1% against +10.4% for v1.
That is worth stating carefully rather than celebrating. **It is not independent confirmation.** The
morning's figures were +30.7% and +3.7%, an eightfold gap, and it closed because two different fixes
were applied to two different windows: the OI gate pulled in-sample down, and rupee-weighting pushed
out-of-sample up. Both are defensible from first principles and neither was chosen to make the
numbers meet. But the prediction was that in-sample would fall to out-of-sample, and instead the
other half rose through a mechanism that was not being tested. Treat the agreement as encouraging,
not as proof.

**What in-sample can and cannot claim.** It is the better-measured window — 191/322/216 trades over
five and a half years, spot from parity, open interest enforced. It is **not independent evidence**,
because the c/w gate, the geometry and the exits were all chosen on this data. Note also that the
bhavcopy pickle ends **2024-07-05**, so the "sixth year" is a six-month stub.

**What out-of-sample can and cannot claim.** Bootstrapped 90% ROM intervals span zero for all three
books: v2 [−27.8%, +39.7%], v1 [−5.0%, +13.3%], v0 [−14.8%, +12.5%]. v2's 58 trades include a
four-trade 2024 stub. **This window cannot rank the books.** v1 is the best-measured of the three at
192 trades and 3 of 3 positive years; v2 pays more per trade and fires a third as often.

**Still not modelled, stated plainly:** the live bid-ask gate, the 5-new-per-day and 20-open caps,
current lot sizes applied to older trades, margin as (width − credit) rather than exchange SPAN, and
out-of-sample has no OI gate (its candles exist only for contracts that traded, so it is largely
redundant there, but the two windows are not identical experiments).

**An untested assumption sits under all of it.** `STOCK_CREDIT_MIN_DTE = 10` has no study behind it
in this repo. Every study that mentions DTE holds it fixed at 10 while sweeping something else, and
the only "DTE sweep" on record belongs to the rejected low-c/w rescue. The rule pushes the books
into far expiries where strikes are thin — the same illiquidity correction 5 now filters out — so it
may be creating the problem the OI gate removes. Sweeping it is the obvious next test.

## 6. Rupee calibration — what the books are worth per month (17-Aug-2026)

Every trade multiplied by its own current lot size, median cohort, at the deployed take-profit.
The out-of-sample column is the one to plan on.

| book | signals/mo | ₹/trade | ₹/month |
|---|---|---|---|
| v2 | 2.6 | +₹3,477 | **+₹9,040** |
| v1 | 8.5 | +₹1,145 | **+₹9,733** |
| v0 | 4.3 | +₹565 | **+₹2,430** |

Stock books together pay roughly **₹21,200 a month at 1 lot**. With the two index books (₹2,775 and
₹3,031) the system totals about **₹27,000**, and the standing 80% planning rule puts the number to
plan on near **₹21,600**. July 2026 realised ₹44,789 across 24 closed trades, above this — that
month ran under the old assumptions and included trades the current rules would block, so read it as
a good month rather than the baseline.

**Every book loses more on a loser than it makes on a winner.** That is normal for selling credit
spreads and it is exactly why the win rate has to stay high. v0 wins four trades in five and still
clears only ₹565 each.

## 7. Open interest: the gate, and what the buckets actually say (17-Aug-2026)

The gate exists as a **fidelity fix**, not an edge filter. An exchange CLOSE on a contract that never
traded is a theoretical settlement price rather than a fillable quote; pricing a backtest off those
inflates it, and gating them out roughly halved the in-sample ROM. That argument does not require
open interest to predict anything.

The user pressed the separate question — is there evidence that MORE open interest earns more? — and
the answer changed as the measurement improved.

**First pass, coarse buckets, 100-unit floor:** the buckets looked unordered, so the conclusion was
"open interest does not predict returns" and the live floor was dropped to `> 0`, which is the only
rule the fidelity argument supports.

**Second pass, full window and finer buckets:** the pattern is not unordered. It decays.

| OI (lots) | v2 n | v2 ROM-₹ | v0 n | v0 ROM-₹ |
|---|---|---|---|---|
| 1–2 | 23 | **+37.2%** | 12 | +25.6% |
| 2–5 | 39 | **+38.2%** | 35 | **+26.1%** |
| 5–10 | 38 | +26.8% | 19 | +9.7% |
| 10–25 | 36 | +24.1% | 39 | +8.0% |
| **25+** | **60** | **+2.4%** | 124 | +7.8% |

**The thinnest contracts pay the most and the most liquid pay almost nothing.** That is backwards for
a liquidity story, and it is the classic signature of stale pricing: illiquid contracts carry closes
nobody transacted at, so the backtest books wins that could not have happened. The most trustworthy
cell is the least attractive one — v2 at 25+ lots, n=60, pays **+2.4%**.

Two readings survive and the in-sample window cannot separate them. Either the illiquid marks are
flattering the result, in which case the `> 0` floor is too loose and should rise; or illiquid names
genuinely carry richer premium, in which case the floor is correct and the decay is an edge.

**The out-of-sample window is the deciding test**, because an Upstox expired-option candle exists
only for a contract that actually traded — phantom trades cannot appear there at all. If the decay
persists out-of-sample it is real; if it vanishes, the in-sample low-OI cells are artifacts and the
floor must go up. **That run is in flight and nothing changes until it lands.**

Recorded plainly: the 10-lot and 5-lot floors deployed earlier on 17-Aug were justified on SIGNAL
COUNTS rather than returns, which was an error, and both were reverted. Live the gate is close to
inert either way — on 17-Aug the bid-ask check blocked all four names this one blocked, plus six
more. Spread is the binding liquidity constraint; open interest is the floor beneath it.

## 8. What is measured, and what is still open (17-Aug-2026, end of day)

**Measured on the corrected harness, in-sample only** (2019-01-01 → 2024-09-30, 1,418 sessions,
median cohort):

| book | n | WIN | ROM-₹ | ₹/trade | +ve yrs |
|---|---|---|---|---|---|
| v2 | 217 | 78.8% | +27.2% | ₹5,798 | 6/6 |
| v1 | 359 | 79.1% | +10.3% | ₹2,016 | 6/6 |
| v0 | 237 | 83.1% | +14.4% | ₹3,460 | 5/6 |

**Still open, all three waiting on the same out-of-sample run:**

1. **The headline out-of-sample numbers.** No valid figure exists for that window on the corrected
   harness. Every previously published OOS number predates at least one of the corrections in §5.
2. **Whether the open-interest floor should be above zero** (§7).
3. **Whether v1's minimum DTE should move from 10 to 25** (`MIN_DTE_SWEEP.md`). In-sample it is worth
   about ₹7,300 a month, and in-sample is exactly the window that cannot be trusted to say so.


## 9. FINAL — both windows on the corrected harness (18-Aug-2026)

The out-of-sample run completed on 18-Aug. These are the first numbers in this repo measured
identically on both windows: open interest required on both legs at entry AND on every exit-check
day, legs joined by date, parity spot in-sample, expiry settled from each option's own close, one
open position per symbol, the live hierarchy, exit costs charged, no stop.

| book | IS 2019 → Sep-2024 | OOS Oct-2024 → Aug-2026 |
|---|---|---|
| v2 | 78.8% · **+27.2%** ROM-₹ [+18.4, +34.7] · 6/6 yrs (n=217) | 83.6% · **+27.2%** [+16.4, +37.2] · **2/2 full yrs** (n=55) |
| v1 | 79.1% · **+10.3%** [+2.9, +17.1] · 6/6 yrs (n=359) | 79.3% · **+9.5%** [+2.5, +15.9] · **2/2 full yrs** (n=179) |
| v0 | 83.1% · +14.4% [+5.9, +21.9] · 5/6 yrs (n=237) | 79.6% · **+3.0%** [−6.2, +11.5] · **1/2 full yrs** (n=93) |

**SUPERSEDED 21-Aug-2026 — these are the RE-RUN figures.** The 18-Aug numbers that stood here
(v2 +28.0% n=49, v1 +11.5% n=169, v0 +3.0% n=90, all "3/3 yrs") came from the harness BEFORE a
six-defect audit. Two things changed and both matter:

1. **"3/3 years" was wrong** and is now "2/2 full years". Out-of-sample 2024 is an Oct–Dec stub
   holding ONE v2 trade and ONE v0 trade. Counting a single observation as a confirming year turned
   "positive in both full years plus one trade" into a much stronger-sounding claim. `MIN_YR_N = 10`
   now reports short years as stubs instead of folding them into the ratio.
2. **The audit did NOT move the result.** In-sample came back bit-identical, out-of-sample moved by
   at most two points. That is the outcome that says the conclusion never rested on the bugs.

**And the binding limit is now the data feed, not the sample.** The re-run printed
`FETCH INTEGRITY: 293 signal(s) dropped` — book-level evaluations abandoned because Upstox would not
answer after six retries, roughly 100–150 unique signal days against 374 trades kept. Earlier runs
lost trades the same way and never counted them. **Every OOS `n` above is a FLOOR and the run is not
reproducible.** No further sweep fixes this; the cause is vendor availability.

**On the v2 match.** +27.2% in both windows is +27.203% against +27.245% at full precision — a
rounding collision, not a match. Both bootstrap intervals are ~18 points wide, so two draws landing
0.04pp apart is luck. Read it as agreement well inside the error bars, never as the same number.

**Parity is not a hidden filter.** Measured 21-Aug on 6,916 sampled symbol-expiry chains: it derives
spot successfully on 98.8%, dropping 1.2% on the 2%-span guard and 0% for lack of common strikes.
It runs on EVERY in-sample candidate, so it is the universal spot source, not a patch for some.

**v2 and v1 agree across the two windows to within one point** — 27.2 against 28.0, and 10.3
against 11.5 — on independent data with identical gating. That is the first genuinely like-for-like
comparison this system has produced, and it holds. Note this is convergence between windows that
were NOT adjusted toward each other, unlike the 15-Aug episode recorded in §5.

**v0 does not agree, and it is the weak book.** +14.4% in-sample against +3.0% out-of-sample, and
positive in only 1 of 3 out-of-sample years. It clears ₹411 a trade because a loser costs three
times a winner. It stays live as a paper forward-test by the user's decision of 15-Aug.

### Rupee calibration, out-of-sample, at current lot sizes

| book | signals/mo | avg WIN | avg LOSS | win:loss | ₹/trade | ₹/month |
|---|---|---|---|---|---|---|
| v2 | 2.2 | +₹6,274 | −₹9,645 | 0.65 : 1 | +₹3,675 | **₹8,003** |
| v1 | 7.5 | +₹3,838 | −₹9,758 | 0.39 : 1 | +₹1,263 | **₹9,490** |
| v0 | 4.0 | +₹3,814 | −₹13,199 | 0.29 : 1 | +₹411 | **₹1,644** |

Stock books **₹19,137/month** at 1 lot. With the two index books (₹2,775 and ₹3,031) the system
totals about **₹24,943**, and the 80% planning rule puts the number to plan on near **₹19,955**.

Every book loses more on a loser than it makes on a winner. That is normal for selling credit
spreads and it is exactly why the win rate has to stay high.

### The open-interest question, settled

§7 recorded an in-sample pattern where ROM DECAYED as open interest rose — v2 paid +38.2% at 2–5
lots and +2.4% at 25+ — which looked like stale illiquid marks flattering the result and argued for
raising the floor above zero.

**Out-of-sample that pattern does not appear.** Nearly every trade sits in the 25+ bucket and the
low-OI cells are almost empty: v2 has 1, 4, 5 and 8 trades in its bottom four buckets. This is the
confirmation the question needed. An Upstox expired-option candle exists only for a contract that
actually traded, so the phantom low-OI trades that inflated in-sample cannot occur there at all.
**The in-sample decay was an artifact, the fidelity argument was right, and the floor at `> 0` is
correct. Do not raise it.**

### Still open

The **out-of-sample DTE sweep** — whether v1's minimum tenor should move from 10 days to 25. The
in-sample sweep says yes, worth about ₹7,300 a month (`MIN_DTE_SWEEP.md`), but v1's take-profit
slope already inverted between windows once, so an in-sample-only DTE result deserves the same
suspicion. That run is in flight; results land in `research/DTE_OOS_RESULT.txt`. **Nothing changes
until it does.**


---

*Superseded figures.* Everything published before 17-Aug-2026 predates at least one of the six
corrections above and must not be quoted. The ones most likely to resurface: v2 "87% win /
+41%/margin", "95.4% / +182.8% ROM", "+30.7% IS vs +3.7% OOS", the ₹64,311/mo and ₹106,736/mo
totals, and any reference to a 3x stop.
