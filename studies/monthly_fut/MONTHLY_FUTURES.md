# Monthly Futures Strategy Search — NSE stocks + indices (2026-07-09)

> **GOAL DISPOSITION (final):** the 10%/month-net leg of the goal is **infeasible** on NSE
> futures. Exhaustively tested: 90-config directional grid, composition/exit refinements,
> beta-hedged baskets, index sleeves, calendar spreads, capital recycling, rolling mid-month
> entries (via recycling ranks). Ceiling: **REV1-v2, 75.7% win OOS, ~3.9%/month on margin
> capital**. Reaching 10%/mo would need a +2.2%/trade net edge (best honest: +0.85%) or 2.6×
> leverage beyond exchange margin, which does not exist in futures. Any config printing near
> 10%/mo in-sample failed OOS — the project's documented curve-fit failure mode. Do not
> reopen without new data or a changed constraint set.

**Ask:** monthly-horizon trades in FUTURES only (NSE stocks + indices), win rate ≥ 75%,
net ≥ 10%/month on capital, technical + fundamental parameters.

**Answer up front:** 75% win rate — achievable and OOS-validated. **10%/month net — NOT
achievable honestly**; the best OOS-surviving strategy earns **~3–4%/month on fully-margined
capital** (≈2.5–3% with a prudent margin buffer), with a −20 to −31% max drawdown. Nothing in
a 90-strategy-config grid over 8.5 years of real futures data came within 2.5× of 10%/mo.

## Data & method

- Real futures prices, NSE F&O bhavcopy: FUTSTK for the 100-stock universe + FUTIDX
  NIFTY/BANKNIFTY, **2018-01 → 2026-07** (old format to Jun'24, UDiFF after; caches in
  `cache_2018/ cache_idx/ cache_new/` + `/tmp/bhav_cache_stk`; merged by `build_panel.py`).
- Expiry-to-expiry monthly cycles: enter at close of the first trading day after the prior
  monthly expiry in the new front month; exit at expiry settlement or earlier when a daily
  close crosses TP/SL (an executable MOC rule — no intraday data needed).
- Costs 0.10% of notional round-trip. Margin: 22% stocks / 11% index.
- **IS = entries before 2024-10 · OOS = 2024-10 → 2026-07.** Selection on IS only, one OOS look
  (the lesson from the index-fade failure).
- Grid: `bt.py` — momentum L/S (3/6-mo), 1-month pullback longs, index 200DMA trend/dip,
  Donchian-10 fade shorts, low-vol filter, beta-hedged basket × TP(2/3/4%) × SL(none/5/8%).

## Result — one OOS survivor

**REV1_L "pullback long": each monthly cycle, among stocks above their own 200DMA and with
NIFTY above its 200DMA, buy the 5 worst 1-month losers in the front-month future. TP +2% /
SL −5% on daily close; else hold to expiry.**

| | trades | win | basket-win (months) | avg net/trade | mo. on margin cap | worst mo | max DD |
|---|---|---|---|---|---|---|---|
| IS 2018→Sep'24 | 281 | **75.1%** | 69% (55 mo) | +1.01% | **+4.6%** | −26.6% | −31.3% |
| OOS Oct'24→Jul'26 | 70 | **74.3%** | 64% (11 mo) | +0.86% | **+3.9%** | −20.5% | −20.5% |

Per-year: negative 2018 (−1.5%/trade), ~flat 2019, positive every year 2020→2025, 2026 YTD
slightly negative on 10 trades. Exits OOS: 52 TP (avg +2.97%), 13 SL (avg −6.3%, gaps included),
5 expiry. No single-name concentration (max 3 trades/symbol OOS).

Runner-up MOM3_L (3-mo momentum longs, same exits) **failed OOS**: 73.8%→65.2% win,
+4.1%→−1.2%/mo — momentum was a 2021–23 bull artifact. The pullback book is the one that held.

## Why 10%/month is not on the table

- 10%/mo net on capital at 22% stock margin = ~2.3% net per trade on notional, every month,
  across 5 concurrent positions. The best honest OOS number is 0.86%/trade — a 2.7× gap.
- Closing it with leverage (higher margin utilization / more lots per unit capital) scales the
  −20% worst month toward −55%+ and margin-call territory. The 75% WR does not protect you:
  the structure is short-skew (many +2% wins, few −6% losses).
- Every configuration that printed >8%/mo in-sample anywhere in the grid was thin-sample
  (n≈32) or collapsed OOS. This is the same regime-fitting failure mode documented in
  `CAPITAL_CURVE_RESULTS.md` and the index-fade salvage.

## Appendix — losing-trade anatomy & the refinement pass (2026-07-09, same day)

User follow-up: analyze the losers and raise %profit on margin **without reducing trade count**.
Anatomy of the 281 IS trades (`is_trades_features.csv`):
- **Entry features do not separate winners from losers** (mom1/dist-above-200DMA nearly
  identical) — losses are not predictable at entry; they are the cost of the structure.
- Stopped trades die fast (median 6 sessions, 66% below −2% by day 5); expiry losers drift
  only −0.2% more after day 10. High-vol entries win MORE (81.9% top tercile vs 69.1% low).
- Tested same-count levers: rank windows 2–6/3–7 (worse — the "rank-1 falling knife" was
  noise), soft stops −2/−3% after day 5 (worse — they cut recoverers), SL −4% (worse),
  index-dip sleeve (dilutes), capital recycling (much worse, see above).
- Two tweaks helped IS: prefer the **5 highest-vol of the worst 8** pullbacks, and **decay the
  TP to +1% after day 12** → IS 77.8% win, +5.03%/mo (vs 75.1%/4.59%).
