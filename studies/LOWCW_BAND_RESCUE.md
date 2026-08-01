# The 0.30–0.40 credit/width band: one-sided REJECTED, two-sided CONFIRMED out-of-sample

**Question (user, 2026-07-31):** the union watchlist is full of blocked names sitting at c/w ≈ 0.30.
Is there a configuration — geometry, target, anything — that makes them tradeable at a good win
rate and real net?

**Answer: as a one-sided spread, no. As a TWO-sided one, in-sample yes — see section 9.** Selling the
opposite side as well takes combined credit/width from 0.32 to 0.65 and the 0.30-0.35 band from
+3.5% to +24.8% ROM in-sample (5 of 6 years). That is IN-SAMPLE ONLY and the previous in-sample
winner here died out-of-sample, so it is not deployed. Splitting the band also found one live cell:
The 0.30-0.35 half (the names actually filling the watchlist) is dead in every test. The 0.35-0.40
half at the DEPLOYED geometry with TP-40/no-stop is positive in both windows (+1.9% IS, +19.4% OOS,
90.7% win, 3/3 OOS years) — the deferred two-tier gate, finally validated on 2019-24, and the
validation is marginal. Paper forward-test material, not a deployment. See section 7.

In-sample the answer looked like yes, and it looked strong: re-cutting the wing from 4 strikes to
1 turned the band from −1.1% return on margin into **87.8% win / +18.1% ROM, positive in all six
years**, on 680 trades, surviving a matched-sample bias check, a month-block bootstrap (p5 +26%)
and a live liquidity probe. Out-of-sample on real Upstox premiums it collapsed to
**74.3% win / +1.4% ROM — worse than doing nothing** — and 2026 is negative for every variant.

That is the whole result. A 432-cell search found a winner; the winner was a regime artifact.
This repeats the index-fade salvage of July (CLAUDE.md Part 11): six positive years inside one
regime is not out-of-sample evidence, and the 2019→Sep'24 bhavcopy window is one regime.

The second finding — dropping v2's 3× stop — is **not confirmed either**, though it is harmless
rather than wrong: in-sample it gained +21% relative net, out-of-sample it is a wash (n=48).

**Nothing deployed. Nothing recommended.** The standing conclusion of `CW_BUCKET_ANALYSIS` is
reinstated: below c/w 0.40 the win rate stays respectable and the money does not follow.

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

## 2. Re-cutting the width rescued them — IN-SAMPLE ONLY (this is the result that failed)

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

## 4. What the in-sample result implied — SUPERSEDED, never deployed

Recorded for the file, not as a recommendation. Not "add a width-1 book": keep the c/w ≥ 0.40 gate exactly as it is, and let the engine pick a
width the signal can support. All rules on the full priced population, IS 2019 → Sep'24:

| rule | trades/mo | win | ROM | total net | +ve yrs |
|---|---|---|---|---|---|
| **DEPLOYED** W4 fixed, gate 0.40, TP-50, stop-3× | 4.9 | 82.9% | +58.1% | 9,414 pts | 6/6 |
| **NOSTOP** W4 fixed, gate 0.40, TP-40, no stop | 4.9 | 89.4% | **+70.4%** | 11,403 pts | 6/6 |
| **ADAPT-W** widest of {4,2,1} clearing 0.40 | 13.0 | 88.2% | +51.0% | 15,574 pts | 6/6 |
| **ADAPT-41** W4 if it clears 0.40, else W1 if IT clears | **11.5** | **89.9%** | +58.7% | **14,147 pts** | 6/6 |
| ADAPT-1ANY W4 if clears, else W1 **ungated** | 28.7 | 85.9% | +20.6% | 14,711 pts | 6/6 |

**ADAPT-41 won in-sample** (and then failed the held-out window — see the verdict): +50% more total net than deployed, 2.3× the trades, and a *higher* win rate
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

## 5. Honest limits (written before the OOS run — every one of these held, and the result still failed)

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
  sample — but it is still a search, and out-of-sample is the test that matters. It was, and it
  failed. See the verdict section.

---

## Out-of-sample — THE VERDICT

`studies/ndte/stkfade_lowcw_oos2.py`, Upstox expired options **Oct'24 → Jul'26**, 38 of the 113
names (every 3rd by position in `config.UNIVERSE` — an arbitrary slice w.r.t. performance; the
endpoint throttles to ~7 s/call and the full universe needed ~30k calls). Signals seen:
**48 gated · 109 band · 198 below**. Two claims were pre-registered before the window was touched.

### CLAIM 2 — the band rescue: **FAILED**

