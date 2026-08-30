# Studies — the research notes

These are the notes that ship with the reader edition. Each one states a question that was asked,
how it was tested, and what the answer turned out to be.

They do not contain a specification. There are no parameter values here, no screens, no distances,
no widths, no floors and no exits. The strategies the author trades are not in this repository in
any form, and these notes do not describe them. What they carry is the method and the verdict,
which is the part that transfers.

Read them for how to run a test and how to read a result. Then run your own tests. The book
explains the method in full.

## Start here

| File | The question it answers |
|---|---|
| [HOW_TO_WRITE_AN_OBJECTIVE.md](HOW_TO_WRITE_AN_OBJECTIVE.md) | How do you write a test that can fail? |
| [DATA_LIMITS.md](DATA_LIMITS.md) | What can and cannot be backtested with the data you can get? |
| [COSTS_DECIDE.md](COSTS_DECIDE.md) | What happens to a strategy once real costs are charged? |

## Reading a result honestly

| File | The question it answers |
|---|---|
| [A_RANDOM_BASELINE.md](A_RANDOM_BASELINE.md) | Does the rule beat a coin wearing the same exits? |
| [HIGH_WIN_RATE_IS_NOT_PROFIT.md](HIGH_WIN_RATE_IS_NOT_PROFIT.md) | Can you buy a high win rate, and is it worth buying? |
| [IN_SAMPLE_VS_OUT_OF_SAMPLE.md](IN_SAMPLE_VS_OUT_OF_SAMPLE.md) | Why does a good backtest stop working? |
| [THE_FALSIFICATION_SWEEP.md](THE_FALSIFICATION_SWEEP.md) | How do you prove a whole idea is dead? |
| [WHAT_TO_COMPARE_AGAINST.md](WHAT_TO_COMPARE_AGAINST.md) | A return on its own means nothing. Against what? |

## Where backtests go wrong

| File | The question it answers |
|---|---|
| [SURVIVORSHIP_BIAS.md](SURVIVORSHIP_BIAS.md) | What does testing on today's list do to the result? |
| [CORPORATE_ACTIONS.md](CORPORATE_ACTIONS.md) | What do splits and bonuses do to an option backtest? |
| [PER_NAME_SELECTION_IS_OVERFIT.md](PER_NAME_SELECTION_IS_OVERFIT.md) | Should you trade only the names that won last year? |
| [UNIVERSE_CHOICE.md](UNIVERSE_CHOICE.md) | Which stocks should a screen run over? |
| [FORECASTING_MODELS.md](FORECASTING_MODELS.md) | Does a forecasting model help? |

## Risk and running it live

| File | The question it answers |
|---|---|
| [POSITION_SIZING.md](POSITION_SIZING.md) | How much should go on each position? |
| [CORRELATED_POSITIONS.md](CORRELATED_POSITIONS.md) | When is a basket of positions really one bet? |
| [WHAT_A_FORWARD_TEST_IS_FOR.md](WHAT_A_FORWARD_TEST_IS_FOR.md) | What does paper trading actually tell you? |
| [WHEN_TO_STOP_A_SYSTEM.md](WHEN_TO_STOP_A_SYSTEM.md) | Has the edge gone, or is this a normal bad run? |
| [KEEPING_AN_AUDITABLE_RECORD.md](KEEPING_AN_AUDITABLE_RECORD.md) | Can you explain a trade six months later? |

## Ideas that were tested and did not survive

| File | The question it answers |
|---|---|
| [CANDLESTICK_PATTERNS_FALSIFIED.md](CANDLESTICK_PATTERNS_FALSIFIED.md) | Do candlestick conjunctions work? 760,594 entries say no. |
| [SEARCHING_FOR_2PCT_A_DAY.md](SEARCHING_FOR_2PCT_A_DAY.md) | Ten studies, 2008 to 2026, looking for two percent a day. |

## The strategies that ship, and what they measured

Both of these run. Both have been backtested on real data with costs charged, and the results are
in the notes. Neither is recommended and the author trades neither.

| File | |
|---|---|
| [VWAP_EXAMPLE_STRATEGY.md](VWAP_EXAMPLE_STRATEGY.md) | The worked VWAP example. 2,362 signals over 4,860 sessions: mean −0.047% per trade on the underlying, t = −2.69. It loses. |
| [THREE_SIMPLE_RULES_TESTED.md](THREE_SIMPLE_RULES_TESTED.md) | A crossover, a dip buy and a gap fill, over eight years with costs. One convincing mean, one coin, one that wins often and pays nothing. |
| [THE_THREE_FAMILY_SYSTEM.md](THE_THREE_FAMILY_SYSTEM.md) | The system the book describes. 19,454 signals, +0.107% per signal on direction, positive every year since 2019, and −1.0% once you buy the option. A real edge that costs more to trade than it earns. |

## Other ground, and what is not settled on it

| File | The question it answers |
|---|---|
| [MOMENTUM_ROTATION.md](MOMENTUM_ROTATION.md) | Cross-sectional momentum, and what to check before believing your own result |
| [PAIRS_AND_MEAN_REVERSION.md](PAIRS_AND_MEAN_REVERSION.md) | Why the hard part of pairs trading is not the statistics |
| [SEASONALITY_AND_DATA_MINING.md](SEASONALITY_AND_DATA_MINING.md) | Day-of-week effects and other things you will find if you look |
| [EVENT_DRIFT.md](EVENT_DRIFT.md) | Trading around a date that is known in advance |
| [WHAT_THE_ORDER_BOOK_CAN_TELL_YOU.md](WHAT_THE_ORDER_BOOK_CAN_TELL_YOU.md) | Depth data, and the question this trail has not answered |

Those five carry no result. They set out the question, the traps and the checks, and say plainly
that nothing is published here. A note that records an open question is worth keeping; a note that
invents an answer is not.

## Reproducing the published numbers

| Script | Produces |
|---|---|
| `reproduce_vwap_result.py` | the table in [VWAP_EXAMPLE_STRATEGY.md](VWAP_EXAMPLE_STRATEGY.md) |
| `reproduce_daily_rules_result.py` | the table in [THREE_SIMPLE_RULES_TESTED.md](THREE_SIMPLE_RULES_TESTED.md) |

Run them from the repository root with your own market-data token. You should land close to the
published figures. If you do not, one of us has a bug.

## The six newest notes

| File | The question it answers |
|---|---|
| [LOOK_AHEAD_BIAS.md](LOOK_AHEAD_BIAS.md) | Did your rule use information it would not have had? |
| [AUDIT_YOUR_OWN_BACKTEST.md](AUDIT_YOUR_OWN_BACKTEST.md) | How do you check a result you want to be true? |
| [SAMPLE_SIZE.md](SAMPLE_SIZE.md) | How many trades settle the question? |
| [MULTIPLE_TESTING.md](MULTIPLE_TESTING.md) | What does trying three thousand things cost you? |
| [THE_SPREAD_YOU_ACTUALLY_GET.md](THE_SPREAD_YOU_ACTUALLY_GET.md) | Can your backtest know what was quotable? |
| [WHEN_THE_MARKET_CHANGES.md](WHEN_THE_MARKET_CHANGES.md) | What if the exchange changed, not your rule? |

Study notes. Not investment advice. If you trade on anything here you do so at your own risk,
and Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
