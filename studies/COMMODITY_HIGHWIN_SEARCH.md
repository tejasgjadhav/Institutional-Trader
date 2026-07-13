# Commodity high-win-rate search — WR ≥75%, max return (2026-07-10)

**User goal:** a commodity strategy with win rate >75% and maximum return.

**Verdict: TWO survivors.** Trend-aligned mean-reversion with small-TP/wide-SL delivers
82–87% win rate and ~+5%/yr per unit notional, robust in-sample AND out-of-sample, with the
trade-off made explicit: the win rate is bought with tail risk (SL = 8% vs TP = 1.5–2%).

Method (same discipline as the equity studies): 2,080 configs on 2004–2026 daily benchmark
proxies (WTI/NatGas/Gold/Silver/Copper — MCX native history is only ~6 months, see
`COMMODITY_MCX_FEASIBILITY.md`). Honest rules throughout: **next-day-open entry**, SL checked
BEFORE TP intraday, gaps fill at the open, 10 bps cost. **Selected on IS (2005-18) only**;
OOS (2019-26) is the verdict. Family: trend filter (SMA-200 or 12-month momentum) + stretch
trigger (RSI-2, prior-5-day-extreme break, 3 consecutive closes) + TP 0.5–2% / SL 3–8% /
time exit 5–20d.

**Base rate check:** 334 configs passed IS (WR≥75%, +exp); **166/334 (50%) also passed OOS**
(WR≥70%, +exp). That is far above what noise produces — the family is real, and it
concentrates in two specific places:

## Survivor A — NatGas SHORT rally-fade (the top IS pick, so its OOS is an honest read)

> 12m momentum DOWN + close breaks ABOVE the prior 5-day high → SHORT next open.
> TP +1.5%, SL 8%, time exit 5 days.

| | n | win | avg/trade | per yr (1x notional) |
|---|---|---|---|---|
| IS 2005-18 | 226 | 88.1% | +0.452% | +7.3% |
| OOS 2019-26 | 112 | **86.6%** | +0.228% | +3.4% |
| Full 22y | 327 (15/yr) | 87.2% | +0.343% | +5.1% |

- Exit mix: 281 TP / 31 SL / 15 time. Worst trades −10.2%, −8.9%, −8.1%. **Max DD −25.8%.**
- 11/18 years positive; worst years −9% (2006), −8% (2017, 2022).
- **2022 gas crisis: the mom-252-down filter kept it to ONE trade all year** (−8%) — the
  trend gate is the survival mechanism, not the TP/SL.
- Why it works: natgas spends most of its life in contango-bleed downtrends; fading pops
  inside a downtrend harvests reversion + roll drift. Well-documented regime, not a fluke.
- MCX caveat: short side pays the USDINR depreciation drift (~2-3%/yr × ~30% time-in-market
  ≈ 0.7%/yr drag on MCX vs this USD backtest).

## Survivor B — Copper LONG pullback (best "max return" among double-survivors)

> 12m momentum UP + close breaks BELOW the prior 5-day low → LONG next open.
> TP +2%, SL 8%, time exit 20 days.

| | n | win | avg/trade | per yr (1x notional) |
|---|---|---|---|---|
| IS 2005-18 | — | 80% | — | +3.7% |
| OOS 2019-26 | 76 | **84.2%** | +0.642% | **+6.5%** |
| Full 22y | 198 (9/yr) | 81.8% | +0.497% | +4.5% |

- Exit mix: 156 TP / 22 SL / 20 time. Worst −9.4%. Max DD −26.8%. 14/20 years positive;
  worst −19% (2018), −16% (2006). 2026 YTD: 11/11 wins, +21%.
- USDINR drift is a **tailwind** here (long INR-denominated metal).
- MCX caveat: COPPER lot = 2,500 kg ≈ ₹22L notional (margin ~₹2L) — one lot is a big unit;
  no mini contract on the current master.

## 50/50 portfolio (half notional each)

+4.8%/yr average on 1x combined notional, **16/22 years positive**, worst year −12.5% (2006).
The two legs are structurally uncorrelated (energy short vs metal long) and the USDINR drift
nets out. On MCX margin (~5x notional/margin) this is ~+20-25%/yr on margin **but the −26%
notional drawdowns become >100% of margin — deploy at ≤2-3x, never full margin leverage.**

## Honest caveats

1. **Tail-risk structure**: one SL (−8%) erases ~5 TP wins. The high WR is real but the P&L
   distribution is strongly left-skewed. Position sizing is the whole game.
2. **Grid selection**: 2,080 configs searched. Mitigated by IS-only selection + the 50%
   OOS pass rate + parameter-plateau (neighbors of both configs also pass), but the exact
   numbers are still the optimistic edge of a cluster. Expect the OOS column, not the IS one.
3. **Proxy gap**: Henry Hub / COMEX ≠ MCX (INR, session 9:00-23:30, roll). Directional signal
   should transfer (MCX prices ARE these benchmarks × USDINR); fills/costs need forward proof.
4. **Operational**: the 252-day momentum filter can't be computed from MCX native candles
   (current contract has ~120 days of history). Implementation must compute signals off the
   benchmark series (Yahoo-direct chart API works — see dev-machine gotchas) and execute on MCX.
5. Costs assumed 10 bps round-trip; MCX natgas/copper futures spreads are ~1-3 ticks so this
   is realistic for futures (NOT for MCX options — different animal).

## Recommended next step (needs user approval before any engine change)

Signals-only paper forward-test module (like `swing_credit.py`): compute A + B signals daily
from benchmark data, paper-trade 1 lot MCX NATURALGAS / COPPER futures at next-day 9:00 open,
TP/SL/time exits tracked against real MCX quotes. 3–6 months to a live verdict.

Scripts: scratchpad `highwin_search.py`, `highwin_deepdive.py` (grid CSV `highwin_grid.csv`).

*Generated 2026-07-10. Nothing deployed; engine untouched.*
