# Using information you would not have had

## The question
A backtest says a rule works. Did the rule have access to anything the live system would not have
had at that moment?

## How it hides
Look-ahead rarely appears as an obvious peek at tomorrow. It appears as an off-by-one.

A trigger fires on a bar, and the backtest fills at that bar's **open**. The open happened before
the trigger condition was known. Live, the earliest you could act is the next price after the bar
completed. The backtest is buying at a price that existed only before the decision could be made.

Other common forms: using a session's closing price in a rule that runs during the session, using
a figure that is published after the close as if it were available at 15:20, and taking a rolling
high or low that includes the current bar when testing a breakout.

## What it cost here
An audit of one deployed addition found exactly the trigger-bar-open form. Correcting it turned a
clearly profitable add-on into a losing one, and turned its best historical day from a large gain
into a large loss. The addition had been live. It was switched off the same day.

Nothing crashed. The numbers were plausible throughout. The only way it was found was an audit
that started from the assumption that the result was wrong.

## How to find it in your own work
For every price your backtest uses, ask what time it became known and what time your rule decides.
Write both down. If the first is not strictly before the second, you have look-ahead.

Then shift every fill one bar later and re-run. If the edge disappears, the edge was the off-by-one.
That single test catches most of it and takes ten minutes.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
