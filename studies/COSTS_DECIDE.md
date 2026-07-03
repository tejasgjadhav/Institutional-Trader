# Costs decide, not signals

## The question
A screen looks profitable on prices. Does it survive once you pay to trade it?

## How it was tested
Every candidate was re-run with the costs charged on each leg: brokerage, exchange fees,
securities transaction tax, GST, stamp duty, and the bid-ask spread actually quoted at the
moment of entry. Nothing was assumed. Where a quote was missing, the trade was dropped rather
than filled at a guess.

## What came back
Most ideas died here and nowhere else. A signal with a small edge on prices turns negative the
moment a real spread is charged against it, and short-dated options have the widest spreads of
anything on the exchange. The gap between a gross result and a net result was routinely larger
than the edge itself.

Two things mattered more than the signal. The first is how often it trades, because every trade
pays the toll again. The second is how wide the market is in the contract you have to use, not
the contract you wish you could use.

## What to take from it
Charge full costs from the first run, not at the end. A backtest that reports gross numbers is
not a backtest, it is a chart. If your edge per trade is smaller than your cost per trade, no
amount of tuning will save it.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

