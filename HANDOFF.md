# Handoff — institutional-trader
_Updated: 2026-07-13 by Claude Code_

## LATEST (2026-07-13 cont.) — gated 8-pick options FAILED OOS; user asking what's already live
OOS validation (opt_oos_gated.py) KILLED the gated 8-pick long-call config: 6.4%/mo IS →
55% win / −2.7%/mo (LOSES) OOS. Isolation: 5→8 picks killed edge (+6-7%→+0.3%); gates overfit.
ONLY simple 5-pick −5% early-exit survives OOS (+6-7%/mo, 67%, −51% worst mo). Committed. User's
current Q: "are we already deploying defined-risk credit spreads?" → YES, several are live paper
books (check config *_ENABLED flags: SWING_CREDIT, STOCK_CREDIT v1, stock_credit_v2, the 0DTE
books). Pending user pick: wire 5-pick calls as paper, or stay with the spread books.

## ACTIVE TASK (2026-07-13) — MAX-trades / MAX-return monthly OPTIONS on ₹2L
User RESOLVED the monthly-futures frontier: 10%/mo @ 75% win proven impossible (studies/monthly_fut/
MONTHLY_FUTURES.md + the win-rate/payoff-ratio math). User's decision: **₹2L capital, OPTIONS route
(higher return-on-capital), 67% win is ACCEPTABLE, wants MAX trades + MAX return.** So drop the win-rate
constraint and optimize the REV1-v2-signal-as-CALLS book for total return on a fixed ₹2L.
- Base options result (opt_bt2.py/opt_oos.py): REV1-v2 signal, 5 picks/cycle, ATM call, early-exit
  (+2%/−5% on underlying) → OOS Oct'24→Jul'26 67% win, +6-7%/mo on capital, −51% worst mo.
- MAX-trades levers to test: expand picks/cycle (5→8→all qualifying pullbacks), cheaper structures
  (call debit spread) to fit MORE positions per ₹2L, measure TOTAL return on fixed ₹2L + DD + win.
- Data: bhav stock-option closes 2019→Sep'24 (IS, /tmp/bhav_cache_stk), Upstox expired (OOS Oct'24→).
- Keep data/ gitignored (already is); commit scripts+study only. approval-first before any live deploy.

## Prior goal (RESOLVED/paused)
Monthly-futures 10%/mo goal-loop — concluded empirically+mathematically infeasible; all real
deliverables committed (REV1-v2 futures paper book, options expression, ≥80%-win Tier A grouping,
live_tracker.py). Standing rule: **approval-first**. Nothing deployed live this session.

