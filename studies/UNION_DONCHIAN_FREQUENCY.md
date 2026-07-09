# Union-Donchian frequency study — pushing v2 toward daily (2026-07-09)

**Goal (user):** daily stock trades, >=75% win, >=5% net/trade.

**Result:** quality bar massively exceeded; true "daily" is capped by the credit gate (the edge).
Merging all four validated breakout windows (DC5/10/15/20, each passed the 96-config grid) into
one stream, with v2's exact gates+exits, real bhavcopy premiums 2019->Sep'24, entry at close:

| | DC10-only (deployed v2) | UNION DC5+10+15+20 |
|---|---|---|
| Trades | 273 (4.5/mo, 227 days) | 369 (5.8/mo, 296 days) |
| Win | 85.3% | 84.3% (min year 78.0%) |
| Net/trade | +26.9% of width | +26.2% of width |
| Years positive | 6/6 | 6/6 |

+35% frequency at statistically identical quality. Frequency beyond ~6/mo is blocked by the
c/w>=0.40 gate — which is the validated edge (generic/daily stock selling tested NEGATIVE).
Portfolio-level the system already signals near-daily across its 5 books.

**Status: REPORT-ONLY.** Union has IS evidence only; DC10 also has OOS (Oct'24->Jun'26 88% win).
If deploying, run the union through the same OOS validation first. Script:
studies/ndte/stkfade_union.py; data /tmp/bhav_cache_stk (re-downloadable via bhav_dl_stk.py —
the tmp cleaner wiped it once 2026-07-09).
