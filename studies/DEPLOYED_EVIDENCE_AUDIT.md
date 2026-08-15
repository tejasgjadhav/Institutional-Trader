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

## 5. The production harness — the numbers of record (added 15-Aug-2026)

`studies/ndte/deployed_backtest.py` is the single harness of record for the deployed configs,
written under the research-scripts-are-production-code rule. It runs the three books exactly as
the engine trades them: full 113-name universe, date-aligned in both windows, the CROSS-BOOK
3-day re-entry gap, the v1-wins-clash rule (a same-day same-stock signal goes to v1, not v0),
exit costs charged on TP/stop closes, and the impossible-mark stop filter. Not modelled, stated
plainly: the live bid-ask/OI quote gate, the 5-per-day and 20-open caps, and 15:36-15:40 fill
timing versus the close print.

**IS, bhavcopy 2019 → Sep-2024, full universe:**

| book | band | n | WIN | ROM | +ve years |
|---|---|---|---|---|---|
| v2 | >=0.40 | 2,497 | **95.5%** | **+183.2%** | **6/6** |
| v1 | >=0.40 | 3,078 | **92.9%** | **+160.3%** | **6/6** |
| v0 | 0.35-0.40 | 191 | 81.7% | +11.2% | 5/6 |

These supersede the §2/§3 sweep figures where they differ, and every difference traces to a
modelled rule: v2's win rate rises 91.6% → 95.5% because 120 fake stop triggers on impossible
marks no longer fire; v1's ROM falls +173% → +160% because TP closes now pay exit costs; v0's n
falls 424 → 191 because the clash rule hands its overlapping signals to v1 — the engine always
did this and no earlier backtest modelled it. What v0 keeps for itself is a real but small edge:
+11.2% ROM, 5 of 6 years, about one-sixteenth of the gate books per rupee of margin.

**OOS, Upstox expired options Oct-2024 → 15-Aug-2026, full universe (landed 15-Aug):**

| book | band | n | WIN | ROM | +ve years |
|---|---|---|---|---|---|
| v2 | >=0.40 | 91 | **80.2%** | **+31.8%** | **3/3** |
| v1 | >=0.40 | 443 | **79.0%** | **+18.0%** | **3/3** |
| v0 | 0.35-0.40 | 55 | 76.4% | **−11.5%** | 1/3 |

**The gate books are confirmed in both windows on the production harness.** v2 pays +31.8% ROM
out-of-sample at 80.2% win, positive all three years — in line with the old +41%/margin claim and
far below the 38-name slice's +237%, which was a thin lucky draw (n=24). v1 pays +18.0% at 79.0%,
also positive all three years on a real sample (n=443). The IS-to-OOS decay (183% → 32%, 160% →
18%) is the settlement-print optimism the forensics predicted; the direction, the cliff at 0.40
and the year-consistency all hold.

**v0 is negative out-of-sample: −11.5% ROM, 1 of 3 years positive, on its true 55-trade share.**
Against +11.2% in-sample, that is the regime-flip signature this repo has rejected strategies for
before (the index-fade gates, the width-1 recut). Every corrected measurement now agrees v0's
band pays nothing after 2024: +5.2% on the slice at its own geometry, −11.1% at v1's geometry,
−11.5% on the full universe with engine rules. The evidence for keeping v0 live is gone; the
decision to switch it off is the user's.

The ROM column everywhere is an upper bound: bhavcopy marks are settlement prints (9-18% of
exits price off an OI=0 leg). The win-rate column moves far less under cost and mark stress, so
trust it first, and keep the 80%-of-model planning rule and 1-lot sizing regardless.
