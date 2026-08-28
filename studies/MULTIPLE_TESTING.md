# The cost of trying many things

## The question
A sweep tested three thousand combinations and the best one looks excellent. How excited should
you be?

## The arithmetic
Not at all, by default. Test three thousand things at the usual significance level and about
a hundred and fifty will clear it on noise alone. The best cell in a large sweep is, in
expectation, mostly a record of which combination met the kindest run of data.

The correction is to raise the bar in proportion to how many things you tried. If you tested six
thousand cells, the threshold a result must clear is far higher than the one a single
pre-registered test would face.

## What came back here
Applied honestly on one large sweep, with the threshold raised for roughly seven thousand tests,
the number of candidates clearing both the win-rate and the profit constraint was zero. Not few.
Zero, on the data used to search.

That is a clean answer and it is worth far more than the best cell would have been.

## The practical version
Count your tests. Every parameter you swept, every variant you tried and discarded, every rule you
adjusted after seeing a result. That total is what your threshold has to account for, and it is
always larger than people admit, because the discarded attempts are forgotten.

Then look at the neighbours of your winning cell. A good result surrounded by good results is a
plateau and may be real. A good result surrounded by bad ones is an island, and islands do not
survive contact with new data.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
