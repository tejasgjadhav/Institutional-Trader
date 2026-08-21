# Three simple rules, tested on eight years

## The question
The three most commonly taught mechanical rules are a moving-average crossover, an oversold dip
buy, and a gap fill. All three are easy to compute and easy to run. Do any of them make money on
Indian stocks after costs?

## How it was tested
Twenty liquid NSE names. Daily bars from December 2018 to October 2026, which is just under eight
years. Long only. Costs charged at 0.10 percent round trip, which is about what an Indian retail
cash equity trade pays all in.

Each rule was coded exactly as it is usually taught, with no tuning.

**Moving-average crossover.** Buy when the 20-day average crosses above the 50-day. Sell when it
crosses back below.

**Oversold dip buy.** Buy when the 2-period RSI falls below 10, but only while the close is above
the 200-day average. Sell on the first close above the previous day's high.

**Gap fill.** Buy at the open when the stock opens one percent or more below the previous close.
Sell at that day's close.

All three are implemented in [engine/example_daily_rules.py](../engine/example_daily_rules.py) and
every number is visible in [engine/config.py](../engine/config.py).

## What came back

| | Crossover | Dip buy | Gap fill |
|---|---|---|---|
| Trades | 431 | 946 | 2,238 |
| Win rate | 42.5% | 65.5% | 50.8% |
| Mean net per trade | **+2.56%** | +0.20% | +0.08% |
| Median net per trade | **−1.27%** | +0.84% | +0.03% |
| Standard deviation | 14.8% | 3.4% | 2.5% |
| t-statistic | **3.59** | 1.84 | 1.57 |
| Best trade | +125.9% | +9.4% | +20.9% |
| Worst trade | −27.8% | −26.9% | −20.0% |

## Reading the three rows that matter

**The crossover is the only one with a statistically convincing mean, and most of its trades
lose.** Win rate 42.5 percent, median −1.27 percent, mean +2.56 percent. One trade in the sample
made 126 percent. That is what trend following looks like from the inside: you are wrong most
days, and a small number of long holds pay for all of it. A standard deviation of 14.8 percent on
a mean of 2.56 percent means you need a lot of trades before the average shows up, and you have to
still be trading when it does.

**The dip buy wins often and barely pays.** It wins two trades in three and makes 0.20 percent a
trade after cost, with t = 1.84. Below two, so not significant on 946 trades. This is the pattern
described in [HIGH_WIN_RATE_IS_NOT_PROFIT.md](HIGH_WIN_RATE_IS_NOT_PROFIT.md): the exit rule, sell
on the first close above the previous day's high, manufactures the win rate. Note the worst trade,
−26.9 percent. There is no stop, so one position can give back a hundred small wins.

**The gap fill is a coin.** 50.8 percent win, 0.08 percent a trade, t = 1.57. Before costs it is
slightly positive. The 0.10 percent round trip is most of what it earns.

## What to take from it

None of these three is an edge you should trade as it stands. The crossover has the only
defensible statistic, and holding it requires sitting through a losing majority and a 28 percent
drawdown on a single name, which most people will not do.

The useful part is the shape of each result. A high win rate came with no money. A low win rate
came with money and a long wait. A rule with no asymmetry in it came back as a coin. Those three
shapes cover most of what you will meet, and recognising which one you are holding is more useful
than any of the three rules.

**Test them yourself before you believe this table.** The rules are twenty lines each and the data
is a free API call. Reproducing someone else's result is the cheapest research you will ever do,
and it is the only way to find out whether they made a mistake.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
