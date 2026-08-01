# How much to put on

## The question
A rule has an edge. How large should each position be?

## What the arithmetic says
Growth-optimal sizing tells you a fraction based on the edge and the odds. It is correct and it
is almost never what you should trade, for two reasons.

The first is that it assumes you know the edge. You do not. You have an estimate from a sample,
and the estimate is high, because you chose this rule out of many. Size on an overestimated edge
and the formula hands you a fraction that is too large.

The second is the path. Even with the edge exactly right, full growth-optimal sizing produces
drawdowns most people cannot sit through. A halving is a routine event at that size. Stopping
after the halving converts a theoretical optimum into a realised loss.

## What was measured
Running the same trade sequence at different fractions shows the shape clearly. Return rises with
size, then falls, and the drawdown rises the whole way. The best risk-adjusted point sits well
below the growth-optimal one, and the difference in final money between a half-size and a
full-size run is much smaller than the difference in how it feels to hold.

## What to take from it
Pick a fraction you can hold through the worst stretch in your own backtest, then halve it
because the worst stretch is not over. Keep the size constant while you forward-test, so that
what you learn is about the rule and not about the sizing.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

