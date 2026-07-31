# The 0.30–0.40 credit/width band: not premium-poor, just cut too wide

**Question (user, 2026-07-31):** the union watchlist is full of blocked names sitting at c/w ≈ 0.30.
Is there a configuration — geometry, target, anything — that makes them tradeable at a good win
rate and real net?

**Answer: yes, and it is not a gate change.** Those signals are not short of premium. They are
being priced at a width their premium cannot fill. Buy the wing **1 strike away instead of 4**
and the same signals show c/w ≈ 0.42 — they clear the existing 0.40 gate on their own terms,
and go from losing money to 88% win / +18% return on margin, positive in all six years.

Separately and worth more money: **v2's 3× stop is costing it ~21% of its net.** v1 got the
TP-40/no-stop fix on 30 Jul; v2 never did.

Status: **in-sample complete, out-of-sample running. Nothing deployed.** Per the approval-first
rule, no engine change until the OOS numbers are in and the user has seen them.

---

## Harness faithfulness (run this check before believing anything below)

Same code, same cost model, deployed v2 config, the c/w ≥ 0.40 population:

| | n | win | net % of width | +ve yrs |
|---|---|---|---|---|
| this harness | 340 | 82.9% | +24.6% | 6/6 |
| known target (UNIVERSE_EXPANSION / STOCK_FADE_V2_UNION) | ~370 | 84.1% | +25.7% | 6/6 |

Within noise. Script `studies/ndte/stkfade_lowcw_controls.py`, section A.

**Note on the money metric.** Everything below reports **ROM = return on margin**
(net ÷ (width − credit)). `% of width` is *not* comparable once width changes — a width-1 spread
and a width-4 spread put different capital at risk per contract. ROM is, and it is also what the
₹5L margin constraint actually cares about.

---

## The population

Priced UNION (DC5/10/15/20) signals, bhavcopy 2019 → Sep'24, 113-name universe, reference
geometry short-2-OTM / width-4 / first monthly expiry ≥ 10 DTE:

| reference c/w | n | share | what the engine does today |
|---|---|---|---|
| ≥ 0.40 | 340 | 15.1% | trades |
| **0.30 – 0.40** | **782** | **34.7%** | **blocked — the question** |
| < 0.30 | 1,132 | 50.2% | blocked |

A third of everything the scanner finds is in the band.

---

## 1. The band is genuinely dead at the deployed geometry

| the band, priced at… | n | win | ROM | +ve yrs |
|---|---|---|---|---|
| deployed S2/W4, TP-50, stop-3× | 782 | 74.3% | **−1.1%** | 3/6 |
| S2/W4, TP-40, no stop | 782 | 78.6% | +0.8% | 4/6 |

So the gate is not wrong. At width 4 these are coin-flips paying roughly 1:3 and they lose money.
Removing the stop alone does not rescue them — it moves −1.1% to +0.8%, still breakeven.
**This is the do-nothing baseline every candidate below must beat.**

## 2. Re-cutting the width rescues them

Same 782 signals, wing bought closer:

| geometry (short 2-OTM) | n | win | ROM | net %w | +ve yrs | avg c/w at that width |
|---|---|---|---|---|---|---|
| width 4 (deployed) | 782 | 74.3% | −1.1% | −0.7% | 3/6 | 0.34 |
| width 2 | 737 | 81.7% | +6.1% | +3.8% | 5/6 | 0.39 |
| **width 1** | **680** | **87.8%** | **+18.1%** | +10.5% | **6/6** | **0.42** |

The `avg c/w` column is the whole mechanism. A spread's credit/width is a function of how far the
wing sits. Holding width fixed at 4 strikes and rejecting on c/w rejects names whose **strike
ladder is coarse relative to their premium** — not names whose premium is thin. Today's watchlist
shows it plainly: DIVISLAB's 400-point wing is 5% of spot, BAJAJHLDNG's 400-point wing is 3.6%.

Best cells were stable across the neighbourhood, not one lucky point: every width-1 cell from
short-0-OTM to short-3-OTM and every TP from 40 to 75 came out positive in all 6 years, and every
one of them wanted **no stop**. Full 432-cell grid in `/tmp/lowcw_sweep.json`.

### Bias check — is the width-1 result just a friendlier sample?

Width 1 prices 680 of the 782 (the rest fail short-premium ≥ ₹50 or credit ≥ width). If the 102
dropped were the losers, the comparison would be rigged. They are not:

| | n | win | ROM | +ve yrs |
|---|---|---|---|---|
| the 680, priced at deployed W4 | 680 | 74.4% | −0.9% | 2/6 |
| the 102 dropped, priced at deployed W4 | 102 | 73.5% | −2.2% | 3/6 |
| the 680, priced at W1 TP-40 no-stop | 680 | 87.8% | **+18.1%** | 6/6 |

Same signals, same window, only the geometry differs. The gain is geometry.

### Physical settlement — checked, no new exposure

NSE stock options are physically settled, so a narrower spread reaching expiry in the money is an
operational event, not just a P&L one. It does not get worse:

| | reaches expiry | short ITM at expiry |
|---|---|---|
| deployed W4 | 13% | 11% |
| candidate W1 | 13% | 12% |

## 3. Days-to-expiry is a dead end

The other structural knob is which expiry the engine sells (`STOCK_CREDIT_MIN_DTE = 10`). More
days means more premium, which is exactly what the band appears to lack — so it is the obvious
suspect. It is not the answer:

| band, short-2-OTM, TP-40, no stop | DTE ≥ 10 | DTE ≥ 20 | DTE ≥ 30 | DTE ≥ 40 |
|---|---|---|---|---|
| width 4 | +0.8% ROM | −0.6% | +2.8% | +15.1% *(n=105)* |
| width 1 | **+18.1%** | +18.1% | +18.0% | +26.7% *(n=50)* |

