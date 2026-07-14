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
| **Model** (backtest) | ~₹39,000/mo | ~₹78,000/mo |
| **Plan-on (~half — repo rule)** | **~₹18–20k/mo** | **~₹36–40k/mo** |
| Capital required | ~₹2–2.5L | ~₹4–5L |

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
