# Run 4 (17-Sep-2026): harness hardening after two adversarial audits — and a guard that was wrong

**Context.** Two "more signals" levers (far-expiry v1; width-3 v2) were tested IS then OOS and both
refuted by adversarial audits (research/audit_farexp_v1.md, research/audit_v2w3.md). The audits
also exposed harness defects. Run 4 fixed the observability ones and TRIED an inverted-wing guard.

**What stayed (result-neutral, proven).** Contract-list and underlying fetch failures are now
counted instead of swallowed; every legfails.jsonl entry carries a run stamp; positions walk to
expiry instead of a d+45 cap; the integrity summary is `print_integrity()`, callable from drivers.
Run-4e reproduces run 3 **bit-identically in-sample: 1,085/1,085 rows** (book, sym, day, cw, net,
margin). Suite 20/20.

**What was tried and withdrawn: a monotonic-chain ("inverted wing") guard.**
- Strict: rejected 1,790 spreads — 270/373 v2, 270/506 v1 — and the removed rows were the BEST
  (v2 removed @ 81.9% / 62.1% ROM). Traded-only (OI>=1): still 170/147/56. Tolerance 1.25: 81/65/25.
- Ratio distribution over 10,204 spreads: median 1.000, p90 1.155, p95 1.459, p99 2.581;
  >1.10: 1,198 · >1.25: 792 · >1.50: 464 · >2.0: 201.
- The ladders (research/run4_wing_ladders.jsonl, 1,198 cases) show the cause: ZIGZAGS on illiquid
  INTERMEDIATE strikes. MPHASIS PE 26-Aug-2021: 2600:83.8 → 2550:26.0 → 2500:49.3 → 2450:19.0 →
  2400:30.0. Round strikes trade and carry live prints; half-steps carry stale last-trade closes
  (open interest stays positive long after the last trade). The spreads sit on the liquid round
  strikes and are sound. Worst-inversion location: 371 inside the span, 336 at the wing, 491 one
  strike beyond — stale intermediates everywhere, bad legs nowhere.
- Therefore a monotonic check, strict or tolerant, measures intermediate-strike staleness, not leg
  validity, and it was deleting legitimate winners on the IT names. **Rejection disabled**
  (`WING_INVERSION_TOL = None`); the ladder log stays as an audit aid. **Run-3 numbers are NOT
  overstated by this mechanism** — the "phantom winner" hypothesis was tested and is wrong.

**What the in-sample data cannot do.** The bhavcopy pickle carries CLOSE, EXPIRY, STRIKE, SYMBOL,
TYP, OPEN_INT — no volume — so "did this leg trade today" (which OOS enforces via Upstox candles)
cannot be applied in-sample. OI>=1 remains the best IS proxy; this is the documented bhavcopy
friction, now confirmed rather than assumed.

**Footnote on the width-3 audit.** Its "15 wing artefacts" assumed monotonic chains; some were
likely genuine thin-market trades where the width-4 wing really did trade expensive that day. It
does not rescue width-3 — the 58% overlap with v1/v0 and the negative residual stand.

**Lesson.** Predict-then-verify caught a bad guard three times before it reached the record: the
before/after showed it removing winners; the ratio distribution showed a long tail; only the
ladders showed WHY. A guard that changes the answer needs the evidence that it changes it for the
right reason.

## Run-4 OOS (17-Sep-2026) — now the OOS file of record

First single-run out-of-sample on the actual 116-name universe with every fetch failure counted:
439 rows, **197 network drops** (run 3: 293; the counts remain a FLOOR), 8 contract/candle fetch
failures. `research/deployed_bt_oos_rows.json` is now this run; the 21-Aug 113-name file is kept as
`deployed_bt_oos_rows_21aug_113names.json`. Rows that "vanished" vs the 21-Aug file are the pruned
bleeders (TCS, HCLTECH, TECHM, OFSS) — universe change, not harness.

| book | basis | published run 3 | run 4 | +yrs |
|---|---|---|---|---|
| v2 | median cohort 0.40–0.50 | 79 · 83.5% · +27.0% | **81 · 84.0% · +25.9%** | 3/3 |
| v1 | median cohort 0.40–0.50 | 186 · 83.3% · +16.6% | **194 · 83.0% · +15.2%** | 3/3 |
| v0 | own band 0.35–0.40 | 99 · 81.8% · +7.2% | **106 · 83.0% · +2.4%** | 2/3 |

v2 and v1 are inside network noise of the published numbers; v0's ROM is the one material move
(thin watch book, ~100 trades — a handful of trades swing it). Rupees/month at 1 lot on the
published basis: v2 +12,150 · v1 +15,382 · v0 +5,617 = **+33,149** (published 30,992).
