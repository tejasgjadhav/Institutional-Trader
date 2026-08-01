# Several positions that are really one bet

## The question
A screen opens positions on five different names on the same day. How many bets is that?

## How it was tested
Open positions were grouped by day and their outcomes compared. The question was simple: when one
loses, what do the others do?

## What came back
They lose together far more often than independence would predict. The screen fires on a market
move, so it fires on several names at once, and those names share the move that triggered it. On
the worst days every open position went the same way.

This matters for the thing people measure least. Average outcome per trade barely changed, and the
worst day got much worse as the position count rose. A rule that looks tame per trade can be
dangerous per day.

## What to take from it
Count the correlated exposure, not the position count. Cap how many positions may be open on the
same side on the same day, and measure your drawdown by day rather than by trade.

Then look at the worst day in your backtest and ask whether you would have kept running the
system the next morning. That, not the average, is what decides whether you ever see the average.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

