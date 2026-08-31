# Three more simple rules, and the trap each one hides

## The question
Bollinger reversion, the 52-week high breakout and the classic oversold bounce. All three are
taught everywhere and all three are a few lines of code. Do they work on Indian stocks after costs?

## How it was tested
The same harness as [THREE_SIMPLE_RULES_TESTED.md](THREE_SIMPLE_RULES_TESTED.md). Twenty liquid NSE
names, daily bars from December 2018 to October 2026, long only, 0.10 percent charged round trip.
No tuning. The script is [reproduce_three_more_rules.py](reproduce_three_more_rules.py).

**Bollinger reversion.** Buy a close below the lower band, 20-day average and two standard
deviations. Sell on a touch of the middle band.

**52-week high breakout.** Buy a close at a new 250-day high. Sell after a 10 percent fall from the
running peak.

**Oversold bounce.** Buy when the 14-period RSI falls below 30. Sell when it rises above 50.

## What came back

| | Bollinger reversion | 52-week high | Oversold bounce |
|---|---|---|---|
| Trades | 589 | 139 | 235 |
| Win rate | 66.6% | 38.8% | **71.9%** |
| Mean net per trade | +0.33% | **+2.59%** | +1.07% |
| Median net per trade | +1.82% | **−3.27%** | +2.77% |
| Standard deviation | 6.4% | 17.5% | 7.7% |
| t-statistic | 1.25 | 1.75 | **2.14** |
| Best trade | +11.8% | **+86.1%** | +17.0% |
| Worst trade | **−47.5%** | −14.7% | **−46.4%** |

## The trap in each one

**Bollinger reversion hides its risk in one number.** It wins two trades in three with a median of
+1.82 percent, which reads beautifully. Then look at the worst trade: **−47.5 percent**. There is no
stop, and the exit is a touch of the middle band, so a position that keeps falling is simply held.
Thirty good trades do not cover one of those. The t-statistic of 1.25 says the mean is not
distinguishable from zero despite 589 trades.

**The 52-week high is trend following and behaves like it.** It loses on three trades in five, its
median trade is −3.27 percent, and one trade made 86 percent. A mean of +2.59 percent on a standard
deviation of 17.5 percent across only 139 trades gives t = 1.75, which does not clear the bar. See
[SAMPLE_SIZE.md](SAMPLE_SIZE.md) for why 139 trades cannot settle this.

**The oversold bounce is the most dangerous of the three, because it looks the best.** It has the
highest win rate at 71.9 percent, a positive median, and the only t-statistic above 2. It also has
a worst trade of −46.4 percent, for the same reason as the first one: buying an oversold reading
with no stop means buying everything on its way down, including the ones that do not come back.

## What to take from it

**A high win rate and a catastrophic worst trade go together.** Two of these three win about seven
times in ten and both have a worst trade near minus fifty percent. That is not a coincidence. The
exits that produce the win rate are the exits that refuse to cut a loser.

**None of the three clears a sensible bar.** One has t = 2.14 and a −46 percent tail. The other two
are not significant at all. Run them yourself before you believe this table.

**The useful question is what a stop would do.** Adding one to the two reversion rules would cut the
win rate and cut the tail. Whether it helps the money is an empirical question, and it is a good
first exercise with this repository. Test it on a window, then check it on a window you held back.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
