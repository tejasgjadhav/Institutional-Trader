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

---

## 24-Aug-2026 — the universe moved 113 → 122, so the P&L moves

Nine names were admitted (`studies/UNIVERSE_EXPANSION_2.md`): PAGEIND, MCX, TVSMOTOR, SHREECEM on
both-windows evidence, plus LTM, TIINDIA, SOLARINDS, BDL, AMBER — F&O entrants after Sep-2024 with
no in-sample history, admitted on OOS + forward evidence only.

**The measured base (21-Aug re-run, median cohort, 1 lot):**
v2 ₹8,450/mo + v1 ₹8,359/mo + v0 ₹1,674/mo = **₹18,483/mo stock books**.
Index books: 0DTE SENSEX ₹3,153 + 0DTE NIFTY ₹1,771 = ₹4,924. Monthly futures ₹0 (regime-off).

**The expansion increment, by the expectancy model (win% × avg win − loss% × avg loss):**
- IS window: 84.9% × ₹6,513 − 15.1% × ₹10,806 = +₹3,903/trade × 1.1 sig/mo = **+₹4,317/mo**
- OOS window (floors): 86.5% × ₹4,867 − 13.5% × ₹7,585 = +₹3,184/trade × 3.3 sig/mo = **+₹10,473/mo**
- The gap is signal frequency: five of the nine did not exist in the IS window. Planning figure:
  **+₹6,000–8,000/mo**.

**New totals at 1 lot:**
| | conservative (IS) | planning | optimistic (OOS floor) |
|---|---|---|---|
| stock books | ₹22,800 | **₹25,500** | ₹29,000 |
| + index books | ₹27,700 | **₹30,400** | ₹33,900 |
| plan on 80% | ₹22,200 | **₹24,300** | ₹27,100 |

**Read this as an estimate until the forward record confirms it.** The increment is backtest
expectancy; the live spread gate takes its cut first, the OOS window is one favourable regime for
the defence/manufacturing entrants, and the IS-blind five are on probation by construction. The
forward-record DB tags their trades from day one; the 30-trade rule is unchanged and the expansion
does not reset its counter.

## 24-Aug-2026 (later) — pruned to 114 on the validation principle

Eight names removed the same day ("we dont want to waste efforts on something which is not
validated in the past"): HCLTECH, SBILIFE (negative both windows), OFSS, TCS, TECHM, HDFCBANK,
DMART, JINDALSTEL (net-negative, never validated positive). Four of eight are IT names — the fade
reads structurally weak in that sector.

**Impact on the measured base:** the eight contributed −₹690/mo in-sample and −₹3,939/mo
out-of-sample. Removing them RAISES the measured stock-book base by roughly **+₹0.7–3.9k/mo**
(centre ~+₹2k). Nothing else changes: the expansion increment stands at +₹6–8k/mo.

**Updated totals at 1 lot (114 names):**
| | conservative | planning | optimistic |
|---|---|---|---|
| stock books | ₹23,500 | **₹27,500** | ₹32,900 |
| + index books | ₹28,400 | **₹32,400** | ₹37,800 |
| **plan on 80%** | ₹22,700 | **₹25,900** | ₹30,200 |

Estimates until the forward record confirms; the spread gate taxes them first.

## 24-Aug-2026 (final) — corrected rupee scale, 114-name basis, expansion folded in

The split-name rupee fix (NESTLEIND +63,490 → +3,172/trade) plus the prune re-based every rupee
figure. **Totals: 1,253 IS trades · 412 OOS trades = 1,665** — universe names only (an earlier
draft said 1,792 by wrongly summing the 127 IS trades of NON-admitted expansion candidates; the
name-wise side-split table caught it, since 946 bear calls + 719 bull puts = 1,665). Median
cohort, deployed universe:

| | IS | OOS |
|---|---|---|
| v2 | 217 tr · 79.3% · +23.3% · ₹2,733/tr | 78 tr · 83.3% · +27.0% · ₹3,276/tr |
| v1 | 354 tr · 80.8% · +12.9% · ₹1,115/tr | 183 tr · 83.1% · +16.2% · ₹1,799/tr |
| v0 | 227 tr · 85.0% · +15.2% · ₹1,823/tr | 96 tr · 82.3% · +7.6% · ₹1,038/tr |

**Stock books measured: IS ₹21,236/mo · OOS ₹30,417/mo.** The earlier planning figure ₹25,500/mo
sits between the two windows; it stands. Earlier rupee figures (v2 ₹5,798/trade etc.) were inflated
by split names carrying today's lot on yesterday's points; ROM percentages were never affected in
ratio, only in pooled weighting.

**116-name basis (post ICICIGI/PIIND, the deployed universe):** IS 1,269 · OOS 428 trades. Median
cohort — v2 IS 78.6%/+22.0% → OOS 83.5%/+27.0% (₹11,472/mo); v1 80.9%/+13.1% → 83.3%/+16.6%
(₹15,228/mo); v0 84.7%/+15.2% → 81.8%/+7.2% (₹4,292/mo). Stock OOS ₹30,992/mo; +index ₹35,916;
plan-on-80% ₹28,733. Every future admission shifts these — the UI reads this basis.
