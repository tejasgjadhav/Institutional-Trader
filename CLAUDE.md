# CLAUDE.md — Institutional Trader (project context for Claude Code)

Read this first. It is the canonical context for working on this repo. Add task-specific
instructions on top of it.

## What this is

A **paper-trading** algo system for NSE (Indian market) intraday **options**. It scans
NIFTY, BANKNIFTY and ~100 liquid stocks every 5 minutes, scores each with a 3-family model,
and surfaces buy-option signals on a dashboard. **It never places orders** — the user places
them manually in Upstox. Status: a forward paper-test of a thin, ~52–61% directional,
roughly-breakeven-after-costs edge. **Not proven profitable.** Be honest about this always.

## CURRENT LIVE BOOKS (2026-07-21) — read this before the strategy sections below

The strategy prose further down is **historical narrative** and describes several things that are now
OFF (3-Family `SCAN_3FAMILY_ENABLED=False`, ORB+VWAP `ORB_VWAP_ENABLED=False`, monthly-call shelved).
**This table is the deployed reality.** All are paper/signals-only at 1 lot.

| Book | Flag | Win | ₹/mo @1 lot | Evidence strength |
|---|---|---|---|---|
| ★ Stock fade v2 UNION (TP-50) | `STOCK_CREDIT_ENABLED` | 82.2% IS / 82.8% OOS | ₹8,198 (2.6/mo × ₹3,180) | IS +30.7% ROM, +ve 6/6 yrs (n=667); OOS +3.7%, 2/3 yrs (n=58, CI spans zero) |
| Stock credit v1 (TP-40/no-stop, D10 only) | `STOCK_CREDIT_ENABLED` | 79.9% IS / 79.8% OOS | ₹8,711 (8.6/mo × ₹1,016) | IS +19.9% ROM, +ve 6/6 yrs (n=477); OOS +4.8%, **3/3 yrs** (n=193) — the best-measured stock book |
| Stock credit **v0** (c/w 0.35–0.40, v1 wins same-stock clash) | `STOCK_CREDIT_V0_ENABLED` | 83.1% IS / 80.4% OOS | ₹1,443 (4.3/mo × ₹335) | IS +17.8% ROM, +ve 6/6 yrs (n=569); OOS **−0.7%**, 2/3 yrs (n=97). Kept live as a paper forward-test, user 2026-08-15 |
| 0DTE SENSEX | `dte_multi` BOOKS | 89.0% | ₹3,153 | measured · 3 yrs only |
| 0DTE NIFTY (FLIP) (+hybrid add 07-31) | `ZERO_DTE_ENABLED` | 88.3% | ₹1,771 | t=+4.43 · +ve 7/8 yrs |
| ~~0DTE BANKNIFTY~~ | `DTE_MULTI_BANKNIFTY_ENABLED=False` | 78.6% | — | **REJECTED 07-19** · t=+0.10, CI spans 0 |
| Index swing fade | `SWING_CREDIT_ENABLED` | 54% | ~₹0 | regime-dep · failed OOS |
| Monthly futures | `MONTHLY_FUT_ENABLED` | 75.7% | ₹0 now | REGIME-OFF · needs ~₹15L |

**THE NUMBERS ABOVE ARE THE 16-AUG-2026 PRODUCTION HARNESS** (`studies/ndte/deployed_backtest.py`),
after four corrections that each changed the answer materially: option legs joined BY DATE, v1 given
its real Donchian-10 population, spot derived from the option chain by put-call parity (split-adjusted
closes against unadjusted strike ladders had been fabricating deep-ITM trades and printing +182.8%
ROM), and the live one-position-per-symbol rule applied (59% of in-sample trades were re-entries the
engine could never have taken). Every earlier figure in this repo predates at least one of those and
must not be quoted. Read on the MEDIAN COHORT, c/w 0.40–0.50, where all 21 real live fills sit.

