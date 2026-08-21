# Candlestick patterns, tested properly and falsified

## The question
Chart patterns are the most widely taught entry signal there is. Single patterns had already
failed here. Nobody had tested **conjunctions** — a pattern plus a level plus a volume condition
plus a time of day — which is how patterns are actually taught and actually used.

## How it was tested
Thirty instruments, six indices and twenty-four F&O stocks. Five-minute bars built from one-minute
history, 1,710 symbol-months, zero fetch failures.

Six completed-candle patterns: bullish engulfing, bearish engulfing, hammer, shooting star, and
inside-bar breaks up and down. Each was crossed with a level condition (none, the previous day's
low, the previous day's high, VWAP), a volume condition (any, or at least 1.5 times the recent
average) and a time condition (any, the first hour, the last hour). That gives 138 conjunction
gates with at least 300 entries each.

Entry at the pattern bar's close. First-touch stop at 20, 30, 50, 80 or 120 basis points, crossed
with a target ratio from 0.25 to 1.5. Both directions. Three basis points of cost per trade, traded
on the underlying.

In-sample 2022 to 2024 selected, with a Bonferroni threshold of z = 4.49 across 6,900 tests.
Out-of-sample 2025 to 2026 judged, and was never searched over. **760,594 pattern entries in all.**

## What came back

| | |
|---|---|
| In-sample candidates clearing 75% win **and** positive net at the Bonferroni bar | **0** |
| Out-of-sample survivors, 75% win and positive net on 100+ trades | **0** |
| In-sample to out-of-sample correlation of net, across 6,800 cells | **+0.34** |
| Cells that were net-positive out of sample | **4.0%** |

Read the last two rows together, because that is the finding. A correlation of +0.34 means the
cells do carry persistent information from one window to the next. Only 4 percent of them were
profitable out of sample, against 50 percent if they carried no information at all.

So the information is real and the information is **"this loses"**. It carried from 2022 to 2024
through to 2025 and 2026, consistently, on both sides, across every geometry tested.

The high win rates exist. Many cells cleared 75 percent. Every one of them was net-negative, because
a small target with a wide stop manufactures the win rate and the cost eats what is left. At three
basis points of cost, a trade risking twenty basis points needs roughly an eighty percent win rate
just to break even.

## Verdict
**The candle-conjunction class is falsified on this data, out of sample, for a directional trade.**
That is the fourth independent falsification of chart-based entries in this research trail.

Two things remain untested and should not be called dead. Order flow was never tested; three weeks
of depth recordings is not enough and a year would be needed. Candles as a timing input for an
entry that already has an edge from somewhere else is a different question from candles as the
edge, and it was not tested here.

## What to take from it
If you are building on patterns, this is the bar you have to clear: a pre-registered threshold that
accounts for how many things you tried, a window you did not search over, full costs, and a check
on whether your winning cells have winning neighbours. Most published pattern results clear none of
those four.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
