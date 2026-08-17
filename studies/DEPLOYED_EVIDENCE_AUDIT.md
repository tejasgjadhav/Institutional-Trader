# The deployed books' evidence, audited and re-measured (14-Aug-2026)

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

## 5. The production harness — the numbers of record (16-Aug-2026, final)

`studies/ndte/deployed_backtest.py` is the single harness of record. It reached these numbers
through four corrections, each found by an adversarial audit or by the user reading a figure that
could not be true:

1. **Leg alignment.** Option legs were paired by list position, so ~47% of multi-leg windows
   compared prices from different calendar days. Legs are now keyed by date and both must trade on
   the entry day.
2. **Signal population.** v1 was fed the Donchian UNION while live v1 scans **D10 only**
   (`STOCK_CREDIT_DONCHIAN = 10`), and the harness never modelled v1 standing down while v2 holds a
   name.
3. **Corporate-action scale.** `fetch_upstox_historical` returns split-adjusted closes while the
   strike ladders are unadjusted, so on any split or bonus name the harness picked deep-ITM legs,
   collected near-full width and booked fabricated wins. It returned +182.8% ROM and a 1.92:1
   win:loss, both impossible for a defined-risk vertical, and the user caught both. **In-sample
   now derives spot from the option chain by put-call parity** — at the strike where a call and a
   put cost the same, that strike is the forward, and S = K + C − P. Both quotes carry the same
   unadjusted scale as the strikes, so a split cannot desynchronise them. Out-of-sample cannot use
   parity: Upstox expired candles exist only for strikes that traded, and demanding both sides
   returned 0 trades for v2. OOS uses two structural guards instead and is read on the median
   cohort.
4. **One open position per symbol.** Live, each book skips a name it already holds open
   (`stock_credit.py:223`, `stock_credit_v2.py:372`). The harness had only the 3-day gap, so **59%
   of in-sample and 31% of out-of-sample trades were same-book re-entries inside 35 days**. The
   bias had a direction: a winner exits fast and frees the name while a loser stays open, so the
   extra trades were drawn from names still moving against the fade. Modelling the rule **raised**
   every book in **both** windows, which is the confirmation that those trades were adverse.

Also modelled: the cross-book 3-day gap, v0 standing down to v1, premium >= 50, >= 10 DTE, and
exit costs on TP and stop closes. Not modelled, stated plainly: the live bid-ask and OI quote
gate, the 5-new-per-day and 20-open caps, today's lot sizes applied to older trades, and margin as
(width − credit) rather than exchange SPAN.

**Read on the MEDIAN COHORT — c/w 0.40–0.50, where every one of the 21 real live fills sits
(0.39–0.47).** The headline ROM was previously carried by a high-c/w tail: a third of v2's profit
came from trades above 0.65, where margin is tiny and ROM per trade approaches its 488% ceiling.
Those quotes are real on high-priced dense-ladder names, but the live book has never traded one.

| book | band | IS 2019 → Sep-2024 | OOS Oct-2024 → Aug-2026 |
|---|---|---|---|
| v2 | >=0.40 | **82.2%** · **+30.7%** ROM · **6/6 yrs** (n=667) | 82.8% · **+3.7%** · 2/3 yrs (n=58) |
| v1 | >=0.40 | **79.9%** · +19.9% · **6/6 yrs** (n=477) | 79.8% · **+4.8%** · **3/3 yrs** (n=193) |
| v0 | 0.35-0.40 | **83.1%** · +17.8% · **6/6 yrs** (n=569) | 80.4% · **−0.7%** · 2/3 yrs (n=97) |

**All three books are positive in every in-sample year.** In-sample is the better-measured window
(667/477/569 trades, parity spot, six full years) but it is **not independent evidence**: the c/w
gate, the geometry and the exits were all chosen on this data. A precise in-sample number is still
in-sample.

**Out-of-sample cannot rank the books.** Bootstrapped 90% intervals on ROM: v2 **[−27.8%, +39.7%]**,
v1 **[−5.0%, +13.3%]**, v0 **[−14.8%, +12.5%]**. All three span zero. v2's 58 trades include a
four-trade 2024 stub. The point estimates put v1 (+4.8%) and v2 (+3.7%) in a tie, and an earlier
claim in this repo that v1 was clearly ahead of v2 does not survive the fourth correction.

**v0 is the one that changed most.** It reads +17.8% in-sample across six positive years and −0.7%
out-of-sample, against the −11.5% an earlier version of this study reported. It stays live as a
paper forward-test by the user's decision of 15-Aug-2026.

## 6. Rupee calibration — what the books are worth per month (16-Aug-2026, final)

Every trade multiplied by its own current lot size, median cohort, at the deployed take-profit.
The **out-of-sample** column is the one to plan on; in-sample rupees are shown for shape only,
because bhavcopy prices are settlement prints and 85% of rows above ₹50 carry zero open interest.

| book | signals/mo | avg margin | avg WIN | avg LOSS | win:loss | ₹/trade | ₹/month |
|---|---|---|---|---|---|---|---|
| v2 | 2.6 | ₹12,755 | +₹6,022 | −₹10,461 | 0.58 : 1 | +₹3,180 | **+₹8,198** |
| v1 | 8.6 | ₹11,049 | +₹3,887 | −₹10,324 | 0.38 : 1 | +₹1,016 | **+₹8,711** |
| v0 | 4.3 | ₹13,683 | +₹3,815 | −₹13,954 | 0.27 : 1 | +₹335 | **+₹1,443** |

Stock books together pay about **₹18,350 a month at 1 lot**. With the two index books (₹2,775 and
₹3,031) the system totals roughly **₹24,200**, and the standing 80% planning rule puts the number
to plan on at about **₹19,300**. July 2026 realised ₹44,789 across 24 closed trades, which is above
this — that month ran under the old harness's assumptions and included trades the live rules would
now block, so treat it as a good month rather than the baseline.

**Every book loses more on a loser than it makes on a winner**, from 0.58:1 down to 0.27:1. That is
normal for selling credit spreads and it is exactly why the win rate has to stay high: v0 at
80.4% still only clears ₹335 a trade, and a few points of win rate would put it underwater.

