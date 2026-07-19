# Handoff — institutional-trader
_Updated: 2026-07-19 by Claude Code_

## DONE (2026-07-19) — D5/D10/D15/D20 standalone Donchian validation, 2019→date (commit c423ac8, pushed origin+private)
Question: is a stricter/longer Donchian window (D10/15/20) more DURABLE than the deployed UNION (≡D5)?
Ran each window STANDALONE (own breakout stream + own re-entry gap, NOT the union), deployed v2 config
(short 2-OTM, w4, TP-50, stop-3x, c/w>=0.40, prem>=50, min-DTE10, reentry3d), two eras stitched:
- 2019→Sep'24 NSE bhavcopy (re-downloaded /tmp/bhav_cache_stk via NEW studies/ndte/bhav_dl_stk_opt.py,
  1359 days, OHLC+OI). Backtest studies/ndte/stkfade_d5_10_15_20_bhav.py.
- Oct'24→date real Upstox premiums. studies/ndte/stkfade_d5_10_15_20_oct24.py (stkfade_d5_vs_d10 engine, 4 configs).
VERDICT = **NO, longer is NOT more durable.** Combined: D5 85.4%/+29.1%w/6.3mo · D10 86.3%/+29.0%w/4.6mo ·
D15 85.4%/+27.2%w/3.8mo · D20 83.4%/+26.2%w/3.3mo. Win PEAKS at D10 then falls; net/trade declines past
D10; total edge/mo (freq×net) D5 1.83 > D10 1.33 > D15 1.03 > D20 0.86 — D5's frequency wins. All four +ve
every year 2019-26; the c/w>=0.40 GATE is the durable edge, not the window. REPORT-ONLY, engine unchanged.
GOTCHA I hit: first bhav pass used a daily-OHLC-low TP proxy (short.LOW-long.HIGH) → inflated win to 97-98%,
contradicted documented 85.35%. FIXED to close-only detection (matches documented v2 pipeline + Oct'24 era);
D10 bhav then reproduced documented 273/85.3% exactly. Use close-only for cross-era comparability.
Cross-checks passed: Oct'24 D5 200/87.5% ≡ known 203/87.2%; bhav D10 273/85.3% ≡ documented 273/85.35%.
Deliverables (all committed+pushed BOTH remotes): studies/DONCHIAN_5_10_15_20.md, the 3 scripts above,
STUDIES-tab res() card in engine/ui_terminal.py (viewer relaunched, PID stable — verified no crash).

## DONE (2026-07-13 latest) — SHELVED the monthly long-call book as UNRELIABLE
12-mo ledger exposed it: +Rs63,815/65% win BUT one POLYCAB trade (+Rs47k from a real +8.2% ONE-DAY
GAP, not a +2% edge) = 3/4 of the profit; ex-POLYCAB = +Rs16.5k/40 trades ≈ noise. The "+2% TP"
doesn't cap wins — it rides gap-throughs to the day's close, so profit is luck/gap-dependent.
User: "remove the 5 option for now, document in studies UI + github." → MONTHLY_CALL_ENABLED=False,
PM DECISIONS section hidden when disabled, STUDIES writeup marked SHELVED w/ the gap finding,
MAX_TRADES_OPTIONS.md updated. Code kept (engine/monthly_call.py) but dormant. Ledger scripts +
call_ledger_6mo/12mo.csv committed. Reliable core stays the defined-risk spreads (86% win).

## Q (2026-07-13) — user wants trade-by-trade last-6-mo long-call example, 1 lot each, running P&L
Building from OOS trade data (opt_oos_trades.csv had returns but not strikes/lots/₹ — need a
script that emits per-trade: date, sym, strike, entry prem, exit prem, lot size, ₹ P&L, cumulative).
Live book has 0 real trades yet (fires next cycle), so this is the BACKTEST trades = the honest
"what it would have done." Script: studies/monthly_fut/opt_trade_ledger.py (to build).

## DONE (2026-07-13) — MONTHLY LONG-CALL book DEPLOYED as 6th paper book (user-approved)
Wired engine/monthly_call.py: same REV1-v2 pullback signal, BUY ATM call, trigger on underlying
+2%/-5%, P&L on premium. Simple 5-pick (OOS-validated 67% win /+6-7%/mo); 8-pick+gates NOT used
(failed OOS). Config MONTHLY_CALL_ENABLED, runner _monthly_call hook, PM DECISIONS section +
STUDIES writeup in ui_terminal.py. Engine+viewer restarted, committed+pushed. First signals fire
next cycle where NIFTY>200DMA (this cycle already <20DTE + REGIME_OFF). HIGH VARIANCE (-51% crash
mo). Profit expectation: ~6-7%/mo on premium deployed, ~5 trades/mo, but highly variable.

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

## NEXT FEATURE TO BUILD (user-requested 2026-07-14, deferred to a fresh session — live-engine
surgery, not safe at the deep context where it was asked). UNION WATCHLIST on PM DECISIONS:

Goal: an always-on watchlist proving the engine ran, showing every strategy breakout stepping
through the UNION gates with a tick-bar — so a quiet day is visibly "engine ran, 0 passed," not
a dead screen.

