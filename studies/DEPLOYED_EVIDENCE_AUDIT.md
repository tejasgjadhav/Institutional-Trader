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

## 5. The production harness — the numbers of record (15-Aug-2026, corrected)

`studies/ndte/deployed_backtest.py` is the single harness of record. A second adversarial audit
caught the first version of it feeding v1 the wrong signal population, so these numbers post-date
two fixes, not one. The harness now models the live hierarchy exactly:

- **v2** scans the Donchian UNION (D5/10/15/20); **v1 scans Donchian-10 only** (`STOCK_CREDIT_DONCHIAN = 10`).
- **v1 stands down while v2 holds the name** (`stock_credit.py:221`), tracked to v2's actual exit date.
- **v0 stands down for v1** on a same-day clash. One book takes a stock on a day, never two.
- Cross-book 3-day re-entry gap, premium >= 50, >= 10 DTE, exit costs charged on TP/stop closes,
  and stop triggers on arbitrage-impossible marks discarded.

Not modelled, stated plainly: the live bid-ask and OI quote gate, the 5-new-per-day and 20-open
caps, and fills in the 15:36-15:40 window rather than at the close print.

| book | band | IS 2019 → Sep-2024 | OOS Oct-2024 → Aug-2026 |
|---|---|---|---|
| v2 | >=0.40 | **95.4%** · +182.8% ROM · 6/6 yrs (n=2,526) | **81.2%** · **+32.5%** · 3/3 yrs (n=96) |
| v1 | >=0.40 | **89.4%** · +84.5% · 6/6 yrs (n=805) | **81.7%** · **+14.6%** · 3/3 yrs (n=268) |
| v0 | 0.35-0.40 | 80.1% · +12.4% · 5/6 yrs (n=322) | 76.8% · **−3.9%** · 2/3 yrs (n=99) |

**Both gate books are positive in every year of both windows.** That is the confirmation the audit
set out to test, and it survives on corrected code. v1's population fell from 3,078 to 805 in-sample
once it scanned D10 only and deferred to v2 — its edge is real every year, but its true share of the
flow is about a quarter of what the earlier harness implied.

**v0 does not clear its costs out-of-sample.** It reads +12.4% ROM in-sample and −3.9%
out-of-sample. The user decided on 15-Aug-2026 to keep it live as a paper forward-test rather than
switch it off, to see whether real fills disagree with the backtest. Nothing was changed.

## 6. Rupee calibration — what the books are worth per month (15-Aug-2026)

Every trade multiplied by its own **current lot size**, from the live contract feed. Rupees come
from the **out-of-sample window only**: the in-sample window prices bhavcopy settlement prints and
returns figures that are not credible (v2 reads ₹51,380 a trade in-sample against ₹14,956
out-of-sample, on ₹13,531 of margin — nobody makes 380% a trade).

| book | signals/mo | avg margin | avg WIN | avg LOSS | win:loss | ₹/trade | ₹/month |
|---|---|---|---|---|---|---|---|
| v2 | **4.3** | ₹12,620 | +₹20,916 | −₹10,872 | **1.92 : 1** | **+₹14,956** | **+₹64,311** |
| v1 | **11.9** | ₹10,764 | +₹6,048 | −₹9,810 | 0.62 : 1 | +₹3,149 | **+₹37,509** |
| v0 | **4.4** | ₹13,596 | +₹3,818 | −₹13,439 | 0.28 : 1 | **−₹191** | **−₹842** |

With the two index books (~₹2,775 and ~₹3,031) the stock-plus-index total is about **₹106,700 a
month at 1 lot**, and the standing 80% planning rule puts the number to plan on at about
**₹85,400**. July 2026 realised ₹44,789 across 24 closed trades, so treat ₹85,400 as a ceiling and
one live month as the floor.

Two things the table says that the win rates hide. **v2 carries the book**: it fires only 4.3 times
a month, but it is the one book whose average winner outsizes its average loser, at 1.92:1.
**v0 wins 76.8% of its trades and still loses money**: a winner pays ₹3,818 and a loser costs
₹13,439, so the arithmetic does not clear at that win rate.

