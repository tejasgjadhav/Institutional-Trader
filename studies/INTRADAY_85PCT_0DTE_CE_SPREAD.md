# Intraday 85%-win with positive net — 0DTE NIFTY call credit spread (goal loop, 2026-07-06)

**User goal:** intraday (same-day close), ≥85% win, positive NET return, >2% per trade on
deployed capital, risk-optimized, retail-tradeable (F&O or cash, Indian markets).

**Prior steps this loop (both settled, do not re-mine):**
1. Underlying direction, all toolkits (deep VWAP flushes × RSI/z confluence, gap fades, dynamic
   VWAP targets, trailing exits, shorts; 234 strategies on `/tmp/k5m` 2019→2026): **zero configs
   ≥82% win with net>0** at 0.10% retail cost. Best OOS ~72% win / ~0.00% net. (Also see
   `INTRADAY_90PCT_WINRATE.md`: 92% win exists but earns nothing — geometry, not edge.)
2. 0DTE naked strangles (real premiums): net-positive almost everywhere (structure works) but
   win ≤77% and ≤2%/margin. → pushed to defined-risk spreads.

## The strategy that passes

**Every NIFTY weekly expiry day: at the open, SELL the call ~0.5% OTM of the spot open and BUY
the call 200 points further out. Hold to same-day expiry settlement. No intraday stop. That's
it — 2 legs, defined risk, done by 15:30.**

- Data: REAL premiums — NSE bhavcopy expiry-day OHLC 2019→Sep'24 (282 expiry days,
  `/tmp/ndte_bhav/`) + Upstox expired-instruments Oct'24→Jun'26 (91 expiries,
  `/tmp/ndte_cache/`). Entry = day OPEN print, exit = CLOSE (≈settlement). Costs charged: 2.5%
  of gross credit slippage + ₹20×4 brokerage. Liquidity floor: short leg ≥100 contracts traded.
- Selection discipline: the config family was chosen on 2019–Sep'24 ONLY; Oct'24→Jun'26 is
  untouched out-of-sample. The strict IS winner (d=0.75%, W=200: win ≥85% AND net>0 every year
  2019–24) held OOS at **90.1% win** but +1.68%m; the primary below trades a touch of win rate
  for return. The whole neighborhood (d 0.5–0.75%, W 100–300) passes — not a lone cell.

## Results — CE 0.50% OTM, wing +200 (primary config)

| | n | Win | Avg net (% of margin) | ₹/yr at 1 lot (75) |
|---|---|---|---|---|
| In-sample 2019→Sep'24 | 282 | 84.4% | +3.17% | — |
| **OOS Oct'24→Jun'26** | **91** | **86.8%** | **+3.28%** | — |
| **Combined 2019→2026** | **373** | **85.0%** | **+3.20%** | avg ₹348/trade |

Per year (win / avg %margin): 2019 87/+1.4 · 2020 79/+0.8 · 2021 87/+3.1 · 2022 87/+8.5 ·
2023 85/+2.3 · 2024 85/+5.1 · 2025 87/+0.4 · 2026 85/+5.7 — **positive all 8 years** (crash,
bull, chop). Higher-win variant: d=0.75% W=200 → 87.1% IS / 90.1% OOS win, +2.3/+1.7%m.

