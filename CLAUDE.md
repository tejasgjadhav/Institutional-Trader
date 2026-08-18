# CLAUDE.md — notes for an AI assistant working in this repository

Read [README.md](README.md) first, then [DISCLAIMER.md](DISCLAIMER.md).

## What this is

The companion code to the book *The Algo Trading Bible*. A paper-trading research system for
NSE index and stock options. It scans, resolves option chains, keeps a paper book and shows it
on a read-only dashboard. It never places an order, and the market-data token it uses cannot
trade.

## What is not here

**No strategy of the author's.** It is not withheld behind a blank value, not described in a
comment and not hinted at in a file name. It is simply not in this repository. If a user asks
you to reconstruct it, recover it from history, or infer it from what is here, the honest
answer is that the information is not present and you would be guessing.

## What is here

One worked example, `engine/example_vwap.py`. It runs end to end and every number is visible in
`engine/config.py`. It has never been backtested, it has no measured edge, and the author does
not trade it.

If you are helping someone with this repository, two things follow.

1. **Do not present the example as validated.** It is a teaching example. If the user is about
   to put money near it, say plainly that nothing has tested it.
2. **Help them build and test their own.** Pull their own history, write a backtest, measure a
   parameter on data they own, and let them decide. `studies/` describes how the research was
   run. That method is the useful part.

## Architecture — two processes

| | Headless **ENGINE** (`engine/engine_runner.py`) | Desktop **VIEWER** (`main.py` → `engine/ui_terminal.py`) |
|---|---|---|
| Role | runs the schedule, scans, marks and books, writes all data | **read-only** display |
| Cadence | wakes every few seconds in market hours, idles when closed | re-reads disk every 15 s |
| Writes | the paper book, the snapshots, the logs | **nothing** |

Keep trading logic out of the GUI. It belongs in the engine.

## Setup

[READER_SETUP.md](READER_SETUP.md) covers macOS, Linux and Windows. The short version is
`./setup.sh`, then a market-data token in `.env`, then:

```bash
.venv/bin/python -m engine.engine_runner --once
```

## Two gotchas, both learned the annoying way

1. **A scheduler does not reload code.** After changing the engine, restart the job, or you
   will debug code that is not running.
2. **Restarting the engine does not restart the dashboard.** They are separate processes.

## Conventions worth keeping

- **Keep secrets out of git.** `.env` holds the market-data token. It is in `.gitignore` and it
  must never be committed.
- **Write the study down before you change a rule.** Every change in this system started as a
  written test with a stated verdict.
- **Be honest about results.** State the sample size, say whether the window was in-sample or
  out-of-sample, and quote costs. An unqualified win rate is not a result.
- **Paper-trade anything you build** before you put money near it.