ENGINE (`engine/stock_credit_v2.py::scan_signals`): as it walks UNIVERSE, append EVERY breakout
(before the `continue`s) to a list: `{symbol, dir, dc, side, cw, prem, spread, oi,
gate: "BREAKOUT"|"G1_CW"|"G2_PREM"|"G3_LIQ"|"PASS"}` where `gate` = the first gate it FAILED
(or PASS). At the end write `data/union_watchlist.json` = `{ts: now, scanned: N, passed: M,
rows: [...]}` EVERY scan, even when empty. IMPORTANT: additive only — do NOT alter the existing
signal-writing/gate logic; just record alongside it. The write itself is the engine-ran proof.
Guard the whole thing in try/except so a watchlist error can never disturb the scan.

UI (`engine/ui_terminal.py::_screen_pm` + a refresh hook): a new always-visible panel at the TOP
of PM DECISIONS titled "UNION WATCHLIST — engine heartbeat". Header line: "last scan HH:MM · N
breakouts · M passed" (read ts from the json; if ts>20min old during market hours, colour it RED
= engine may be stuck). One row per breakout with a tick-bar across columns:
Breakout ✓ | Credit/Width (✓ if cw>=0.40 else ✗ show cw) | Premium (✓ if>=50 else ✗) |
Liquidity (✓/✗) | → SIGNAL/blocked-at. Empty state: "engine ran HH:MM — 0 breakouts today".
Sort blocked-closest-first (highest cw on top). This REPLACES the old dead 3-Family WATCHLIST
concept (that tab was removed; _screen_watchlist still exists but isn't in the tab list).
After edits: restart engine (`launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`)
AND viewer (kill main.py + kickstart). VERIFY by launching the viewer (ast.parse is NOT enough —
it missed a NameError crash this session; only a real launch + stable-PID check confirms render).

## NEXT: v2 UNION TWO-TIER SPLIT (0.35-0.40 secondary + ≥0.40 core) — user-requested 2026-07-15,
DEFERRED (live deployment; do fresh, not at 600k+ tokens). Basis: studies/CW_BUCKET_ANALYSIS.md —
0.35-0.40 nets +9.2%w (82% win, +ve all 3 yrs) vs ≥0.40 +31.7%w; 0.30-0.35 is breakeven (skip).

**CRITICAL CAVEAT before deploying:** SINGLE REGIME (Oct'24→now only). NOT validated 2019-24
(bhavcopy purged). Repo's index-fade failure = single-regime edge that died OOS. So: (a) ideally
run the 2019-24 bhavcopy c/w-bucket backtest FIRST (needs re-download via studies/ndte/bhav_dl_stk.py
+ a new bhav bucket script); (b) if user still wants it live, deploy 0.35-0.40 as a SEPARATE tier,
1 lot, tracked apart — NEVER merge into the ≥0.40 book's stats.

ENGINE (`engine/stock_credit_v2.py`): add `STOCK_CREDIT_MIN_CW_SECONDARY=0.35` to config. In
scan_signals, a breakout with 0.35≤c/w<0.40 (+ all other gates) opens a SECONDARY position tagged
`tier:"0.35-0.40"` into a SEPARATE book file (e.g. stock_credit_v2b_positions.json) so core stats
stay clean; ≥0.40 stays the primary book unchanged. Telegram _tg for secondary must say "SECONDARY
tier — unvalidated OOS, 1 lot".

UI (`engine/ui_terminal.py::_screen_pm`): the STOCK CREDIT v2 UNION section becomes TWO labelled
sub-sections in the existing PM_CREDIT_COLS table format: "★ v2 UNION ≥0.40 (CORE)" and
"v2 UNION 0.35-0.40 (SECONDARY · 1 lot · unproven)". The watchlist 🔥 flag already marks c/w≥0.35.

User intent: will manually take 1 lot in the 0.35-0.40 range. Recommendation given: promising not
proven, keep tiers separate, validate 2019-24 first, 1 lot is right sizing.

## TELEGRAM v2 (2026-07-16, commit c765839) — SHIPPED
- Standard signal format (`engine_runner._tg`): both legs WITH premiums, backtested win% per
  book (`_TG_WIN` map), max profit/lot + max loss/lot, footer "Execute with your broker" (group
  members are not all on Upstox — never say "place in Upstox" in Telegram).
- `dte_multi.scan_signals()` now returns position dicts (was a count) so SENSEX/BANKNIFTY 0DTE
  alerts carry full legs; call site uses len().
- `engine_runner._outcomes()`: every ~60s, watches the 6 book files for status→WIN/LOSS and
  Telegrams the result quoting the ENTRY-DATE call + P&L (pnl_pts × qty). Notified ids persist
  in data/outcome_notified.json — SEEDED SILENTLY on first run (9 ids) so history never floods.
- 3-Family is DISABLED (SCAN_3FAMILY_ENABLED=False) and rejected — its Telegram path is dormant
  dead wiring; optional cleanup only.
- Watchlist json is written ONLY by the 15:05 engine build; ad-hoc "check now" runs must NOT
  overwrite data/union_watchlist.json (user wants the UI to reflect the official 15:05 scan only).
- Watchlist sort (2026-07-17, aa3c5bd): PASS first → most gates cleared → richest c/w. A
  prem+liq-clean near-miss outranks a fatter c/w that fails premium. Results Telegram fires
  same-cycle as settlement (~15:35, a1251c3); 0DTE signals are per-index labels (75bffcf).
