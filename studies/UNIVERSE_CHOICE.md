# Which stocks should the screen run over?

## The question
The exchange lists a few hundred names with futures and options. Should a screen run over all of
them, over an index membership list, or over a chosen subset?

## How it was tested
The same rule was run over different lists on the same window, and the lists compared on money
after costs, on trade count, and on how many names ever produced a trade at all.

## What came back
Most names never trade. On several runs, fewer than a quarter of the list produced a single
signal, and the money came from a small part of that quarter. Expanding the list added more
names that did nothing and a few that diluted the result.

Choosing a subset by past results is the overfit described in
[PER_NAME_SELECTION_IS_OVERFIT.md](PER_NAME_SELECTION_IS_OVERFIT.md), and it did not survive.
Choosing by something structural is defensible. Whether an option on the name is quoted at a
spread you can pay is a real constraint, and it rules names out for a reason that will still be
true next year.

## What this repository ships
UNIVERSE in engine/config.py is the full exchange list of names with futures and options, not a
selection. It is there as a starting point. Narrowing it is your work, and your backtest should
decide it.

## What to take from it
Pick the list for a reason you can state without referring to past profit. Then measure how many
names actually trade, because a list of two hundred that produces signals on twenty is really a
list of twenty.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

