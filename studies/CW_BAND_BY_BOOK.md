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

## IS leg — bhavcopy 2019 → Sep-2024 (added 14-Aug-2026)

Full universe, 1,358 sessions of NSE F&O bhavcopy OPTSTK, same geometry and same live gates
(premium ≥ ₹50, 3-day cross-book re-entry, ≥10 DTE), settled on the option's own daily path:

| band | v2 | v1 | v0 |
|---|---|---|---|
| **0.25–0.30** | 80.6% · +8.9% ROM (n=546, +ve 5/6) | 80.3% · +2.4% (n=441, 5/6) | **85.7% · +11.3%** (n=546, 5/6) |
| **0.30–0.35** | 75.6% · **−3.4%** (n=574, 3/6) | **80.3% · +9.6%** (n=618, **5/6**) | 81.0% · +5.0% (n=574, 3/6) |
| 0.35–0.40 | 74.3% · +6.9% (n=424, 3/6) | 81.4% · +8.9% (n=918, 4/6) | 79.2% · +10.4% (n=424, 4/6) |
| **≥0.40** | 91.6% · +176% (n=2406, 6/6) | 93.1% · +173% (n=2918, 6/6) | **96.3% · +192%** (n=2406, 6/6) |

**The one cell that survives both windows is v1 at 0.30–0.35.** Its in-sample year path is
`2019 +24% · 2020 −2% · 2021 +6% · 2022 +13% · 2023 +11% · 2024 +7%`, so the only losing year is
2020 and it loses 2%. Out-of-sample it returns +11.6% ROM at 82.6% win, positive in all three years.
No other low band is positive in both windows under the same exit.

**v2's stop fails identically in both windows.** It is 0.0% ROM out-of-sample and −3.4% in-sample at
0.30–0.35, and it is the only cell that is negative anywhere. The mechanism is the same in both:
a stop set at 3× credit binds when credit is thin.

**v0 is regime-dependent down here.** It reads +5.0% ROM in-sample at 0.30–0.35 but only 3 of 6
years positive (`2020 −6% · 2021 −2% · 2024 −6%`), which is the same pattern that made v0's own
0.35–0.40 band a marginal deployment.

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

**Both windows are now measured, and one cell passed both.** That is the first time a low-c/w band
has done so in this repo. It still does not make the band deployable, for three reasons:

1. **The money is not there.** v1 at 0.30–0.35 pays +9.6% ROM in-sample and +11.6% out-of-sample.
   The deployed gate pays +173% to +192%. Every rupee of margin spent down here earns roughly a
   fifteenth of what the same rupee earns above 0.40, and margin is the binding constraint.
2. **It competes for the same margin.** These trades are on the same names on the same days as the
   v1 signals already firing above the gate. Adding them does not diversify the book; it dilutes it.
3. **It is a fourth book on one clean result.** v0 was added on a similar-strength case and is
   already the weakest live book. Two low-c/w books running against one gated book changes what the
   system is.

The honest read: the band is not dead, and the earlier "dead" verdict was an artifact of measuring
c/w at v2's geometry only. But "not dead" and "worth deploying" are different claims, and only the
first one is supported.

**Method limits.** The OOS leg runs a 38-name slice (`UNIVERSE[::3]`), n = 58–92 per cell; the IS leg
runs the full universe, n = 424–2,918 per cell. Neither applies a live liquidity or bid-ask filter,
so both are optimistic on fills at the thin end. IS settles on the option's own daily close path;
OOS settles on Upstox expired-instrument closes.

**Nothing deployed. No engine file touched.** Scripts: `studies/ndte/cw_band_sweep.py` (OOS),
`/tmp/cw_is.py` → copied to `studies/ndte/cw_band_sweep_is.py` (IS).
