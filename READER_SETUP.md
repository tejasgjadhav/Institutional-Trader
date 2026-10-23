# Setup guide for readers of *The Algo Trading Bible*

This guide is for readers of *The Algo Trading Bible* by Tejas Jadhav, CFA, FRM. It sets up the reader
edition of the system described in the book. The reader edition is frozen at 3 September 2026. Read
[READER_EDITION.md](READER_EDITION.md) first, because it lists the known defects and the weak backtest results.

This system is built for the Indian market. It needs an account with an Indian stockbroker called Upstox, and a
market-data token from that account. It is a paper-trading research system and it never places an order. Nothing here is investment advice.

## Quick start (macOS, about 15 minutes once you have the token)

1. Get an Upstox account and its Analytics token (sections 1 and 2).
2. Install Python 3.10 or 3.11 from python.org.
3. Run these three commands in Terminal:
   ```bash
   git clone https://github.com/tejasgjadhav/Institutional-Trader.git
   cd Institutional-Trader
   ./setup.sh
   ```
4. Open `.env` in a text editor and paste your token after `UPSTOX_ANALYTICS_TOKEN=`.
5. Test one cycle with `.venv/bin/python -m engine.engine_runner --once`, then open the dashboard with
   `.venv/bin/python main.py`.

On Windows, run `setup.bat` instead of `./setup.sh`, then start `run_engine.bat` and `run_viewer.bat`.
The full steps are in sections 3 to 5.

## What is in this repository

**Start here**
- `READER_EDITION.md`: the known defects and the weak results. Read it first.
- `READER_SETUP.md`: this guide.
- `README.md`: an overview of the system and its strategy books.
- `LICENSE`: the PolyForm Noncommercial licence.

**Install and run**
- `setup.sh` (macOS) and `setup.bat` (Windows): the installers.
- `requirements.txt`: the Python libraries the installers add.
- `.env.example`: the template for your settings file, `.env`. It holds the Upstox token and the optional
  Telegram keys.
- `main.py`: opens the dashboard.
- `run_engine.bat`, `run_viewer.bat` and `autostart_windows.bat`: the Windows start scripts.
- `deploy/`: the macOS launchd job files that `setup.sh` installs.

**The system, in `engine/`**
- `engine_runner.py`: the engine. It runs the daily schedule and writes every result to `data/`.
- `ui_terminal.py`: the dashboard. It only reads what the engine wrote.
- `config.py`: every setting and rule in one place. This is where you change a rule.
- `data_fetcher.py`, `instruments.py` and `options.py`: read prices and option contracts from Upstox.
- `stock_credit.py` (v1), `stock_credit_v2.py` (v2), `stock_credit_v0.py` (v0) and `stock_credit_vlc.py`
  (vlc): the stock credit-spread books.
- `zero_dte.py` (NIFTY) and `dte_multi.py` (SENSEX): the expiry-day index books.
- `signal_recheck.py`: the 09:30 morning re-check.
- `notifications.py`: the Telegram alerts.
- `forward_record.py`, `trade_log.py`, `paper_resolver.py`, `signal_db.py` and `store.py`: the record
  keeping.
- `expired_options.py`: historical option prices for backtests. It needs a paid Upstox plan.
- `swing_credit.py`, `monthly_fut.py` and `monthly_call.py`: the index swing and monthly books. They are
  switched off or paper-only in this edition.
- `agent.py`, `signals.py`, `orb_vwap_live.py`, `portfolio.py`, `events.py` and `options_flow.py`: the first
  strategy from the book's early chapters. They are kept for the history and switched off.

**Research and records**
- `studies/`: one write-up per research question, plus the scripts behind them. `studies/README.md` is the
  index.
- `studies/ndte/`: the backtest harness (`deployed_backtest.py`) and the offline tests (`test_*.py`).
- `CLAUDE.md`: the working notes for an AI coding assistant, with the rules, conventions and health checks.
  Point your assistant at it first.
- `BACKTEST_RESULTS.md` and `CONFIG_CHANGELOG.md`: the results log and the history of every setting change.
- `live_tracker.py`: compares paper results with the backtest, as described in the book's trade-log chapter.
- `How_We_Built_The_Strategy.pdf` and `build_teaching_pdf.py`: a teaching PDF and the script that builds it.
- `trade_log_120d.csv`: an example paper trade log.
- `research/`: two short research notes.

**Created when you run it**
- `.venv/`: the Python environment that the installer creates.
- `data/`: positions, the trade log and the databases. It starts almost empty.
- `logs/`: the engine and dashboard logs.

## 1. Check this first: you need an Indian broker account and a market-data token

**Upstox** is an Indian stockbroker, the Indian equivalent of a US brokerage such as Schwab or Interactive
Brokers. This system gets every price it uses from Upstox: stock prices, index levels and option quotes.

It reads those prices through a **token**. A token is a long code that you generate inside your Upstox account
and paste into a settings file. It lets the system view and read market data on your behalf. It cannot place
orders or move money. Without a token the system has no prices, so it cannot run.

- **Who can open an Upstox account.** Upstox follows India's identity-check rules (KYC, "know your
  customer"). You need a PAN card (India's tax ID), an Aadhaar number (India's national ID) linked to your
  mobile, and an Indian bank account. Non-resident Indians should check Upstox's
  own rules for NRI accounts.
