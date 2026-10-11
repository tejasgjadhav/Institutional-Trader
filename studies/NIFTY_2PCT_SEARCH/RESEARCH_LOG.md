# HANDOFF: nifty-2pct-study (2026-10-09)

## Goal
He wants a NIFTY stock or strategy making >2%/day, with an expected win rate >75%.
No credit or debit spreads. Single-leg F&O (futures, plain options) is allowed.
Latest instruction: "look at all history and data that we saved in github and use different strategy only that makes sense with our parameters".

## Done
1. Daily-bar intraday grid, 50 stocks x 7 rules x 6 geometries, IS H1-2026 / OOS Jul-Oct 2026 (study.py, intraday_grid.csv). Pooled, nothing positive OOS. JIOFIN trend-short looked best at +0.35%/trade.
2. Upstox 1-min replay 2022-2026 of the 11 survivors (fetch_m1.py, replay_m1.py, m1/, m1_trades.csv). Daily-bar edges shrink ~3x. The best four make ~+0.1%/trade, t<1.3. Dead.
3. Trend-filtered mean reversion on 2008-2026 adjusted daily data (daily_long.parquet, mr.py, mr2.py, tr_*.parquet, tr2_*.parquet).
   - The rule: C>SMA200, SMA50>SMA200, RSI2<10, close<lower BB(20,2). Buy at close, sell at the first close above entry, 20-day time stop, -8% disaster stop.
   - Wins 83% IS (2010-19) and 81% OOS (2020-26). Net +0.2-0.3%/trade at 0.1% cost.
   - port.py portfolio: 10 slots unlevered gives ~3% CAGR, -10% DD. 10 slots at 5x futures gives 14.5% CAGR, -43% DD, ~0.07%/day.
   - High win rate is achievable; 2%/day is not.

## Gotchas
- Survivorship: these are today's NIFTY 50 constituents back to 2010, which flatters dip-buying.
- yfinance close = closing auction price. A 1-min check (15:20 decision) is NOT done yet.
- The TMPV Upstox key is the old Tata Motors ISIN.
- Memory nifty-2pct-day-verdict holds the 1-min result.

## Next
Survey institutional-trader data (bhavcopy, market_history.db) and the monthly-futures REV1_L pullback-long verdict as candidates that fit the parameters.

## Update (later the same session)
- He added more constraints: at least 3-4 trades a month; any F&O stock in India, not only NIFTY 50; "sample then go deep".
- fut_replay.py replays the dip-buy on the real futures bhavcopy panel (institutional-trader/studies/monthly_fut/panel.csv.gz, 103 symbols, 2018 to 2026-07-09, daily close plus OI).
  - Long: 787 trades, 80.7% win, -0.01%/trade.
  - Short mirror (fut_replay_short.py): 397 trades, 80.9% win, +0.01%/trade.
  - A target/stop frontier (g_*.py) puts every cell within +/-0.04%. Win rate is easy; edge is zero after carry and costs.
- The REV1 monthly paper book has been REGIME_OFF every cycle since July (NIFTY below its 200DMA), so it has made zero trades.
- Next: go deep with open-interest conditioning. This is the never-tested non-OHLC family.
  Hypothesis: dip + falling OI (long unwinding) beats dip + rising OI (fresh shorts); rip + falling OI (short covering) fades better.
  Use the full 103-symbol panel, IS 2018-2022, OOS 2023-2026.

## Result of the OI deep dive (deep_oi.py -> deep_trades.parquet)
- 100 F&O stocks, 2018 to 2026-07. Long dip (C>SMA200, SMA50>SMA200, RSI2<10), exit at the first profitable futures close, 20-day time stop, -8% stop.
- Split by the 3-day change in total futures OI. The hypothesis was stated in advance and held in both periods:
  - OI falling (<-1%): 1,645 trades, 83% win, +0.26%/trade. OOS 2023-26: 85.6% win, +0.43%, t=4.0.
  - OI rising: about 0.
- Caveat 1: with T-1 OI only (no same-day OI), the OOS edge halves to +0.21%, t=1.9. Live viability depends on intraday OI at ~15:25 matching EOD OI. NOT verified.
- Caveat 2: crash clustering. With no NIFTY regime filter, March 2020 gives -66% in a month at 4.5x.
  - With NIFTY>200DMA: 10 slots at 4.5x make ~1.5%/month avg, worst month -27%, max DD -44%.
  - But it made 0 trades from Mar to Jun 2026.
