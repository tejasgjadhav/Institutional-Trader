# NIFTY FADE OPTIMIZATION — can the index credit-spread fade be fixed?

**Date:** 2026-07-31 · **Scripts:** `studies/ndte/niftyfade_dl.py` (bhavcopy cache) →
`studies/ndte/niftyfade_grid.py` (IS grid) → `studies/ndte/niftyfade_oos.py` (OOS confirm)
· **Logs:** `/tmp/niftyfade_dl.log`, `/tmp/niftyfade_grid.log`, `/tmp/niftyfade_oos.log`
· **Data:** `/tmp/bhav_nifty_opt` (1,438 days NSE bhavcopy NIFTY OPTIDX, 2019→Sep'24,
legacy+UDiFF), `/tmp/nsei_daily_2019_sep24.csv` (Upstox NIFTY daily OHLC)

## Question

The NIFTY index fade is booked at 54% win / −1.4%w IS (bhavcopy 2019→Sep'24) and has
survived two failed salvage attempts (direction gates — reversed OOS; exit-only sweep —
win% up but net down, `INDEX_FADE_EXIT_SWEEP.md`). Third and last attempt, entry-quality
focused: grid c/w gates × geometry × Donchian window × DTE × exits **in-sample first**
(bhavcopy is free to iterate), then OOS-confirm only survivors on real Upstox premiums.

## Method

- **IS:** NSE bhavcopy 2019→Sep'24, all NIFTY OPTIDX rows daily. Sim mirrors the OOS
  harness (`idxfade_oos_exits.py`): Donchian breakout at daily close → FADE (up-break →
  bear-call CE, down-break → bull-put PE), entry at close, walk daily closes to expiry,
  intrinsic settle from spot, `spf` slippage (1–6%/leg) at entry and exit, re-entry 3d/side.
- **Grid:** DC {5,10,20} × geometry {short-1-OTM/w3, short-2-OTM/w4} × DTE {≥10,≥20}
  (12 trade collections) × c/w gate {none, ≥.40, ≥.45, ≥.50} × exit {hold/stop2×,
  TP-75/stop2×, hold/stop3×, hold/no-stop} = 384 cells, all n-preserving within a collection.
- **Success bar set in advance:** IS win ≥70% AND net ≥ +10%w AND positive ≥5/6 years,
  then OOS ≥ similar.
- **Sanity anchor:** base config (DC10 s1w3 DTE≥10, no gate, hold/stop2) reproduces the
  booked result: n=206, 53.4% win, −3.2%w, 2/6 years (booked: 181 / 54% / −1.4%w — small
  deltas from strike-chain details).

## IS grid — what the 384 cells say (condensed)

Ungated, EVERY collection is negative with the deployed exit (−1.7 to −14.6%w). The only
consistently positive region is **high c/w (≥0.50) + long DTE (≥20)**:

| Collection | ungated hold/stop2 | best gated cell |
|---|---|---|
| DC5 s1w3 D10 | −3.2%w / 54% | cw≥.45 nostop +1.0%w (4/6) |
| DC5 s1w3 D20 | −13.9%w / 40% | cw≥.50 nostop +11.7%w / 56% (4/6) |
| DC5 s2w4 D10 | −2.2%w / 56% | cw≥.50 n=8 only |
| **DC5 s2w4 D20** | −9.8%w / 45% | **cw≥.50 TP75/stop2 +21.8%w / 72.2% (6/6, n=36)** |
| DC10 s1w3 D10 | −3.2%w / 53% | cw≥.45 TP75 +1.7%w; **cw≥.50 = −10 to −14%w** |
| DC10 s1w3 D20 | −14.6%w / 38% | cw≥.50 nostop +9.8%w (4/6) |
| DC10 s2w4 D10 | −3.6%w / 55% | nothing at n≥20 |
| DC10 s2w4 D20 | −10.0%w / 44% | cw≥.50 TP75 +27.5%w / 76% (6/6) but n=21 |
| DC20 s1w3 D10 | −1.7%w / 54% | cw≥.45 stop3 +7.7%w (3/6) |
| DC20 s1w3 D20 | −14.4%w / 37% | cw≥.50 nostop +9.2%w (4/6) |
| DC20 s2w4 D10 | −3.4%w / 54% | nothing at n≥20 |
| DC20 s2w4 D20 | −10.2%w / 44% | cw≥.50 TP75 +40.2%w but n=15 |

- **Breakout-size buckets: no signal** (base collection, quartiles: −3.7 / +2.6 / −10.4 /
  −1.5%w — not monotonic, dead end).
- **Exits alone still fix nothing** (confirms the exit sweep): ungated, no exit turns any
  collection positive except DC5 s2w4 D20 no-stop at −6.1%w best. Entry quality is the lever.
- The c/w≥0.50 gate FAILS on the deployed geometry (DC10 s1w3 D10: −14%w) — rich credit
  on a *tight* 1-OTM/w3 structure at short DTE means the market is pricing a real move.
  It works only on the wider 2-OTM/w4 structure with ≥20 DTE of theta runway.

## The one survivor (of 384) — and its OOS confirmation

**Config: DC5 breakout · short 2-OTM · width 4 · nearest expiry ≥20 DTE · c/w ≥ 0.50 ·
TP-75% of credit / stop 2× credit.**

| Window | n | Win | Net %w | Per-year |
|---|---|---|---|---|
| IS 2019→Sep'24 (bhavcopy) | 36 | 72.2% | **+21.8%w** | 6/6 positive: '19 +27.9 · '20 +19.1 · '21 +14.9 · '22 +36.3 · '23 +48.3 · '24 +1.0 |
| OOS Oct'24→Jul'26 (real Upstox premiums) | 16 | 75.0% | **+32.5%w** | '24 +11.9 (n=3) · '25 +42.0 (n=11) · '26 +11.1 (n=2) |

- IS bootstrap mean%w: p5 +8.7 / p95 +34.3. OOS: p5 +14.0 / p95 +49.7. Both p5 > 0.
- Balanced sides IS (19 CE / 17 PE); trades spread across years (n per year 2–8).
- OOS gate neighborhood also positive (cw≥.40: +19.2%w/73.9%, n=46; cw≥.45: +23.2%w/75.7%,
  n=37), and ungated same-geometry OOS is −1.5%w/49.4% — the gate does the work OOS too,
  it is not the window being generically kind to this geometry.
- Frequency: ~6/yr IS, ~9/yr OOS. This is a THIN book (~1 trade every 6–8 weeks).

## The regime trap, documented (why the obvious c/w gate is NOT the answer)

The stock edge's c/w≥0.40 gate on the **deployed geometry** (DC10 s1w3 D10) looks
spectacular on the OOS window alone: +24.9%w / 79.4% win (n=34, cached 67-trade set). But
the SAME config in-sample 2019→Sep'24 is **−5.0%w / 48.8% / 1 of 6 years positive**
(n=125). Anyone testing only Oct'24→Jul'26 would have shipped it. This is exactly the
Part-11 lesson in reverse — the favorable-regime window flatters gates that failed the
6-year test. Only the ≥0.50 + s2w4 + DTE≥20 cell worked in BOTH periods.

## Honest caveats (do not skip)

- **1 survivor out of 384 cells.** The OOS confirmation is genuine out-of-time on a
  different data source (real Upstox premiums vs bhavcopy settle prices), which is the
  main defense against the multiple-testing charge — but n=36 IS + 16 OOS ≈ 52 trades
  total over 7.6 years. Thin. 2025 carries the OOS result (+42%w on 11 of 16).
- IS uses bhavcopy CLOSE, which for illiquid far strikes is an NSE settle print, not a
  tradeable quote; entry legs were not volume-filtered. OOS real premiums partly answer
  this (net came in HIGHER, not lower), but live fills on a 2-OTM/w4 structure are 4 legs.
- Costs = spf slippage model (1–6%/leg, entry+exit) only; gross of brokerage/STT/fees.
- Close-only daily walk: stops/TPs trigger on closes, not intraday touches; expiry =
  intrinsic at spot close. Same convention as every prior fade study, so comparable.
- c/w ≥ 0.50 on a 2-OTM 4-wide spread = strongly elevated IV; the gate passes ~13% of
  signals and clusters in stress windows. That IS the edge thesis (overpaid fear), but it
  also means the book sits short vol exactly when vol is high — a 2020-style gap through
  both strikes is a −100%w outcome; IS worst single trade was −59%w.
- 2024 IS cell is +1.0%w (weakest year); OOS 2026 YTD is n=2. Neither disproves nor
  proves much at this n.

## Verdict

**The deployed index fade (DC10 · 1-OTM/w3 · DTE≥10) cannot be fixed** — not by exits
(prior study), not by direction gates (Part 11), and not by c/w gates (fails IS, above).
Keep `SWING_CREDIT_ENABLED` judged as-is.

**But the pre-registered bar was cleared by exactly one re-geometried config** — DC5 ·
short 2-OTM · width 4 · DTE≥20 · c/w≥0.50 · TP-75/stop-2× — at 72.2%/+21.8%w IS (6/6
years) and 75.0%/+32.5%w OOS. It behaves like the gated stock edge finally expressed
correctly on the index: rich premium + wide structure + theta runway, ~6–9 trades/yr.
Given two prior salvages died OOS, the honest read is: promising, thin-n, and the ONLY
acceptable next step is a signals-only paper forward-test — no config/engine change, no
capital, and user approval before anything is deployed.
