# DRAFT — Why we rejected the BANKNIFTY 0DTE book (2026-07-19)

**Status:** DISABLED in the engine (`DTE_MULTI_BANKNIFTY_ENABLED = False`). Reversible.
Open positions still resolve normally; only new entries are stopped.

**One line:** it is not that the book loses — the median trade is **+14.1% of margin** — it is that
its edge is **statistically indistinguishable from zero**, its entire profit came from **three
trades**, and a single bad day costs **~102 months** of it.

---

## The evidence

84 monthly expiries, 2019-01 → 2026-06, 1 lot, net of costs.

| Measure | Value | Reading |
|---|---|---|
| Win rate | 78.6% | below the ~76% breakeven only by a hair |
| Avg return | **+0.55% of margin** | t = **+0.10** |
| 95% CI on avg | **[−9.98%, +11.09%]** | **contains zero comfortably** |
| Bootstrap p(mean ≤ 0) | **0.33** | 1-in-3 chance the true edge is ≤ 0 |
| Total, 7.5 years | +₹11,824 | **+₹141/month** at 1 lot |
| Worst single day | **−₹14,298** | **≈ 102 months of profit, in one session** |

**The profit is three trades.** This is the decisive number:

| Sample | Total ₹ |
|---|---|
| All 84 trades | +₹11,824 |
| Drop the single best | +₹7,630 |
| **Drop the 3 best** | **−₹8** |
| Drop the 3 worst | +₹43,934 |

Remove three lucky days from seven and a half years and the book is exactly break-even. That is not
an edge; that is a coin that happened to land well a few times.

## What we ruled out first

We did not reject on one number. Two competing explanations were tested and both failed to rescue it.

**1. "Monthly expiry should win more."** A fair hypothesis with a real mechanism — monthly contracts
carry far larger open interest, and OI concentration causes strike *pinning* that holds the index
near a big strike into settlement, which is what an OTM seller wants. Tested **within Era A** so
regime and data source are held constant and only expiry type varies (`ndte19_bnf_monthly.py`):

| Expiry type | n | Win % | Avg %margin |
|---|---|---|---|
| MONTHLY | 67 | 76.1% | **−1.55%** |
| WEEKLY | 214 | 80.4% | **+8.51%** |

Monthly was **worse**, beat weekly in only 2 of 6 years, and did not collect richer premium
(median c/W 0.190 vs 0.170). z = −0.75 → not significant, so properly: monthly confers **no**
win-rate advantage.

**2. "The recent era proves it works."** Era B shows 88.9% / +8.60%m — but that is **n=18** (16W/2L,
binomial CI ≈ 65–99%), and **every book improved in Era B** (NIFTY 86.5% → 93.2%). It is regime lift
on a tiny sample, not a structural gain.

## Audit — we tried to break our own result first

`ndte20_bnf_audit.py`, written to *falsify* the rejection rather than confirm it.

| Check | Result |
|---|---|
| Bad prints (stale far-wing OPEN fabricating credit) | **CLEAN** — c/W range 0.021–0.568, 0 suspicious |
| Monthly tagging correct | **CLEAN** — exactly 1 trade/month, 84 months |
| Lot-size artifact (₹ used fixed lot 30) | **CLEAN** — %margin is lot-free and agrees in sign |
| Survivorship (missing the worst days?) | **CLEAN** — skipped days 0.91% avg move vs traded 0.86% |
| Outlier dependence | **FAILED** → this is *why* we reject (drop 3 best → −₹8) |
| Long-wing liquidity floor | **Known gap** — see below |

**The one real weakness, stated plainly:** the `CONTRACTS ≥ 100` liquidity floor was applied to the
**short** leg only, not the long wing. A dead wing would mean we "paid" too little for protection —
which would make the book look **better** than reality. That bias runs **against** our conclusion, so
rejecting is the conservative side of that error. If anything the true numbers are slightly worse.

No bug was found that would flip the sign.

## Why reject rather than keep as a cheap paper forward-test

- **It contributes nothing.** ₹141/month against ~₹37k consolidated is rounding error.
- **It carries real tail risk.** One −₹14,298 day erases 8.5 years of its own contribution, and it is
  correlated with every other short-premium book — a crash month hits them together.
- **It consumes attention and margin** that the two books with actual measured edges do not have to
  compete for.
- **Its headline claim was never supported.** It was carried in the UI at "91% win / ~₹1,500 per
  month". Measured, that is 78.6% / ₹141. Keeping a book on an unsupported number is the failure mode
  this repo has been burned by before.

## What is NOT being claimed

- **Not** "BANKNIFTY 0DTE is proven unprofitable." The CI spans −9.98% to +11.09%; the honest verdict
  is *unproven*, not *disproven*.
- **Not** a verdict on the structure. The same geometry works on SENSEX (89.0%, ₹3,153/month) and
  NIFTY (88.3%, ₹1,771/month). This is a verdict on **this index**, whose monthly-only cadence gives
  ~12 trades a year — too few to ever accumulate evidence at a useful rate.
- The weekly→monthly structural break (SEBI rationalisation) still confounds the era comparison; that
  is part of *why* the book can't prove itself, not a defence of it.

## Reversal condition

Re-enable only on fresh evidence, not on a good run. A defensible bar: **≥ 30 new monthly expiries**
(≈2.5 years) under the current monthly-only regime, showing a mean return whose 95% CI excludes zero.
At ~12 trades/year this book cannot clear that bar quickly — which is itself the argument for putting
the capital somewhere that can.

---

Scripts: `ndte19_bnf_monthly.py` (monthly-vs-weekly), `ndte20_bnf_audit.py` (adversarial audit).
Data: `ndte13_trades.json`, `ndte14_trades_2019.json`.