At width 1 the result is flat from 5 to 30 days — DTE adds nothing. At width 4 it only looks
useful past 40 days, where n collapses to 105 and the trade is held ~51 days. Deployed DTE ≥ 10
is fine. Width was the variable all along.

## 4. The deployable form: adaptive width

Not "add a width-1 book". Keep the c/w ≥ 0.40 gate exactly as it is, and let the engine pick a
width the signal can support. All rules on the full priced population, IS 2019 → Sep'24:

| rule | trades/mo | win | ROM | total net | +ve yrs |
|---|---|---|---|---|---|
| **DEPLOYED** W4 fixed, gate 0.40, TP-50, stop-3× | 4.9 | 82.9% | +58.1% | 9,414 pts | 6/6 |
| **NOSTOP** W4 fixed, gate 0.40, TP-40, no stop | 4.9 | 89.4% | **+70.4%** | 11,403 pts | 6/6 |
| **ADAPT-W** widest of {4,2,1} clearing 0.40 | 13.0 | 88.2% | +51.0% | 15,574 pts | 6/6 |
| **ADAPT-41** W4 if it clears 0.40, else W1 if IT clears | **11.5** | **89.9%** | +58.7% | **14,147 pts** | 6/6 |
| ADAPT-1ANY W4 if clears, else W1 **ungated** | 28.7 | 85.9% | +20.6% | 14,711 pts | 6/6 |

**ADAPT-41 wins**: +50% more total net than deployed, 2.3× the trades, and a *higher* win rate
(89.9% vs 82.9%). Where it comes from:

| source | n | win | ROM | net contribution | avg width |
|---|---|---|---|---|---|
| c/w ≥ 0.40 (unchanged trades, minus the stop) | 340 | 89.4% | +70.4% | +11,403 pts | 113 |
| 0.30–0.40 band, re-cut to W1 | 355 | 89.6% | +29.9% | +1,720 pts | 31 |
| below 0.30, re-cut to W1 and still clearing 0.40 | 101 | 93.1% | +48.2% | +1,024 pts | 44 |

Two guardrails the table enforces:

- **Keep the gate after the re-cut.** ADAPT-1ANY drops it and ROM falls +58.7% → +20.6%; its
  sub-0.30 slice earns +2.3%, i.e. nothing. The gate remains the edge, exactly as
  `CW_BUCKET_ANALYSIS` concluded — it is just being applied to the wrong fixed width today.
- **Skip width 2.** ADAPT-W allows it and lands below ADAPT-41. W2 trades are mediocre (+6.1% ROM
  standalone); going straight from 4 to 1 is better than stepping through.

## 5. Honest limits

- **The added trades are small.** A band W1 trade nets +3.43 points/lot on ~19 points of margin,
  against +27.69 on ~48 for a core gated trade — roughly an eighth of the rupees each. The rule
  more than doubles trade count to add ~24% more money. More fills, more slippage surface, more
  positions to carry.
- **Marginal ROM is well below core ROM** (~+30% on the added trades vs +70% on the core). It is
  additive, not a second v2.
- **Liquidity at width 1 — checked live, and it is fine.** `ndte/lowcw_live_liquidity.py`
  re-priced today's 18 blocked names at width 1 against live Upstox quotes. The adjacent long
  strike carries 23,000 to 8.5 M OI at 0.4–2.5% bid-ask on every liquid name — well inside the
  engine's 6% / 100-OI gates. One reject: BAJAJHLDNG (OI 75, 47% spread), which the existing
  liquidity gate already catches. This was the biggest practical unknown and it is closed.
- **The rule is selective, and that is the point.** On today's tape width 1 lifts c/w by ~+0.07
  to +0.10 (DIVISLAB 0.26 → 0.38, SBIN 0.29 → 0.37) but **nothing clears 0.40** — zero rescued.
  That is consistent with the backtest, not against it: ADAPT-41 takes only **355 of the band's
  782 signals (45%)**. Fewer than half the band clears the gate even re-cut. Thin-premium days
  still correctly produce no trade. Do not expect the watchlist to empty out.
- **432 cells were swept.** Guarded by neighbourhood stability, 6/6 positive years, and a matched
  sample — but it is still a search, and out-of-sample is the test that matters.

---

## Out-of-sample — PENDING

`studies/ndte/stkfade_lowcw_oos2.py`, Upstox expired options Oct'24 → date. Confirms exactly two
pre-registered claims and nothing else: (1) the gated book improves with TP-40/no-stop at
unchanged geometry, (2) the band is dead at W4 and tradeable at W1. Results to be appended here
before any recommendation becomes a deployment.

## Scripts

| file | what it does |
|---|---|
| `ndte/bhav_stk_parquet.py` | one-time compaction of the 1,500-file bhavcopy CSV cache → `/tmp/bhav_stk.pkl`. The old per-row `pd.to_datetime` loader cost ~75 min per run; this is 45 s once, seconds thereafter. |
| `ndte/stkfade_lowcw_geometry.py` | the 432-cell IS sweep (geometry × target × stop) on the band |
| `ndte/stkfade_lowcw_controls.py` | faithfulness, the everywhere-control, trade size, no-gate |
| `ndte/stkfade_lowcw_matched.py` | matched-sample bias check + settlement exposure |
| `ndte/stkfade_lowcw_dte.py` | days-to-expiry sweep |
| `ndte/stkfade_lowcw_adaptive.py` | the deployable adaptive-width rules |
| `ndte/stkfade_lowcw_oos2.py` | focused OOS confirmation |
