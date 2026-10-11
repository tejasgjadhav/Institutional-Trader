# NIFTY 2% a day search (9-10 Oct 2026)

> **Disclaimer.** This is a personal research project. It is illustrative and educational only. It is not investment advice or a recommendation to buy or sell any security. The views are my own and not my employer's, and my employer has not reviewed this work. Nothing here reflects a holding or an intended trade. Stock names appear only as backtest data.

## The question

The goal was to find a NIFTY or F&O stock strategy that makes more than 2% a day. Later constraints added these rules:
- the win rate should be above 75%;
- there should be at least 3 to 4 trades a month;
- no credit or debit option spreads;
- single-leg F&O is allowed.

## The answer

No tested strategy makes 2% a day. The search covered daily, 15-minute, 5-minute and 1-minute bars, from 2008 to October 2026.

A 75% win rate is easy to reach with stop-free dip buying. However, its profit per trade is about zero after costs and live timing.

The only trade that stayed positive every time was cash-futures arbitrage. It returns about 6-9% a year at 2025-26 basis levels.

## What was tested, in order

| # | Study | Script | Result |
|---|---|---|---|
| 1 | Daily-bar intraday rules, 50 stocks x 7 rules x 6 target/stop settings | `study.py` | Pooled across stocks, nothing was positive out of sample |
| 2 | 1-minute replay of the 11 survivors, 2022-2026 | `fetch_m1.py`, `replay_m1.py` | Daily-bar edges shrank about 3x. The best made +0.1% a trade with t < 1.3 |
| 3 | Trend-filtered dip buying (RSI2, Bollinger band), 2008-2026 | `mr.py`, `mr2.py`, `port.py` | 81-83% win in both periods, but only about 3-4% a year unlevered |
| 4 | The same dip buy on real futures bhavcopy prices, long and short | `fut_replay.py`, `fut_replay_short.py` | 81% win, about 0.00% a trade. Futures carry and costs remove the edge |
| 5 | Dip buy filtered on falling futures open interest, 100 F&O stocks | `deep_oi.py` | 83% win, +0.26% a trade, t = 4 in 2023-26 on bhavcopy OI |
| 6 | The same filter on fresh data and live-timing OI | `extend_panel.py`, `deep_oi_ext.py`, `oi_timing.py` | Failed. On fresh Jul-Oct 2026 data it lost 0.72% a trade. On the OI visible at 15:20 it lost 0.57% a trade |
| 7 | Machine-learning model that picks one stock a day at the open | `pick_one.py` | It doubled the odds of a clean 2% move, from 14% to 24-30%. It still made about zero net |
| 8 | 450 exit designs on the model's picks, 1-minute data | `fetch_picks.py`, `exits.py` | The best exit from 2023-24 made 0.00% in 2025-26. The hindsight ceiling was +0.04% |
| 9 | Cash-futures arbitrage, 100 F&O stocks, 2018-2026 | `arb.py`, `arb_early.py` | 100% of trades were positive when entered at a basis of 0.8% or more. That is 13% a year to expiry, or about 19% with an early exit. Basis gaps became rare in 2025-26 |
| 10 | Published intraday strategies on 5/15-minute bars | `fetch_m5.py`, `lab.py` | See below |

## Published strategies on Indian data (study 10)

| Strategy | Win rate | Net per trade, 2024-26 |
|---|---|---|
| Stocks-in-Play 5-min opening range breakout (Barbon, Zarattini, Aziz) | 18% | -0.05% |
| Noise-boundary intraday momentum on NIFTY (Zarattini, Aziz, Barbon) | 37-40% | -0.02% to -0.03% |
| First 30 minutes predicts the last 30 minutes on NIFTY (Gao, Han, Li, Zhou) | 41% | -0.03% |

The opening range breakout has a real edge before costs. It made +0.10% a trade in 2022-23 and +0.03-0.05% in 2024-26. Indian round-trip costs of about 0.10% are larger than that edge, and the edge gets smaller every year.

## Lessons for future studies

- Never quote a daily-bar intraday edge without a 1-minute replay. Daily bars fill at the auction open, which no one can trade.
- Test every open-interest signal on OI that is visible before entry. Bhavcopy OI is published after the close. Upstox intraday OI correlates with it at only 0.61 over three days.
- A high win rate with a "first profitable close" exit is almost free to get, and it says nothing about profit.
- Exits cannot create an edge that the entry does not have.

## Files

- `results/` holds the trade-level outputs of each study.
- `RESEARCH_LOG.md` is the full working log, including dead ends.
- The raw data (about 600 MB of Upstox 1-min and 5-min bars, plus bhavcopy extensions) is not committed. The `fetch_*.py` scripts download it again. They were run from `~/files/nifty-2pct-study/`, so the paths are relative to that folder.
