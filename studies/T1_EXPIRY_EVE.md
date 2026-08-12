# T-1 expiry-eve credit spread — 80%+ win rates yes, the money no (11-Aug-2026)

**Verdict: REJECTED as a new book.** The hypothesis half-holds and half-fails, and the half that
fails is the one that matters.

## The question

Enter the deployed 0DTE structure one session EARLIER — 09:16 on the day before expiry, ~2% OTM —
and hold through expiry. Premise: two days of decay instead of one means "much larger premiums to
harvest". Target: 80%+ win rate. Data: Upstox expired options, Oct-2024 -> Aug-2026.

## Method

Entry at the T-1 daily **OPEN**, which IS the 09:15-09:16 print — the one entry time daily bars price
exactly, so the usual "intraday option history does not exist" limit does not bite here. Settlement =
expiry-day index close, intrinsic vs strikes, capped at width. Entry slippage on both legs via the
repo's `spf()`. Sweep: OTM {1.0, 1.5, 2.0, 2.5, 3.0}% x width {2,4,6} steps x {bear-call, bull-put}
x {NIFTY, SENSEX, BANKNIFTY}. 4,000+ priced trades.

## Win rate: the target is beaten easily — and that is the trap

| index | best geometry | n | WIN | ROM | avg credit |
|---|---|---|---|---|---|
| BANKNIFTY | BEAR_CALL 2.5% w4 | 25 | **100.0%** | +2.8% | 12.8 |
| SENSEX | BEAR_CALL 2.0% w6 | 90 | **97.8%** | +2.3% | 19.2 |
| NIFTY | BEAR_CALL 2.5% w4 | 88 | **97.7%** | +0.5% | 3.7 |

Every top cell clears 80% comfortably; several clear 95%. **And they are worthless.** NIFTY's 97.7%
collects an average credit of **Rs3.7** on a 4-step-wide spread — c/w **0.02**. This is the exact
illusion `studies/` was built to expose: the 227,000-trade sweep found a 0.15%-target bot printing
83.6% win while losing money. Selling a 2.5%-OTM option one day from expiry wins almost always
because it is almost worthless, and it is priced accordingly.

## The user's premise is REFUTED at the strikes proposed

"Much larger premiums" is false at 2%+ OTM. One session before expiry a 2.5%-OTM NIFTY option is
Rs3.7, not a harvest. Premium only appears as strikes move CLOSER, and then the win rate falls back
toward the 0DTE books' own level — the trade-off the deployed books already sit on.

## Money — the only comparison that decides it

Best rupee cell per index, 1 lot, at the real expiry cadence:

| index | geometry | WIN | Rs/trade | /mo | **Rs/month** |
|---|---|---|---|---|---|
| NIFTY | BEAR_CALL 1.5% w6 | 94.6% | 335 | 4.2 | **1,418** |
| SENSEX | BEAR_CALL 1.0% w6 | 88.2% | 418 | 4.2 | **1,768** |
| BANKNIFTY | BEAR_CALL 1.0% w6 | 92.0% | 1,620 | 1.1 | **1,841** |

Against the DEPLOYED books, which need no new code and carry 8 years of validation:

| | WIN | Rs/month |
|---|---|---|
| 0DTE NIFTY (live) | 88.3% | **1,771** |
| 0DTE SENSEX (live) | 89.0% | **3,153** |

**SENSEX T-1 earns Rs1,768/mo against the live 0DTE book's Rs3,153 — 44% LESS, for double the
holding risk.** NIFTY T-1 is a rounding error below its live book. Nothing here beats what is
already running.

## Why it fails, structurally

Every T-1 cell prices at **c/w 0.01-0.10**. This repo's one durable, repeatedly re-validated finding
is that **c/w >= 0.40 IS the edge** — strip that gate and the same structure loses (-1.1% vs +5.3% of
width, `STOCK_OPTIONS_NO_EDGE.md` Part 10; `CW_BUCKET_ANALYSIS.md`). T-1 far-OTM spreads sit an order
of magnitude below the gate. They are not a cheaper version of the edge; they are the population the
gate exists to exclude.

## What is NOT rejected

The 1.0-1.5% OTM band is where premium actually lives (SENSEX Rs68.5 credit, BANKNIFTY Rs76.5) and
still holds 88-92%. It remains inferior to the deployed books on money, but it is the only direction
worth a second look — and it is the OPPOSITE of the 2%+ the hypothesis proposed. BANKNIFTY's cells
rest on n=25 monthlies and its 0DTE book was already REJECTED on t=+0.10, so treat 100% there as
sample noise, not a finding.

## Do not re-mine

T-1 entry at 2%+ OTM is closed. Any future look belongs at 1.0-1.5% OTM, must be judged on Rs/month
against the live 0DTE books rather than on win rate, and must clear the c/w gate to be credible.
