# Pairs trading, and why the hard part is not the statistics

## The idea
Find two instruments whose prices have moved together historically. When the gap between them
widens, sell the expensive one and buy the cheap one, and wait for the gap to close.

## Why it is attractive and why it disappoints
It is attractive because it is market neutral in principle, the statistics are standard, and a
cointegration test gives you a clean number to act on.

It disappoints for a reason that is not statistical. A pair that has moved together for three years
can stop, permanently, because something changed in one of the two businesses. The test tells you
they moved together. It cannot tell you whether the reason they moved together still holds.

That is the whole problem. A widening gap looks identical whether it is a temporary dislocation
about to revert or the start of a permanent divergence, and the trade is profitable in the first
case and ruinous in the second.

## What to check
**Search cost.** Testing every pair in a hundred-name universe is 4,950 tests, and
[MULTIPLE_TESTING.md](MULTIPLE_TESTING.md) says what that does to your threshold. Pairs selected
from a large search almost never survive out of sample.

**A reason, before a statistic.** Require an economic story for why the two should track, written
down before the test. Two companies in the same business with the same inputs is a story. A
correlation of 0.94 is not.

**A time stop.** Reversion that has not happened in some number of days is probably not going to.
Decide that number before you trade, because afterwards every day feels like the one before it
turns.

**Borrow and costs on both legs.** Two legs means two round trips, and the short leg has to be
borrowable at a price you know in advance.

## The honest caveat
No result is published here. This note is the checklist, not the answer.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