## Current state
- **Done (verified, this session):** 0DTE entry-time sweep on real 1-min premiums, 92 expiries
  Oct'24→Jul'26. Verdict: keep 09:16 entry — later entry (9:45/10:00) adds +3-4pp win rate
  (noise, n=73) but costs 35-45% of profit, no tail reduction. Study
  `studies/ZERO_DTE_ENTRY_TIME.md`, script `studies/ndte/ndte11_entrytime.py`, grid
  `/tmp/ndte11_results.json`. 09:16 row reproduces ndte7 exactly (90.4% / +5.85%m / ₹49,527).
  User decision: keep in studies, do NOT extend `ZERO_DTE_ENTRY_CUTOFF` ("i don't think we
  will miss").
- **Done (verified, this session):** non-fade intraday search — long gamma falsified. ATM
  straddle @open, gap-follow and trend-follow debit verticals all NET NEGATIVE on bhav
  2019→Sep'24 (282 exp) AND 1-min era Oct'24→Jul'26 (92 exp). Hot-week (rv5≥0.9) long-gamma
  complement hypothesis REJECTED (IS −23.2%/trade, n=77). Study
  `studies/NONFADE_INTRADAY_SEARCH.md` (includes the full falsified-families ledger), script
  `studies/ndte/ndte12_longgamma.py`. Conclusion: no retail-accessible non-fade intraday edge
  in testable data; remaining directions are multi-day/overnight (needs user risk sign-off).
- **Done (live check, 2026-07-10 close):** stock fade v2 UNION read-only gate replica — 9 D5
  breakouts (8 down: AXISBANK/HDFCLIFE/NTPC/ADANIGREEN/POLYCAB/MARUTI/M&M/DRREDDY; 1 up:
  SUNPHARMA), ALL blocked by credit/width ≥0.40 (best ADANIGREEN 0.36, M&M 0.32). No v2 entry
  today; TCS bull-put booked TP-75 at 09:24; TRENT (entered 07-08) still open.
- **Still true (prior session, 2026-07-10 am):** monthly futures book REV1-v2 deployed as the
  5th signals-only paper book (commit 1a70fef): `engine/monthly_fut.py`, `MONTHLY_FUT_*` in
  config. NIFTY < 200DMA → scans mark REGIME_OFF until regime flips. Full details in
  `studies/monthly_fut/MONTHLY_FUTURES.md`; do NOT retry MOM3/MOM6, calendar spreads,
  capital recycling (all failed).
  TIMING (answered to user 2026-07-10): the 5 signals fire ONCE per monthly cycle, on the first
  trading day AFTER the prior monthly expiry (≈ last Fri of each month; front-month expiry then
  ≥ MONTHLY_FUT_MIN_DTE=20 days out), scanned after 15:10, held to that expiry. Next windows
  ~2026-07-31, ~2026-08-28, ~2026-09-25 — but ONLY on the first where NIFTY>200DMA. Cycle
  2026-07-30 already recorded REGIME_OFF, so 0 signals now and every cycle until NIFTY reclaims
  its 200DMA. The PM DECISIONS row shows that stand-aside state, not blank.
- **Done (UI, 2026-07-13):** (a) PM DECISIONS headers now show IS alongside OOS — v1
  "54% IS (hold-exp) / 73% OOS (TP-75)", monthly "77.8% IS / 75.7% OOS", v2 already had both;
  (b) SWING TRADE LOG headers had backtested win rates REMOVED per user (that tab shows the LIVE
  book; backtest stats live on PM DECISIONS / STUDIES). Both in `engine/ui_terminal.py`, viewer
  restarted. IS numbers sourced from studies (STOCK_V1_OOS.md, STOCK_FADE_TP50_UPGRADE.md,
  monthly_fut/MONTHLY_FUTURES.md:75-76).
- **Running (background):** `studies/ndte/stkfade_v2_side_decay.py` — v2 UNION CE-vs-PE side
  split + holding-period decay curve (answers "any chance of v2 CALL / is it front-loaded").
  Slow (uncached option histories). Output `/tmp/v2side_run.log`, json `/tmp/stkfade_v2_side.json`.
  NOT yet reported to user.
- **Live check 2026-07-13 13:26 IST (market open):** v2 UNION read-only scan = 7 breakouts,
  ALL blocked by credit/width<0.40 (best OFSS D5 bear-call 0.35). No signal cleared gates
  pre-15:10 scan. Replica pattern in the inline python (import `_todays_breakout`/`_pick_legs`/
  `_quote` from `engine.stock_credit_v2`; NEVER call `scan_signals()` — it writes).
- **Not started:** SENSEX/BANKNIFTY 0DTE entry-time confirmation sweep (same mechanism
  expected); multi-day/overnight goal-loop (awaiting user opt-in).

## Next steps
1. Nothing pending without user input. If user opts into overnight/multi-day: start from the
   shelved daily-ladder result in `studies/DAILY_HIGHWIN_SEARCH.md` (81.2% win, +9.06%m,
   REPORT-ONLY, correlated-stacking risk) and the swing fade book.
2. If asked to commit: `studies/ZERO_DTE_ENTRY_TIME.md`, `studies/NONFADE_INTRADAY_SEARCH.md`,
   `studies/ndte/ndte11_entrytime.py`, `studies/ndte/ndte12_longgamma.py` are untracked.
   NEVER commit `.env` (verify `git diff --cached --name-only | grep -q "\.env$"` is empty).

## Key files
| File | Why it matters |
|---|---|
| `CLAUDE.md` | canonical repo context — read first; strategy status + honesty rules |
| `studies/ZERO_DTE_ENTRY_TIME.md` | new: entry-time sweep verdict (keep 09:16) |
| `studies/NONFADE_INTRADAY_SEARCH.md` | new: long-gamma falsification + intraday search ledger |
| `studies/ndte/ndte11_entrytime.py` | entry-time harness (pooled cached fetchers `intra`, `spot5m`) |
| `studies/ndte/ndte12_longgamma.py` | straddle/gap/trend debit backtests, both eras |
| `engine/stock_credit_v2.py` | UNION_DCS=(5,10,15,20) scanner; gate sequence ~lines 154-232 |
| `engine/config.py` lines 246-282 | STOCK_CREDIT_* and ZERO_DTE_* tunables (unchanged) |
| `/tmp/ndte_intra/`, `/tmp/ndte_spot5m/`, `/tmp/ndte_bhav/`, `/tmp/ndte_cache/` | data caches (1-min option, 5-min spot, bhavcopy, daily spot); /tmp may be wiped — scripts refetch |

## Decisions & gotchas
- Entry-time sweep is single-regime evidence: 1-min premiums exist only Oct'24→; 2019-24 bhav
  has OPEN prints only, so later-entry variants cannot be validated pre-Oct'24.
- `ndte11_entrytime.intra()` caches EMPTY candle results too (ndte7's version didn't — far
  wings that never traded caused ~90s retry stalls; ndte7-style runs crawl without this).
- Upstox v3 `historical-candle/{key}/minutes/5/…` serves NIFTY INDEX 5-min back past Oct'24 —
  this unlocked spot-at-entry-time strike selection.
- Long-gamma IS cells can show positive avg% with negative total ₹ (small-debit trades win big
  %) — judge on total ₹ + OOS, not avg%.
- Do NOT re-mine (all falsified): intraday underlying direction, high-win exit geometry,
  pairs, non-expiry same-day selling, expiry-day long gamma. Ledger in
  `studies/NONFADE_INTRADAY_SEARCH.md`.
- v2 UNION gate check can be replicated read-only by importing `_todays_breakout`, `_pick_legs`,
  `_quote` from `engine.stock_credit_v2` — never call `scan_signals()` outside the engine (it
  WRITES the paper book). `_quote` returns a 4-tuple (mid, bid, ask, oi).
- Engine + viewer run via launchd. Restart engine after engine-code changes:
  `launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`.

## How to resume
Read `CLAUDE.md`, then the two new studies above. No unfinished code work; the loops concluded
with report-only verdicts. Health: `pgrep -f engine.engine_runner`;
`.venv/bin/python -c "from engine import store; print(store.stats())"`. Backtests:
`.venv/bin/python studies/ndte/ndte11_entrytime.py` (or `ndte12_longgamma.py`) — needs
`UPSTOX_ANALYTICS_TOKEN` in `.env`; /tmp caches rebuild automatically.
