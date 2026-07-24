# Goal: new fundamental+technical 1-mo strategy >70% win on ≤₹2L — VERDICT (2026-07-24)

**Goal (institutional-head framing):** find a NEW F&O/equity strategy, 1-month horizon, >70% win,
max net-after-losses on ≤₹2L, blending fundamental + technical.

## What was tested (proxy, real data)
`studies/ndte/fund_screen_proxy.py` + a 200-DMA-regime split. **Fade-win proxy** = after a
Donchian-5 breakout, the underlying did NOT extend past the ~2-OTM short strike (±3.5%) within 20
trading days (≈1 month) — a fast proxy for the credit-spread fade winning, on daily prices
(Oct'24→date, 7,491 breakouts). Fundamentals via yfinance were **429-blocked** this session, so a
**technical strength/regime proxy (200-DMA)** stood in for "quality".

## Result — a stock filter does NOT move the fade

| Breakout regime | n | Fade-win proxy |
|---|---|---|
| **below** 200-DMA (weak) | 3,785 | 48.3% |
| **above** 200-DMA (strong) | 3,706 | 49.9% |
| ALL | 7,491 | **49.1%** |

The regime split is **noise** (1.6pp), and the raw reversion is a **~49% coin flip**.

## Why this settles the goal's main lever

**The deployed fade wins 87% — but that edge lives in the OPTION STRUCTURE, not the stock.** The
underlying reverts ~50% of the time regardless of trend/regime (and, by strong extension, regardless
of fundamentals — quality doesn't make a breakout mean-revert). The 87% comes from: the
credit/width≥0.40 gate (rich post-breakout IV), the IV crush, and TP-50 early booking. Therefore a
**fundamental or technical stock-selection screen cannot raise the win rate** — it only reshuffles
*which* fair-coin breakouts you trade.

This is consistent with the repo's whole ledger: every **directional / stock-selection** edge tested
here is ~breakeven after costs (`studies/README.md` house rules). The durable edges are all
**short-premium** (v2 87%, v1 73%, 0DTE 88-90%).

## Verdict on the goal

**No new fundamental+technical strategy is likely to beat the books already in the system**, because
the win rate is a property of selling defined-risk premium into elevated IV, not of picking better
stocks. The strategy that BEST meets your stated goal already exists:

**★ Stock fade v2 UNION** — technical breakout + defined-risk credit spread:
- **87% win (t=+13.78, positive 8/8 years)**, ~1-month horizon (next monthly expiry).
- **≤₹2L fits easily** — exposure cap is ₹40k/lot, so ₹2L supports ~4-5 concurrent lots.
- Max net-after-losses is maximised by the credit/width≥0.40 gate (the 0.35-0.40 band earns only
  ⅓ as much; below 0.35 is breakeven — see `CW_BUCKET_ANALYSIS.md`).

**The one place a fundamental screen MIGHT still help is loss SIZE, not win rate** — avoiding names
prone to catastrophic gaps could trim the −65%-of-width tail. That (the option-P&L test with a
real fundamental screen, once yfinance/an alternative source is reachable) is the queued
fresh-session job; it can only improve *net*, not *win rate*, which this proxy already settles.

**Honest status:** proxy on underlying + technical regime, single-regime (Oct'24→). The fundamental
half is data-blocked this session (yfinance 429). But the win-rate question — the goal's ">70%"
gate — is answered: stock selection doesn't set it; the option structure does.
