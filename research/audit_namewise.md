# Adversarial audit: data/symbol_history.json (per-name backtest table)

Date: 2026-08-24
Auditor stance: assume the table is wrong; refute by independent recomputation.
Method: throwaway scripts in `research/audit_tmp/` (`audit_stats.py`, `audit_sides.py`).
No code from `studies/ndte/build_symbol_history.py` was imported or reused. The Donchian
UNION(5/10/15/20) breakout rule was re-implemented from its one-line spec, and daily candles
were re-fetched independently via `engine.data_fetcher.fetch_upstox_historical` (133 symbols,
0 fetch failures).

Ground truth row files:
- `research/deployed_bt_is_rows.json` (1180 rows) + `research/expansion2/is_rows.json` (200 rows)
- `research/deployed_bt_oos_rows.json` (374 rows) + `research/expansion2/oos_rows.json` (204 rows)

Window sanity: 0 IS rows dated after 2024-09-30; 0 OOS rows dated before 2024-10-01.
Duplicate check: 0 duplicate (book, sym, day) keys within combined IS and within combined OOS.

File shape: 162 symbol entries; 133 carry an `is` or `oos` object (the other 29 are
scanned-only entries with no trades). Every symbol present in the row files has an entry.

---

## Section 1 — Per-name window stats (is/oos: n, win%, avg_win, avg_loss)

Recomputed for all 133 traded symbols (198 non-null is/oos objects) directly from the row
files: n = row count, win% = 100·Σwin/n (1dp), avg_win = mean of net_rs>0 (rounded int),
avg_loss = mean of net_rs≤0 (rounded int). Tolerance win% ±0.05, rupees ±1.

Mismatches: **none**. Every cell in every `is` and `oos` object matches the recomputation
exactly, including null avg_win/avg_loss where no winning/losing rows exist.

**VERDICT: CONFIRMED.**

## Section 2 — Side attribution (bear_call / bull_put, is/oos bc/bp, book_vX_bc/bp)

Independent derivation: for each symbol, fetched the adjusted daily series from 2018-11-01
and implemented the breakout rule myself (iterate i from 20; c=Close[i]; for dc in
5/10/15/20: c > max(High[i-dc:i]) → CE = bear call, else c < min(Low[i-dc:i]) → PE = bull
put, first hit wins). Each trade row's day was mapped through this table.

(a) Unmapped rows: **0 of 1958**. Every trade day in every row file lands on a derived
    breakout day with a direction. The join is intact.
(b) Value conflicts: **0**. Wherever the file carries a side cell (bear_call, bull_put,
    is/oos bc/bp, book_vX_bc/bp), its n, win and net match my recomputation within
    tolerance — for all universe names, across all books.
(c) bc+bp == n: holds in every `is` and `oos` object that carries bc/bp keys (0 failures),
    and book_vX_bc + book_vX_bp row counts equal book_vX counts everywhere sides exist.

One finding, an omission rather than an error: **48 expansion-only (non-universe) symbols
have NO side keys at all** — no `bear_call`/`bull_put`, no bc/bp inside is/oos, no
book_vX_bc/bp — although sides derive cleanly for every one of their rows. The symbols:
ADANIENSOL, APLAPOLLO, BHARATFORG, BIOCON, BLUESTARCO, BSE, CDSL, COCHINSHIP, CONCOR,
DIXON, DMART, GLENMARK, GODFRYPHLP, HCLTECH, HDFCAMC, HINDPETRO, HYUNDAI, ICICIGI,
ICICIPRULI, IEX, INDUSTOWER, KAYNES, KEI, KFINTECH, LAURUSLABS, LICHSGFIN, MANKIND,
MAZDOCK, MFSL, OBEROIRLTY, OFSS, PAYTM, PHOENIXLTD, PIIND, POLICYBZR, POWERINDIA,
PRESTIGE, RADICO, RBLBANK, SBICARD, SBILIFE, SRF, SUPREMEIND, TCS, TECHM, UNITDSPR, UPL,
WAAREEENER. None is in `engine.config.UNIVERSE`; every universe name has full side cells.
Their window stats and book cells (sections 1 and 3) are correct; only the side breakdown
is absent. My audit script logged these as 207 "missing-key" rows (file=None, recomputed
value exists); zero of the 207 is a wrong number.

