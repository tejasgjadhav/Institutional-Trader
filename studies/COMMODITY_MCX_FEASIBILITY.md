# Commodity (MCX) strategy search — feasibility + first-pass backtest (2026-07-10)

**User goal:** find a tradable commodity strategy for the institutional trader.

**Verdict: NO validated commodity edge found in the first pass.** Two headline candidates
appeared and both died under the project's standard stress tests (honest entry, year-by-year,
benchmark comparison). Data plumbing for MCX is confirmed working; what's missing is an edge.

## Part 1 — Data feasibility (the good news)

Probed with the existing `UPSTOX_ANALYTICS_TOKEN` (scratch scripts, nothing in engine):

| Capability | Status |
|---|---|
| MCX instruments master | ✅ `assets.upstox.com/.../MCX.json.gz` — 16,077 instruments (149 FUT, ~8k CE + 8k PE) |
| Live futures daily candles | ✅ `v3/historical-candle/MCX_FO\|<token>/days/1/...` — but only since contract listing (~6 months for crude) |
| Live futures 5-min candles | ✅ works with ≤~1-month chunks (same chunking as NSE); evening session included (to 23:30 IST) |
| MCX options chains | ✅ contracts exist for CRUDEOIL / NATURALGAS / GOLD / SILVER / COPPER |
| **Expired MCX contracts** | ❌ `v2/expired-instruments/expiries` returns **empty** for MCX keys (accepts the key, no data) |

**Consequence:** native MCX backtests are capped at the life of the current contract
(~6 months of daily, less of clean 5-min). Deep validation must use the underlying-proxy
method (same as `UNDERLYING_VALIDATION_365D.md`): MCX crude tracks NYMEX WTI, gold/silver
track COMEX, natgas tracks Henry Hub — all with 20+ years of daily data. Caveat: proxies
ignore USDINR drift (~+3%/yr tailwind to INR longs) and MCX roll/session differences.

Note: `yfinance 0.2.32` in the venv is now blocked by Yahoo. Direct
`query1.finance.yahoo.com/v8/finance/chart/<sym>` with a browser User-Agent works fine.

## Part 2 — First-pass backtest (2004→2026 daily, WTI/NatGas/Gold/Silver/Copper)

Three strategy families, 10 bps round-trip cost, IS = 2005-18, OOS = 2019-26:

| Family | Result |
|---|---|
| **Trend-follow Donchian-20** (2×ATR stop, 10d max hold) | Inconsistent — positive on crude both halves (weak, ~50% win), negative on natgas/copper OOS-negative on silver/gold. No portfolio-wide edge. |
| **Fade Donchian-10** (the equity-validated direction) | Only NatGas looked good: +13.2%/yr IS AND +14.6%/yr OOS at signal-close entry. **See Part 3 — it fails honest entry.** |
| **TSMOM 12m, hold 1m** | Long-short inconsistent. Long-only survives — **see Part 4, it's mostly beta.** |

## Part 3 — NatGas fade: killed by the entry assumption

The +14.6%/yr OOS headline assumed entry AT the signal close. Re-run with next-day-OPEN entry
(the executable version, since Donchian needs the full session close):

- Signal-close entry OOS: **+0.52%/trade** → next-day-open entry OOS: **−0.10%/trade**.
- The whole edge lives in the overnight gap after the breakout close — not capturable.
- Also: 8/23 negative years with −71% (2006) and −49% (2019) clusters; parameter grid
  (D8-12 × stop 1.5-2.5 × hold 5-15) swings −0.4% to +1.2% per trade — noise, not a plateau.

**FAIL.** Same lesson as the equity studies: fade edges are entry-timing-fragile.

## Part 4 — Gold/Silver 12-month momentum, long-only: survives entry test, but it's beta

Long-only (flat when 12m return negative), next-day-open entry, hold 21d — robust across
lookbacks 126/189/252 (a real plateau, +0.8-1.5%/trade IS, +1.2-2.0%/trade OOS). But:

| | Strategy | Buy-and-hold | Worst DD | 2026 YTD |
|---|---|---|---|---|
| Gold | +8.0%/yr (70% in-market) | **+10.7%/yr** | −33% | **−30%** |
| Silver | +12.0%/yr (60% in-market) | +10.7%/yr | **−61%** | **−57%** |

Gold momentum UNDERPERFORMS just holding gold. Silver adds ~1.3%/yr over B&H at a −61%
drawdown. And 2026 is an active momentum-crash year (−30%/−57% YTD) — the worst possible
regime to deploy into. This is documented-in-literature beta harvesting, not an edge this
system can monetize at 1-lot futures scale.

**FAIL** (as an alpha strategy for this system).

## What remains worth trying (not yet tested)

1. **Port the ONE validated equity edge**: post-breakout **credit-spread fade with the
   credit/width ≥ 0.40 rich-IV gate** onto MCX CRUDEOIL/NATURALGAS options (the only liquid
   MCX option chains). Cannot be backtested (no expired MCX data) — would have to go straight
   to a **signals-only paper forward-test** like `swing_credit.py`/`stock_credit.py`, with the
   same gates (credit/width, min premium, live OI/spread). Zero capital risk, ~3-6 months to
   a verdict.
2. **Intraday ORB on crude 5-min** (MCX evening session overlaps US pit hours, good range):
   testable natively but only on ~6 months of current-contract 5-min data — small sample.
3. Paid data (TrueData/GDFL) for real MCX history — same wall as NSE options, same cost call.

## Scripts

Scratch only (not committed): `mcx_probe*.py`, `commodity_study.py`, `natgas_fade_robust.py`,
`tsmom_robust.py`, `tsmom_final.py` — session scratchpad. Rebuild from this doc if needed.

*Generated 2026-07-10. Nothing deployed; engine untouched.*