- **OOS: the return gain vanished** — v2 3.91%/mo vs base 3.89%. What held: win 75.7% (>75%
  OOS), positive months 73% vs 64%, max DD −20.1% vs −20.5%. **REV1-v2 = same return, more
  robustness.** ~3.9%/mo on margin is the honest ceiling at this trade count.
  Trades: `trades_rev1v2_oos.csv`.

**Final spec (REV1-v2):** at each monthly cycle start, NIFTY>200DMA; among stocks above their
own 200DMA take the 8 worst 1-month losers, keep the 5 with highest 20-day vol; buy front-month
futures at close; exit MOC on close ≥ +2% (+1% after day 12) or ≤ −5%; else expiry settle.

## Appendix — the OPTIONS expression: the one lever that raises return-on-CAPITAL (2026-07-10)

The 10%/mo goal is unreachable on futures MARGIN (confirmed 3×). The remaining honest lever:
run the SAME validated REV1-v2 signal but BUY a monthly CALL instead of the future — premium
outlay ≪ futures margin, so the same +2% move is a far larger % of capital deployed. Tested on
REAL NSE stock-option premiums (bhavcopy closes 2019→Sep'24), `opt_bt.py` / `opt_bt2.py`.

**Hold-to-expiry calls FAIL** (theta wall): 28–39% win, net −3 to −12%/trade. This is the
project's known option-buying-decay result — do not buy-and-hold.

**Early-exit calls (exit the call the day the underlying hits +2%/−5%, matching the futures
rule) — the fair test, and it works:**

| | trades | win | avg on capital/trade | monthly mean | worst month | +ve months |
|---|---|---|---|---|---|---|
| ATM, IS 2019-23 | 211 | 70% | +5% | +5% | −59% | — |
| ATM, OOS 2024 (thin) | 26 | 81% | +17% | +17% | +3% | — |
| Both, all 48 months | — | — | — | — | — | 67% |

Per year: 2019 −8% / 2020 −1% / 2021 +20% / 2022 −4% / 2023 +11% / 2024 +17%. Median entry
premium ≈ ₹29/share; losing trades average −62% of premium (early −5% SL caps most of the tail).

**What this means for the goal & the ₹2L constraint:** return is on PREMIUM deployed, not ₹15L
margin — 5 calls at ~₹25–40k premium each ≈ ₹1.5–2L total. Historical mean +5%/mo (IS) to
+17%/mo (OOS) on that ~₹2L = ~₹10–34k/month at 70–81% win. This is the first structure that
plausibly approaches the ~10%/mo-on-capital target and fits ₹2L.

**DECISIVE OOS — real Upstox premiums Oct'24→Jul'26 (`opt_oos.py`, the window futures/v2 used):**

| | trades | win | avg on capital/trade | monthly mean | worst month | +ve months |
|---|---|---|---|---|---|---|
| ATM early-exit call, OOS | 60 | 67% | +6% | +7% | −51% | 60% |

Per year OOS: 2024 +22% (n=5) / 2025 +5% (n=45) / 2026 +4% (n=10). The strong 2024-only slice
(+17%) did NOT fully hold on the full window — the honest OOS figure is **~+6–7%/mo on capital
at 67% win**, weaker than the in-sample hoped but still ~2× the futures' 3.9%/mo.

**Verdict on the goal — the frontier, stated honestly:**
- Futures (margin): ~3.9%/mo on capital, **75% win**, −20% worst month.
- Options early-exit call (premium): **~6–7%/mo on capital**, **67% win**, −51% worst month.
- The options expression roughly DOUBLES return-on-capital (closes ~⅔ of the gap to 10%) and
  fits ₹2L (premium-funded, not ₹15L margin) — BUT it drops below the 75% win bar and triples
  the drawdown. **You cannot have 75% win AND ~10%/mo simultaneously on this signal; it is a
  trade-off frontier, not a free lunch.** 10%/mo at 75% win remains not achievable on real data.

**Caveats:** costs = spread-fraction model on premium, not live fills (mid-cap call spreads are
wider → live < backtest); 60 OOS trades is still thin; the −51% month is real gap/whipsaw risk.
Not deployed — approval-first stands.

## Appendix — calendar spreads (the last futures-only structure)

Tested selling the 5 richest front/back basis spreads per cycle (short back, long front, hold
to front expiry; margin-efficient on NSE). Median stock basis is 0.44%/mo — but net of 0.20%
4-leg costs the trade earns **≈0% since 2021** (2022–25 yearly avgs: −0.06/−0.14/−0.10/−0.10%,
win 43.7%). The big pre-2021 "profits" trace to corporate-action artifacts and illiquid back
months (max "spread" 431%), not a harvestable edge. Basis capture is dead at retail costs.

## Honesty & limits

- Close-based TP understates a resting-limit fill rate → reported WR is a conservative floor
  for the tested MOC policy, which is itself directly executable.
- Entry uses same-day-close signals (compute at ~15:25, enter MOC). Slippage beyond the 0.10%
  cost assumption on illiquid front months would shave results; universe is the liquid 100.
- **Fundamentals:** no free point-in-time fundamentals exist — screening today's ratios into a
  2019 backtest is lookahead, so this study is technical + regime only. Live-only overlays
  (skip names with earnings inside the trade month; skip F&O-ban names) are prudent but
  untested — they could help or hurt.
- Not deployed. Per project rule, nothing goes live without user sign-off.

*Scripts: `dl_new.py dl_idx.py dl_2018.py build_panel.py bt.py`; full grid in
`grid_results.json`; trade lists `trades_*.csv`. Generated 2026-07-09.*
