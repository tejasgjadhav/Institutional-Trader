# Handoff — institutional-trader (intraday high-win-rate goal loop)
_Updated: 2026-07-06 ~19:10 by Claude Code_

## Goal
Active /goal+/loop from the user: find an **intraday** strategy (entered and closed same day),
Indian markets, cash or F&O, liquid and retail-tradeable. First asked at **90% win rate**
(answered, see Done); now revised to **≥85% win + positive NET returns + >2% per trade on
deployed capital + risk/reward optimized**, "use all tech parameters, not restricted".

## Current state
- **Done — iteration 1 (90% question), documented + reported to user:**
  `studies/INTRADAY_90PCT_WINRATE.md` + `studies/intraday90_bt.py`. On 7.5 yrs of cached Kite
  5-min bars (100 F&O stocks, `/tmp/k5m`, 2019→2026-07): VWAP-flush fade (buy ≥2% below VWAP,
  TP +0.20%, SL −3%, EOD close) wins **92% IS / 90.8% OOS (7,688 trades)** but averages
  **≈0.00% gross / −0.095% net**. The 90% is exit geometry, not edge; none of 2,400 grid cells
  is net-positive after 0.10% retail costs.
- **Done — iteration 2 (85% + net>0 on the UNDERLYING: FAILS):** scratchpad `intraday85_v2.py`.
  234 strategies (deep flushes × RSI/z confluence × VWAP-target/trailing/fixed exits, shorts,
  gap fades; TRAIN 2019-23 / TEST 2024-26): **zero configs ≥82% win with net>0**. Best OOS ~72%
  win, ~0.00% net (3%-flush fade, trailing exit). Underlying intraday direction is settled: the
  gross edge (~+0.05-0.15%) is smaller than retail cost. Do NOT re-mine this.
- **Done — iteration 3a (0DTE NIFTY naked strangle/straddle grid, REAL premiums):**
  scratchpad `ndte_bt.py`; `/tmp/ndte_cache/` = daily O/H/L/C for ~1,966 expiry-day option legs
  (92 NIFTY weekly expiries Oct'24→Jun'26, Upstox expired-instruments API) + `spot.json`.
  Entry=day OPEN, per-leg stop vs day HIGH (conservative), exit=CLOSE≈settlement, costs 2.5% of
  credit+brokerage, TRAIN Oct'24–Dec'25/TEST Jan'26–Jun'26. **Result: short premium is
  net-positive across almost the whole grid (train AND test) — structure works — but win rate
  caps ~70–77% and return on naked-strangle margin ~0.3–2%/trade.** Doesn't meet 85%+2% yet.
- **In progress — iteration 3b (defined-risk credit spreads/condors, tuned for 85% + 2%/margin):**
  scratchpad `ndte2_bt.py`: shorts 0.5–2% OTM × wings 100/150/200/300pts × stop {2×,3×,none} ×
  calm-open gap filter × {IC, CE-only, PE-only}; margin = width−credit (defined risk).
  Fixed two real bugs: (1) leg cache poisoning — failed fetches were cached as null (now never
  cache None; 22 nulls purged); (2) **closure late-binding** — per-day `get()` captured the last
  expiry's chain, so every day resolved June'26 contracts → empty results (now bound via default
  args). Upstox expired-API throttles in bursts presenting as **401** (not 429) — retry wrappers
  added (contracts ×5/6s, legs ×3/4s). A cached-only validation run (wings=300, shorts ≤1%) is
  executing now; the full far-OTM grid needs ~1,400 new leg fetches when the API cooperates.

## GOAL LOOP COMPLETE (19:55) — see `studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md`
OOS PASSED: CE d=0.50% W=200 no-stop → 86.8% win / +3.28%m OOS; combined 2019-26: 373 trades,
85.0% win, +3.20%m, positive all 8 years. Documented + reported. Scripts in `studies/ndte/`.

## NOW EXECUTING (user request 20:00): deploy as paper forward-test
1. New engine module (signals-only, mirror stock_credit_v2 pattern): 0DTE CE spread — expiry
   day, short CE 0.5% OTM of spot open (strike step 50), wing +200, no stop, book at 15:30
   settlement; own book data/zero_dte*.json; ZERO_DTE_* tunables in config.
2. New INTRADAY DECISIONS tab in ui_terminal.py (read-only) + study visible in STUDIES tab.
3. Commit studies + code to GitHub (verify .env NOT staged), restart engine+viewer.
4. Numbers for user: ~4.3 calls/mo (one per NIFTY weekly expiry), ~₹14-15k margin/lot used only
   expiry day, avg ₹348/trade/lot (model) ≈ ₹1.5k/mo/lot.

