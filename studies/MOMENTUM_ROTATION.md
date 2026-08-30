# Cross-sectional momentum, and what to check before you believe it

## The idea
Rank a list of stocks by their return over the last six or twelve months, skipping the most recent
month. Hold the top decile, rebalance monthly. It is the most documented anomaly in finance and it
has been written about for thirty years.

## Why it is worth testing here
It is trivial to compute, it needs only daily closes, and it rebalances twelve times a year rather
than daily, so costs are a small fraction of the return rather than most of it. For anyone whose
first attempt at intraday trading died on costs, this is the obvious next place to look.

## What to check before you believe your own result
**Skip the most recent month.** Momentum measured including last month is contaminated by
short-term reversal and the two effects partly cancel. The published versions skip it for a reason.

**Rebuild the list as it stood.** Ranking today's index members on ten years of history is the
survivorship trap described in [SURVIVORSHIP_BIAS.md](SURVIVORSHIP_BIAS.md), and momentum is
unusually exposed to it, because the names that fell out are exactly the ones that lost.

**Measure the drawdown, not the average.** Momentum's failure mode is a sharp reversal at a market
turn, and those are concentrated: a handful of months do most of the damage. An average annual
return tells you nothing about whether you could have held it through those months.

**Compare against buying the index.** A strategy returning twelve percent a year is not interesting
if the index returned twelve percent a year. See
[WHAT_TO_COMPARE_AGAINST.md](WHAT_TO_COMPARE_AGAINST.md).

## The honest caveat
This note describes what to test and how to test it. It does not report a result, because no result
is published here. Run it yourself on your own data and write down what you find, including if the
answer is that it does not work on the names you can actually trade.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
