# The quote you can trade, not the one in your history

## The question
A backtest fills at the closing price, or at the mid. What does the live system actually get?

## The gap
Historical files give you a price. They do not give you the two-sided market that existed at the
moment you would have acted. Those are different things, and in illiquid instruments they are very
different things.

Measured live here, a bid-ask filter that required a tradeable two-sided market rejected the
majority of candidates that passed every other test. That rejection rate is not in any historical
file, because the file records what traded, not what was quoted.

## Why this is the hardest part to model
You can estimate costs, and you can estimate slippage. You cannot reconstruct, from end-of-day
data, whether anybody was willing to quote you a price at 15:36 on a given afternoon. The honest
position is that a backtest built on historical prices has a ceiling on how well it can represent
execution, and that ceiling is not removable by better modelling.

## What to do about it
Record the live quotes your system sees, from the first day it runs, whether or not you are
trading. After a few months you will have the one dataset nobody can sell you: what was actually
quotable in the instruments you care about at the time you care about.

Until then, apply a liquidity filter in the backtest that is at least as strict as the one you
will apply live, accept that your result is optimistic, and say so when you quote it.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
