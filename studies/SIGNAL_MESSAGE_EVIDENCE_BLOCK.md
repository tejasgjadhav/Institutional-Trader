# The per-name evidence block in every signal message (built 24-Aug-2026)

**Why this study exists.** Signals used to carry one book-level paragraph — identical for every
stock — so the message's evidence carried no decision weight. The user asked for the named stock's
own record at the moment of decision: "for taking a real trade this adds value." Built and shipped
the same day, through four sample iterations (TORNTPHARM, HCLTECH, BAJAJHLDNG, TITAN, PAGEIND).

## The final format (live since 24-Aug-2026, TG_SYMBOL_HISTORY_ENABLED)

Six lines, each at a different grain, none redundant:

1. **Scanned counts** — how many union-Donchian breakouts the gates saw per window, so the reader
   sees the selectivity (~4% admitted).
2. **In-sample line** — trades (bear calls · bull puts) · win% · avg profit · avg loss per trade.
3. **Out-of-sample line** — same shape, so the two windows can disagree in public.
4. **Strategy line** — "As per the strategy vX: n trades · win% · net = actual profit per trade,
   of which this side: n/win/net." The firing book's own record, never a blend.
5. **By side** — bear call vs bull put, each with "actual overall profit".
6. **Bold verdict** — "This signal is a BEAR CALL for which <name> has given N bear call trades ·
   win% · actual profit till date = per lot per trade."

Plus, inside the rich-credit bucket only (v2↔v1, never v0): a **routing note** when the OTHER
geometry's record for the name is materially better (n≥8, +10pp win, higher net) — informational,
the engine hierarchy unchanged pending the pre-registered routing backtest.

**Retired on the way:** the pooled expectancy line (blended both sides and all books — redundant
once strategy-level and side-level actuals were shown) and the book-level strategy bullets.

## Data path

`data/symbol_history.json`, built by `studies/ndte/build_symbol_history.py` from the harness row
files — per name: both windows, scanned counts, side splits, per-book records (`book_vX`) and
book×side cells (`book_vX_bc/bp`). All rupees on the corrected split-name scale. Signal time is a
dict lookup (0 ms, no network). **Regenerate after any backtest re-run or universe change, then
restart the engine.**

## What the samples proved

- **TITAN** — the block argued against its own signal: bear calls −₹11,135 over 33 trades, and the
  book×side split localised the damage to v0 (−₹24,174 at 54%) while v1 bear calls are fine.
- **HCLTECH** (pre-prune) — negative expectancy shown in bold; that render fed the 8-name prune.
- **BAJAJHLDNG** — "no trades in this window" and no-loss cells degrade gracefully.
- **PAGEIND** — all grains agree near ₹6k/trade; the routing note points v2 signals to v1's
  stronger record (93% on 14).

Observations stay informational — per-name selection on 8–20-trade cells is the July overfit trap
(64%→49%); the scanner is never blocked.