| the band, OOS Oct'24→Jul'26 | n | win | ROM | +ve yrs | per-year |
|---|---|---|---|---|---|
| S2/W4 TP-50 stop-3× *(do nothing)* | 109 | 76.1% | +1.9% | 1/3 | +38% / −1% / −2% |
| S2/W4 TP-40 no-stop | 109 | 81.7% | +2.2% | 2/3 | +34% / +0% / −2% |
| S1/W1 TP-40 no-stop | 103 | 79.6% | **+0.1%** | 2/3 | +15% / +2% / −6% |
| **S2/W1 TP-40 no-stop** *(the IS winner)* | 101 | **74.3%** | **+1.4%** | 2/3 | +39% / +4% / **−7%** |
| S2/W1 TP-50 no-stop | 101 | 75.2% | +4.0% | 2/3 | +40% / +5% / −3% |

Against in-sample **87.8% win / +18.1% ROM**. The win rate fell 88% → 74% and the money went to
zero. The best variant (TP-50, +4.0%) beats doing nothing by 2 points of margin — inside noise on
n=101, and negative in 2026. **No configuration rescues the band.**

Note what did *not* happen: the band is not catastrophic, it is *flat*. That is the same shape
`CW_BUCKET_ANALYSIS` found — win rate holds up because a TP exit books small winners early, and
net money collapses because the payoff is lopsided. The width re-cut changed the geometry without
changing that.

### CLAIM 1 — remove v2's stop: **not confirmed, a wash**

| c/w ≥ 0.40, geometry unchanged, OOS | n | win | ROM |
|---|---|---|---|
| TP-50, stop-3× *(deployed)* | 48 | 95.8% | +219.4% |
| TP-40, no stop | 48 | 97.9% | +204.5% |
| TP-50, no stop | 48 | 97.9% | +221.0% |
| TP-75, no stop | 48 | 95.8% | +229.1% |

In-sample the no-stop version gained +21% relative (+70.4% vs +58.1%). Out-of-sample all four are
indistinguishable — because at a 96% win rate over these 48 trades the 3× stop almost never binds,
so there is nothing for its removal to save. Not evidence against it; not evidence for it.

**Do not change v2's exits on this.** If the case is ever revisited it needs the full universe
(n=48 here vs ~200 in the earlier full-universe OOS studies) and this window is an unusually
favourable regime — +219% ROM is not a number to reason from. The v1 TP-40/no-stop change of
30 Jul rests on much stronger ground (242 OOS trades) and is untouched by this.

### Why in-sample lied

The IS window (2019 → Sep'24) and the OOS window (Oct'24 →) are different volatility regimes; the
repo's own IS/OOS boundary exists for exactly this reason. Every guard that was run — neighbourhood
stability across 20 width-1 cells, 6/6 positive years, matched sample, month-block bootstrap p5
+26%, 32/34 symbols positive — passed, **and none of them detected this**. They test consistency
*within* a regime. Only a genuinely held-out window tests across one. Worth remembering the next
time a sweep produces a clean-looking survivor.


---

## 7. Sub-band split — the pooled test buried a live cell (user challenge, same session)

The 432-cell sweep and the OOS run both treated 0.30-0.40 as one bucket. `CW_BUCKET_ANALYSIS`
reports the halves behaving very differently, so pooling could hide a live upper half under a dead
lower one. Split (`ndte/stkfade_lowcw_subband.py` OOS, `_subband_is.py` IS):

**OOS Oct'24 -> Jul'26** (38 names; upper n=43, lower n=66)

| | do nothing (W4 TP-50 stop-3x) | **W4 TP-40 no-stop** | W1 re-cut TP-40 |
|---|---|---|---|
| upper 0.35-0.40 | 79.1% · +12.1% · 2/3 | **90.7% · +19.4% · 3/3** | 75.0% · +0.3% · 1/3 |
| lower 0.30-0.35 | 74.2% · −2.6% · 1/3 | 75.8% · **−5.2%** · 1/3 | 73.8% · +1.8% · 2/3 |

**IS 2019 -> Sep'24** (upper n=310, lower n=472)

| | do nothing | **W4 TP-40 no-stop** | W1 re-cut TP-40 |
|---|---|---|---|
| upper 0.35-0.40 | 72.9% · −1.4% · 4/6 | 77.4% · **+1.9%** · 4/6 | 88.6% · +23.6% · 6/6 |
| lower 0.30-0.35 | 75.2% · −0.9% · 3/6 | 79.4% · +0.2% · 3/6 | 87.3% · +15.5% · 6/6 |

1. **The width re-cut is dead, and the split makes the rejection stronger** — excellent IS in BOTH
   halves (+23.6% / +15.5%, 6/6 yrs each), dead OOS in BOTH (+0.3% / +1.8%). No ambiguity.
