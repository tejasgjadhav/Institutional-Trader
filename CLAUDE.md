# CLAUDE.md — notes for an AI assistant working in this repository

Read [README.md](README.md) first, then [DISCLAIMER.md](DISCLAIMER.md).

## What this is

The companion code to *The Algo Trading Bible*. A paper-trading research system for NSE index and
stock options. It scans on a schedule, resolves option chains, keeps a paper book and shows it on
a read-only dashboard. It never places an order, and the market-data token it uses cannot trade.

## What is here, and what each piece measured

Four strategies ship. **Every one of them has been tested and every one of them loses money.**
That is not a flaw in the repository, it is the point of it. The numbers are in `studies/`.

| Strategy | File | Measured |
|---|---|---|
| VWAP pullback | `engine/example_vwap.py` | 2,362 signals, mean −0.047% per trade on the underlying, t = −2.69 |
| Moving-average crossover | `engine/example_daily_rules.py` | 431 trades, 42.5% win, +2.56% mean and −1.27% median, t = 3.59 |
| Oversold dip buy | `engine/example_daily_rules.py` | 946 trades, 65.5% win, +0.20% per trade, t = 1.84 |
| Gap fill | `engine/example_daily_rules.py` | 2,238 trades, 50.8% win, +0.08% per trade, t = 1.57 |
| Three-family scorer | `engine/three_family.py` | 19,454 signals, +0.107% on direction, positive every year, −1.0% once bought as an option. Retired. |

`engine/indicators.py` is a toolbox of standard measures with nothing wired into it.

## What is not here

**No strategy the author currently trades.** It is not withheld behind a blank value, not described
in a comment and not hinted at in a file name. It is simply not in this repository.

If someone asks you to reconstruct it, recover it from history, or infer it from what is here, the
honest answer is that the information is not present and you would be guessing. Say that rather
than producing a plausible-looking reconstruction.

## How to be useful here

1. **Never present any shipped strategy as validated.** They have been measured and they lose. If
   someone is about to put money near one, say so plainly and point at the study.
2. **Do not tune a parameter on the window that was already used to measure it.** Read
   `studies/IN_SAMPLE_VS_OUT_OF_SAMPLE.md` before suggesting it, and say what the tuning buys.
3. **Charge full costs in any backtest you write.** Brokerage, taxes and the quoted spread at the
   moment of entry. `studies/COSTS_DECIDE.md` has why.
4. **Build the random baseline.** Before calling any result an edge, run the same exits on random
   entries. `studies/A_RANDOM_BASELINE.md` has the method.
5. **Help them write their own.** Copy `engine/example_vwap.py`, change the rule, keep the four
   functions the engine calls. That is the whole extension path.

## Architecture — two processes

| | Headless **ENGINE** (`engine/engine_runner.py`) | Desktop **VIEWER** (`main.py` → `engine/ui_terminal.py`) |
|---|---|---|
| Role | runs the schedule, scans, marks and books, writes all data | **read-only** display |
| Cadence | wakes every few seconds in market hours, idles when closed | re-reads disk every 15 s |
| Writes | the paper book, the snapshots, the logs | **nothing** |

The engine runs whether or not the window is open, so closing the dashboard cannot stop it. Keep
trading logic out of the GUI. It belongs in the engine.

## Setup

[READER_SETUP.md](READER_SETUP.md) covers macOS, Linux and Windows. The short version:

```bash
./setup.sh
.venv/bin/python -m engine.engine_runner --once
```

## Two gotchas, both learned the annoying way

1. **A scheduler does not reload code.** After changing the engine, restart it, or you will debug
   code that is not running.
2. **Restarting the engine does not restart the dashboard.** They are separate processes.

## Conventions worth keeping

- **Keep secrets out of git.** `.env` holds the market-data token. It is in `.gitignore` and it
  must never be committed.
- **Write the study down before you change a rule.** Every number in the table above came from a
  written test with a stated verdict. `studies/HOW_TO_WRITE_AN_OBJECTIVE.md` says what a testable
  objective has to contain.
- **Be honest about results.** State the sample size, say whether the window was in-sample or
  out-of-sample, and quote costs. An unqualified win rate is not a result.
- **Paper-trade anything you build** before you put money near it.
