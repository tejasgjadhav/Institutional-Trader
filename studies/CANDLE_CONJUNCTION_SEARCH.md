# Candle-conjunction search — the untested class, tested (17-Sep-2026)

**User goal:** a NON-SPREAD directional strategy, more signals, >75% win, positive net after cost.
**Why this study exists:** WR70 (3,550 single-feature cells, 0 survivors, IS→OOS r = −0.11) never
tested pattern CONJUNCTIONS; the standing note said "don't call candlesticks dead".

**Design.** 30 instruments (6 indices + 24 F&O stocks), 5-min bars from 1-min Upstox v3 history
(research/m1cache, 1,710 symbol-months, 0 fetch failures). Six completed-candle patterns (bull/bear
engulfing, hammer, shooting star, inside-bar break up/down) × level (none / prior-day low / prior-day
high / VWAP) × volume (any / ≥1.5× surge) × time (any / first hour / last hour) = 138 conjunction
gates with ≥300 entries. Entry at the pattern bar's close, first-touch stop {20,30,50,80,120 bps} ×
target ratio {0.25…1.5}, both sides, 3 bps cost, futures-style on the underlying. IS 2022–24 selects
(Bonferroni z 4.49 over 6,900 tests), OOS 2025–26 judges and was never searched over.
**760,594 pattern entries.** Script: studies/candle_conj_search.py; outputs research/candle_conj/.

## Result

- IS candidates meeting win ≥ 75% AND net > 0 at the Bonferroni bar: **0**.
- OOS survivors (win ≥ 75% AND net > 0 on ≥ 100 trades): **0**.
- IS→OOS net correlation over 6,800 cells: **+0.34** — the cells DO carry persistent information.
- Cells net-positive out of sample: **4.0%** (50% = no information).

Read together, those last two lines are the finding: candle-conjunction entries are consistently
and persistently **losing** after cost, on both sides, across geometries. The information they
carry is "this loses", and it carries over from 2022–24 to 2025–26. The high win rates exist (see
report.txt: many cells above 75%) and every one of them is net-negative — the small-target /
wide-stop geometry manufactures the win rate and the cost eats the expectancy, exactly the
arithmetic the WR70 note derived (at 3 bps a 20-bps-risk trade needs ~80% just to break even).

**Verdict: the candle-conjunction class is falsified on this data, out of sample, for a
directional non-spread trade.** This is the fourth independent falsification of chart-based
entries here (champion sweep, WR70, Turtle Soup, this). Order flow remains untested (three weeks of
depth recordings; a year is needed). Candles as TIMING for a spread entry remains untested.
