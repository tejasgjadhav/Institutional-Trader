# Reader edition: read this before you run anything

This repository is the reader edition of the system described in *The Algo Trading Bible*. It is frozen at
3 September 2026 (commit `c13fbaa`, 562 commits). It is a paper-trading research system for study. It is not
investment advice.

It is built for the Indian market (NSE options). It reads every price through a market-data token from an Indian
stockbroker. The token lets the system view and read market data; it cannot place orders. The code ships set up
for Upstox. To use Zerodha, Groww, Angel One or another broker, ask your AI assistant to configure the data
connection. The setup guide, [READER_SETUP.md](READER_SETUP.md), explains both routes.

The defects below are not fixed in this edition. Fixing them is up to you. Clone the repository, use an AI
coding assistant to study and change it, run the backtests again, and paper-trade it before you deploy
anything. Everything you do with it is at your own risk. The book walks through that same loop.

## Known defects in this edition (fix these yourself)

**Backtests**
1. The backtest figures in this edition are too high. On days an option did not trade, the exchange file
   carries its last close forward. The harness entered trades and booked profits on those prices, which nobody
   could trade. A re-run on traded prices only (11 October 2026) cut the v2 book's 2019–2024 win rate from
   77.1% to 61.3%.
2. The harness cannot see the bid-ask spread or check whether an order would fill. Every profit figure is a
   ceiling.
3. The out-of-sample window (October 2024 onwards) has been used to answer many research questions. Each
   reuse makes it a weaker test.
4. The vlc book's stock and side pairs were chosen on the out-of-sample window, so its out-of-sample win rate
   is inflated. Plan on its in-sample rate.

**Trading logic**

5. The liquidity check looks only at the leg you sell. The leg you buy can have no trades and a very wide
   spread, mostly on next month's expiry. If you cannot buy that leg, the sold leg stands alone and needs far
   more margin.
6. Stock-book take-profits are booked on mid prices even when the spread cannot be closed at that price.
7. The 0DTE books close early at 95% of the credit. A later test showed that the early close cost money.
8. The SENSEX 0DTE book sells a call spread every expiry day, and it loses on mornings that gap up.
9. The 15:31 watchlist prices v2's strikes only. The v1 book can fire on a stock the watchlist showed as
   blocked.
10. Every stock book uses the same ₹50 premium floor. A later study found a ₹30 floor works for v1 and v0
    only.

**Running it**

11. The engine runs on your own computer. If the computer sleeps or the battery dies, it misses the daily scan.
12. There is no exchange holiday calendar. On an NSE holiday the engine still sends messages as if it were a
    trading day.
13. The 15:36 scan can hit Upstox's per-minute limit. A failed price fetch can look the same as a stock with
    no breakout.
14. A restart can reset the day's markers and repeat a scan.
15. The 09:30 morning re-check does not cover the vlc book.
16. Rejected candidates are not logged, so you cannot see why a breakout did not become a signal.
17. The stock universe includes some names that have no option contracts.

## Weak results you should know about

These are measured results, not defects. They describe the strategy itself, so fixing the defects will not
remove them.

- An average loss is about 2.5 times an average win (about ₹9,500 against ₹3,900, out of sample). The stock
  books need roughly 71% winners to break even, so the margin of safety is about nine points of win rate.
- On traded prices only, v2 won 61.3% of its trades from 2019 to September 2024 and made money in 4 of 6 years.
- The worst out-of-sample drawdown for the stock books was about ₹1.41 lakh at one lot.
- The index swing fade failed out of sample, and BANKNIFTY 0DTE showed no edge. Both were removed.
- The engine's own paper record from 6 August to 22 October 2026 is small, and it was flat in September and
  October.

## What this edition is for

Read the code, the studies and the commit history to see how a system like this gets built and corrected.
Then make it yours: fix the defects, re-run the backtests on your own data, and paper-trade it until your own
record says it works. Do not trade real money from it as it stands. The licence (PolyForm Noncommercial 1.0.0)
allows personal, noncommercial use only.
