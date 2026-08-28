# When the exchange changes underneath you

## The question
Your rule did not change and your results did. What if the market changed instead?

## A concrete example
In August 2026 the exchange changed the session structure for stocks with derivatives. Continuous
cash trading now stops earlier, a closing auction runs after it, and the official closing price is
the auction's equilibrium price rather than the old weighted average of the final half hour.

That is not a small administrative change. It means a "closing price" before that date and a
"closing price" after it are two different constructs. Any rule that uses the close, and any
backtest that spans the date, is comparing two things that are not the same measurement.

## Why it matters more than it sounds
A structural change like this does not announce itself in your results. It shows up as a rule that
quietly stops working, or as a backtest that looks fine because it averaged across the boundary.
Nothing errors.

The same applies to lot size revisions, expiry day changes, changes in which instruments have
derivatives at all, and tick size changes. All of them silently alter what your historical series
means.

## What to do
Keep a dated list of structural changes in the markets you trade, and check it before you test any
window that spans one. Where a change splits your history into two regimes, test each side
separately and say which side your conclusion rests on.

And when a live rule stops working, check the exchange's circulars before you check your code. It
is cheaper, and it is the explanation often enough to be worth doing first.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
