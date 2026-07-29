# Target & Stop-Loss — per book (2026-07-29)

The exact profit target (TP) and stop each deployed book uses, straight from `engine/config.py`
and the module overrides. All are **paper/signals-only at 1 lot**. Credit spreads are defined-risk:
**max profit = credit collected; max loss = (width − credit)**, both × lot size.

| Book | Entry structure | **TARGET (take-profit)** | **STOP-LOSS** | Fallback exit |
|---|---|---|---|---|
| ★ **Stock Fade v2 UNION** (TP-50) | sell **2-OTM** / buy **width-4** credit spread, *against* a UNION Donchian(5/10/15/20) breakout | **book at 50% of the credit** (early — captures the IV crush) | 3× credit — **INERT** (never binds, see below) → floor = max loss | settle intrinsic at monthly expiry |
| **Stock Credit v1** (control) | sell **1-OTM** / buy **width-3** | **75% of max profit** | 2× credit — binds only when c/w < 0.50 | monthly expiry |

> **The stop is largely a no-op under the c/w ≥ 0.40 gate (user-caught 2026-07-29).** A vertical spread can
> never cost more than its width to close (no-arbitrage: max value = distance between strikes). The stop fires
> only when `stop_mult × credit < width`, i.e. `c/w < 1/stop_mult`. So **v2's 3× stop needs c/w < 0.333 — impossible
> past the 0.40 gate → it NEVER triggers; every v2 trade is effectively held to TP-50 or expiry, floored at the
> defined max loss `(width − credit) × lot`.** **v1's 2× stop needs c/w < 0.50 — it binds for c/w 0.40–0.50 (caps
> loss at ~1× credit) but is inert for c/w ≥ 0.50.** This is exactly why the stop-loss sweep found 3× ≈ no-stop
> (`SWING_PUTCALL_STOP_ANALYSIS.md`), and tighter stops tested WORSE — so the inert 3× is left as-is (no trading
> change); only the labels were corrected. The Telegram signal now prints this per-trade.
| **0DTE NIFTY** (FLIP) | sell ~0.5% OTM / buy **200-pt wing**, same-day expiry | none — **hold to expiry** | none (the bought wing IS the cap; `ZERO_DTE_STOP_MULT=0`) | same-day 15:30 settle |
| **0DTE SENSEX** | sell 1-OTM / buy wing, same-day expiry | hold to expiry | none | same-day settle |
| **Monthly Futures** (REGIME-OFF) | BUY front-month future on pullback | **+2% on close** (decays to +1% late in cycle) | **−5% on close** (real gaps avg ≈ −6.3%) | monthly expiry |
| ~~Swing index fade~~ | DISABLED (`SWING_CREDIT_ENABLED=False`) | was hold-to-expiry | was 2× credit | — (failed OOS) |

## Why these values (the evidence)

- **TP-50 on v2 is the edge, not "keep the full credit."** Booking early at half the credit captures
  the post-breakout IV crush; holding to expiry for the whole credit actually *lowers* net (base
  fade held-to-expiry = 54% win/+5.3%w vs TP-50 = 87%/+31.7%w). See `CW_BUCKET_ANALYSIS.md`.
- **The stop barely matters for a defined-risk spread.** New IS+OOS sweep (`SWING_PUTCALL_STOP_ANALYSIS.md`):
  looser ≥ tighter in both windows, never worse; worst single loss is bounded ~−62 to −65% of width by
  the defined-risk structure regardless of stop. 3.0× (deployed) is fine; 3.5×/no-stop is marginally
  better but small and OOS-thin — **not changed without more evidence.**
- **0DTE carries no stop by design** — it is a same-day short-vol book paid for visible fear; a stop
  keying on intraday stress removes exactly the trades the market overpays (settled question, see
  `README.md` house rules). The bought wing caps the loss.

## Max profit / max loss per trade (defined-risk credit spreads)

- **Max profit** = credit collected × lot (with TP you book a fraction of it early).
- **Max loss at expiry** = (width − credit) × lot. With the c/w ≥ 0.40 gate, that is ≈ 0.6 × width × lot.
- **Intraday stop realization** can exceed the expiry max-loss on a transient spike (a 3× stop = 2× credit
  ≈ 0.8–1.2 × width), which is why a *looser* stop tests slightly better — see the sweep above.

_All figures gross of taxes/STT; single-regime OOS. Keep lots at 1 while forward-testing._
