# Splits, bonuses and what they do to an option backtest

## The question
A stock splits. The price halves overnight. What does that do to a test that reads prices and
strikes from history?

## What goes wrong
Everything downstream of the price. A breakout screen sees a fifty percent fall and fires. A
strike that was at the money becomes deep in the money. A spread width measured in rupees now
means something different. None of it is a market move and all of it is in the data.

The option side is worse than the stock side. The exchange adjusts contracts on a corporate
action, so the strike list changes, the lot size can change, and the same contract carries two
different meanings either side of the date. A backtest that joins by strike alone will pair the
wrong legs.

## What it cost here
A scale bug of exactly this kind survived a long time in one harness and inverted the ranking of
two variants. It was found by checking put-call parity on the stored legs, not by reading the
code. The published numbers from before the fix were wrong.

## What to take from it
Pull the corporate-action calendar and adjust history before you test anything. Join option legs
by date and by contract identity, never by strike alone. Then check the result against an
identity that must hold, such as put-call parity, and treat a breach as a data fault until proven
otherwise.

Arithmetic you did not check is the most expensive kind.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