**What the two windows can and cannot say.** In-sample is far better measured — 667/477/569 trades,
six full years, all three books positive in every year — but it is NOT independent, because the c/w
gate, the geometry and the exits were all chosen on that data. Out-of-sample is honest but thin:
bootstrapped 90% ROM intervals are v2 [−27.8%, +39.7%], v1 [−5.0%, +13.3%], v0 [−14.8%, +12.5%], all
spanning zero, and v2's 58 trades include a four-trade 2024 stub. **The out-of-sample window cannot
rank the books.** Stock books total about ₹18,350/mo at 1 lot; with the index books ~₹24,200, and the
80% planning rule puts it at ~₹19,300. **Keep lots at 1.** The forward record, restarted 6-Aug-2026,
is the only instrument that settles this.

**Take-profit is settled — do NOT re-tune it.** Swept 30/40/50/60/70 on both windows (`tp_sweep.py`):
v2 is flat across the whole range, and v1's slope INVERTS between windows (lower is better in-sample,
higher is better out-of-sample), which is what a parameter carrying no information looks like.
Deployed levels stay: v2 TP-50, v1 TP-40, v0 TP-40.

**Structural exclusions deployed 2026-07-19** (risk limits, NOT edges):
`ZERO_DTE_MULTI_MIN_CW=0.04` (SENSEX/BNF; NIFTY unchanged) and `ZERO_DTE_ELECTION_BLACKOUT`.
⚠ **The blackout is a HAND-MAINTAINED list with NO news engine behind it and currently holds only past
dates, so it cannot fire.** Nothing fetches election/policy dates at runtime — `engine/events.py`
scrapes NSE *corporate* news for STOCK scoring only; `studies/ndte/event_calendar.json` is research
data the engine never reads. The engine logs a once-daily WARNING while the list has no future dates.

