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

**OOS VALIDATION PASSED (2026-07-09, stkfade_oos_union.py, real Upstox premiums the search
never saw):** UNION Oct'24->Jun'26 = **173 trades (+31% vs DC10's 132), 87% win, +29.5% of
width** (2024: 93%/+35.4 · 2025: 84%/+30.5 · 2026: 90%/+25.8) — statistically indistinguishable
from DC10's 88%/+31.9% benchmark. Full evidence: IS 369tr 84.3%/+26.2%w + OOS 173tr 87%/+29.5%w.
The frequency gain is edge-preserving. **Awaiting user decision to upgrade v2's scanner**
(engine change = scan all four Donchian windows instead of DC10 only; exits/gates unchanged).
Caveats: +30% book capital (~Rs1.3L/lot-set), +30% loss frequency (same per-loss size), extra
trades cluster on the same market moves (bad weeks scale slightly super-linearly). Script:
studies/ndte/stkfade_union.py; data /tmp/bhav_cache_stk (re-downloadable via bhav_dl_stk.py —
the tmp cleaner wiped it once 2026-07-09).
