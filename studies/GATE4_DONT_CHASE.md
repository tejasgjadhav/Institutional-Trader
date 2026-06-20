# Gate 4 — "Don't Chase" (entry-extension filter)

A 4th gate on the 3-Family stock system: **skip a signal if the stock has already moved
more than `MAX_ENTRY_EXTENSION_PCT` (2.6%) in the trade's direction from the day's open.**
Buying an already-extended stock is buying the top — it loses directional edge.

## How it was found

From the **365-day underlying-proxy validation** (772 aligned trades, real price data),
each trade's signal-time features were logged and binned. Only **extension** showed a
clean, mechanism-backed, *monotonic-in-the-tails* relationship; conviction (alpha-z),
volume surge, time-of-day and alignment-strength were all noisy / non-monotonic (no gate),
and per-stock loss-rates were too small-sample to use (8–14 trades each = noise).

| Extension at entry | Hit-rate | Avg move |
|--------------------|----------|----------|
| Barely moved (1.0–1.5%) | 47% | +0.08% |
| **Sweet spot (1.5–2.3%)** | **55–56%** | **+0.18%** |
| 2.3–3.0% | 47% | +0.16% |
| **Chasing (>3% already)** | **45%** | **+0.06%** |

## Train/test validation (anti-overfit)

Train = oldest 70% of days, test = newest 30%. The filter improves the **held-out** test
set, not just the training set — the key check:

| | Test hit | Test avg/trade |
|---|---|---|
| Baseline (Gate 3 only) | 45% | +0.134% |
| **+ Gate 4 (ext ≤ 2.6)** | **49%** | **+0.163%** |

Held-out per-trade edge: **+0.13% → +0.16%** (~20% lift), trades kept ~65–72%.

## Option-level backtest (+10%/−20%, 1 lot, GROSS)

| Window | Config | Trades | Win % | P&L | Return on capital |
|--------|--------|--------|-------|-----|-------------------|
| 30-day | Gate 3 | 60 | 58% | +₹13,383 | +1.1% |
| 30-day | **Gate 3+4** | 43 | 56% | +₹9,259 | +1.1% |
| 60-day | Gate 3 | 88 | 59% | +₹32,519 | +1.7% |
| 60-day | **Gate 3+4** | 65 | **60%** | **+₹32,937** | **+2.5%** |

## Honest read

- **60-day: a real *efficiency* gain** — same profit on **26% fewer trades** and far less
  deployed capital, so return-on-capital rises **+1.7% → +2.5%** and win-rate ticks up.
- **30-day: a wash** — same +1.1% on capital, lower absolute ₹ (fewer trades), win-rate
  dips 58→56%. The window is too small (only ~1 month of real option-premium history) to
  show a thin filter.
- The strongest evidence is the **365-day underlying test** (large, held-out). The option
  windows are too short to confirm a fine filter cleanly.
- **Net:** Gate 4 is a *risk-efficiency refinement* (trim the worst chasers, same profit on
  less capital) — not a profit multiplier. The underlying strategy is still a thin,
  ~52–60% directional edge.

Config: `ENTRY_EXTENSION_FILTER = True`, `MAX_ENTRY_EXTENSION_PCT = 2.6` in
`engine/config.py`; enforced as Gate 4 in `engine/agent.py:scan_stock`. Loosen to 2.9 to
keep more trades (the 365-d data showed that also works, dropping fewer entries).

*Generated 2026-06-19. All option P&L gross of brokerage / STT / spread.*
