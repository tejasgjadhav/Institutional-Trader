# Stock fade v2 — UNION vs D10, and the signal-frequency question (2026-07-13)

**Decision: keep UNION. Do not loosen the credit gate. Use v1 for frequency.**

## History (git)
- **Jul 6** (5757c7e): v2 deployed as **D10-only** (TP-50 upgrade; short 2-OTM, width 4, gates:
  credit/width ≥ 0.40, short prem ≥ ₹50, live two-sided liquidity, ₹40k exposure cap).
- **Jul 9** (308e6f2): **UNION scanner added** — `UNION_DCS = (5,10,15,20)`, user-approved.
Same book/module (`engine/stock_credit_v2.py`), two config phases. The lone TRENT signal
(Jul 8) was fired by the **D10-only** version, before UNION existed.

## The question the user asked
"Keep UNION or D10 — or both for more signals?"

## The answer
**UNION already IS "both."** UNION = D10 + D5 + D15 + D20 — a strict superset of D10. There is
no separate "run both" mode; adding D10 on top of UNION would double-count the same breakouts.

The choice is therefore only D10-only vs UNION, and UNION dominates:

| | signals (OOS ~21mo) | IS win | OOS win | expectancy |
|---|---|---|---|---|
| D10-only | ~6/mo | 85% | 88% | +24.5%w |
| **UNION (D10+D5/15/20)** | **~8/mo (+34%)** | 84% | 87% | +26–30%w |

+34% more signals at statistically identical win rate/expectancy (84 vs 85, 87 vs 88 = noise).
Source: `UNION_DONCHIAN_FREQUENCY.md` (IS 369 tr 84.3%, OOS 173 tr 87%, "+34% trades at DC10
quality"), `STOCK_FADE_TP50_UPGRADE.md` (base D10: 85/88).

## The important caveat — the scanner is NOT the bottleneck
Widening the Donchian net does **not** produce more *fired* signals in the current regime,
because the binding constraint is the **credit/width ≥ 0.40 gate**, not breakout detection:
- July 1–13: D10 alone threw **105 breakouts**, and **1** cleared (TRENT).
- Since UNION went live Jul 9 (an even wider net): **0** fired — same credit wall.

So more windows = more breakouts, all slamming into the same gate. The signal drought is
**regime** (low IV → thin credit), not the scanner.

## What NOT to do
- **Do not lower the credit/width gate to force signals.** That gate *is* the edge — stripping
  it turns +26%w into **−1.1%** (it re-admits the losing generic 4-leg spreads). See
  `STOCK_OPTIONS_NO_EDGE.md` Part 10.

## Where frequency actually comes from
The parallel **v1 book** (1-OTM / width-3) naturally produces richer credit/width → **~10–16/mo**,
and runs alongside v2 for exactly this reason (73% OOS win, +17.9%w). If you want more trades,
that's the book — not a looser v2 gate.

## Verdict
Keep UNION (best net: +34% signals, same quality). Leave the gate alone. Lean on v1 for
frequency. Signals return when IV/credit richens, not from widening the breakout window.
No config change. REPORT-ONLY per approval-first.
