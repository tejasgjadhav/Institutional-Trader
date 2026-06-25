# What you can and cannot backtest

## The question
Before testing anything, what history can you actually get, and what does that rule out?

## What is available
Daily bhavcopy from the exchange goes back many years and covers every listed contract,
including ones that never traded. Intraday option history from a broker API goes back a few
years at best, and a contract only appears in it if somebody traded it.

Those two facts are not the same kind of gap, and confusing them is how a backtest goes wrong.

## The trap
A missing row has two causes that look identical in a dataframe. The contract may never have
traded, or your fetch may have failed. One is information and the other is a bug. If you do not
separate them, a network problem silently becomes a trading result.

A run that skipped a tenth of its symbols because of a DNS failure still reports a clean win
rate on the symbols it did reach. Nothing in the output says a fetch failed.

## What to take from it
Decide what history you need before you design the rule. Count what you fetched and compare it
with what you asked for, on every run, and fail loudly when the two disagree. Keep a separate
marker for "no trade" and "no data", and never let them share a value.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

