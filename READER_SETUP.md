# Setup

Getting the system running on your own machine, start to finish. It takes about ten minutes.

> **Before you start.** This is study code. The one strategy that ships with it is a teaching
> example that has never been backtested, and the author does not trade it. Nothing here is
> investment advice. If you run it, or act on anything it prints, that is your decision and
> your risk. Read [DISCLAIMER.md](DISCLAIMER.md) in full.

## What you need

- Python 3.9 or newer.
- An Upstox account and a market-data API key. The token is read-only. It cannot place an order.
- About 200 MB of disk for the instrument and option caches.

Check your broker's own API terms first. Some brokers charge a monthly fee for market data, and
some forbid automated access on a retail account.

## macOS and Linux

```bash
git clone https://github.com/tejasgjadhav/Institutional-Trader.git
cd Institutional-Trader
./setup.sh
```

`setup.sh` creates a virtual environment in `.venv`, installs the requirements and writes a
`.env` from `.env.example`. Open `.env` and put your own token in it.

Then run one cycle and watch it work:

```bash
.venv/bin/python -m engine.engine_runner --once
```

It prints every price it fetches and every decision it reaches. If the market is closed it
writes a snapshot and says so.

To leave the engine running:

```bash
.venv/bin/python -m engine.engine_runner
```

Open the dashboard in a second terminal:

```bash
.venv/bin/python main.py
```

## Windows

```
setup.bat
```

It creates the virtual environment, installs the requirements, writes a `.env` from the template
and makes the `data` and `logs` folders. Open `.env` and put your own token in it.

Then start the engine with `run_engine.bat` and leave that window open, and open the dashboard
with `run_viewer.bat`.

To start the engine at login, put a shortcut to `run_engine.bat` in your Startup folder.

## Keeping it running

The engine and the dashboard are two separate processes. The engine does all the work and
writes to `data/`. The dashboard reads those files every fifteen seconds and draws them.
Closing the dashboard does not stop the engine.

Whatever you use to keep the engine alive, remember that it will not reload your code by
itself. After you edit anything in `engine/`, restart it, or you will debug code that is not
running. Restarting the engine does not restart the dashboard either.

## What is in the folder

- `README.md`: start here.
- `DISCLAIMER.md`: read it before you run anything.
- `CLAUDE.md`: notes for an AI assistant working in this repository.
- `main.py`: opens the dashboard.
- `engine/`: the system. `engine_runner.py` is the loop, `example_vwap.py` is the one strategy,
  `indicators.py` is the toolbox, `ui_terminal.py` is the dashboard, and the rest is data,
  instruments, options and storage.
- `studies/`: the research notes.
- `data/` and `logs/`: written at runtime. Both are ignored by git.
- `.env`: your token. It is ignored by git and it must stay that way.

## Troubleshooting

**Nothing fetches.** Check the token in `.env` first. An expired token fails silently in some
paths and loudly in others. `python -m engine.api_diagnostics` tells you which calls work.

**Nothing changes after you edit the code.** Restart the engine. See above.

**No signal for days.** That is normal, and it is not a fault. The example only trades when the
index stretches below VWAP inside its entry window, which does not happen most days. The
dashboard says what it is waiting for.

**An option is skipped as illiquid.** That is the liquidity check in `engine/config.py` doing
its job. Widen it if you want, and understand that you are agreeing to pay the wider spread.

## Where to go next

Read `engine/example_vwap.py` end to end. It is short and it is commented. Then copy it, change
the rule, and test your version properly before you believe it. `studies/` describes how, and
the book describes it at length.