## Next steps  (superseded — kept for context, updated 19:45)
0. **CANDIDATE FOUND (2019-24 bhavcopy, `ndte3_bhav_bt.py`, data `/tmp/ndte_bhav/`, 282 expiry
   days):** CE credit spread d=0.75% OTM, wing W=200, NO stop, every NIFTY weekly expiry:
   **87.1% win, +2.32%/margin avg, win>=85% AND net>0 EVERY year 2019-24** (19:89/+1.4 20:87/+0.5
   21:87/+3.2 22:88/+6.5 23:85/+0.6 24:88/+0.8). Neighborhood coherent (W=100: 84.8%/+5.1;
   W=300: 87.4%/+1.9; symmetric IC ~78%/+2.5-4.5). ndte2 cached run (Upstox Oct'24-Jun'26, W=300
   only) already showed CE d=0.75 no-stop at 93.8%TR/84.6%TE win, -0.1/+5.9%m.
1. OOS-validate CE d=0.75 W={100,150,200} no-stop on Upstox Oct'24->Jun'26 (needs W=100-200 wing
   legs; expired-API 401-bursts — reuse ndte2_bt.py retry wrappers). Scratchpad:
   `/private/tmp/claude-501/-Users-sayali-files/9e3c4735-97f8-4604-915d-79cbc15d4f77/scratchpad`
2. Shortlist configs: ≥85% win AND net>0 AND ≥2%/trade on margin (strangle margin ~₹1.6L/lot;
   condor ≈ 300×75−credit ≈ ₹20k). Judge the whole d×stop neighborhood + train/test agreement +
   worst day, not one cell.
3. If promising: per-month PnL, drawdown, loss streaks; BANKNIFTY monthlies (27 expiries) as a
   robustness check. If nothing passes: best honest risk-reward answer.
4. Write `studies/INTRADAY_85PCT_POSITIVE.md` (honest: 21-month single-regime window,
   stop-vs-HIGH conservative, live fills unproven) and report to the user.

## Key files
| File | Why it matters |
|---|---|
| `studies/INTRADAY_90PCT_WINRATE.md` + `studies/intraday90_bt.py` | iteration-1 answer, reproducible |
| `/tmp/k5m/*.json` | Kite 5-min, 100 stocks, 2019→2026-07 (Kite token stale — cache is the only copy) |
| `/tmp/ndte_cache/` | REAL expired NIFTY 0DTE option daily OHLC, 92 expiries + spot |
| scratchpad `intraday85_v2.py`, `ndte_bt.py` | iteration 2/3 scripts |
| `engine/expired_options.py` | expired-instruments helpers ndte_bt drives |
| `studies/WIN_RATE_RESEARCH_LOG.md` | prior art: the ~52-57% intraday wall, win-vs-profit opposition |
| `studies/STOCK_FADE_TP50_UPGRADE.md` | the validated 85-88%-win strategy (multi-day, deployed as v2) |

## Decisions & gotchas
- ">2% returns" interpreted as per-trade return on deployed margin (impossible on notional
  intraday; iteration-1 report said so).
- Intraday option premium history doesn't exist anywhere (`studies/DATA_AVAILABILITY_LIMITS.md`)
  — hence daily-OHLC 0DTE modeling with a deliberately conservative stop rule.
- `/tmp/bhav_cache_stk` (1.1 GB) has CLOSE+OI only — no OPEN/HIGH → can't extend the 0DTE test
  to 2019-24 without re-downloading full NSE bhavcopy (defer; note as future work).
- Prior session (2026-07-04) deployed stock fade v2 (`engine/stock_credit_v2.py`, 1 lot,
  ₹40k exposure cap) — separate from this loop; canonical verdicts in
  `studies/STRATEGY_SUMMARY.md`.
- HONESTY rules: gross vs net always, sample-size caveats, never promise riches; live < model.

## Security constraints (permanent)
- `.env` (Upstox+Kite keys) NEVER committed; check `git diff --cached --name-only | grep .env`.
- No secrets in the public wiki; `wiki_push.sh` secret-scans.

## How to resume
Read `studies/INTRADAY_90PCT_WINRATE.md`, `studies/WIN_RATE_RESEARCH_LOG.md`, and this file;
then do step 1 (instant rerun) and continue through step 4. Engine venv:
`/Users/sayali/files/institutional-trader/.venv/bin/python`. Don't commit HANDOFF.md or `.env`.
