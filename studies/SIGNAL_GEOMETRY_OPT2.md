# Signal → geometry optimization, iteration 2 (2026-07-31)

**The ask (iteration 2 of the optimization loop):** iteration 1 proved the two-stage machinery
finds REAL band-hold conditions but every geometry died because band-edge structures collect
cheap premium (c/w 0.04–0.18). Two untried syntheses that combine both proven ingredients —
real condition × rich premium: **(A)** re-run the stage-2 credit-spread grids for the strongest
stage-1 conditions with the credit/width floor swept as an ENTRY gate {0.25, 0.30, 0.35, 0.40}
(the condition picks the day, the richness gate picks whether the premium is worth selling —
exactly how the deployed stock fade works); **(B)** earnings IV-crush — T-1 before NSE results,
sell defined-risk premium into the inflated IV, measuring the c/w distribution first.

**VERDICT UP FRONT — filled in after OOS.**

## Data & denominator

- IS: NSE bhavcopy closes 2019→Sep'24 (stocks `/tmp/bhav_cache_stk` 1,418 days; NIFTY
  `/tmp/bhav_nifty_opt` 1,500 days). Underlyings: Upstox daily (scratchpad `sg_underlyings.pkl`).
- OOS: NSE **UDiFF** bhavcopy Oct'24→Jul'26, downloaded this session to
  `/tmp/bhav_cache_stk_oos` + `/tmp/bhav_nifty_opt_oos` (~445 days, WITH per-contract volume) —
  plus an Upstox expired-premium cross-check of the frozen NIFTY config (real chains).
- Costs: house `spf()` per-leg slippage at entry and any early exit; intrinsic settle at
  expiry. Identical to iteration 1 and all prior bhavcopy studies.
- Signals: `sg_signals.pkl` (iteration-1 stage-1 conditions, computed through Jul'26).
- Earnings dates: `studies/ndte/nse_results_dates.csv` — 12 large-caps, 362 usable events,
  272 in IS. Entry = close of the last trading day BEFORE the result is public
  (`first_tradable` − 1 session), so POST_CLOSE announcements enter same-day, intraday
  announcements enter the prior day.
- **Cells searched this iteration: 1,476** (NIFTY cross 432, stock cross 864, earnings 180)
  on top of iteration 1's ~1,572. Winner bar pre-set: ≥5/6 IS years positive AND OOS positive.
- Scripts (session scratchpad): `sg2x_nifty.py`, `sg2x_stk.py`, `sg2x_dl_oos.py`,
  `sg2x_oos.py`, `sg2x_oos_upstox.py`, `sg2x_nifty_check.py`, `sg2x_stk_check.py` + JSONs.

## Synthesis B first — earnings IV-crush: the premium IS rich, the trade is DEAD

The measurement (publishable on its own): on T-1 of 272 IS earnings events, the credit/width
of an iron condor at ±3% strikes is **structurally richer than on normal days for the same 12
symbols — median c/w 0.539 vs 0.415, mean 0.519 vs 0.454, p90 0.700 vs 0.630** (n = 199 event
days vs 11,874 normal days). At the first-OTM strike the lift nearly vanishes (median 0.858 vs
0.818) — the richness lives in the wings, where the market prices the gap.

The trade: 180 cells (side × placement {otm1, ±3%} × width {1,2} × exit {T+1 close,
hold-to-expiry, expiry+stop3} × floor {0…0.40}). **174 of 180 cells lose.** Every T+1-exit
cell is negative (median −17.9%w; the flagship IC-otm1 T+1 = −37.2%w, 2.0% win, 0/6 years).
Hold-to-expiry: median −14.1%w. The 6 positive cells are n ≤ 17 shards at f0.40 (e.g. +66.8%w
on n=5) — selection noise at this denominator. Why the rich premium doesn't pay: the earnings
gap routinely exceeds the extra credit (the directive's guard was right — earnings ARE the
post-breakout-gap tail risk), and a T+1 exit pays the second helping of per-leg slippage on
2–4 legs. **The market prices its own crush correctly. Axis closed.**

## Synthesis A — the richness floor works, but it is also a stale-close magnet

### The honest finding first: floor monotonicity (stocks, OTM1 placement, TP50/hold-to-expiry)

| Floor | comp5d PE w2: n / net/w / yrs+ | nr7_comp PE w2: n / net/w / yrs+ |
|---|---|---|
| none | 11,041 / **−0.5%** / 3/6 | 3,284 / **−1.1%** / 2/6 |
| 0.25 | 9,452 / +0.7% / 3/6 | 2,788 / +0.1% / 2/6 |
| 0.30 | 8,272 / +1.4% / 3/6 | 2,399 / +0.6% / 2/6 |
| 0.35 | 6,052 / +4.0% / 6/6 | 1,729 / +3.1% / 5/6 |
| 0.40 | 3,279 / **+6.7%** / 6/6 | 892 / **+5.0%** / 6/6 |

Monotone in the floor, both conditions, win% flat (~71–72%) throughout — the same
c/w≥0.40 gate that carries the deployed fade, re-derived on compression days instead of
breakout days. IS says: on a compression day, sell the first-OTM put spread ONLY when it pays
≥40% of width, take profit at 50% of credit, else hold to expiry.

### The trap this iteration adds to the house book: a richness floor at FAR strikes selects data errors

The gross winners of the raw grid were edge-placement cells (short at the ±3–5% band edge)
with impossible economics — e.g. nr7_comp edge CE w2 f0.40: +48.7%w, 6/6 years, avg c/w 0.71
at a 5%-OTM stock strike. The volume audit killed them: on the NIFTY equivalent (rsi14_60_70
edge IC w4 f0.25, IS +32.5%w) **28% of entry legs traded ZERO contracts that day**, and the
fattest "credits" (c/w 0.6–0.91) sat precisely on the zero-volume legs — stale closes
masquerading as rich premium (2023-06-21: "credit" 181.8 on width 200). A c/w floor applied
where nobody trades doesn't find overpriced options; it finds prices that aren't there. All
edge-placement floor cells REJECTED on this audit, not on P&L.

The frozen OTM1 stock configs are near-the-money and mostly real (raw-bhavcopy contracts
audit: 19/24 and 20/24 sampled entry legs actually traded; ~7% of legs carry zero OI), but
the stale minority inflates entry credits (e.g. BRITANNIA close 233.65 vs settle 91.9), so IS
+6.7%/+5.0%w are UPPER bounds. The OOS run reports raw and volume-verified numbers separately.

## Frozen configs (pre-registered before any OOS look — `sg2x_frozen.json`)

| # | Config | IS (2019→Sep'24) |
|---|---|---|
| 1 | STK comp5d · OTM1 PE w2 · f0.40 · TP50/hold-exp | n=3,279 · 71.4% · +6.7%w · 6/6 yrs |
| 2 | STK nr7_comp · OTM1 PE w2 · f0.40 · TP50/hold-exp | n=892 · 70.3% · +5.0%w · 6/6 yrs |
| 3 | NIF rsi14_60-70 H10 · OTM1 PE w4 · f0.35 · TP50 | n=64 · 84.4% · +12.7%w · 5/5 yrs |
| 4 | NIF up4 H5 · edge IC w2 · f0.25 · hold | n=46 · 80.4% · +14.1%w · 6/6 yrs (vol clean: 2/184 zero legs) |

## OOS (Oct'24→Jul'26) — PENDING, filled in below

TBD

## Honest verdict

TBD

*Research only — no engine/config changes, nothing deployed, no commits. 2026-07-31.*
