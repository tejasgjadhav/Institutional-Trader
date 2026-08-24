# The three-family signal system: a real edge that still loses money

This is the system the book describes in full. It is in
[engine/three_family.py](../engine/three_family.py) and every weight and threshold is in
[engine/config.py](../engine/config.py). It is retired, and this note says why.

## How it works

Three families vote on each stock.

**TREND** carries most of the weight, 0.72. It reads momentum, trend quality and microstructure,
weighted 0.37, 0.24 and 0.04 inside the family.

**FLOW** carries 0.18. It reads the option put-call ratio and the macro regime, which is the index
trend and volatility.

**EVENT** carries 0.10. It reads news sentiment and corporate filings. It started at 0.18 and was
cut, because a thirty-day test showed keyword sentiment did not lift the win rate. It stays in the
vote at a weight small enough that it cannot drag the result.

The three scores combine into one alpha-z. A signal needs the absolute alpha-z above 0.55 with at
least two of the three families pointing the same way. Then a separate check asks whether the
latest five-minute candle broke the opening range, the first six bars of the session, by at least
0.01 percent on at least 1.2 times recent volume. Both have to pass. A market-alignment filter
then allows longs only when the index is up and shorts only when it is down.

When it traded, it bought one strike out of the money, booked at +10 percent on the premium and
cut at −15 percent.

## What it measured

Tested on real five-minute history back to 2019, using this exact code rather than a simplified
stand-in.

| | |
|---|---|
| Signals | 19,454 |
| Hit rate on direction | 50.6% |
| Mean move per signal | **+0.107%** |
| Years positive | **every year, 2019 to 2026** |
| The same screen with the gates removed | 48%, a coin flip |
| Traded as a bought option, one full year on real premiums | **−1.0%** |

## The finding

**The gates are real.** Strip them and the screen is a 48 percent coin. Keep them and it hits 50.6
percent and makes +0.107 percent a signal on direction, in every year across seven years. That is
not a curve fit. A curve fit does not hold its sign across seven years including two regime changes.

**And it still loses money.** +0.107 percent per signal is about eleven basis points. Expressing a
move that size by buying a near-the-money option means paying the spread twice and paying decay for
the hold. A full year on real option premiums came back at −1.0 percent.

That gap is the whole lesson. The edge is real, it is measured, it persists, and it is smaller than
the cost of the instrument chosen to trade it.

## Why it is retired, and why it is published

It is retired because an edge you cannot express profitably is not a strategy. It ran as a paper
forward-test for months and was eventually switched off and removed from the live engine.

It is published because it is the most instructive thing in this repository. Most systems fail
because the signal is noise. This one has a signal that is not noise, and it fails anyway, at the
execution step. You will meet that failure far more often than you expect, and it is invisible
until you price the instrument you actually have to trade.

## What to do with it

**Do not switch it on and trade it.** It has been measured and it loses.

**Do reproduce the direction number.** Pull your own five-minute history, run
`compute_all_families` and `is_orb_confirmed` over it, and measure the move after each signal. If
you land near +0.1 percent, you have confirmed the gates do something.

**Then ask the better question.** Given a real directional edge of about eleven basis points, what
instrument could express it for less than eleven basis points? That question has answers, and
working through them teaches more than another entry screen.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
