# The worked example: a VWAP pullback, and how to test it

This is the one strategy that ships with this repository. It lives in
[engine/example_vwap.py](../engine/example_vwap.py) and every number it uses is visible in
[engine/config.py](../engine/config.py).

**It has not been tested.** There is no backtest behind it, no win rate, no expectancy and no
out-of-sample window. The author does not trade it. The numbers in it were chosen to be readable.
This note exists to state the rule precisely and to set out how you would find out whether it is
worth anything, because that is the work the book is about.

## The rule, stated so it can be tested

1. Take 5-minute bars of one liquid stock, from today's open.
2. Compute VWAP, the volume-weighted average price so far today. It needs traded volume, which is
   why this runs on a stock. A spot index has no volume and no VWAP.
3. Wait until the stock trades below VWAP by more than the configured stretch, in percent.
4. Wait for a turn. A turn is a configured number of bars each closing above the one before.
5. Buy one at-the-money call on that stock, in the near expiry, if it is quoted inside the
   configured spread and open-interest limits.
6. Exit at the configured profit on the premium, the configured loss on the premium, or at the
   configured time, whichever comes first.
7. One trade a day at most, inside the configured entry window.

Everything in italics there is a number in `config.py`. You can read all of them.

## Why to expect it to lose before you test it

Say this part out loud before you run anything, because it is the honest prior.

The position is a bought option, so it pays the spread on the way in and on the way out, and it
pays time decay for every hour it is held. A near-expiry at-the-money call on a stock is one of
the widest quotes on the exchange. The move has to be large enough to cover all of that before
the trade is worth anything.

Mean reversion to VWAP is also one of the most widely known intraday ideas there is. That does not
make it wrong. It does mean you should not be surprised to find the edge has already been taken.

## How to test it properly

Follow the method in the other notes in this folder rather than going straight to a run.

**Write the objective first.** See [HOW_TO_WRITE_AN_OBJECTIVE.md](HOW_TO_WRITE_AN_OBJECTIVE.md).
Decide what you are measuring, over what window, and what result would make you drop it.

**Find out what history you can get.** See [DATA_LIMITS.md](DATA_LIMITS.md). Option history is
short and a contract only appears in it if somebody traded it. Decide now what a missing row means.

**Charge full costs from the first run.** See [COSTS_DECIDE.md](COSTS_DECIDE.md). Brokerage, taxes
and the quoted spread at the moment of entry, not an assumed spread.

**Build the random baseline.** See [A_RANDOM_BASELINE.md](A_RANDOM_BASELINE.md). Replace the
signal with a coin toss, keep the same exits, and see what the exits alone produce. Compare your
rule with that, not with zero.

**Hold a window back.** See [IN_SAMPLE_VS_OUT_OF_SAMPLE.md](IN_SAMPLE_VS_OUT_OF_SAMPLE.md). Choose
the stretch and the exits on an earlier window, freeze them, and look at the later window once.

**Then judge it on money, not on win rate.** See
[HIGH_WIN_RATE_IS_NOT_PROFIT.md](HIGH_WIN_RATE_IS_NOT_PROFIT.md). Moving the exits will buy you
any win rate you like and it will not buy you money.

## Your results

Fill this in from your own run. It is blank because nobody has run it.

| | |
|---|---|
| Window tested | |
| Universe | |
| Trades | |
| Win rate | |
| Net per trade, after costs | |
| Worst day | |
| Random baseline, same exits | |
| Out-of-sample window | |
| Out-of-sample result | |
| Verdict | |

If the verdict is that it does not work, write that down and keep the note. A study that records a
death is worth more than one that records a hope, because it stops you testing the same thing
again in six months.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
