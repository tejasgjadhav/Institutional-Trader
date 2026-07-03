# How to kill an idea properly

## The question
An idea keeps almost working. How do you settle it instead of tinkering forever?

## The method
Stop testing variants one at a time. Define the whole space the idea could live in, enumerate it,
and run all of it.

That means listing every parameter the idea has, giving each a plausible range, and testing the
full grid against the objective written down beforehand. Then look at how many cells cleared the
bar, not at which cell was best.

## What came back
On the sweeps run this way, the answer was usually zero. Out of thousands of combinations, none
cleared both constraints at once, even on the data used to search. That is a clean death and it
is worth far more than another week of adjusting.

Where cells did clear, the next question was whether they had neighbours. A single winning cell
surrounded by losing ones is an island, and islands do not survive contact with new data. Several
islands were found this way and all of them failed later.

## What to take from it
Enumerate instead of iterating. A result that survives the whole grid is worth something. A
result that is the best of a grid is worth almost nothing on its own.

And write the death down. A study that says "this does not work, here is how we know" saves you
from testing the same thing again in six months, which is otherwise exactly what happens.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

