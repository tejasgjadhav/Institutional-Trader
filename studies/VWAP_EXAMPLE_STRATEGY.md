# The worked example: a VWAP pullback, and how to test it

This is the one strategy that ships with this repository. It lives in
[engine/example_vwap.py](../engine/example_vwap.py) and every number it uses is visible in
[engine/config.py](../engine/config.py).

**It has now been tested, and it loses.** The result is below. The author does not trade it and
never did. The numbers in it were chosen to be readable, not because a test said so. This note
states the rule precisely, sets out how it was tested, and gives the answer.

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

## The result

The rule above was run on real 5-minute data. Ten liquid NSE names, 4,860 sessions, September
2024 to October 2026. The signal fired on 2,362 of those sessions, which is 48.6 percent of them.

This measures the move in the **underlying** from the signal bar's close to 15:15. It does not
include the option. That is deliberate, and it is enough to settle the question, because a bought
call cannot make money if the underlying does not go up.

| | |
|---|---|
| Window | 12 Sep 2024 to 30 Oct 2026 |
| Names | 10 liquid NSE stocks |
| Sessions scanned | 4,860 |
| Signals | 2,362 (48.6% of sessions) |
| Mean move to the exit | **−0.047%** |
| Median move | −0.068% |
| Win rate | 45.3% |
| Standard deviation | 0.84% |
| t-statistic | **−2.69** |
| Mean best point reached | +0.60% |
| Mean worst point reached | −0.67% |
| Random entry, same window and exit | −0.17%, 38.5% win |

## What that says

**The signal loses on the underlying.** The mean move after it fires is negative, and the
t-statistic of −2.69 says that is not noise at this sample size. It is a real, measurable negative
drift, not a flat line.

**It is better than entering at random, and both are losing.** A random entry in the same window
with the same exit gave −0.17%. So waiting for a stretch below VWAP and a turn does pick a better
moment than a coin would. It picks a better moment to lose money.

**The option version is worse than this, necessarily.** This table ignores the option entirely. A
bought at-the-money call pays the spread twice and pays time decay for every hour it is held. The
underlying would have to rise enough to cover all of that, and on average it falls.

**The best and worst points are close to symmetric.** The trade reaches +0.60% at its best and
−0.67% at its worst before the exit. There is no asymmetry for a target and a stop to exploit.
Moving the exits will change the win rate and will not create an edge, which is the point made in
[HIGH_WIN_RATE_IS_NOT_PROFIT.md](HIGH_WIN_RATE_IS_NOT_PROFIT.md).

## Verdict

**Falsified for this purpose, on this data.** The shipped example does not have a directional edge
and should not be traded. It stays in the repository because it is a complete, readable, working
strategy and the machine needs something to run. It is a teaching example, and now it is a
teaching example with a measured result attached.

If you want to improve it, the honest next steps are to test a different exit on the same entries,
to test the short side, or to replace the entry altogether. Do not re-tune the stretch on this
data. Read [IN_SAMPLE_VS_OUT_OF_SAMPLE.md](IN_SAMPLE_VS_OUT_OF_SAMPLE.md) first and understand
what re-tuning on the window you just looked at buys you.

## Reproducing it

The rule is in [engine/example_vwap.py](../engine/example_vwap.py) and every number is in
[engine/config.py](../engine/config.py). Pull your own 5-minute history, apply the seven steps,
and measure the move to the exit time. You should land close to the table above. If you do not,
one of us has a bug, and finding out which is a better use of an evening than tuning a parameter.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