**Settled question — do NOT re-mine:** event/news avoidance for 0DTE. RBI/Budget/FOMC, overnight gap,
India VIX (level *and* spike), heavyweight earnings, and geopolitical shocks were **all tested and all
cost money** (448 expiries, 2019→Jul'26). Mechanism: this is a short-vol book that is **paid for
visible fear**, so filters keying on ex-ante-visible stress remove exactly the trades where the market
overpays. Shock-day expiries went 7/7. See `studies/README.md` for the index and the 6 house rules.

## Architecture — two processes (decoupled)

| | Headless **ENGINE** (`engine/engine_runner.py`) | Desktop **VIEWER** (`main.py` → `engine/ui_terminal.py`) |
|---|---|---|
| launchd job | `com.sayali.institutionaltrader.engine` (KeepAlive, always on) | `com.sayali.institutionaltrader` (auto-launch 9:00 weekdays) |
| Role | scan · fire signals · resolve paper trades · 15:30 EOD-book · save all data | **read-only** display |
| Cadence | wakes every **5 s** in market hours; scans every 5 min; idles (5-min sleep) when closed | re-reads disk every 15 s |
| Writes | `engine.db`, `signals.db`, `trade_log.json`, `latest_scan.json`, `market_snapshot.json` | **nothing** |

The engine runs the full schedule **whether or not the viewer is open**. The viewer only
reads what the engine wrote, so a viewer crash can never stop trading. Do not put trading
logic in the GUI — it belongs in the engine.

## Setup from a fresh clone (macOS, Apple Silicon)

```bash
git clone <repo-url> institutional-trader && cd institutional-trader
./setup.sh                 # venv + deps + .env template + launchd jobs (engine starts)
# then edit .env, add UPSTOX_ANALYTICS_TOKEN, and:
launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine
.venv/bin/python main.py   # open the read-only viewer (or it auto-launches 9:00 weekdays)
```

`setup.sh` generates the launchd plists with the clone's absolute path, so it works from any
location. Reference plists are in `deploy/`. Requires Python 3.9+, a free Upstox **Analytics**
token (read-only data feed — no trading token needed).

## Strategy (what the gates do)

**3-Family stocks** → alpha-z (TREND 0.72 + FLOW 0.18 + EVENT 0.10), then the gates:
1. **Alpha** — |alpha-z| > 0.55 AND ≥2/3 families agree.
2. **ORB** — latest 5-min candle breaks the opening range with a volume surge.
3. **Market alignment** — only LONG when Nifty up / SHORT when Nifty down (`MARKET_ALIGN_FILTER`). Robust out-of-sample.
4. **Don't chase** (extension) — **DISABLED 2026-06**: didn't hold on the real-option 180d test.
5. **Wide open** (ORB-width) — **DISABLED 2026-06**: same.
5b. **Min option premium** — only trade when the OTM+1 option ≥ `MIN_OPTION_PREMIUM` (₹30) (`MIN_OPTION_PREMIUM_FILTER`). **The real edge** from the 180d backtest: cheap lottery options (avg ₹38) bleed out; richer ones (avg ₹101) follow through AND have ~3× smaller spread.
6. **Liquidity** — OTM+1 option needs a live two-sided market: spread ≤ `MAX_OPTION_SPREAD_PCT` (4%), OI ≥ `MIN_OPTION_OI` (100). Checked with 5b after gates 1-3 pass. Fails open on a quote error.
All pass → buy OTM+1 CALL/PUT, exit **+10% / −15%** on premium (−15 stop drops breakeven win 67%→60%).

**ORB+VWAP index** (NIFTY/BANKNIFTY, parallel) → 15-min ORB + VWAP + 30-min trend + clean-trend
filter → buy ATM, **trend-ride exit** (exit on VWAP reclaim after +12%, hard **−15%** stop).

**Swing credit spread** (NIFTY/FINNIFTY, the 3rd strategy, multi-day) → daily **Donchian-10**
breakout → **SELL a credit spread AGAINST it** (fade: up-break → bear-call, down-break → bull-put),
mid-tenor (≥10 DTE), short 1-OTM, width 3, **hold to expiry**, hard stop at 2× credit. (A directional
+ flush gate was tried 2026-07 to lift it above +15% but FAILED out-of-sample — reverted; the fade
runs ungated. `SWING_FADE_DOWN_ONLY`/`SWING_MIN_BREAKOUT_PCT` exist but default OFF. See Part 11.) Overnight
carry — NOT squared at 15:30. Signals-only paper forward-test (`engine/swing_credit.py`,
`config.SWING_*`); its own **SWING CREDIT SPREADS** section on PM DECISIONS between stocks and index.
The one validated edge — robust across 5 breakout defs (D10/15/20/30/prior-week) AND across NIFTY+FINNIFTY (BANKNIFTY dropped: tested −6.7%). HIGH variance; still forward-test.

**Stock credit spread** (the 4th strategy, high-FREQUENCY ~16/mo) → same fade, on the full ~100-stock
universe, but GATED: credit/width ≥ 0.40 (rich premium = elevated post-breakout IV — the edge) +
short premium ≥ ₹50 + live liquidity gate (OI, bid-ask) + per-day/total-open caps. Backtest 65% win,
+16–25% net/trade, holdout p5 +6.8%, 76/100 stocks. The credit/width gate is essential — a *generic*
stock spread LOSES (−4.7%, the 4-leg slippage wall). **REAL-DATA CONFIRMED (2026-07, NSE bhavcopy
2019→Sep2024, 718 trades): gated = +5.3% of width (≈+9%/trade on margin), 54% win, positive 5 of 6
years — the ONE durable, regime-robust edge. Strip the gate and it loses (−1.1%, like everything
else). But the real edge is ~⅓–½ of the optimistic backtest (+16–25% → +5.3% of width; 65% → 54% win)
— the backtest IS optimistic as warned. Keep lots at 1.** See `STOCK_OPTIONS_NO_EDGE.md` Part 10. Signals-only paper forward-test
(`engine/stock_credit.py`, `config.STOCK_CREDIT_*`); own STOCK CREDIT SPREADS PM + trade-log section.
**Backtest is OPTIMISTIC (~20%/mo on margin won't fully survive live mid-cap fills) — KEEP LOTS AT 1.**

**REAL option data (expired-instruments / Upstox Plus) — honest standing after the 1-year test:**
- **STOCKS: no proven durable edge.** The min-premium config looked like +1.5% (64% win) on a
  180-day window but came in at **−1.0% (55% win) over a full year** — overfit to a recent
  regime. Min-premium is kept only for the *spread/cost* benefit (richer options, ~3× tighter
  spread), NOT as a profit edge. Treat stocks as a paper forward-test, not a money-maker.
- **INDEX: thin but durable edge.** Trend-ride (−15 stop) ran **+0.9% over 18 months (453 trades),
  positive on both train and test.** The one real (small) edge.
- **BUY strategies tested to 2019 on real Kite 5-min (2026-07, `studies/BUY_STRATEGIES_2019_REALTEST.md`).**
  Zerodha Kite historical gives 5-min UNDERLYING back to 2019 (intraday option premiums still don't
  exist historically, so this measures the underlying DIRECTION edge). **3-Family FULL-GATE** (real
  `compute_all_families` + `is_orb_confirmed`: alpha-z + volume-surge ORB + alignment), 19,454 signals:
  **50.6% hit, +0.107%/trade, POSITIVE EVERY year 2019→2026** — the gates are real (a no-gate proxy is
  a 48% coin flip), a fairer verdict than "overfit". BUT direction ≠ profit: net of option-buying costs
  the real-option year was −1.0%. **ORB+VWAP**: 2,303 signals, +0.04%/trade, negative ~2/8 yrs per index
  — thin & inconsistent. Neither survives option-buying costs NET; both stay paper forward-tests.
- **STOCK multi-day credit spreads: rejected on real cost.** Sell-premium/theta-harvest looked
  like +6.9% holdout on an *estimated* cost, but **real per-leg cost (₹1,137/trade, 4 legs) flipped
  it to −4.7% net, PF 0.87.** Dead. See `studies/STOCK_OPTIONS_NO_EDGE.md` Part 4.
- **INDEX fade credit spread: VALIDATED & deployed (the 3rd strategy).** Selling a credit spread
  *against* a daily index breakout (theta + tightest bid-ask + trades with the reversion) clears
  measured costs: **+12–20% net/trade (live geometry), PF 1.4–1.95, survives 2× cost**. **Robust
  across 5 breakout definitions** (D10/15/20/30 + prior-week — genuine reversion, not a D10 fit).
  **HIGH variance** (wins ~+40–60% of margin, losses ~−100%; thin-holdout bootstrap p5 negative —
  positive EV but a bad draw can lose). At 1 lot: **~₹1–2k/month** (margin ~₹6–7k/trade).
  **Lineup = NIFTY + FINNIFTY** (a 5-index robustness test DROPPED BANKNIFTY: −6.7% on 40 trades,
  its earlier +13% was 14-trade luck; MIDCPNIFTY REJECTED on real bhavcopy 2022→Sep24: ~20% win,
  −25 to −28% of width, illiquid, options only from mid-2022 so can't test from 2019). Runs as a parallel paper
  FORWARD-TEST in `engine/swing_credit.py` (`SWING_LOTS` sizes it; keep at 1). See Parts 5–7. NOTE:
  the *follow* version (with the breakout) loses (40% win); the edge is specifically the **fade**.
  (An earlier +4%/p5+2.3% figure was a width-bookkeeping bug — now fixed; the live engine was always correct.)
  **REAL-DATA CAVEAT (2026-07, NSE bhavcopy 2019→Sep2024, cleaned): NIFTY index fade is net-NEGATIVE
  out-of-time (−1.4% of width, 181 trades), positive only in 2019 & 2024 — the favorable regimes.
  The Oct'24–Jun'26 "+12%" landed on a good regime, NOT a durable edge.** See Part 10.
  **SALVAGE ATTEMPT — TRIED AND REJECTED (2026-07): a winner/loser analysis on bhavcopy 2019→Sep24
  suggested two gates (fade DOWN-breaks only + flush ≥0.5%) giving +15.1%/78% win, positive all 6
  years, boot p5 +4.1%. It FAILED out-of-sample: on real Upstox premiums Oct24→date the direction
  asymmetry REVERSED (there CE won +7.8%, PE lost −8.7%) and the deployed gate came in −2.8%
  (FINNIFTY −17.7%). The asymmetry was a 2019–24 bull-regime artifact, not structural. Gates
  REVERTED to neutral (`SWING_FADE_DOWN_ONLY=False`, `SWING_MIN_BREAKOUT_PCT=0.0`). Index fade stays
  regime-dependent / unproven. Lesson: 6 positive years in ONE regime ≠ out-of-sample.** See Part 11.
- Lesson: a train/test split *inside a short window* is not true out-of-sample; use the longest
  window the data allows. See `studies/REAL_OPTION_OPTIMIZATION.md` (CORRECTION at the top).
Old gates 4/5 are OFF tunables; everything is GROSS of costs.
The universe is the hand-picked ~100 (mostly mid/large-cap movers) — NOT ranked by market cap:
a head-to-head showed a free-float-mcap top-100 *lost* to it (61% vs 67% on the same window),
because mega-caps don't break out. Select by intraday movement, not size — see
`studies/UNIVERSE_94_VS_100_HEADTOHEAD.md`.

**Priority stocks (`config.PRIORITY_STOCKS`, 13 names):** the only stocks whose gates-1-5 win
rate persisted out-of-sample (train→test, ~75%/110 trades). Per-stock win-rate selection
overfits (top-60 by win rate: 64% train → 49% test), so the universe stays broad at 100 and the
engine fires on all of them; these 13 are just **★-flagged in the read-only UI** as a focus tilt
— they do NOT change engine selection or the overall win rate. See `studies/PRIORITY_STOCKS_PERSISTENCE.md`.

## Key files

```
engine/engine_runner.py   HEADLESS ENGINE daemon — the schedule + all writes
engine/store.py           data/engine.db — daily scan rows + market snapshots
engine/agent.py           run_scan orchestrator (3-Family + ORB+VWAP), execute_signals
engine/signals.py         3-family scoring + alpha-z + ORB gate
engine/orb_vwap_live.py   index ORB+VWAP strategy (trend-ride exit)
engine/swing_credit.py    SWING credit-spread strategy (multi-day · fade · book in data/swing_positions.json)
engine/paper_resolver.py  closes PENDING paper trades on the option premium
engine/options.py         strike resolver + live option order builder
engine/signal_db.py       SQLite log of every PM signal
engine/trade_log.py       paper log: win rate, PF, expectancy
engine/data_utils.py      market snapshot (batched LTP + fallbacks)
engine/config.py          ALL tunables (gates, exits, universe, paths)
engine/ui_terminal.py     READ-ONLY viewer (tabs: PM / WATCHLIST / ALPHA / TRADE LOG / STUDIES / README)
main.py                   viewer launcher
deploy/                   launchd plists (engine + viewer)
studies/                  research log (9 .md studies) + reproducible scripts
data/                     engine.db / signals.db / trade_log.json (gitignored runtime data)
```

## Operating conventions (follow these)

- **RESULTS → STUDIES → UI → GITHUB (standing rule, user 2026-07-31):** whenever new trading
  results land (a backtest completes, a paper trade resolves into a meaningful sample, a book's
  measured stats change), update the STUDIES tab + README tables in `engine/ui_terminal.py` in the
  SAME format as the existing cards/tables, restart the viewer, and commit+push BOTH remotes
  (`origin` = Institutional-Trader public, `private` = Institutional-Trader-private-). Never leave
  the UI or the repos behind the studies/ files.

- **NSE SESSION, since 3-Aug-2026 (do not re-derive this):** equity **derivatives close 15:40**
  (not 15:30). **F&O stocks** stop continuous cash trading at **15:15**, run a **Closing Auction
  Session 15:15–15:35**, and their official close is the **auction equilibrium price**. Every name in
  `UNIVERSE` is an F&O stock. The engine has ONE session model in `config.py` — `CASH_CLOSE` 15:30,
  `CAS_END` 15:35, `FNO_CLOSE` 15:40, **`SETTLE_AFTER` 15:40** — and every settle site reads it; do
  not reintroduce a bare time literal (there were seven). Schedule: watchlist+digest **15:17**, scans
  **15:36**, place 15:36–15:40, EOD 15:40. Settlement takes the **official close first**, live spot
  only as fallback. **Backtests before 3-Aug-2026 use 15:00–15:30 VWAP closes; after, auction
  equilibrium prices — not the same construct.** See `studies/NSE_SESSION_CHANGE_2026_08_03.md`.

- **CHECK THE STUDIES FIRST (standing rule, user 2026-08-01):** before running ANY backtest, search
  `studies/` for whether the question has already been answered, and say so. This repo has 56+ written
  studies and 100+ runnable scripts; several questions have been asked and settled more than once.
  Practical steps: `ls studies/*.md`, grep the topic across `studies/`, and read `studies/README.md`
  (the index + the house rules). If a study already covers it, quote its numbers and its verdict and
  ask whether a re-run is actually wanted — do not silently re-spend hours of API-throttled compute.
  If it is covered only PARTLY, say exactly which part is missing and test only that. Settled
  questions are marked in this file and in `studies/README.md` — e.g. event/news avoidance for 0DTE
  is closed and must NOT be re-mined.

- **SECURITY:** `.env` holds the Upstox token + notification keys. It is **gitignored and must
  NEVER be committed/pushed.** Before every commit verify: `git diff --cached --name-only | grep -q "\.env$"` returns nothing.
- **Restart after engine/UI code changes** (launchd does not hot-reload):
  - engine: `launchctl kickstart -k gui/$(id -u)/com.sayali.institutionaltrader.engine`
  - viewer: `kill -9 $(pgrep -f main.py); sleep 3; launchctl kickstart gui/$(id -u)/com.sayali.institutionaltrader`
  - (plain `kickstart -k` does NOT restart a detached GUI process — kill it first.)
- **Backtest before deploy.** Never change a live tunable on a hunch. Run the 30/60-day option
  backtest (and the 365-day underlying study for direction) and show the numbers first. Several
  "good-looking" ideas (time-of-day filter, removing the +10% cap, index gates) were tested and
  correctly **not** deployed.
- **Data limits:** real option-premium history is only ~1 month back; index futures ~33 days.
  Daily price = 2+ yrs, 5-min price = ~1 yr. Long backtests must use the underlying proxy or a
  paid vendor — see `studies/DATA_AVAILABILITY_LIMITS.md`.
- **DEPLOYMENT FREEZE IN THE SIGNAL WINDOW (standing rule, user 2026-08-07).** On trading days, do
  NOT deploy code/config or restart the engine between **15:15 and 15:40** (auction start to
  derivatives close) unless fixing an active failure the user knows about. Mechanism: the engine's
  once-a-day markers (watchlist built, digest sent, scan done) are IN-MEMORY, so a mid-window
  restart resets them and RE-RUNS the daily scans under whatever was just deployed — a late or
  wrong signal then lands in the trade log after the close, when nothing can be done about it.
  Deploy after 15:40 or before 09:00. The 7-Aug v0-rule deploy at 15:44 was safe by four minutes,
  not by design — hence this rule. Restarting after 15:40 is safe (scans are market-hours gated).

- **A BUG CHECK IS FOUR LAYERS, NOT CODE REVIEW (standing rule, user 2026-08-06).** Born from the
  stale-bar incident: repeated code sweeps missed that the Upstox daily endpoint publishes NO
  current-day bar during the session, so `df["Close"].iloc[-1]` — correct-looking code — silently
  traded the PREVIOUS day's breakout for weeks (all 19 booked positions reconstructed as T-1). The
  decisive evidence was even recorded ("18:15, no same-day data") and not connected. Therefore,
  when asked to "check for bugs", ALL FOUR, every time:
  1. **DATA** — verify what each external source actually returns AT THE MOMENT the code reads it
     (a check after hours saw the bar present and wrongly cleared the feed);
  2. **TIME** — run the check at the real decision times (15:31/15:36 here), not whenever convenient;
  3. **INVARIANTS** — prefer runtime guards that refuse to act and log loudly (freshness guard,
     direction-vs-move audit) plus permanent instrumentation (session observer) over more review —
     review finds code bugs, only runtime observation finds data bugs;
  4. **UI** — surface the inputs a decision used next to live values (SIGNAL→LIVE), so a wrong input
     is visible to the user rather than silent; his instinct, not a sweep, caught GRASIM.
  Reporting: state which layers were checked; a code-only sweep is never reported as "no bugs".

- **RESEARCH SCRIPTS ARE PRODUCTION CODE (standing rule, user 2026-08-14).** Born from the
  leg-misalignment incident: every Upstox OOS validation of v2/v1/v0 paired the two option legs
  BY POSITION (`sp[k]-lp[k]`) instead of by DATE. Illiquid stock options skip days, so ~47% of
  multi-leg windows compared prices from different calendar days. The bug survived dozens of runs
  and many recorded studies because (1) it crashes nothing and prints plausible numbers, (2) each
  new study copy-pasted the same harness, so "cross-checks" were the same bug agreeing with
  itself, (3) the four-layer bug check was only ever applied to the ENGINE, never to studies/,
  and (4) re-running a bugged test reproduces the bug — only an adversarial audit that assumed
  the result was wrong found it. Therefore: backtest harnesses get the same audit as engine code;
  every OOS script joins option legs BY DATE and requires both legs to have a candle on entry
  day; and any result that gates a deployment decision gets an independent audit pass (a fresh
  agent told to refute it) before it is believed. See studies/DEPLOYED_EVIDENCE_AUDIT.md.

- **DO NOT BE CARRIED ALONG BY THE USER'S FRAMING (standing rule, user 2026-08-05).** This is
  distinct from "honesty over optimism" below, which is about how to report results. This one is
  about who is asking. If the user's question embeds a conclusion — "is this much better?", "so this
  is good, why not buy?", "this must have broken the strategy" — answer the underlying question,
  not the premise. Agreeing because he leaned that way is a failure mode, and so is contradicting
  him to look rigorous. Real cases: he asked "c/w is 0.48 so good actually, why not buy" — the
  correct answer was that c/w had stopped measuring the thing the gate exists for, because the
  strike had gone ITM and the extra credit was intrinsic, not vol. He asked whether the new 15:36
  timing was "much better" — the correct answer was better on signal fidelity, WORSE on execution
  cost, net unmeasured. He asks for this explicitly and repeatedly. When a question has a mixed
  answer, give the mixed answer and say plainly which part is measured and which is not.

- **Honesty over optimism.** This is a thin, unproven edge. Always frame results gross-vs-net,
  sample size, and out-of-sample fragility. Don't sell a curve-fit.
- **Commits:** branch off main if needed; end commit messages with the Co-Authored-By trailer.

## Health checks

```bash
pgrep -f engine.engine_runner   # engine alive?
pgrep -f main.py                # viewer alive?
.venv/bin/python -c "from engine import store; print(store.stats())"   # engine.db counts
tail logs/engine.out.log        # engine log
.venv/bin/python -m engine.engine_runner --once   # run one engine cycle manually
```


## Voice pass (binding, added 2026-08-10)

Any prose written in his name — notes, docs, commit bodies, READMEs, book text — gets the
sentence-level voice pass defined in `~/.claude/CLAUDE.md` ("Sentence-level voice pass"):
every sentence needs a subject and a verb and one fact, no verbless caption lists, plain verbs,
concrete places and moments. He may write examples with grammar slips; copy the voice, correct
the grammar.

## THE VOICE PASS GATE (strict, added 2026-08-10)

**No prose written in his name ships without the sentence-level voice pass.** Standing
instruction from 2026-08-10, covering every book, article, KDP asset, post, note and doc.
The gate is grammatical: every sentence needs a subject, a verb and one fact. No verbless
sentences, no caption lists used as prose, no staccato fragments. Plain verbs, concrete places,
"Example:" to signpost an example. Imperatives are fine and disclaimers are exempt.
Grep cannot detect a fragment, so read every sentence. Full rule and worked example:
`~/.claude/CLAUDE.md`, sections "THE VOICE PASS GATE" and "Sentence-level voice pass".
He may write examples with grammar slips; copy the voice and correct the grammar.


Polish without the AI feel: a sharp line that is a complete sentence carrying one fact is his
voice and stays. Cut fragments, not personality. Full rule in `~/.claude/CLAUDE.md`.
