# Universe expansion 2 — all 103 outsiders, name by name, through the harness of record (23-Aug-2026)

**Why this study exists.** PAGEIND moved and we missed it: the user asked which of the F&O names
outside the universe would have paid, name by name, in both windows. The July expansion study cannot
answer this — its candidate data lived in /tmp and died with the reboot, and its backtest predates
all six harness corrections. NSE carries 208 F&O stock underlyings; UNIVERSE holds 113; this
measures the other 103 at v2, v1 and v0's deployed configs.

**Method.** Both legs IMPORT `studies/ndte/deployed_backtest.py` (the no-copy rule) and override
only the symbol list, the lot map (resolved from the Upstox instrument master for all 103) and the
IS pickle path. IS: fresh bhavcopy download 2019→Sep-2024, 1,418 sessions, parity spot, OI on both
legs at entry and every exit-check day. OOS: Upstox expired instruments, Oct-2024→date, START
enforced in code; verified 0 (symbol, day) overlap with IS. Scripts: `studies/ndte/expand2_*.py`.

## In-sample, complete

**Only 24 of 103 outsiders produce ANY trade in 5¾ years.** The ₹50 premium floor and the c/w gate
reject the rest wholesale — most outsiders are outside for a structural reason: their options
cannot pay.

Aggregate on the MEDIAN COHORT (the band where all live fills sit), versus the current 113:

| | outsiders | current universe |
|---|---|---|
| v2 | 38 trades · 60.5% · +6.3% ROM | 78.8% · +27.2% |
| v1 | 37 · 81.1% · +8.5% | 79.1% · +10.3% |
| v0 | 31 · 83.9% · +9.2% | 83.1% · +14.4% |

**v2's outsider cohort is far below the book it would join** (60.5% win vs 78.8%). The outsiders'
big full-band numbers (+33.3% ROM) come from rich-credit trades above c/w 0.50. As a block, the
outsiders would dilute v2; only individual names earn consideration.

## Name by name

Full table: `research/expansion2/byname_table.txt`, machine-readable `byname.json`. Leaders:

| name | IS n | IS win | IS net | note |
|---|---|---|---|---|
| PAGEIND | 24 | 88% | +₹175,731 | the user's example, and the single best outsider |
| IEX | 2 | 100% | +₹121,689 | 2 trades — unjudgeable |
| CONCOR | 5 | 100% | +₹74,732 | thin |
| SHREECEM | 24 | 83% | +₹67,098 | real sample |
| SRF | 26 | 73% | +₹58,544 | real sample |
| MCX | 16 | 81% | +₹29,492 | real sample |
| HDFCAMC | 19 | 74% | +₹18,979 | real sample |

Net-negative in-sample: ICICIPRULI, HINDPETRO, BIOCON, PIIND, MFSL, INDUSTOWER.

**A class the IS window cannot see:** names that entered F&O after Sep-2024 (BDL, AMBER, BSE, CDSL,
ADANIENSOL, APLAPOLLO, COCHINSHIP, BLUESTARCO…) have zero IS history by construction and only an
OOS record. They can never meet a both-windows bar; if any is admitted it is on OOS + forward
evidence only, and must be labelled as such.

## Out-of-sample: partial, being re-measured

Two OOS runs on 23-Aug were ruined by a local DNS outage (a Wi-Fi extender was being tested that
evening): 79 symbols lost at the underlying fetch, 163 leg evaluations dropped, 9 of 103 symbols
measured. **Those numbers are not tabled as answers.** A self-healing loop
(`research/expansion2/oos_until_clean.sh`) re-runs passes on a persistent cache until one pass has
ZERO symbol losses and ZERO leg drops; only that pass will fill the OOS column. Lesson recorded:
symbol-level underlying-fetch failures are invisible to the FETCHFAIL counter — a per-symbol visit
ledger is the future fix.

## Decision rule for admission (fixed before the OOS lands)

A name comes inside only if ALL hold:
1. **Both windows positive** at the deployed configs (new-entrant names exempted from IS, labelled).
2. **IS n ≥ 10** or the name is judged unmeasurable and deferred to the forward record.
3. **Non-dilutive:** its cohort win rate is not below the receiving book's, per the July rule.
4. The engine's live gates (spread, OI) are unchanged — admission adds names, never loosens gates.

On the IS evidence alone, the candidates that can even reach this bar: **PAGEIND, SHREECEM, SRF,
MCX, HDFCAMC, ICICIGI** (10+ trades each). Everything else is thin, negative, or IS-blind.

Nothing is added to `config.UNIVERSE` until the clean OOS lands and the user decides.
