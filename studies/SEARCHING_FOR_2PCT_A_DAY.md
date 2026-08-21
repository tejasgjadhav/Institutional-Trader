# The search for two percent a day

## The question
Is there a NIFTY or F&O stock strategy that makes more than two percent a day? Constraints were
added as the search went on: a win rate above 75 percent, at least three or four trades a month,
no option spreads, single-leg futures allowed.

## The answer
**No tested strategy makes two percent a day.** The search covered daily, 15-minute, 5-minute and
1-minute bars, from 2008 to October 2026.

A 75 percent win rate turned out to be easy to reach with stop-free dip buying. Its profit per
trade was about zero after costs and realistic timing.

The only trade that stayed positive in every test was cash-futures arbitrage, and it returns about
six to nine percent a year at recent basis levels.

## What was tested, in order

| # | What | Result |
|---|---|---|
| 1 | Daily-bar intraday rules, 50 stocks, 7 rules, 6 target and stop settings | Pooled across stocks, nothing was positive out of sample |
| 2 | One-minute replay of the 11 survivors, 2022 to 2026 | The daily-bar edges shrank about threefold. The best made +0.1% a trade with t below 1.3 |
| 3 | Trend-filtered dip buying using RSI(2) and Bollinger bands, 2008 to 2026 | 81 to 83 percent win in both periods, and only about 3 to 4 percent a year unlevered |
| 4 | The same dip buy on real futures prices, long and short | 81 percent win, about 0.00 percent a trade. Futures carry and costs removed the edge |
| 5 | Dip buying filtered on falling futures open interest, 100 F&O stocks | 83 percent win, +0.26 percent a trade, t = 4, on end-of-day open interest 2023 to 2026 |
| 6 | The same filter on fresh data and on the open interest actually visible before entry | **Failed.** On fresh data it lost 0.72 percent a trade. On the open interest visible at 15:20 it lost 0.57 percent |
| 7 | A machine-learning model picking one stock a day at the open | It doubled the chance of a clean two percent move, from 14 percent to 24-30 percent, and still made about zero net |
| 8 | 450 exit designs on that model's picks, one-minute data | The best exit from 2023-24 made 0.00 percent in 2025-26. The hindsight ceiling was +0.04 percent |
| 9 | Cash-futures arbitrage, 100 F&O stocks, 2018 to 2026 | Every trade entered at a basis of 0.8 percent or more was positive. That is about 13 percent a year held to expiry, or 19 percent with an early exit. Those basis gaps became rare by 2025-26 |
| 10 | Published intraday strategies from the academic literature, on Indian data | See the table below |

## Published strategies on Indian data

| Strategy | Win rate | Net per trade, 2024-26 |
|---|---|---|
| Opening-range breakout on stocks in play | 18% | −0.05% |
| Noise-boundary intraday momentum on NIFTY | 37-40% | −0.02% to −0.03% |
| First thirty minutes predicting the last thirty on NIFTY | 41% | −0.03% |

The opening-range breakout does have a real edge before costs. It made +0.10 percent a trade in
2022-23 and +0.03 to +0.05 percent in 2024-26. Indian round-trip costs of about 0.10 percent are
larger than that edge, and the edge has shrunk every year.

## The four lessons

**Never quote a daily-bar intraday edge without a one-minute replay.** Daily bars fill at the
auction open, which nobody can actually trade. Step 2 above cost two-thirds of the apparent edge.

**Test every open-interest signal on the open interest visible before entry.** End-of-day open
interest is published after the close. Intraday open interest correlated with it at only 0.61 over
three days. Step 5 looked like a real finding and step 6 killed it.

**A high win rate with a "first profitable close" exit is almost free to get, and it says nothing
about profit.** Step 3 reached 83 percent and made three percent a year.

**Exits cannot create an edge the entry does not have.** Step 8 tested 450 of them and the
hindsight ceiling, the best exit chosen with full knowledge of the future, was +0.04 percent.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