2. **0.30-0.35 is dead everywhere** (IS +0.2%, OOS −5.2%). The names sitting at c/w 0.30 in the
   watchlist — the ones that prompted the question — are specifically the dead half. Keep blocking.
3. **One live cell, and it is NOT a geometry change: 0.35-0.40 at the DEPLOYED width with TP-40 and
   no stop.** Positive in both windows: +1.9% ROM IS (4/6 yrs), **+19.4% ROM / 90.7% win / 3/3 yrs
   OOS**. Consistent with CW_BUCKET_ANALYSIS's OOS +9.2% of width for this bucket (this run: +12.2%).

### This settles the deferred two-tier gate

The 0.35-0.40 tier was spec'd on 2026-07-16 and left un-deployed because it could not be validated
on 2019-24 (stock-option bhavcopy purged). It can now. **Verdict: real but marginal.** +1.9% ROM
in-sample with 2 of 6 years negative, against the core book's +58-70%. The added trades earn about
a thirtieth of the core's return on margin, and the cell only works paired with TP-40/no-stop —
which the OOS run says is neutral on the core book.

**Recommendation: paper forward-test a 0.35 tier with TP-40/no-stop. Do NOT deploy on this.**
n=43 out-of-sample and an in-sample leg inside noise of zero is not a deployment case. Nothing was
changed in the engine.

---

## 8. The last untested lever — a calm-regime filter on 0.30–0.35 — also fails

Everything structural had been tried: 432 configurations (geometry as strike-steps and as
percent-of-spot, targets, stops), a DTE sweep, adaptive-width rules, and the sub-band split. The one
lever left was a **conditional entry filter**, and there was a strong in-house prior for exactly one:
the 0DTE book's **validated** calm-regime filter (skip when 5-day realized vol is elevated), which
took it from 85.0% to 87.8% win. Same mechanism — a short-premium book is paid for fear already in
the price, so it should do worst on a hot tape. Thin credit **plus** a hot tape is the natural
suspect for why this band loses.

Pre-registered before looking: *0.30–0.35 entries taken when the underlying's rv5 is LOW outperform
high-rv5 entries, enough to turn the band positive.* Bar: positive in both windows, stable across a
threshold neighbourhood, n ≥ ~100, IS first — and if IS does not clearly turn positive, the OOS run
is not worth its 3–5 hours of throttled API calls.

`ndte/lowcw_regime_filter.py`, 506 band trades, 2019 → Jul 2024:

| rv5 cut | calm side (rv5 ≤ cut) | hot side (rv5 > cut) |
|---|---|---|
| 20th pct (0.79%) | 79.4% · +4.5% | 81.9% · +3.3% |
| 30th pct (0.91%) | 77.0% · **−1.3%** | 83.3% · +5.8% |
| 40th pct (1.07%) | 77.8% · +3.4% | 83.8% · +3.6% |
| median (1.21%) | 79.4% · +5.3% | 83.4% · +1.1% |
| 60th pct (1.42%) | 80.3% · +2.7% | 83.2% · +5.4% |

Unfiltered baseline: 81.4% win, +3.5% ROM. **Refuted.** The calm side is not better, and the hot side
carries the *higher* win rate at every single cut — the reverse of the hypothesis. ROM swings between
−1.3% and +5.3% with no monotonic structure, which is what a variable with no relationship looks like.
No threshold survives the neighbourhood test, so per the pre-registered bar the OOS run was not made.

### The more important observation

This run rebuilt the bhavcopy cache from scratch (the old one was lost when `/tmp` was cleared) and it
ends **Jul 2024 rather than Sep 2024**, with 108 symbols instead of 113. On that slightly different
data the SAME band at the SAME config reads **+3.5% ROM, positive 5 of 6 years** — against the
**+0.2%, positive 3 of 6** measured earlier. Two months of data and five symbols moved the in-sample
estimate by three points of margin and two positive years.

That is the real lesson of this whole study, and it is worth more than the filter result: **the
0.30–0.35 band's in-sample signal is not stable enough to lean on in either direction.** The binding
evidence remains the held-out window, where the band returned **−5.2% on margin**. It stays rejected,
and this closes the last open lever.

---

## 9. The one thing that DOES work on 0.30–0.35: sell BOTH sides

Every earlier attempt changed *where* the single spread sits (offset, width, expiry) or *when* it is
taken (regime filter). None addressed the actual defect: at c/w 0.30 the trade does not collect
enough premium for the risk it carries. A condor attacks that directly — sell the fade side **and**
the opposite side. Credit roughly doubles while width barely moves, because at expiry only ONE side
can finish in the money when the wings do not overlap.

