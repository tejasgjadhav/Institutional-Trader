# Does a forecasting model help?

## The question
Time-series forecasting is a solved-looking problem with good libraries. Does putting one in
front of a trading rule improve it?

## How it was tested
A standard additive forecasting model was fitted on index and stock history, refitted walking
forward so it never saw the future, and its direction used as a filter on an existing screen.
Results were compared with the same screen unfiltered.

## What came back
The fit looks excellent and predicts nothing useful. The model reproduces trend and seasonality,
which is most of the variance in a price series and almost none of the tradeable part. As a
directional filter it was indistinguishable from a coin toss, and it cut the trade count enough
to make the remaining sample too small to judge.

## What to take from it
A good fit is not a forecast. Judge a model by whether it improves the decision you actually
make, measured on trades you did not use to fit it. Most of the time the honest answer is that
it does not, and the simpler rule wins because it has fewer ways to be wrong.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

