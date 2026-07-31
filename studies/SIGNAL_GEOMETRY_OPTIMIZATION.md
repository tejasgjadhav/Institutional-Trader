# Signal → geometry two-stage optimization (2026-07-31)

**The ask (user's methodological directive):** stop testing canned strategies with fixed exits.
Do what built the winning books: STAGE 1 — mine raw conditions for a base rate (directional
follow-through or stays-in-band) ≥65% over 1–10 day horizons; STAGE 2 — for each survivor,
optimize the payoff geometry (credit structures on real NSE bhavcopy premiums, plus
asymmetric cash exits) jointly for win% AND net. Freeze the top-3 on IS, confirm on real
Upstox expired premiums Oct'24→Jul'26.

**Verdict up front: the machinery works, the conditions are real, and the money still is not
there. Stage 1 found 53 genuine band-hold conditions (0 directional). Stage 2 converted the
best of them into 80–98%-win credit structures that were positive 5–6 of 6 IS years. The
frozen #1 (98.3% win, +9.7%/width IS, 6/6 years) came back FLAT out-of-sample (−0.1%w): two
full-width wipeouts in 38 trades erased 36 winners. Nothing here displaces the deployed
gated-fade books. One cell (up4 iron condor) stays mildly positive OOS and is watch-list
material at best.**

## Data & method

- **Underlying:** Upstox daily OHLC, NIFTY + the 113-stock universe, 2018-06→2026-07
  (fetched 2026-07-31; scratchpad `sg_underlyings.pkl`).
- **IS options:** NSE bhavcopy closes — stocks `/tmp/bhav_cache_stk` (1,418 usable days,
  2019→Sep'24), NIFTY `/tmp/bhav_nifty_opt` (1,500 days ≥2019, incl. weeklies). 91% of the
  entry legs of the top cell had non-zero traded volume that day (stale-close check).
- **OOS options:** Upstox expired-instruments daily premiums, Oct'24→Jul'26 — real chains,
  real closes, fetched per trade (same harness as `stkfade_v1_oos_exits.py`).
- **Costs:** the house `spf()` per-leg slippage (min 1%, max 6% of premium, 60/prem) charged
  at entry AND at any early exit; intrinsic settlement at expiry (no exit slippage), same as
  every prior bhavcopy study. Cash exits were never reached (no directional survivors).
- **Multiple-testing denominator:** stage 1 = 1,260 cells (32 conditions × class × 4 horizons
  × band grid + directional). Stage 2 = 168 NIFTY + 144 stock geometry cells. Total ≈ 1,572
  cells searched to produce 3 frozen configs. Judge everything below with that denominator
  in mind.
- Scripts (session scratchpad): `sg_fetch.py`, `sg_stage1.py`, `sg_stage2_nifty.py`,
  `sg_stage2_stk.py`, `sg_probe.py`, `sg_freeze_check.py`, `sg_oos_nifty.py`;
  results JSONs alongside.

## Stage 1 — condition mining (IS = 2019→Sep'24)

Conditions at each close (NIFTY + 113 stocks): NR7/NR4/inside-bar, consecutive up/down runs,
RSI(14) and RSI(2) bands, distance-from-20/50DMA bands, 5-day-range compression/expansion
percentile, ATR5/ATR20 compression, post-big-move states, expiry-week / month-start.
Outcomes per horizon H∈{1,3,5,10}: **band-hold** P(max |close move| ≤ X within H days) and
**directional** P(up at H). Baselines are **matched** (per-symbol unconditional rates weighted
by each symbol's condition-day count) — pooled-universe lifts that just pick low-vol names
die on this. Survivor bar set in advance: n≥150 and (band ≥65% with lift ≥+5pts) or
(direction ≥65%/≤35% with |lift| ≥8pts).

**Result: 53 band-hold survivors, 0 directional survivors** (best directional lift anywhere:
ATR-compression P(up,5d) 42.0% vs base 53.8 — n=162, below bar). The 53 collapse into two
families:

| Family | Best cells (rate / matched base / n) | Raw OOS rate (Oct'24→Jul'26) |
|---|---|---|
| **NIFTY calm-strength** (up3/up4 runs, RSI14 60–70, RSI14>70, RSI2>95, ext>50DMA) | up4 H5 ±2%: 75.3%/55.4/182 · rsi14_60-70 H10 ±3%: 66.8%/53.6/391 · rsi14_60-70 H5 ±3%: 91.6%/79.6/391 | 77.8%/36 · 86.3%/73 · 94.5%/73 — **holds** |
| **Range compression** (comp5d, NR7×compression) | nr7_comp STK H5 ±5%: 75.2%/69.0/7,006 · comp5d STK H5 ±5%: 74.6%/69.3/36,060 | 80.4%/1,922 · 80.5%/10,612 — **holds** |

The raw conditions are genuine and persist out-of-sample. After strength, NIFTY drifts
quietly; after compression, stocks stay compressed. The question was always whether the
option market underprices this. Per-year: every cell's weakest year is 2020 (COVID), still
at/above baseline.

## Stage 2 — geometry grids on real bhavcopy premiums (IS)

Band-hold → sell premium at the band edges: short strike = first strike beyond ±X%, long W
strikes further; sides {iron condor, PE-only, CE-only}; NIFTY weeklies, expiry = first ≥H
days; exits TP{50%,none} × stop{3×credit,none}; stocks add {close-at-day-H vs
hold-to-expiry}. Reentry 3d. 168 NIFTY + 144 stock cells.

**NIFTY** — 24 of 168 cells pass (win ≥80%, net ≥+3%w, ≥5/6 years positive, n≥100). The
consistent pattern across every calm-strength condition: **PE side pays, CE side loses**
(quiet drift up: the sold put is the edge, the sold call fights the drift — 44/56 PE cells
positive vs 37/56 CE cells negative). comp5d on NIFTY is dead — 22 of its 24 cells ≤0, best
+0.6%w: compression = cheap premium = nothing worth selling. Strength ≠ compression: the
sellable state is the one where premium is still bid.

Top IS rows (net = % of width, after per-leg slippage):

| Config | n | Win | Net/w | Yrs+ | Per-year %w |
|---|---|---|---|---|---|
| rsi14_60-70 H10 ±3% **PE w4 hold/no-stop** | 181 | **98.3%** | **+9.7%** | 6/6 | 19:+15.6 20:+20.9 21:+9.0 22:+4.3 23:+2.4 24:+6.9 |
| rsi14_60-70 H10 ±3% IC w4 hold/no-stop | 165 | 86.7% | +9.3% | 5/6 | 23:−1.4 the miss |
| up4 H5 ±2% **IC w4 hold/stop3** | 101 | 80.2% | +6.7% | 6/6 | 19:+7.6 20:+10.9 21:+0.9 22:+11.7 23:+2.6 24:+4.8 |
| ext_up50 H5 ±3% **IC w4 hold/no-stop** | 177 | 90.4% | +3.8% | 6/6 | max yr +9.9, min +1.4 |

Reality check on the #1 (from `sg_freeze_check.py`): avg credit 23.9 pts on width 200
(c/w ≈ 0.08–0.12), median DTE 14, avg win +21.3 pts vs avg loss −91.8 pts, only 3 losers in
181 — including one full-width −185.8 (Jan'22). 2023 avg credit was 6 pts: the "edge" in
calm years is selling ₹450 of premium per lot against ₹15,000 of width risk. The IS P&L is
credit-vintage-weighted: 2019–20 (credits 36–47 pts) contribute 60% of the pooled profit.

**Stocks (nr7_comp / comp5d, monthly options, short strikes at ±4–5%)** — 144 cells, and the
a-priori NR7-band cell answers plainly:

| Config | n | Win | Net/w | Yrs+ | Note |
|---|---|---|---|---|---|
| comp5d H5 ±5% PE w2 **hold-to-expiry** | 10,241 | 83.8% | **+2.1%** | 5/6 (2022 −3.0) | best stock cell |
| comp5d H5 ±5% CE w2 hold-to-expiry | 11,163 | 81.2% | +1.9% | 5/6 (2024 −7.1) | opposite year misses |
| comp5d H5 ±5% IC w2 hold-to-expiry | 9,584 | 69.4% | +1.5% | 5/6 | |
| nr7_comp H5 ±5% CE w2 hold-to-expiry | 3,293 | 82.1% | +2.6% | **4/6** | 2022 +11.7 carries it |
| nr7_comp H5 ±5% PE w2 hold + stop3 | 2,934 | 77.0% | +0.6% | 5/6 | |
| **every close-at-day-H variant** | — | 13–62% | **−1.0 to −15.4%** | — | see below |

Two structural findings. (a) **The day-H time exit — the exit that actually matches the
5-day band-hold claim — loses in all 72 of its cells**: closing a monthly stock spread after
5 days pays the second helping of per-leg slippage before meaningful theta accrues. The only
positive stock cells are hold-to-expiry, i.e. mostly *generic* monthly theta selling on
low-vol names with the condition as a mild tilt — not the band edge doing the work.
(b) The best honest stock cell (+2.1%w, 83.8% win) is **strictly inferior to the deployed
gated stock fade (+5.3%w, same cost model, t=+13.78)** while using the same margin. It did
not make the frozen top-3 (its IS net trails all three NIFTY configs), so no OOS budget was
spent on it.

## Frozen top-3 → OOS confirmation (real Upstox expired premiums, Oct'24→Jul'26)

Frozen on IS before any OOS look (`sg_frozen.json`), n-preserving paths fetched once:

| # | Frozen config | IS (2019→Sep'24) | **OOS (Oct'24→Jul'26)** | Verdict |
|---|---|---|---|---|
| 1 | rsi14_60-70 H10 ±3% PE w4 hold/no-stop | 181tr · 98.3% · +9.7%w · 6/6 | **n=38 · 94.7% win · −0.1%w** (2024 −43.1 / 2025 +2.2 / 2026 +3.0) | **FAIL — flat** |
| 2 | up4 H5 ±2% IC w4 hold/stop3 | 101tr · 80.2% · +6.7%w · 6/6 | **n=20 · 80.0% · +3.2%w** (2024 +26.3 / 2025 +9.1 / 2026 −25.1) | weak pass, n too small |
| 3 | ext_up50 H5 ±3% IC w4 hold/no-stop | 177tr · 90.4% · +3.8%w · 6/6 | **n=11 · 100% · +11.8%w** (all 2025) | n far too small |

Config 1's autopsy: **two full-width wipeouts in 38 trades** — 2024-10-01 (credit 8.4,
settle 200, net −192.8 pts) and 2025-03-26 (credit 11.2, settle 200, net −190.0). Each
wipeout costs ~10–20 winners; the IS period served one such event in 181 trades, the OOS
period served two in 38. Post-hoc exit rescue attempts on the SAME paths (flagged post-hoc,
not frozen): hold/stop3 → −0.2%w, TP50/stop3 → −1.9%w. **The family fails OOS under every
exit.** The win rate held (94.7%!) — the payoff did not. Same lesson as the manufactured-83%
demo in `CHAMPION_STRATEGY_SWEEP.md`, now demonstrated on a genuine, OOS-persistent
condition: a real band-hold edge of +13pts lift is still not enough when the premium
collected at the band edge is 4–12% of the width you are risking.

## Honest verdict

1. **Stage 1 is real.** 53 conditions with matched-baseline band-hold lift, and the lifts
   persist raw in Oct'24→Jul'26. The mining method (matched baselines, pre-set bars,
   counted denominator) is reusable as-is.
2. **Stage 2 IS looks glorious and does not survive.** 98%-win/6-of-6-years on 5.7 years of
   bhavcopy was still a short-tail time bomb: OOS delivered tail events at ~3× the IS
   frequency and the #1 config landed at −0.1%w. This is the repo's third demonstration
   (after the index fade and the flush-gate) that 6/6 positive years in one 2019–24 pass
   ≠ edge — this time with the entry CONDITION provably real.
3. **Why it fails where the deployed books don't:** the deployed stock fade sells c/w ≥ 0.40
   — ₹40 collected per ₹100 risked, post-breakout IV. These band-edge structures collect
   c/w 0.04–0.18. The two-stage method re-derived the house rule from the opposite
   direction: **the condition doesn't make the trade; the price of the premium does.** A
   65–75% band-hold with 8% credit-to-width is a worse business than a 54% win with 40%.
4. **Nothing new is deployable.** Config 2 (up4 IC, +3.2%w OOS, n=20, 2026 negative) and
   config 3 (+11.8%w, n=11) are the only survivors and both are under-powered; leave them
   as paper watch-list entries only if the user wants a tracker — no engine or config
   changes. The NR7-band + credit-geometry cell the directive flagged was tested in full
   (stocks & NIFTY): the band-hold rate is real (75.2% vs 69.0 base, n=7,006, persists OOS),
   but the geometry money is not — best +2.1%w only when held to expiry (which is no longer
   the band trade), negative under the band-matched day-5 exit, and everywhere below the
   deployed fade book on identical costs.
5. **Searched:** ~1,572 cells for 3 frozen configs, 1 weak OOS pass. At this denominator a
   +3%w on n=20 is indistinguishable from selection noise.

*Research only — no engine/config changes, nothing deployed, no commits. 2026-07-31.*
