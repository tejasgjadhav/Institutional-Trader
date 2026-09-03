# Band 0.30-0.40 name-wise screen (user question, 27-Aug-2026)

**Question.** Within c/w 0.30-0.40, which names give >=80% win AND net ROM > +5% per side since
2018, for stock-wise deployment ("more calls")?

**Method.** v0 geometry (short 2-OTM, width 4, TP-40, no stop), band (0.30, 0.40), run-3 audited
harness. IS = bhavcopy 2018->Sep-2024 (746 trades). OOS = Upstox Oct-2024->Aug-2026, restricted to
the 45 IS-qualifier tickers (227 trades). Sides mapped by breakout direction, the
build_symbol_history join. Screen = 232 cells (116 names x 2 sides).

## Result: the screen FAILS out of sample

- IS found 60 qualifying cells (of 110 with trades); only 7 had n>=15.
- **Pooled OOS over ALL qualifier cells: n=227 · 77.1% win · NET -1.2%.** The mined selection as a
  whole carries no out-of-sample edge.
- Every large-n IS star failed or vanished OOS: INDIGO BC 94%->71%/-16; APOLLOHOSP BC 94%->63%/-27;
  ULTRACEMCO BC 100%->63%/-30; GODREJPROP BC 93%->60%/-14; DRREDDY BC (100%/+33.8 IS) had ZERO OOS
  trades. 27 of 60 qualifier cells produced no OOS trade at all.
- 5 cells "confirmed" both windows (LT BC, COFORGE BP, ALKEM BC, CUMMINSIND BC, MUTHOOTFIN BC) —
  but their combined IS+OOS n runs 9-17 each. After screening 232 cells, five small-n survivors is
  what luck alone produces. They are NOT deployable evidence.
- Data defect found: MRF (both sides), NESTLEIND BP and BOSCHLTD BC print per-trade net ROM above
  the arithmetic maximum (~67% of margin at these c/w) — e.g. MRF BP +367% IS, BOSCHLTD -116% OOS.
  The big-strike scale family again. Their rows are excluded and the defect is open.

## Verdict

**Do not deploy 0.30-0.40 stock-wise.** The pooled band's healthy IS look (82.4%/+10.0%) is v0's
0.35-0.40 doing the work; the mined name selection below it inverts OOS. This is the WR70 lesson at
name grain: selection intensity manufactures 80% win rates in sample. The five survivors can sit on
a watch-only list in the forward record if wanted; nothing enters config.

Files: research/band30_is_rows.json, band30_oos_rows.json, band30_is_cells.json,
band30_oos_cells.json, band30_confirmed.json, driver studies/ndte/band30_study.py.


# Band 0.30-0.40 name-wise screen — CORRECTED (28-Aug-2026)

Correction: the first analysis averaged the rows' `net` (POINTS) as if it were a percentage,
inflating big-strike names (MRF, NESTLEIND, BOSCHLTD printed impossible ROM). The harness of
record was never wrong; cell ROM is now sum(net)/sum(margin). Full corrected table below
(IS 2018->Sep-2024 · OOS Oct-2024->Aug-2026, incl. the HEROMOTOCO/M&M/RELIANCE/TITAN top-up).

## Verdict (unchanged in direction, cleaner in detail)
- Pooled OOS over ALL band cells: n=263 · 78.3% win · +0.2% ROM — the band as a whole is dead net.
- Pooled OOS over IS-QUALIFIER cells: n=156 · 77.6% win · **-3.5% ROM** — the mined selection still fails.
- IS results do not persist at name grain IN EITHER DIRECTION: IS losers EICHERMOT BC (-19.2 -> +8.3),
  ADANIENT BC (-12.0 -> +14.5), PERSISTENT BC (-39.9 -> +30.4), GRASIM BC (-36.4 -> +5.0) all WON OOS.
  Selection on IS name records is anti-informative here.
- 6 cells confirm both windows: HEROMOTOCO BC, LT BC, COFORGE BP, CUMMINSIND BC, MUTHOOTFIN BC,
  ALKEM BC — 9-17 trades each across BOTH windows; at 232-cell screening intensity this survivor
  count is consistent with luck. NOT deployed as trading names.
- RELIANCE BP (best IS sample: 20/85.0%/+7.1%) had ZERO OOS trades - the survivorship censoring.

See research/band30_*_cells2.json and band30_confirmed2.json for machine-readable cells.