Pre-registered, with in-house precedent: the FLIP-CONDOR HYBRID on 0DTE NIFTY was validated and
deployed on exactly this reasoning. `ndte/lowcw_condor.py`, 2019 → Jul 2024:

| 0.30–0.35, TP-40 of total credit | n | win | ROM | +ve yrs | combined c/w |
|---|---|---|---|---|---|
| one side (baseline) | 506 | 81.4% | **+3.5%** | 5/6 | 0.32 |
| + opposite side, its c/w ≥ 0.10 | 336 | 64.3% | **+24.8%** | 5/6 | 0.65 |
| + opposite side, its c/w ≥ 0.20 | 333 | 64.6% | +25.3% | 5/6 | 0.65 |
| + opposite side, its c/w ≥ 0.30 | 236 | 62.7% | **+34.6%** | 5/6 | 0.68 |

Combined credit/width goes **0.32 → 0.65**, i.e. the structure clears the 0.40 level that is the
book's proven edge and the one-sided trade could never reach. Stable across the whole opposite-side
floor (0.10 → 0.30), positive 5 of 6 years, n = 236–336. TP-50 shows the same shape (+20% to +34%).

Note the direction of the change: **win rate FALLS 81% → 64% while net rises about sevenfold.** Every
other candidate in this study did the reverse — flattering win rate, no money. This is the payoff
ratio finally being right, which is the failure mode `CW_BUCKET_ANALYSIS` warned about, inverted.

There is a structural reason, not merely a fitted one: on an up-breakout the fade side is a bear-call,
so the opposite side is a bull-put sold *below a rising stock* — the side least likely to be breached.
The structure is paid twice against one-sided risk.

### It works on the 0.35–0.40 band too — and better

The same test on the half v0 actually trades (TP-40, same window):

