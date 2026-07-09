# Handoff — institutional-trader / monthly futures study
_Updated: 2026-07-09 ~21:30 by Claude Code_

## Goal
User wanted monthly NSE futures trades ≥75% win / ≥10%/mo net. Concluded: infeasible; best is
**REV1-v2: 75.7% win OOS, ~3.9%/mo on margin** (full study `studies/monthly_fut/`). Loser
anatomy done: half of OOS losses are single-day news shocks — technical params can't predict
them. Futures need ~₹15L capital; user has **₹2L max**, so pivoted (2026-07-09 evening):
**options strategies on ₹2L capital targeting ~₹50-60k net profit** (period ambiguous —
monthly ≈25-30%/mo is infeasible; yearly ≈2-2.5%/mo is near the validated stock fade v2
range). Existing validated options edge: stock fade v2 credit spreads (85%/88% win IS/OOS,
live parallel book) — see repo CLAUDE.md + `studies/STOCK_FADE_TP50_UPGRADE.md`.

## Current state
- **Done (all in `studies/monthly_fut/`):**
  - Data: real NSE futures bhavcopy 2018-01→2026-07 merged to `panel.csv.gz` by
    `build_panel.py`. Caches: `cache_2018/`, `cache_idx/` (FUTIDX 2019→Jun'24), `cache_new/`
    (UDiFF Jul'24→Jul'26), plus `/tmp/bhav_cache_stk` (FUTSTK 2019→Jun'24 — tmp, may vanish;
    re-download with `studies/ndte/bhav_dl_stk.py` if wiped).
  - Grid backtest `bt.py` (90 configs, 8 families), results `grid_results.json`.
  - Winner: REV1_L — each expiry-to-expiry cycle, NIFTY>200DMA, buy front-month futures of the
    5 worst 1-month losers still above their own 200DMA; exit MOC on close crossing +2% TP /
    −5% SL, else expiry settle. IS 75.1% win / +4.6%/mo; OOS (Oct'24→Jul'26) 74.3% / +3.9%/mo.
    Trades: `trades_REV1_L_top5.csv`. Study doc: `MONTHLY_FUTURES.md`.
  - Negative results (do NOT retry): MOM3/MOM6 momentum failed OOS; calendar spreads ≈0 net
    after 4-leg costs since 2021; capital recycling (`recycle_bt.py`, `trades_recycled.csv`)
    DILUTES the edge (0.2%/mo OOS) — mid-month refill candidates are weak.
- **Done (loser-analysis pass, same day):** anatomy in `is_trades_features.csv` — losses
  unpredictable at entry; soft stops / rank shifts / index sleeve / recycling all worse.
  Final spec **REV1-v2** (worst-8 pullbacks → top-5 by vol20, TP +2% decaying to +1% after
  day 12, SL −5%): OOS 75.7% win, 3.91%/mo on margin, DD −20.1%, 73% positive months
  (`trades_rev1v2_oos.csv`). Study doc carries a final GOAL DISPOSITION banner: 10%/mo leg
  infeasible; ~3.9%/mo is the ceiling. User asked to clear/revise the /goal.
- **In progress (user approved 2026-07-09 late):** wiring REV1-v2 + live earnings-skip rule
  into the engine as signals-only paper forward-test: new `engine/monthly_fut.py`, PM DECISIONS
  section in `engine/ui_terminal.py`, `MONTHLY_FUT_*` in `engine/config.py`, hook into
  `engine_runner.py` EOD block; update `studies/STRATEGY_SUMMARY.md` (+README) and commit to
  git (gitignore the bhav caches + panel.csv.gz — commit scripts/docs/trade lists only).
  Factor pass done: NO removable loser factor exists (gap-prone names are the BEST bucket);
  safety = diversification / earnings-skip (live-only) / options for defined risk.

## Next steps
1. Regenerate IS trades with entry-time features attached (import from `bt.py`: `load`,
   `near_month`, `build_features`, `run_trades`; join feature values asof entry date).
2. Winner-vs-loser comparison on IS ONLY (2018→Sep'24). Look for structural, explainable
   asymmetries. Constraint: no filters that drop trades — only exit-rule changes (SL level,
   time-stop for losers, TP laddering) and additive sleeves.
3. Test refined exits IS by year; require improvement in every-year consistency, not just mean.
4. ONE OOS look (entries ≥2024-10-01) on the final refined config. Report honestly even if worse.
5. Update `MONTHLY_FUTURES.md` + present to user. Do NOT deploy anything without user sign-off.

## Key files
| File | Why it matters |
|---|---|
| `studies/monthly_fut/bt.py` | core backtest: data load, cycles, features, strategies, exits |
| `studies/monthly_fut/panel.csv.gz` | merged futures panel 2018→2026 (rebuild: `build_panel.py`) |
| `studies/monthly_fut/trades_REV1_L_top5.csv` | validated strategy's full trade list |
| `studies/monthly_fut/MONTHLY_FUTURES.md` | study write-up + honesty caveats |
| `studies/monthly_fut/grid_results.json` | all 90 IS configs incl. per-year blocks |
| `CLAUDE.md` (repo root) | project rules: honesty-over-optimism, backtest-before-deploy |

## Decisions & gotchas
- IS/OOS split: entries before 2024-10-01 = IS. OOS was already looked at ONCE for REV1_L and
  MOM3 (MOM3 failed). Every additional OOS peek burns validity — batch all refinements, look once.
- Close-based (MOC) exits are the executable policy; TP exits average +2.97% (overshoot), SL
  −6.3% (gaps). Only futures CLOSE exists for stocks 2019→Jun'24 (no OHLC).
- 22% stock margin / 11% index margin assumed; "mo_cap" = monthly return with capital = margin
  only (no buffer). Prudent real-world figure ≈ 0.7× that.
- No free point-in-time fundamentals exist — fundamental screens would be lookahead; study is
  technical+regime only.
- Costs 0.10% notional round-trip. The 100-stock universe is `engine.config.UNIVERSE`.
- Prior project lesson (twice confirmed): in-sample winner + salvage gates fail OOS. Don't
  sell a curve-fit; user's approval-first memory applies to any deploy.
- The previous HANDOFF.md (intraday 90% win-rate loop, 2026-07-06) was superseded; its studies
  live in `studies/INTRADAY_90PCT_WINRATE.md` + `studies/intraday90_bt.py`.

## How to resume
Read `studies/monthly_fut/MONTHLY_FUTURES.md`, then `bt.py`, then continue with step 1 above.
Run scripts with the project venv: `cd ~/files/institutional-trader && .venv/bin/python
studies/monthly_fut/bt.py`. Rebuild panel first if caches changed: `.venv/bin/python
studies/monthly_fut/build_panel.py`.
