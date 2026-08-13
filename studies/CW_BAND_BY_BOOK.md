# c/w bands below the gate, scored at EACH BOOK's own geometry (13-Aug-2026)

**User question:** what is the win rate for c/w 0.25–0.30 and 0.30–0.35 under our v0/v1/v2 criteria?

**Answer, OOS Oct-2024 → Aug-2026, 38-name slice, each band priced at that book's own geometry and
exit** (v2 = S2/W4 TP-50 stop-3× · v1 = S1/W3 TP-40 no-stop · v0 = S2/W4 TP-40 no-stop):

| band | v2 | v1 | v0 |
|---|---|---|---|
| **0.25–0.30** | 78.1% · +2.6% ROM (n=64) | **85.7% · +5.1%** (n=70, +ve 3/3 yrs) | 84.4% · +4.9% (n=64) |
| **0.30–0.35** | 74.1% · **0.0%** (n=58) | **82.6% · +11.6%** (n=92, +ve 3/3 yrs) | 77.6% · +3.1% (n=58) |
| 0.35–0.40 *(v0's live band)* | 74.3% · +11.2% (n=35) | 74.8% · −1.0% (n=103) | **88.6% · +22.5%** (n=35) |
| **≥0.40 (deployed v2)** | **95.8% · +219%** | | |

## What this shows

1. **The EXIT decides these bands, not the band.** v1's TP-40/no-stop is the only configuration
   positive in all three low bands and positive in 3 of 3 years.
2. **v2's 3× stop is what kills them** — 0.0% ROM at 0.30–0.35. A stop set as a multiple of credit
   binds precisely when credit is thin, so the same stop that is inert at c/w ≥ 0.40 (where it never
   triggers) becomes the dominant exit down here.
3. **The money is still not there.** ROM is 2–12% across every low band against **+219%** at the
   gate — 20–100× less per rupee of margin. The win rates are respectable and irrelevant; this is
   the same illusion the 227,000-trade sweep exists to expose.

## Why the earlier study missed this — the band was defined at ONE geometry

`LOWCW_BAND_RESCUE.md` swept 432 cells and concluded the 0.30–0.35 half is dead. It is not wrong,
but it answers a different question, and the difference is subtle enough to be worth recording.

That study fixes `S, W = 2, 4` (`lowcw_regime_filter.py:34`) and selects band membership with
`if not (BAND[0] <= cw < BAND[1]): continue` — **c/w computed at v2's geometry.** Its geometry sweep
then re-prices *"the same 782 signals"* at other widths. So throughout, the POPULATION is "names
whose c/w is 0.30–0.35 **when measured short-2-OTM / width-4**", and only the pricing varies.

This sweep asks the inverse: *which signals have c/w 0.30–0.35 **at v1's own S1/W3 geometry**, and
how do they perform there?* That is a **different set of trades**, not the same trades re-priced —
because c/w is a function of how far the wing sits, a name at 0.33 under S2/W4 can be at 0.45 under
S1/W3 and vice versa. The earlier study's own key insight says as much: *"a spread's credit/width is
a function of how far the wing sits… rejecting on c/w rejects names whose strike ladder is coarse
relative to their premium."*

So nothing was overlooked through carelessness — the band was simply always defined by the deployed
geometry, which is the right frame for asking "can we rescue the names our watchlist blocks" and the
wrong frame for asking "what does each book see in its own terms".

## Status — NOT actionable

- **OOS only.** The in-sample leg (bhavcopy 2019→Sep-2024) is queued separately; every previous
  rescue attempt on these bands died in-sample or on the regime flip, so an OOS-only positive means
  little on its own.
- n = 58–92 per cell, 38-name slice (`UNIVERSE[::3]`), not the full 113.
- No live liquidity or spread filter applied.
- **Nothing deployed. No engine file touched.** Script: `studies/ndte/cw_band_sweep.py`.
