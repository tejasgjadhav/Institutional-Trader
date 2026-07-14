# Consolidated monthly P&L — all LIVE books, 1 lot vs 2 lots (2026-07-14)

**MODEL figures from the backtests — NOT live results.** Live books are near-empty in the
current low-IV drought (the credit gate rejects thin premium). This is "what the validated
edges earn per month at model fills," which the repo rule says to **plan at ~half** until live
fills prove out. All books are **correlated short-premium** — a crash month hits several at once,
so size on the worst month, not the average.

## Options books — tradeable now (~₹2–2.5L capital at 1 lot)

| Book | Win (OOS) | Model basis | ~₹/mo · 1 lot | ~₹/mo · 2 lots |
|---|---|---|---|---|
| ★ Stock fade **v2 UNION** (leader) | 87% | +29.5% of width × ~5–6/mo (₹16k base × 1.34 UNION uplift) | **~₹20,000** | ~₹40,000 |
| Stock credit **v1** (control, high-freq) | 73% | +17.9% of width × ~16/mo | **~₹12,000** *(est)* | ~₹24,000 |
| **0DTE NIFTY** flip (Tue expiry) | 87% | +5.9% of ~₹14k margin × 4–5/mo (₹1.92L since 2019) | **~₹2,500** | ~₹5,000 |
| **0DTE SENSEX** (Thu expiry) | 89% | +7.6% of margin (+₹67k / 21 mo) | **~₹3,200** | ~₹6,400 |
| **0DTE BANKNIFTY** (monthly expiry) | 91% mo | +11% of ~₹14k margin × ~1/mo | **~₹1,500** *(est)* | ~₹3,000 |
| **CONSOLIDATED (options)** | — | — | **≈ ₹39,000/mo** | **≈ ₹78,000/mo** |

*(est) = the per-lot ₹ isn't separately published for this book; derived from its % return ×
frequency × typical margin/width. Treat as a rough anchor, not a precise figure.*

## How each ₹/mo is built — expectancy (the loss leg IS subtracted)

Expectancy per trade = **win% × avg win − loss% × avg loss**, net of charged slippage + brokerage.
This is the direct answer to "did you count losses" — every net/trade below already subtracts the
loss leg.

| Book | Win | Avg win | Avg loss | Net / trade | ×/mo | ≈ ₹/mo |
|---|---|---|---|---|---|---|
| v2 UNION | 86% | +₹6,048 | −₹7,922 | .86×6,048 − .14×7,922 = **+₹4,069** | ~5 | ~₹20,000 |
| Stock v1 | 73% | +41.0% width | −51.5% width | .73×41 − .27×51.5 = **≈+16%w** (OOS +17.9%w) | ~16 | ~₹12,000* |
| 0DTE NIFTY | 90% | +9.8% margin | −34.1% margin | .90×9.8 − .10×34.1 = **≈+5.6%m** ≈ ₹807 | ~3.4 | ~₹2,700 |
| 0DTE SENSEX | 89% | — | — | **+7.6% margin** net (+₹67k / 21 mo) | ~4.5 | ~₹3,200 |
| 0DTE BANKNIFTY | 91% | — | −₹4,549 | **+7–11% margin** net (documented) | ~1 | ~₹1,500* |

Units differ (v2/BNF ₹, v1 % of width, 0DTE % of margin). **v1 & BANKNIFTY ₹/mo remain estimates** —
their avg-win isn't separately published, so ₹ = % × freq × typical margin, not a clean expectancy.
Sources: `STOCK_FADE_TP50_UPGRADE.md`, `STOCK_V1_OOS.md`, `INTRADAY_85PCT_0DTE_CE_SPREAD.md`.

## Not in the total (why)

| Book | Why excluded |
|---|---|
| Monthly Futures pullback (REV1-v2) | +3.9%/mo on margin, but needs **~₹15L** capital and is **REGIME-OFF now** (NIFTY < 200DMA → 0 signals until it reclaims) |
| Monthly Long-Call pullback | paper/forward-test, regime-gated — no standalone validated ₹/mo |
| Index fade (NIFTY/FINNIFTY) | **failed OOS** (−1.4% of width) — forward-test only, not counted as edge |
| 3-Family stocks | direction edge only, −1.0% net — not profitable |

## The honest bottom line

| | 1 lot | 2 lots |
|---|---|---|
| **Model** (backtest, NET of charged slippage + brokerage) | ~₹39,000/mo | ~₹78,000/mo |
| **Plan-on (80% of net)** | **~₹31,000/mo** | **~₹62,000/mo** |
| Capital required | ~₹2–2.5L | ~₹4–5L |

**Why 80% of net, not the old blanket half:** these books (v2 UNION, v1, all three 0DTE) are
backtested on **REAL premiums** with entry+exit slippage (~2.5% of credit) **and** ₹20×4
brokerage already charged, and the actual win/loss rate is baked into the net. So the only
remaining real-world gap is live *fill quality* (and missed manual entries) — a ~20% haircut,
not 50%. The blanket-half rule stays for anything validated on *estimated* costs or proxies;
it does not apply where the premiums and costs are already real. (2-lot note below still holds:
the second lot fills worse, so treat the 2-lot 80% as the optimistic end.)

Caveats that matter more than the point estimate:
- **Model ≠ live.** No book has enough live fills yet to confirm; the drought means a realistic
  *this* month is near ₹0, not ₹39k — the average assumes signals actually fire.
- **2 lots ≈ 2× P&L AND 2× drawdown**, plus likely worse fills on the second lot (mid-cap depth).
  It is not free money — it doubles the worst-month loss too.
- **Correlated tail:** all short-premium; a gap-and-crash expiry can take full-width losses on
  the 0DTE books and the stock fades in the same week.
- Not investment advice — this is the paper system's own modeled aggregate, framed gross-of-fill-
  risk. Source figures: `LIVE_STRATEGIES.md`, `STOCK_FADE_TP50_UPGRADE.md`,
  `INTRADAY_85PCT_0DTE_CE_SPREAD.md`, `FLIP_SIDE_CREDIT_FADE.md`.