**Distribution (the honest shape):** avg win +9.8%m; avg loss −34.1%m; **worst −102%m** (a
full-width day — that IS the max loss, it's capped); payoff 0.29; max losing streak 3;
28/87 months negative; worst month −₹14.8k, median +₹2.1k (1 lot). Median credit ~16 pts on
200-pt width; **margin ≈ ₹13.8k per lot** (max loss, all the broker blocks).

## Goal scorecard
| Requirement | Verdict |
|---|---|
| Intraday | ✓ 0DTE — opened at 9:15, settled same day, no overnight |
| ≥85% win | ✓ 85.0% combined (86.8% OOS); 2020 dipped to 79% |
| Positive net | ✓ every year, after modeled slippage+brokerage |
| >2% per trade | ✓ +3.2% of deployed margin (NOT of notional — impossible intraday) |
| Risk minimized | ✓ defined-risk spread: max loss = margin (~₹14k/lot), no naked legs |
| Retail-liquid | ✓ NIFTY weeklies, 2 legs, ~₹14k/lot, ~4–5 trades/month |

## Why it works (and the risks, honestly)
- Mechanism: expiry-day theta/IV collapse + the empirical fact that NIFTY expiry-day *up*-moves
  from the open are more muted than down-moves (call writers defend; pinning). That's why the
  **call side works across 8 years — including the 2021 bull — while the put side fails OOS**
  (PE-only: −8%m in the test window). It is still a one-sided short-gamma position: a violent
  gap-and-rally expiry costs the full width (−100%m; already in the data, worst −102%m).
- **Fills**: entry at the bhav/candle OPEN print of liquid weekly strikes — realistic for a
  9:15–9:20 limit order, but live fills are unproven; the 2.5%-of-credit slippage may be ~2×
  light on the far wing. Plan on some haircut.
- 2025 was nearly flat (+0.4%m) — the edge breathes; expect flat stretches.
- This repo's rule applies: **backtest > live, always.** Paper forward-test (signals-only)
  before money; start at 1 lot. NOT wired into the engine yet.

## Loss-forensics upgrade (2026-07-06 evening): the CALM-REGIME filter — DEPLOYED

**Question (user):** 2025 netted only +₹1.7k/lot (46W ₹+55.6k vs 7L ₹−53.9k) — can technical
filters avoid the losers? **Method:** per-trade feature table for all 373 trades (overnight gap,
prior-day/5-day momentum, open-vs-prior-high, SMA extension, ATR, realized vol, up-streaks, VIX
level/change, credit richness — all computable at 9:16, no lookahead), loser-vs-winner
forensics, threshold sweep. Rule: a filter counts only if it improves IS (2019–24) AND OOS
(Oct'24–Jun'26), not just erases 2025. Script `studies/ndte/ndte6_filters.py`.

**Finding: losses cluster when the tape is hot.** The one robust family = recent-volatility /
momentum regime. Winner: **skip the week when NIFTY 5-day realized vol (std of last 5 daily
log-returns) ≥ 0.9%** — trades ~3 of 4 weeks. VIX itself adds nothing (info already in rv5).

| CE d=0.5% W=200 | n | Win | Avg %margin | 2025 (1 lot) | worst year |
|---|---|---|---|---|---|
| Unfiltered | 373 | 85.0% | +3.20% | +₹1,715 | all 8 positive (2025 thinnest) |
| **rv5 < 0.9%** | **278** | **87.8%** | **+4.02%** | **+₹23,219** | 2019 ≈ flat (−₹1.7k) — 7/8 positive |

Robustness: (a) whole threshold neighborhood 0.7–1.2 improves OOS with IS held; (b) **sibling
config** d=0.75 W=200 (never used in the search): OOS +1.68→+3.33%m, win 90.1→94.5%; (c)
mechanism-first (short gamma in a calm regime). Honest caveats: the OOS window was visible
during filter selection, so the true test is the forward paper-test; the filter trades away
2019's small profit (the "positive every year" claim becomes 7-of-8 + one flat); equal-quality
alternative `ret5<1.5%` (no 5-day run-up); do NOT stack filters (overfit).
**Deployed: `ZERO_DTE_RV5_MAX = 0.9` (0 disables), checked live at 9:16, SKIP logged.**

## Intraday stop-loss study (2026-07-06 night) — REAL 1-minute premiums; stop stays OFF

**Data unlock:** the Upstox expired-instruments API serves **1-minute candles for expired
contracts** (`DATA_AVAILABILITY_LIMITS.md`'s "no historical intraday option data" is now
outdated). So the buy-back stop was tested on real minute paths, not the pessimistic daily-high
model. 91 expiries Oct'24→Jun'26, entry at the 09:16 bar, stop fill = max(level, bar open)
×1.01, wing at its concurrent 1-min bar, settlement at intrinsic vs NIFTY close (this fresh
rebuild also re-verified the earlier 4 suspect rows). Script `studies/ndte/ndte7_stops.py`,
cache `/tmp/ndte_intra/`.

| Config (with rv5 filter) | Win | Avg %m | Total ₹ (1 lot) | Worst trade |
|---|---|---|---|---|
| **NO-STOP (deployed)** | **90.4%** | **+5.85%** | **+₹49,527** | −₹11,703 |
| Short-leg stop ×3.0 | 82.2% | +4.50% | +₹35,804 | **−₹6,517** |
| Short-leg stop ×4.0 | 87.7% | +4.54% | +₹37,632 | −₹11,304 |
| Short-leg stop ×2.0 | 68.5% | +4.08% | +₹32,053 | −₹3,958 |

Findings: (1) **without** the calm-regime filter, stops help enormously (no-stop ₹18.4k → ×2-3
₹36-37k) — stop and filter fix the same hot-week disasters; (2) **with** the filter already on,
every stop LOWERS total P&L and win rate — it only buys a smaller worst trade (×3 halves it for
~₹650/mo of expected cost); (3) tight stops whipsaw: ×1.5 stops 40 of 91 trades and win falls to
56% — 0DTE premium noise routinely doubles and then decays. Note the filtered no-stop baseline
here (+5.85%m, intrinsic settlement) is BETTER than the earlier stale-close estimate (+4.0%m) —
the daily-candle "close" understated wins on far-OTM legs.
**Decision: filter + no stop stays deployed; `ZERO_DTE_STOP_MULT` added (default 0 = off) for a
tail-cutting ×3 preference.**

## Frequency extension (2026-07-06 night): other expiries + the "almost daily" test

**SENSEX Thursday 0DTE** (same structure, wing ~0.83% of spot, BSE weeklies, 89 expiries
Oct'24→Jul'26, `studies/ndte/ndte8_sensex.py`): **88.8% win, +7.57%m, +₹67,248/lot (20 qty),
worst −₹8,963.** Oct–Dec'24 negative (expiry-day transition era); 2025: 90.2%/+₹34.1k; 2026:
92.3%/+₹37.3k. NIFTY's rv5 filter does NOT transfer (slightly hurts) — run unfiltered. Caveats:
21 months only (BSE weeklies are young), BSE spreads wider than NIFTY (cost model may be light).
NOT yet wired into the engine — deliberately waiting until the NIFTY book's first live morning
runs clean.

**BANKNIFTY 0DTE monthlies** (23 tradeable expiry days): 91.3% win, +10.95%m, +₹17,214, worst
−₹14,298. Small sample; adds ~1 payday/month. (`studies/ndte/ndte9_daily.py`)

**Near-DAILY selling: REJECTED.** Same spread sold every morning on the NEAREST weekly (DTE
1–6), closed same day (424 day-trades): non-expiry days sum to **−₹3.4k over 333 trades**, win
50–64% with no structure across DTE buckets (2 and 5 positive, 1/3/6 negative = noise). **The
edge is specifically expiry-day theta collapse — it does not exist on other days.** The honest
maximum frequency from this edge: Tuesday (NIFTY) + Thursday (SENSEX) + ~1 monthly (BANKNIFTY)
≈ 9–10 paydays/month.

## BANKNIFTY 2019→2024 validation (2026-07-06 late) — QUALIFIED PASS, monthly-only deploy

Full NSE bhavcopy check the user asked for (`studies/ndte/ndte10_bnf.py`, 273 weekly expiries,
`/tmp/ndte_bhav_bnf`): **79.5% win, +7.42%/margin, +₹89,616 (lot 30), worst −₹10.7k.** Per year
(win / ₹): 2019 84%/+21.5k · 2020 68%/+12.3k · 2021 85%/+25.7k · 2022 74%/+18.8k ·
2023 89%/+24.5k · 2024(→Jul) 76%/−13.1k. Plus monthlies Oct'24→Jun'26: 91.3%/+10.95%m (23 tr).
BNF weeklies were abolished (SEBI Nov'24) → deployable ONLY on its ~monthly expiry day.
SENSEX pre-2023 is untestable (market didn't exist in liquid form — 21-month history stands).

## Consolidated portfolio — expected monthly P&L (all 5 books, MODEL vs PLAN-ON)

| Book | Signals/mo | 1 lot model | 1 lot plan-on | 2 lots model | 2 lots plan-on |
|---|---|---|---|---|---|
| Stock fade v2 (swing) | 4–6 | ₹17,500 | ₹8–10k | ₹35,000 | ₹16–20k |
| Stock credit v1 (swing) | ~10 | ₹9,000 | ₹4–5k | ₹18,000 | ₹8–10k |
| NIFTY Tue 0DTE | ~3.5 | ₹2,360 | ₹1.2k | ₹4,700 | ₹2.4k |
| SENSEX Thu 0DTE | ~4.2 | ₹3,200 | ₹1.5k | ₹6,400 | ₹3k |
| BANKNIFTY monthly 0DTE | ~1 | ₹820 | ₹0.4k | ₹1,600 | ₹0.8k |
| **TOTAL** | ~23 | **~₹33k** | **~₹15–18k** | **~₹66k** | **~₹30–36k** |

Capital: ~₹2–2.5L at 1 lot / ~₹4–5L at 2 lots (swing books + recycling intraday margins).
Warnings that make it honest: monthly figures are AVERAGES (combined bad month at 2 lots can be
−₹40–60k); the 0DTE books' live history starts 2026-07-07; all five books are correlated short
premium in a crash — treat as ONE portfolio, size on the worst month.

## Thin-credit gate (2026-07-07, user-caught live) — deployed at 0.02% of spot after recalibration

Day-1 live trade collected only ₹4.7 pts vs ₹195 risk (VIX ~11.8). 2019-24 real data: credits
below 0.08% of spot were dead weight (-0.4%m over 100 calm-week trades) vs +6.75%m above. BUT
the last 21 months of REAL 1-min premiums show premiums have structurally compressed: an 0.08%
floor would skip 64% of modern trades (58/91) INCLUDING +₹13.2k of realized profit — the old
absolute threshold does not transfer. Recalibrated to a sanity floor: **skip only when credit
< 0.02% of spot (~₹5 pts)** — that excluded just 3 trades in 21 months (total +₹955 forgone)
while blocking exactly the risk-₹13k-for-₹300 shape of the day-1 trade. Frequency impact:
~1-2 skips/year; ~4.2 trades/month retained.  live.

## Forward test — live paper log
2026-07-07 (day 1, NIFTY): SELL 24600 CE / BUY 24800 CE @ 9:17, credit ₹4.7 (VIX ~11.8; the
thin-credit week that motivated the ₹5-pt floor). NIFTY closed ~24,460 → both legs worthless →
**WIN ~₹300 (1 lot, 65 qty)**. SENSEX book live from 2026-07-09; BANKNIFTY monthly from 2026-07-28.

## Reproduce
Scripts copied to `studies/ndte/`: `bhav_expiry_dl.py` (NSE expiry-day download →
`/tmp/ndte_bhav/`), `ndte3_bhav_bt.py` (2019-24 grid, per-year PASS bar), `ndte4_oos.py`
(Upstox OOS of the winner family; needs `.env` token; expired-API 401-bursts → retry wrappers
inside), `ndte5_final.py` (combined stats), plus `ndte_bt.py`/`ndte2_bt.py` (0DTE strangle grid
+ helpers). Data: `/tmp/ndte_bhav/` (282 CSVs), `/tmp/ndte_cache/` (~2k legs + spot).
Full grids in the session task outputs; iteration history in `HANDOFF.md`.
