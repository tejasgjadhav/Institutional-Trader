# Auditing a result you want to be true

## The question
A backtest supports a decision you are about to make. How do you check it, given that you want it
to be right?

## Why re-running is not checking
Re-running reproduces the bug. So does a second script that reuses the same harness, which is how
most "independent cross-checks" are built. The checks agree with each other because they are the
same mistake, twice.

## What actually works
Assume the result is wrong and go looking for the reason. That framing matters more than any
particular test, because it changes what you look at.

The specific checks that have earned their place here:

**Join on identity, not position.** When combining two price series, join them by date and require
both to exist on the entry day. Joining by row position silently pairs prices from different days
whenever one series skips a day, which illiquid instruments do constantly.

**Check an identity that must hold.** If two things in your data are related by arithmetic that
cannot be false, check it on every row. A breach is a data fault, not a discovery.

**Count what you fetched against what you asked for.** A failed download must not look like an
absence. A run that quietly skipped most of its symbols will still report a clean win rate on the
ones it reached.

**Make the harness deterministic.** If two runs over the same window give different samples,
something non-deterministic is deciding what you measure, and your result is partly luck.

## The standing rule
A research script that gates a real decision is production code and gets the same scrutiny as
production code. Before you act on a result, have it checked by someone, or something, that is
trying to refute it rather than confirm it.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
