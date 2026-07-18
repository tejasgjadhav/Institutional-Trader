# Why a good backtest stops working

## The question
A rule tested well on one window. Does it hold on a window it has never seen?

## How it was tested
Parameters were chosen on an earlier window and then frozen. The frozen rule was run, unchanged,
on a later window that was never looked at during the search.

## What came back
Results fell, often a long way. Some cases inverted outright: the setting that was best in the
first window was among the worst in the second.

The pattern was consistent enough to be worth stating plainly. The more settings a search tried,
the worse the drop. A sweep over thousands of combinations will always hand back a best cell.
That cell is mostly a record of which combination caught the luckiest run of days.

Single-name results were the worst offenders. A name with a spectacular result in the first
window usually came back ordinary in the second, and nothing in the first window said which
names those would be.

## What to take from it
Hold a window back and do not look at it. Look at it once. If the result falls apart, the idea
failed, and re-tuning on the held-back window just spends the only clean data you had.

Prefer a result that is merely good across many settings to one that is excellent in a single
cell. A sharp peak surrounded by bad neighbours is noise with a flag planted on it.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

