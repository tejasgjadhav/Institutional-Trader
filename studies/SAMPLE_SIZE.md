# How many trades settle the question

## The question
A rule won 55 percent of 60 trades. Is it better than a coin?

## The arithmetic
No. Sixty trades at 55 percent is well inside what a fair coin produces. Roughly speaking, telling
55 percent apart from 50 percent with any confidence needs on the order of a thousand trades.
Telling 52 percent apart from 50 percent needs several thousand.

This is why win rate is such a poor instrument for small samples, and why the difference between
two variants measured on a few dozen trades each is almost never real.

## Where it bites in practice
A selective rule produces few signals. A rule firing four times a month takes twenty years to
reach a thousand trades. You will never have the sample the statistic needs, so you have to get
confidence from somewhere else.

The alternatives are pooling across many instruments, which assumes they behave alike, and
measuring money per trade rather than win rate, which uses the size of each outcome instead of
only its sign and therefore needs fewer observations.

## What to do with a small sample
State the number of trades next to every statistic, always. Put a confidence interval on it and
look at whether that interval contains zero. Treat any comparison of two variants on small samples
as undecided rather than as a ranking.

And be especially careful with the best name in a basket. If a hundred names each produce a handful
of trades, the best one is a record of luck, not of merit.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
