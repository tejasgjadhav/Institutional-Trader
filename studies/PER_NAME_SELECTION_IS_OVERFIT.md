# Trading only last year's winners

## The question
Some names win far more often than others in a backtest. Should the screen be restricted to them?

## How it was tested
Names were ranked by their result in one period. The top group was carried forward and measured
over the following period, against the full list traded without selection.

## What came back
The ranking did not persist. Names at the top of one period scattered across the next, and the
selected group did no better than the unselected one. On some runs it did worse, because
selection cut the trade count and left a sample too small to mean anything.

This is what you should expect. With a few hundred trades spread over a hundred names, each name
carries a handful of trades. A handful of trades cannot separate skill from luck, so a ranking
built on them is a ranking of luck.

## What to take from it
Per-name selection is the easiest overfit to commit and the hardest to see, because the output
looks like insight. Select on something structural if you must select: liquidity, spread width,
lot size, whether the contract is quoted at all. Do not select on who won.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

