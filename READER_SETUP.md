# Setup guide for readers of *The Algo Trading Bible*

This guide is for readers of *The Algo Trading Bible* by Tejas Jadhav, CFA, FRM. It sets up the reader
edition of the system described in the book. The reader edition is frozen at 3 September 2026. Read
[READER_EDITION.md](READER_EDITION.md) first, because it lists the known defects and the weak backtest results.

This system is built for the Indian market. It needs an account with an Indian stockbroker called Upstox, and a
market-data token from that account. It is a paper-trading research system and it never places an order. Nothing here is investment advice.

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
- **Python 3.9 or newer.** On Windows, tick "Add python.exe to PATH" in the python.org installer.
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
