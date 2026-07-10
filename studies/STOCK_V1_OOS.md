# Stock credit v1 — first true OOS test (2026-07-10)

**Question (user):** "v1 must be higher than 54%, right? What about in-sample and out-of-sample?"

**Answer: yes — as DEPLOYED, v1 is much better than the stale 54%.** The 54%/+5.3%-of-width
figure (bhavcopy 2019→Sep'24, 718 trades) tested the *hold-to-expiry* geometry on a harsher
data-cleaning pass and predates the TP-75 book-early exit that v1 actually runs live. This test
ran v1's **deployed** config (DC10 · short 1-OTM · width 3 · **TP 75% of credit** · stop 2× ·
c/w ≥ 0.40 + prem ≥ ₹50 gate) on real Upstox expired-option premiums **Oct'24→Jul'26** — the
same window, script and slippage model as v2's OOS test (apples-to-apples).

## Result (script `stkfade_oos_v1.py`, trades `stkfade_oos_v1.json`)

| Year | n | Win | Net (% width) |
|---|---|---|---|
| 2024 (Oct–Dec) | 37 | 76% | +29.7 |
| 2025 | 184 | 74% | +17.0 |
| 2026 (Jan–Jul) | 125 | 72% | +15.0 |
| **ALL** | **346** | **73.4%** | **+17.9%** |

Avg win +41.0%w · avg loss −51.5%w · positive every year, including the 2026 correction
(NIFTY under its 200DMA since Mar'26).

## Same-window comparison (identical methodology)

| | v1 (TP-75 · stop-2× · 1-OTM/w3) | v2 UNION (TP-50 · stop-3× · 2-OTM/w4) |
|---|---|---|
| Win rate OOS | 73.4% | 87–88% |
| Net of width OOS | +17.9% | +29.5–31.9% |
| Trades (21 mo) | 346 (~16/mo) | 173 (~8/mo) |

**v2 remains the leader on both win rate and expectancy; v1 is a genuinely positive,
higher-frequency second book — not the marginal 54% book the old table implied.**

## Honest caveats
- Cross-source: v1's 54% IS figure (bhavcopy, cleaned, expiry-settle) is NOT directly
  comparable to this Upstox-based number — the same script also flattered v2 slightly
  (85.35% IS → 87.88% OOS). The like-for-like statement is the v1-vs-v2 row above.
- The TP-75 early-booking is the main driver of 54% → 73%: booking at 75% of max profit
  converts slow decayers that later reverse into banked wins (same mechanism as v2's TP-50).
- 21 months, one broad era; live fills still unproven (paper book: 3 closed, 2W/1L).
- ~16 signals/mo means v1 accumulates live-fill evidence ~2× faster than v2 — its job as
  the control book stands.