| band | one side | + opposite ≥0.10 | + opposite ≥0.20 | + opposite ≥0.30 |
|---|---|---|---|---|
| 0.30–0.35 (dead half) | 81.4% · **+3.5%** | 64.3% · +24.8% | 64.6% · +25.3% | 62.7% · **+34.6%** · 5/6 |
| **0.35–0.40 (v0's band)** | 78.8% · **+11.0%** | 64.7% · +46.6% | 65.5% · +50.2% | 64.8% · **+65.7%** · **6/6** |

Combined c/w on v0's band reaches **0.73**. Both bands respond, both improve monotonically as more is
demanded of the opposite side, and the better band responds more — coherent behaviour rather than one
lucky cell.

**So the actionable version is not a new book for the dead band. It is upgrading v0 from one-sided to
two-sided:** the same signals it already takes, roughly 6× the return on margin in-sample.

### Status: PROMISING, IN-SAMPLE ONLY. Not deployed, not recommended yet.

Two hard caveats:

1. **The last in-sample winner in this very study died out-of-sample.** The width-1 re-cut showed
   +18.1% ROM, 6/6 positive years, matched-sample clean and bootstrap p5 +26% — and returned +1.4%
   on held-out data. This condor result is *weaker* on years (5/6) than that one was. Per the
   pre-registered bar, a positive in-sample result buys the OOS run and nothing more.
2. **These in-sample estimates are not stable.** On this rebuilt cache (108 symbols, through Jul 2024)
   the 0.35–0.40 one-sided baseline reads **+11.0% ROM**; on the earlier cut (113 symbols, through
   Sep 2024) the same band at the same config read **+1.9%**. Five symbols and two months moved it by
   nine points. Treat every IS figure in this study as directional only.
3. **The margin convention is load-bearing.** This is costed as one-sided risk (max loss = one width
   − total credit), which is correct for the structure and is what SPAN normally recognises. If the
   broker charges both sides separately, **ROM roughly halves to ~12–17%**. Verify in Upstox before
   this goes any further.

Next step, in order: OOS on real Upstox premiums for BOTH sides (a fresh multi-hour run — the leg
cache was lost when /tmp was cleared), then the broker-margin check, then a paper book if both hold.

---

## 10. OUT-OF-SAMPLE VERDICT on the condor — the dead band IS rescued, v0 is not

`ndte/lowcw_condor_oos.py`, real Upstox expired-option premiums **Oct 2024 → Jul 2026**, 38 names,
1 lot, TP-40 of total credit. This window picked none of the in-sample result.

**Band 0.30–0.35 — the band the user asked about:**

| config | n | win | ROM | +ve yrs | IS said |
|---|---|---|---|---|---|
| one side (blocked today) | 67 | 76.1% | **−4.1%** | 1/3 | +3.5% |
| **+ opposite side ≥ 0.10** | 47 | 63.8% | **+18.4%** | **3/3** | +24.8% |
| **+ opposite side ≥ 0.20** | 46 | 63.0% | **+18.2%** | **3/3** | +25.3% |
| + opposite side ≥ 0.30 | 29 | 55.2% | **−5.2%** | 1/2 | +34.6% |

**Band 0.35–0.40 — what v0 trades:**

| config | n | win | ROM | +ve yrs | IS said |
|---|---|---|---|---|---|
| one side (v0, deployed) | 44 | 90.9% | **+20.5%** | **3/3** | +11.0% |
| + opposite side ≥ 0.10 | 32 | 65.6% | +25.9% | 2/3 | +46.6% |
| + opposite side ≥ 0.20 | 28 | 60.7% | +19.4% | 2/3 | +50.2% |
| + opposite side ≥ 0.30 | 21 | 71.4% | +76.1% | 3/3 *(n=21)* | +65.7% |

### What this establishes

1. **The 0.30–0.35 band is tradeable as a CONDOR.** −4.1% → **+18.4% on margin, positive in all
   three out-of-sample years**, at opposite-side floors 0.10 and 0.20. IS +24.8% → OOS +18.4% is a
   consistent result, not a collapse — the first candidate in this entire study to survive the
   held-out window. The mechanism is the one the study kept pointing at: combined credit/width
   0.33 → 0.64, clearing the level that is the book's actual edge.

2. **The ≥ 0.30 floor FAILS out-of-sample (−5.2%) despite being the BEST in-sample cell (+34.6%).**
   The neighbourhood does not hold uniformly. Use 0.10–0.20 and treat the top floor as a live
   reminder of how thin n=29 is.

3. **v0 gains nothing — the in-sample "upgrade v0 to two-sided" claim is WITHDRAWN.** One-sided on
   that band is +20.5% on 3/3 years; the condor is +19.4% to +25.9% on 2/3. The +76.1% cell rests on
   21 trades. v0 stays one-sided.

4. **It does not do what was literally asked.** Net goes −4.1% → +18.4%, but **win rate falls
   76% → 64%.** The request was more net AND a higher win rate; this buys net by fixing the payoff
   ratio and gives up win rate. Anyone reading a 64% win rate as "worse" has it backwards — but it
   must be stated, not buried.

### Still not deployed. What gates it

- **n = 46–47.** Thin, and one floor in the same neighbourhood already failed.
- **The margin convention.** Costed as one-sided risk (one width − total credit), which is the true
  max loss and what SPAN normally grants a condor. **If Upstox blocks both spreads separately, cash
  deployed roughly doubles and +18.4% becomes ~+9%.** Unresolved — check in the app before anything
  is built. This single check decides whether the result is interesting or marginal.
- **Four legs, not two.** Double the slippage surface and double the fill risk on mid-caps; entry
  and exit costs on all four legs are already charged here, but live fills will be worse than modelled.

## Scripts

| file | what it does |
|---|---|
| `ndte/bhav_stk_parquet.py` | one-time compaction of the 1,500-file bhavcopy CSV cache → `/tmp/bhav_stk.pkl`. The old per-row `pd.to_datetime` loader cost ~75 min per run; this is 45 s once, seconds thereafter. |
| `ndte/stkfade_lowcw_geometry.py` | the 432-cell IS sweep (geometry × target × stop) on the band |
| `ndte/stkfade_lowcw_controls.py` | faithfulness, the everywhere-control, trade size, no-gate |
| `ndte/stkfade_lowcw_matched.py` | matched-sample bias check + settlement exposure |
| `ndte/stkfade_lowcw_dte.py` | days-to-expiry sweep |
| `ndte/stkfade_lowcw_adaptive.py` | the deployable adaptive-width rules |
| `ndte/stkfade_lowcw_oos2.py` | focused OOS confirmation (resumable; per-stock checkpoints) |
| `ndte/stkfade_lowcw_subband.py` | OOS 0.30-0.35 vs 0.35-0.40 split (reuses the leg cache) |
| `ndte/stkfade_lowcw_subband_is.py` | in-sample twin of the split |
| `ndte/lowcw_regime_filter.py` | calm-regime entry filter on 0.30-0.35 (refuted) |
| `ndte/lowcw_condor.py` | sell BOTH sides — in-sample |
| `ndte/lowcw_condor_oos.py` | the condor OOS run: 0.30-0.35 CONFIRMED, v0 upgrade withdrawn |
| `ndte/book_win_loss_sizes.py` | avg win / avg loss in rupees per book, one consistent basis |
