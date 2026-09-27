# The Rs 50 short-leg premium floor: what it removes (26–27 Sep 2026)

**Question (user, 26-Sep).** The Rs 50 floor makes the same high-priced names repeat and most of
the universe never converts. Should the floor be segregated: Rs 50 where it works, Rs 30 (c/w ≥ 0.30)
name-wise where names never reach 50?

**Method.** Harness of record (`deployed_backtest.py`, run-4 code) unchanged except `MIN_PREM`.
Sweep A: deployed bands (v2/v1 ≥0.40, v0 0.35–0.40) at floors 10/20/30 vs the live 50, IS (bhavcopy
2019–Sep 2024) and OOS (Upstox Oct 2024–Sep 2026). Sweep B (the user's cut): v0 geometry, one band
c/w ≥ 0.30, floors 30 vs 50, side stamped. "Incremental" = trades present at the lower floor and
absent at the higher one. Friction is the harness's own (60/premium % per leg, so cheap legs pay most).
Scripts: `studies/ndte/prem_floor_sweep.py`, `studies/ndte/prem30_band30.py`. Rows in `research/`.

## Concentration at the live floor
Universe 116. Names with ≥1 trade at floor 50: 70 IS, 67 OOS. Top 10 names carry 152 of 439 OOS
trades (35%). At floor 30: 85 names. 13 names trade ONLY below Rs 50 in both windows: AMBUJACEM,
BPCL, HDFCLIFE, HINDALCO, ICICIBANK, INDIANB, ITC, JSWSTEEL, MARICO, PFC, SBIN, TATACONSUM, WIPRO.

## Sweep A — deployed bands, incremental trades by premium bucket

| bucket | IS n / win / ROM / +yrs | OOS n / win / ROM / +yrs |
|---|---|---|
| live floor 50 (base) | 1085 / 82.4% / +32.2% / 6/6 | 439 / 84.1% / +18.0% / 3/3 |
| **prem 30–50** | 341 / 84.2% / +21.8% / 6/6 | **156 / 78.2% / +5.7% / 3/3** |
| — v2 | 101 / 82.2% / +34.3% | 18 / 61.1% / **−7.6%** / 1/3 |
| — v1 | 151 / 83.4% / +18.6% | **98 / 80.6% / +8.8% / 3/3** |
| — v0 | 89 / 87.6% / +16.5% | **40 / 80.0% / +5.3% / 3/3** |
| prem 20–30 | 201 / 89.1% / +22.5% / 6/6 | 77 / 81.8% / +3.8% / 2/3 (v2 −24%) |
| prem 10–20 | 264 / 79.2% / +12.0% / 5/6 | 91 / 71.4% / **−7.0%** / 1/3 |

Reading: in sample every bucket looks fine; out of sample only the 30–50 bucket survives, and only
for v1 and v0. v2's incremental is negative in every OOS bucket. Below Rs 30 the money is gone.

## Sweep B — the user's cut (v0 geometry, c/w ≥ 0.30, floor 30 vs 50)

| set | IS | OOS |
|---|---|---|
| floor 50 base | 1019 / 82.7% / +16.8% | 438 / 79.9% / +4.0% |
| incremental (floor 30 only) | 421 / 82.9% / +7.4% | **170 / 75.9% / −0.9%** / 2/3 |
| — c/w 0.30–0.35 | 239 / 79.9% / +1.2% | 101 / 76.2% / −2.2% |
| — c/w 0.35–0.40 | 94 / 87.2% / +15.4% | 49 / 73.5% / −1.8% |
| — c/w ≥ 0.40 | 88 / 86.4% / +31.5% | 20 / 80.0% / +14.0% |

Name × side screen on the incremental set (≥80% win AND ROM > +5% in BOTH windows, n ≥ 3 each):
**3 cells qualify** — ASTRAL BP (3 IS / 6 OOS), VOLTAS BP (3 / 4), INFY BC (5 / 3). Pooled OOS
13 trades, 100%, +23%. That is the same selection shape that produced the vlc whitelist (cells chosen
on the OOS window) and PAGEIND (88% IS → 67% OOS). Not a deployable list.

## Verdict
1. The Rs 50 floor IS removing good trades, but only down to Rs 30 and only for v1 and v0. A
   per-book floor — v2 stays 50, v1 and v0 go to 30 — models +138 OOS trades over 23 months
   (≈ +6/mo) at 80% win, ≈ +₹6.3k/mo at 1 lot, positive every OOS year. That is a config change
   under the approval rule, and the live 6% spread gate will block a share of these cheap legs.
2. The c/w 0.30 band does not work at Rs 30 either: −0.9% OOS pooled. The 0.30–0.35 band stays dead.
3. A name-wise whitelist at floor 30 yields 3 cells on 3–6 trades each. Too thin to deploy.
4. Concentration is real (35% of OOS trades in 10 names) but the answer is the per-book floor,
   which brings 15–18 more names into play, not a per-name floor.