- 2%/day: not reachable. Nothing deployed.
- 2026-10-09: he asked how the trade works; answered with a step-by-step playbook plus a real 2026 example from deep_trades.parquet. No code changes.

## Further backtest (later the same session): the OI-unwind dip is NOT tradable live
- extend_panel.py -> panel_ext.csv.gz (+63 days to 2026-10-08). deep_oi_ext.py -> deep_trades_ext.parquet.
  - Fresh Jul-Oct 2026, unfiltered: 46 trades, 76% win, -0.72%/trade.
  - Regime-filtered: 0 trades, because NIFTY was below its 200DMA throughout.
- oi_timing.py -> oi_timing.csv uses Upstox expired-instruments 1-min futures candles with OI, on 758 uptrend dips Oct-2024 to Jul-2026.
  - Upstox OI vs bhavcopy OI 3-day change: corr only 0.61.
  - Classified on the live-realistic 15:20 OI, "OI falling" dips LOST -0.57%/trade (t=-2.0).
  - Classified on bhavcopy EOD OI over the same window: +0.03%.
  - The effect lives only in the published bhavcopy figure, which arrives after the close. Verdict: dead.

## 2026-10-09 next ask: "find always positive trades"
Only a locked-in arbitrage can be always positive. Testing cash-futures arbitrage (buy the stock, sell the same-month future, hold to expiry convergence) on the bhavcopy panel plus unadjusted cash closes. Script: arb.py.
- arb.py result: entering only when basis >=0.8% (about 5/month) made 554 trades 2018-2026, 100% positive, +1.11%/cycle net, ~13% annualised on the stock value. At >=0.6%: 21/month, +0.53%/cycle, 6.5% annualised. Settle-price check: 100% still above costs. Basis is compressing (2025-26 ~6-7% annualised in the 0.8% band). Next idea not yet tested: exit early when the basis collapses before expiry.
- 2026-10-09: he clarified that the goal is to pick, each day, the one constituent that moves 2%. Testing a cross-sectional daily ranker (pick_one.py).
- 2026-10-09: he asked to improve the pick-one net via stops/exits. Plan: 1-min fetch for picked stock-days (fetch_picks.py -> picks_m1.parquet), exit grid chosen on 2023-24, validated on 2025-26 (exits.py).
- exits.py result: 1-min, 09:16 entry. The short top-3 baseline is +0.02% (daily bars had said +0.08%). The best exit picked on 2023-24 gives 0.00% in 2025-26. Long: 0% of 450 configs positive in 2025-26. Exits cannot create an edge; the pick-one line is closed.
- 2026-10-09: he said 'do it'. Doing: memory line for pick-one; then cash-futures arb early exit (arb_early.py); news-day options later.
- arb_early.py: unwinding when the basis is <=0.2% keeps 100% positive and cuts the hold from ~31 to ~20 days. In the 0.8% band, annualised on capital goes 12.8% -> 18.6%, ASSUMING the capital redeploys. Mid-cycle availability checked next.
- Mid-cycle gaps: in 2018-24 at least one existed on ~100% of days. In 2025 only 10-15% of days, in 2026 27-40%. Realistic 2025-26 arb return is ~6-9%/yr even with early unwind. Remaining open idea: news-day options buying.
- 2026-10-09: status check from him; all asked work is complete. Open idea: news-day options buying (not started).

## 2026-10-09 new ask: test 5-min and 15-min strategies from top traders and published research
Plan, pre-registered with no tuning and published specs only:
(A) Zarattini/Barbon/Aziz 'Stocks in Play' 5-min ORB on F&O stocks;
(B) Zarattini/Aziz/Barbon noise-boundary intraday momentum on NIFTY;
(C) Gao et al. first-30-min to last-30-min momentum on NIFTY.
Data: Upstox 1-min -> 5/15-min bars, 2022-2026. IS 2022-23 and OOS 2024-26 are reported separately.
- lab.py result (5/15-min, 2022-26, published specs, no tuning):
  - Gao first-30m->last-30m NIFTY: -0.03%/trade, t=-5 in 2024-26.
  - Noise-boundary NIFTY: -0.02 to -0.03%, win 37-40%.
  - Stocks-in-Play ORB: a real GROSS edge (+0.10% 2022-23, +0.03-0.05% 2024-26, t up to 7, optimistic stop timing), but 18% win, and 0.10% Indian costs make it -0.05 to -0.07% net. Decaying every year. All closed.
- 2026-10-10: he asked to save the studies to GitHub institutional-trader (public and private).