**VERDICT: CONFIRMED for every populated cell; DISCREPANT only in coverage — side cells
are absent for the 48 non-universe expansion names.**

## Section 3 — Book cells (book_v2 / book_v1 / book_v0: n, win, net)

Recomputed per symbol from the rows' `book` field across IS+OOS combined.

- Cell mismatches: **none** across all 133 traded symbols.
- Sum check: for every symbol, book-cell n's sum to the symbol's total row count, and
  file `is.n + oos.n` equals the same total (0 failures).
- Side-split sum check: book_vX_bc.n + book_vX_bp.n == book_vX.n wherever side cells
  exist (0 failures).

**VERDICT: CONFIRMED.**

## Section 4 — Global reconciliation

Filtered to `engine.config.UNIVERSE` (114 names, `.NS` stripped):

| Quantity | Claim | Recomputed | Match |
|---|---|---|---|
| IS trades | 1253 | 1253 | yes |
| OOS trades | 412 | 412 | yes |
| Grand total | 1665 | 1665 | yes |
| Bear calls (universe) | 946 | 946 | yes |
| Bull puts (universe) | 719 | 719 | yes |

Note: 1253 = 1180 main-universe IS rows + 73 universe-name rows inside
`expansion2/is_rows.json` (names like PAGEIND/TVSMOTOR/LTM that were later admitted to the
universe); likewise 412 = 374 + 38. No double counting (duplicate key check above).

TITAN, cell by cell (file vs recomputed):
- book_v2 {14, 64.3, +1263} vs {14, 64.3, +1263} — match
- book_v1 {19, 78.9, +21547} vs {19, 78.9, +21547} — match
- book_v0 {15, 66.7, -11844} vs {15, 66.7, -11844} — match
- bear_call {33, 63.6, -11135} vs {33, 63.6, -11135} — match (claim said ~64%)
- bull_put {15, 86.7, +22101} vs {15, 86.7, +22101} — match (claim said ~87%)

**VERDICT: CONFIRMED.**

## Section 5 — Deep spot-check: TITAN, PAGEIND, BOSCHLTD

Full row-level listing (window, day, book, net_rs, win, independently derived side) is in
`research/audit_tmp/spot_dump.txt` (48 TITAN rows, PAGEIND and BOSCHLTD complete). Sample
verified by eye against the aggregates above; every row's day mapped to a breakout and the
per-side sums reproduce the file cells.

PAGEIND recomputed from its rows: IS n=24, OOS n=6 — matches its file entry (is 24/87.5%,
oos 6/66.7%). BOSCHLTD: IS n=18, OOS n=11 — matches (is 18/72.2%, oos 11/72.7%).

**VERDICT: CONFIRMED.**

## Not audited

`scanned_is` / `scanned_oos` (e.g. TITAN 361/116, PAGEIND 336/113, BOSCHLTD 324/110) were
noted but not recomputed — reproducing scan counts requires a full engine re-run, out of
scope per the audit brief. Note the 48 no-side expansion names also carry
`scanned_is: 0 / scanned_oos: 0` style placeholders in some entries (e.g. ADANIENSOL
0/0 despite having OOS trades); if those fields are ever consumed, treat them as
unpopulated for expansion names.

---

# OVERALL VERDICT

**CLEAN on every populated number.** Zero of the ~2,000 recomputed cells disagreed with
the file. The only defect is coverage, not correctness:

**DEFECTS FOUND: 1 (omission).** Side-attribution cells (bear_call/bull_put, is/oos
bc/bp, book_vX_bc/bp) are entirely absent for the 48 non-universe expansion symbols even
though every one of their trade days maps cleanly to a breakout direction. Any analysis
reading side splits for expansion candidates from this file will silently see nothing.
Related minor note: `scanned_*` fields are 0 for at least some expansion names that do
have trades.
