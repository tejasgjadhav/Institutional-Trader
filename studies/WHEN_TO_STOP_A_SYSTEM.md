# Knowing when a live system has stopped working

## The question
A system is running and it is losing. Is the edge gone, or is this a normal bad stretch?

## Why it needs deciding in advance
After the losses start, every answer is motivated. The only honest version of this decision is
made before the system goes live, written down, and left alone.

## The method
Take the backtest and find the worst run of losses in it. That is the minimum you must be willing
to sit through, because it already happened once in the sample. Then work out how long a stretch
would have to be before it is genuinely unlikely given the measured win rate.

The gap between those two numbers is the honest band. Inside it, say nothing and keep running.
Beyond it, stop and re-test on the new data.

## What came back here
The worst stretch in sample was longer than most people expect, and longer than most people would
tolerate without an agreed rule. A large share of live sessions produced no signal at all, which
feels like failure and is not. Quiet is the normal state of a selective rule.

## What to take from it
Write the stopping rule before you start. Say how many consecutive losses, or what drawdown, or
what period of underperformance, triggers a review. Then review rather than react, because the
review may conclude that nothing is wrong.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

