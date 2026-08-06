# What paper trading actually tells you

## The question
A rule passed its backtest. What does running it on paper add?

## What it is good for
A forward test catches the things a backtest cannot see. Whether the data arrives in time.
Whether the contract you wanted is quoted when you need it. Whether the spread at the moment of
entry is anything like the spread in your history. Whether the scan finished before the window
closed. Whether the engine was even running.

Every one of those has broken a run. None of them shows up in a backtest, because a backtest
always has the data.

## What it is not good for
It is not evidence of an edge, and the sample is the reason. A few weeks of paper trading is
tens of trades. Tens of trades cannot distinguish a good rule from a lucky one, and treating a
good month as confirmation is how people talk themselves into size.

It also flatters you. A paper fill is taken at a price nobody had to give you.

## How to run one
Keep the size at one lot and leave it there. Log every signal, including the ones you did not
take and the reason. Book outcomes automatically rather than by hand, because a position marked
by hand is a position marked kindly. Then judge it on whether the machine behaved, and judge the
edge on the backtest.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

