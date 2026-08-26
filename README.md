# Institutional Trader — reader edition

The companion code to **The Algo Trading Bible**. It is a paper-trading research system for
NSE index and stock options: it scans on a schedule, resolves option chains, keeps a paper book
and shows the lot on a read-only dashboard. **It never places an order.**

## Read this before anything else

**No strategy of the author's is in this repository.** Not behind a blank value, not described
in a comment, not hinted at in a file name. The strategies he trades are not published and they
are not going to be.

What ships instead is the machine, plus **one worked example** so the machine has something to
run. The example is a VWAP pullback on an index, bought as a call. It is written out in full in
[engine/example_vwap.py](engine/example_vwap.py) with every number visible in
[engine/config.py](engine/config.py).

**The example has never been backtested.** It has no measured win rate, no measured expectancy
and no evidence behind it. The author does not trade it. The numbers in it were chosen to be
readable. It is there so you can watch a screen become a signal, a signal become an option, an
option become a paper fill, and a fill become a row on the dashboard.

**Deploy it at your own risk.** If you run it, or act on anything it prints, that is your
decision and your risk alone. See [DISCLAIMER.md](DISCLAIMER.md).

It has now been backtested. [studies/VWAP_EXAMPLE_STRATEGY.md](studies/VWAP_EXAMPLE_STRATEGY.md)
has the numbers: 2,362 signals across 4,860 sessions, a mean of −0.047% per trade on the
underlying, t = −2.69. It loses, and the note says so and shows the working.

Three more rules ship beside it in `engine/example_daily_rules.py`, each measured over eight years
with costs charged. See [studies/THREE_SIMPLE_RULES_TESTED.md](studies/THREE_SIMPLE_RULES_TESTED.md).

**Does this not match the screenshots in the book?** It does not, and
[WHY_THIS_DIFFERS_FROM_THE_BOOK.md](WHY_THIS_DIFFERS_FROM_THE_BOOK.md) explains exactly why.

## What you get

| | |
|---|---|
| **The engine** | `engine/engine_runner.py` — the schedule, the loop, the snapshots |
| **Market data** | `engine/data_fetcher.py`, `engine/data_utils.py`, `engine/instruments.py` |
| **Options** | `engine/options.py` — resolve a strike to a tradeable contract, check it is quoted |
| **Indicators** | `engine/indicators.py` — moving averages, VWAP, ATR, channels, pivots, RSI, MACD |
| **The example book** | `engine/example_vwap.py` — a complete strategy, end to end |
| **Three simple rules** | `engine/example_daily_rules.py` — a crossover, a dip buy and a gap fill |
| **The book's signal system** | `engine/three_family.py` — the three-family scorer, retired and measured ([study](studies/THE_THREE_FAMILY_SYSTEM.md)) |
| **The dashboard** | `engine/ui_terminal.py` — read-only; the engine writes, this reads |
| **The notes** | `studies/` — how the research was run and what it concluded |

The engine and the viewer are two processes. The engine runs whether or not the window is open,
and closing the window cannot stop it.

## Setup

Full walkthrough in [READER_SETUP.md](READER_SETUP.md). On macOS or Linux:

```bash
./setup.sh
cp .env.example .env          # then put your own Upstox market-data token in it
.venv/bin/python -m engine.engine_runner --once
```

The token is read-only market data. It cannot place an order.

Open the dashboard with `.venv/bin/python main.py`.

## Writing your own strategy

Copy `engine/example_vwap.py` to a new file and change the rule. Keep the four functions the
engine calls: `scan_signals`, `resolve_positions`, `write_status`, and the three path constants
at the top. Add a block for it in `engine/config.py`, then call it from `_example_book` in
`engine/engine_runner.py` or write a sibling method next to it.

`engine/indicators.py` has the usual measures already written. None of them is wired into
anything, and none of them is an edge on its own.

Then test it. `studies/` says how, and the book says it at length. Do not skip to running it.

## What this is not

It is not investment advice, not a recommendation and not a signal service. It is not a proven
money-maker, and the book says so at length. Treat it as a study system.

**Before you trade anything from here: run your own backtest, on data you pulled yourself, with
full costs charged. Then paper-trade it. Then decide for yourself and own the decision.** Anything
you run from this repository, you run at your own risk.

Read [DISCLAIMER.md](DISCLAIMER.md) in full before you run anything.