- **Which token.** Upstox calls it the **Analytics token**. It is free and read-only.
- **What you need to trade yourself.** To place option trades by hand, your Upstox account needs the
  F&O (futures and options) segment switched on. Upstox asks for income proof for that. The engine
  itself does not need it.
- **Outside India.** If you cannot open an Upstox account, this code will not get prices. Use the book's
  US chapters instead: "The US Toolkit" shows the free US data sources and brokers, and the US worked
  example runs the same method on American data.

## 2. Get your Upstox Analytics token

1. Open an Upstox account and finish its KYC.
2. Sign in to the Upstox developer page at `account.upstox.com/developer/apps`.
3. Open the Analytics token section and generate a token.
4. Copy the token. Keep it private, like a password.

The Analytics token lasts about one year, so you do not log in every day. When it expires, generate a new
one and paste it into `.env` again.

## 3. What else you need

- **A computer.** macOS is the tested platform. Windows works through the `.bat` files.
- **Python 3.9, 3.10 or 3.11.** Python 3.12 and newer will not install the pinned libraries (numpy 1.24 and
  pandas 2.0). On Windows, tick "Add python.exe to PATH" in the python.org installer.
- **Git**, or download this repository as a ZIP from GitHub and unzip it.
- **Optional: a Telegram bot** for phone alerts (section 6).

## 4. Install

### macOS
```bash
git clone https://github.com/tejasgjadhav/Institutional-Trader.git
cd Institutional-Trader
./setup.sh
```
`setup.sh` creates the Python environment, installs the libraries and creates `.env` from
`.env.example`. It also installs two launchd jobs: the engine runs all the time, and the viewer opens at
09:00 on weekdays.

The library install downloads about 300 MB and takes 5 to 10 minutes. A pip warning that says the scipy
version is "yanked" is harmless.

### Windows
```bat
git clone https://github.com/tejasgjadhav/Institutional-Trader.git
cd Institutional-Trader
setup.bat
```
Windows has no launchd. Start `run_engine.bat` and leave it minimised, then start `run_viewer.bat` for
the dashboard. To start the engine at login, put a shortcut to `run_engine.bat` in your Startup folder
(`Win+R`, then `shell:startup`).

## 5. First run

1. Open `.env` in a text editor and paste your token:
   ```
   UPSTOX_ANALYTICS_TOKEN=your_token_here
   ```
2. Test one cycle in the terminal. It prints every price it fetches and every gate decision:
   - macOS: `.venv/bin/python -m engine.engine_runner --once`
   - Windows: `.venv\Scripts\python -m engine.engine_runner --once`

   An error that says the token is missing or rejected means `.env` is wrong.
3. Restart the engine so it reads the token:
   - macOS: `launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`
   - Windows: close `run_engine.bat` and start it again.
4. Open the dashboard: `.venv/bin/python main.py` on macOS, or `run_viewer.bat` on Windows.

The books start empty, and that is normal. All times are India time (IST):
- **09:16** on expiry days: the 0DTE index books enter (NIFTY on Tuesday, SENSEX on Thursday).
- **09:30**: the morning re-check of the previous session's stock calls.
- **15:31**: the stock watchlist digest.
- **15:36**: the stock credit-spread scan.
- **15:40**: open trades are settled against the close.

Outside market hours the engine waits. A blank dashboard at night is not a bug.

## 6. Phone alerts (optional)

1. In Telegram, create a bot with **@BotFather** and copy its token.
2. Create a private channel and add the bot as an admin.
3. Put both values in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=-1001234567890
   ```
4. Run `python -m engine.notifications` for the guided steps.

## 7. What this edition does not include

- **Backtest data.** The backtests need NSE's daily F&O files and Upstox's expired-option history. They
  are several gigabytes and are not in this repository. The expired-option history needs a paid Upstox
  plan. The study write-ups in `studies/` give every result, so you can read the research without the data.
- **Fixes for the known defects.** They are listed in [READER_EDITION.md](READER_EDITION.md), and fixing them
  is up to you. Defect 5 matters most for real trading: this edition checks only the leg you sell for
  liquidity. Check that both legs of a spread actually trade before you place an order.

## 8. Common problems

- **`pip install` fails on numpy or pandas.** Your Python is 3.12 or newer. Install Python 3.11 and run the
  installer again.
- **Nothing changes after you edit `.env` or the code (macOS).** launchd does not reload code by itself.
  Run the restart command in step 3 of section 5.
- **Two engines.** Run one engine only. Two engines write the same files and send duplicate alerts.
- **The token stopped working.** It has expired. Generate a new one (section 2).
- **No signal for days.** Quiet days are normal. Many sessions have no breakout that passes every gate.
- **Messages arrive on an exchange holiday.** This edition has no holiday calendar (defect 12). Ignore
  messages on NSE holidays.

## 9. Make it yours before you trade

1. Clone the repository and read the code and the studies.
2. Use an AI coding assistant to fix the known defects and change the rules you want to change.
3. Re-run the backtests on your own data. Treat every figure as a ceiling.
4. Paper-trade it until your own record supports it.
5. Only then decide whether to deploy it. You do that at your own risk.

## 10. Licence and safety

The code is under the PolyForm Noncommercial License 1.0.0 (see [LICENSE](LICENSE)). You may use it for
personal, noncommercial study. Commercial use, resale and paid signals need written permission.

Backtests are simulations, and the figures in this edition are higher than the traded prices support. Do not
risk money you cannot afford to lose.
