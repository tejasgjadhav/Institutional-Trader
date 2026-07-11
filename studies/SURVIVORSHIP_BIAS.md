# Testing on the list as it is today

## The question
A backtest runs over the names in the index today. What does that do to the result?

## How it was tested
The same rule was run twice. Once over the current membership list applied to the whole history,
and once over the membership as it stood in each year, rebuilt from the exchange's own revisions.

## What came back
The first run was better, every time. That is not an edge, it is arithmetic. A name is in the
list today partly because it did well, and a name that was delisted, merged away or thrown out
of the derivatives segment never appears at all. The backtest only ever trades survivors.

The gap widened the further back the window went, which is what you would expect. It was large
enough on a long window to turn a losing rule into a winning one.

## What to take from it
Rebuild the universe as it stood on each date, or accept that your number is inflated and say so
when you quote it. The exchange publishes its revisions. Using them is tedious and it is the
difference between a result and a flattering picture.

A related trap: a name that leaves the F&O segment stops producing signals, so the backtest
quietly stops trading it rather than recording a loss. Check what happened to the names that
disappear from your data.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

