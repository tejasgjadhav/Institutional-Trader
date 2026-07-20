# Audit of the two stock books + the NIFTY question (2026-07-19)

Two questions: **(a)** is the ₹32,000/month carried by the stock books real, or inflated like
BANKNIFTY's was? **(b)** should NIFTY 0DTE be removed from the live set?

**Answers: (a) the edges are real and robust — but the magnitude is still optimistic. (b) NO — NIFTY
is the second-strongest book in the portfolio by evidence and should stay.**

---

## The audit, same adversarial checks that killed BANKNIFTY

| Check | **v2 UNION** (n=545) | **v1** (n=346, OOS) | *BANKNIFTY (rejected)* |
|---|---|---|---|
| avg % of capital | **+70.7%** | **+27.3%** | *+0.55%* |
| **t-statistic** | **+13.78** | **+7.09** | *+0.10* |
| 95% CI | **[+60.6, +80.7]** | **[+19.8, +34.9]** | *[−9.98, +11.09]* |
| bootstrap p(mean≤0) | **0.0000** | **0.0000** | *0.33* |
| Positive calendar years | **8 / 8** | **3 / 3** | *noise, 64–92%* |
| Drop 10 best trades | +13,670 of +16,559 (**83% survives**) | +5,435 of +7,898 (**69% survives**) | *drop 3 → −₹8* |
| Worst trade costs | **8 trades** of profit | **12 trades** of profit | *102 months of profit* |

Both books clear every bar that BANKNIFTY failed, and not narrowly — t = 13.8 and 7.1 against
BANKNIFTY's 0.10. **The ₹32,000 is not fabricated.** The edges are statistically real, positive in
every calendar year measured, and not driven by a handful of lucky trades.

## But the magnitude is still optimistic — this is the part to hold onto

The audit validates **that** an edge exists and **that** it is robust. It does **not** validate that
its *size* survives live fills. Two things say the size is inflated:

1. v2's figures imply **≈97%/month on deployed capital** (+52.3% capital-weighted per trade over a
   12.1-day hold, ~2.2 concurrent positions). No real strategy returns that.
2. 24 of 569 v2 trades printed **c/W > 0.95** — stale illiquid marks where a spread appears to pay
   99.5% of its width. Those were excluded here, but their presence shows the fill assumptions are
   generous at the edges. The same weakness found in the BANKNIFTY audit (no liquidity floor on the
   long wing) applies to these books too.

**So: keep the books, distrust the number.** The correct posture is exactly the repo's standing one —
*the backtest is optimistic, keep lots at 1* — now with statistical backing rather than intuition.

The plan-on recommendation stands: **~50% of model is more defensible than the current 80% haircut**
until live fills prove otherwise. That is a statement about magnitude, not about validity.

---

## Should NIFTY 0DTE be removed? No.

| Measure | **NIFTY 0DTE** | *BANKNIFTY (removed)* |
|---|---|---|
| n | **273** over 8 years | *84* |
| avg | **+4.69% of margin** | *+0.55%* |
| **t-statistic** | **+4.43** | *+0.10* |
| 95% CI | **[+2.62, +6.77]** — excludes zero | *[−9.98, +11.09]* — spans zero |
| bootstrap p(mean≤0) | **0.0002** | *0.33* |
| Positive years | **7 / 8** (only 2019, −₹3,522) | *noise* |
| Drop 5 best | +₹132,369 of +₹152,267 (**87% survives**) | *drop 3 → −₹8* |

NIFTY is not a marginal book — it is the **second-most-validated** thing in the portfolio after v2:
273 trades across 8 calendar years, positive in 7, an edge 44× its standard error, and robust to
removing its best trades.

**Why it might feel removable, and why that reasoning is wrong:** its ₹1,771/month is the smallest
contribution among the live books. But that is a **size** question, not a **validity** question — it
trades ~3.2 times a month at ₹13,577 capital per lot. On return *per day of capital committed* it runs
**+4.7%/day**, ahead of v2's +4.3%/day. Removing the book with the second-strongest evidence because
it has the smallest headline rupee number would be exactly backwards.

BANKNIFTY was removed because its edge could not be distinguished from zero. NIFTY's can, decisively.
Those are opposite situations that happen to sit near each other in a ₹/month column.

---

## Disposition

- **v2 UNION — KEEP.** Edge validated (t=13.8, 8/8 years). Magnitude still optimistic; lots stay at 1.
- **v1 — KEEP.** Edge validated (t=7.1, 3/3 years). Note this is the OOS era only; the older IS era has
  no per-trade file.
- **NIFTY 0DTE — KEEP.** Do not remove. Second-strongest evidence in the book.
- **SENSEX 0DTE — KEEP**, with the standing caveat that it has only 3 years and is single-era.
- **Plan-on haircut — still recommend ~50% vs the current 80%.** Unchanged pending your sign-off.

Script: `studies/ndte/ndte22_stock_audit.py`. Data: `/tmp/d5_10_15_20_*.json` (v2, regenerate via
`stkfade_d5_10_15_20_*.py` if /tmp is purged), `studies/stkfade_oos_v1.json` (v1).

**Remaining gap:** v1's in-sample era (2019→Sep'24, the 718-trade figure) still has no per-trade file,
so only its 346-trade OOS era was audited. v2's capital figures rest on an approximation of per-stock
lot sizes rather than exact ones.
