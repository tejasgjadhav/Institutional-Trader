# Handoff — institutional-trader

## DONE (2026-07-30 night) — BOOK column · swing-MTM fix · UI renames · Saavi branding (653d3c9→1bb1f6d)
Four commits, all pushed both remotes, viewer relaunched stable after each (final PID 58816), engine
restarted once (57214):
1. **BOOK column (653d3c9)** — SWING TRADE LOG's two stock-credit tables now carry an explicit BOOK
   column ("v2"/"v1") after ENTERED on both leg rows: SWING_TAB_BOOK_COLS + book_label param on
   _fill_swing_table (engine/ui_terminal.py). Other tables untouched (8 cols).
2. **Stale-MTM root cause + fix (653d3c9)** — SWING_CREDIT_ENABLED=False (07-24) sat BEFORE
   resolve_swing_positions in both engine_runner._swing and the resolver itself, so the OPEN NIFTY
   2026-08-04 BULL_PUT (opened 07-24 15:10, just before the disable) froze at Jul 24 16:35 marks and
   would never have settled. Flag now gates NEW entries only; resolve runs while OPEN positions exist
   (double-gated: scan_swing_signals keeps its own flag check). Verified: book re-marked 19:43,
   short PE 155.65→7.50, position near max profit (+48.68 of 51.3 credit) — engine TP/expiry books it.
3. **Per-figure P&L colours (30424b1)** — stats lines coloured the WHOLE line by booked's sign, so v1's
   negative open MTM (−₹1,031) rendered green. Now booked and MTM each get their own green/red span
   (MTM math itself verified correct: credit − current cost per trade).
4. **Renames + branding (73dfb0b, 1bb1f6d)** — TRADE LOG tab → "INTRADAY TRADE LOG"; "0DTE" stripped
   from ALL UI chrome (tab, titles, section labels → "EXPIRY-DAY"/"INTRADAY", stats, status strip) but
   KEPT in STUDIES/README research prose (quotes study filenames). App renamed SAAVI INSTITUTIONAL
   TRADER (window title, Dock name, header) with a circular gold-ring logo of the user's daughter at
   data/saavi_logo.png — data/ is GITIGNORED on purpose: the child's photo must NEVER be pushed to the
   public repo. All logo uses fall back cleanly if the file is absent. Regenerate: crop (250,520,510,780)
   of ~/Downloads/SAAVI.jpg, gold gradient ring (script was in session scratchpad).

## DONE (2026-07-30 evening) — SENSEX ticker + README LIVE/REJECTED restructure (4c7121b)
SENSEX in top ticker strip (BSE_INDEX|SENSEX in _batch_index_ltp, ^BSESN Yahoo fallback, snapshot key
"sensex", UI sensex_lbl; verified live 77,772.70). README: plain-English narrative + 2 sprawling tables
replaced by two crisp tables — LIVE (win IS/OOS+dates, signals/mo, ₹/mo) & REJECTED/OFF (status+why).
Also this session: bold win rates in TG signals, profit-calc table (live month 21tr/+₹45,488 after user
removed index-swing row), stale totals fixed (30,340/75,848). All pushed both remotes; engine+viewer alive.

## DONE (2026-07-30) — Telegram signal format v2 LIVE (commit 37bccb3, both remotes)
User-designed format deployed in _tg(): "🟢 EXECUTE NOW — MULTIDAY/INTRADAY SIGNAL" · no 0DTE jargon
("Expires TODAY at 3:30 PM") · target ₹ + max P/L · "📚 Why this signal — Tejas Jadhav, CFA…" with effort
funnel (v2 32,852→609; v1 25,978→997) + SEPARATE IS/OOS lines with full dates ({TODAY} auto-fills via
datetime.now(IST)) · SENSEX says in-sample CANNOT be captured · SEBI disclaimer every signal · removed
"Execute with your broker" + "7 of 8 years". BUGFIX: 0DTE BANKNIFTY inherited NIFTY stats ("NIFTY" substring)
— excluded. Dead _TG_WIN/_TG_WIN_SYM removed. STUDIES card documents format. 2 samples sent to Telegram
(🧪-prefixed). Engine+viewer restarted, alive. NOTE: shell env can carry stale TELEGRAM_BOT_TOKEN — use
load_dotenv(.env, override=True) for manual sends; launchd engine unaffected.

## DONE (2026-07-30) — v1 exit TP-40/no-stop DEPLOYED (goal: raise win rate, zero signal loss)
Sweep (V1_WINRATE_SWEEP.md) + OOS path-replay (242 real-premium trades, stkfade_v1_oos_exits.py): TP-40/no-stop
= 85.0% IS / 86.0% OOS win, net +18.2/+17.6%w vs deployed TP-75/stop-2× 64.0/73.6% & +10.3/+15.1%w — SAME
trades, zero signal change. User approved ("then deploy tp-40"). Deployed: config TP 0.75→0.40, STOP_MULT
2.0→99.0 (none; wing caps risk). Labels updated (PM header, STUDIES card, TARGET_STOP_TABLE, _TG_WIN "85% IS /
86% OOS"). v1 is NO LONGER the TP-75 control. NOTE: the 3 existing open v1 positions keep their STORED 2×
stop_cost (baked at entry) but get the new TP-40 immediately (favorable). Commit 8d2aa66, both remotes.
Engine+viewer restarted, alive. Loop goal met → wakeup stopped.

## (prior) ACTIVE (2026-07-30) — /loop GOAL: raise v1 WIN RATE without cutting signals (all technical params)
User goal (dynamic /loop + ScheduleWakeup armed): better v1's win rate (64% IS / 73% OOS), signal count must
NOT drop. Levers = n-preserving only: TP fraction {0.40,0.50,0.60,0.75dep,0.90,hold} × stop {1.5,2,2.5,3,none}
× geometry {(1,3)dep,(2,4),(2,3),(1,4)} — entry gates FIXED. IS SWEEP DONE (log /tmp/v1sweep.log, json in scratchpad
v1sweep_results.json; both faithfulness checks reproduced: v2 85.3%, v1 755/64.0%/+10.3%w). KEY IS RESULT —
only s1w3 keeps n=755 (s2w4→286, s2w3→390, s1w4→571 = signal cuts, violate constraint). n-preserving winners:
TP.40/no-stop 85.0%/+18.2%w · TP.50/no-stop 82.4%/+18.8%w · TP.40/stop3 82.0%/+15.9%w vs deployed 64.0%/+10.3%w
— all 0 neg yrs. Same mechanism as v2 (early booking + stop was realizing recoverable losses; no-stop still
defined-risk). Time-exit overlay marginal (~73-74%). NOW RUNNING: OOS confirmation — NEW script
studies/ndte/stkfade_v1_oos_exits.py (pid 88624, log /tmp/v1oos_exits.log, json /tmp/v1_oos_exits.json):
fetches each v1-geometry trade's daily path ONCE from Upstox (Oct'24→date), evaluates all 4 exits on the SAME
trades. Watcher bv80ungyf fires on exit. PACE WARNING (10:05 IST): 10/113 stocks in ~29min — market-hours Upstox
throttling (engine shares the API) → full pass ~4-5h; interim read possible at ~50-stock checkpoint
(/tmp/v1_oos_exits.json refreshes every 10 stocks — evaluate the 4 exits on partial recs with the walk() in
the script). User told; default = let it grind, interim at ~50. WHEN DONE: if OOS confirms (win%↑ AND net%w ≥
deployed OOS +17.9%w), write studies/V1_WINRATE_SWEEP.md, show user, get approval BEFORE changing
STOCK_CREDIT_TAKE_PROFIT/STOP_MULT in config (v1 is the CONTROL book — flag that changing it loses the
TP-75 control benchmark), commit+push BOTH remotes. WHEN DONE: relay table + honest verdict (TP-earlier
win% gains partly cosmetic — judge on net%w + per-year), get approval BEFORE deploying any param change; commit
+ push BOTH remotes. NOTE: model switched to Fable 5 this session by user (/model claude-fable-5).
_Updated: 2026-07-29 by Claude Code_

## ACTIVE (2026-07-29) — GOAL /loop: MORE swing trades @85% + put/call + timing + stop-loss + size ₹1L/mo on ₹5L
User goal (Stop hook active): expand the swing book — more trades while holding ~85% win — analyse put-vs-call,
entry-timing, stop-loss limits; size to ~₹1 lakh/month for a retail trader with **₹5L margin** (updated from ₹2L).
STATUS: GOAL #1 COMPLETE. Backtest done → studies/SWING_PUTCALL_STOP_ANALYSIS.md (committed). VERDICT:
 (1) PUT vs CALL = NO stable edge. IS puts looked better (92.5%win/+24.9%w vs calls 80.8%/+25.0%w) but OOS the
     put NET COLLAPSED (+9.1%w) while calls held (+23.7%w) — the reversal CLAUDE.md warned of. Trade BOTH sides,
     no tilt. (2) STOP: looser is better-or-equal in BOTH windows, never worse (IS no-stop +30.4%w vs 3.0x +25%w;
     OOS no-stop +18.4%w vs 3.0x +18.0%w), worst loss bounded ~−62 to −65%w by defined risk. Widen 3.0x→3.5x/no-stop
     = marginal + and harmless, but SMALL & OOS-thin. My earlier prelim "-199%w on 3x stop" was a quick-sim artifact
     (intraday path-walk); authoritative close-sim caps ~−65%w. (3) TIMING: no DOW edge (inconsistent IS vs OOS);
     entering at breakout CLOSE (deployed) is optimal — waiting one session drops ~40% of trades for no net gain.
 NET: none of these ADD trades — they're quality/risk tweaks. Only a deploy-worthy OPTIONAL: widen stop 3.0x→3.5x.
 NOT deployed — needs user approval. "More trades @85%" answer = universe expansion (Goal #2, next).
DONE (on-disk, delivered to user):
 - Frequency ceiling CONFIRMED: v2 UNION already = the 85% swing book (~5.8/mo, 84–87% OOS, +26–29%w). "More trades
   at 85%" is CAPPED by the c/w≥0.40 gate (the edge). Below gate: 0.35–0.40→82%win but only +9%w; 0.30–0.35→76%/+1%w
   (breakeven). Win% stays high (mirage, TP-50 books early); MONEY collapses. Sources: UNION_DONCHIAN_FREQUENCY.md,
   CW_BUCKET_ANALYSIS.md.
 - ₹5L sizing (from LIVE forward-test economics): margin ~₹6–13k/trade (defined risk), blended net ~₹2,700/trade,
   ~20–22 trades/mo @1 lot. ₹1L/mo needs ~3 lots at favorable/model rate (~₹300k peak margin, fits ₹5L) but ~6 lots
   at the sober 50%-haircut rate (~₹500k, fully deployed). Verdict: ₹1L/mo = good-regime CEILING; durable base ~₹50–70k/mo
   at 3–4 lots. UNION losses CLUSTER on same down-days (−55% avg loss) → keep dry powder.
IN FLIGHT: a detached backtest `studies/ndte/stkfade_putcall_stop.py` (pid was 91107) is RUNNING on the freshly
 re-downloaded /tmp/bhav_cache_stk (1500 files). It computes, IS(2019→Sep24)+OOS(Oct24→now): (1) BEAR-CALL vs
 BULL-PUT win%/net split; (2) stop-loss sweep {2.0/2.5/3.0(deployed)/3.5/hold}; (3) day-of-week + close-vs-next-open
 timing. Output PENDING: studies/SWING_PUTCALL_STOP_ANALYSIS.md. The spawning subagent (id a38bf824d62b60730) ALREADY
 STOPPED before results landed — resume it via SendMessage OR just wait for the script + read the .md.
NEXT: read SWING_PUTCALL_STOP_ANALYSIS.md when done → relay put/call + stop + timing numbers to user → if any finding
 is deploy-worthy, show numbers & get user approval BEFORE touching engine (never deploy on a hunch). Then commit
 studies + push BOTH remotes (origin + private). Goal Stop hook auto-clears when condition met.
RE-RUN NOTE: the agent-launched detached run died silently mid-collection (no md, no /tmp jsons). Relaunched by me
 (pid tracked, log /tmp/pcs_run.log). Script studies/ndte/stkfade_putcall_stop.py writes /tmp/stkfade_pcs_is.json +
 _oos.json then studies/SWING_PUTCALL_STOP_ANALYSIS.md. Cache load of 1500 full FO-bhavcopy CSVs is SLOW (~mins).
GOTCHA: NSE bhav cache in /tmp is wiped on reboot — re-download via studies/ndte/bhav_dl_stk.py. Don't push .env.

## QUEUED GOAL #2 (2026-07-29, Stop hook) — EXPAND the F&O universe without diluting signal count
User: "look at all fno options band and work on enhancing and increasing the universe without compromising on the
number of signals — do this AFTER you finish the first test." Interpretation: current universe = ~100 hand-picked
names (config.UNIVERSE, chosen by intraday movement; beat a mcap-top-100 67% vs 61%). NSE F&O has ~180–220 stock
underlyings. Take the F&O names NOT already in UNIVERSE, run v2 UNION fade + c/w≥0.40 gate on them, keep those that
ADD signals at ≥~85% quality (the gate self-selects rich-IV higher-priced names — see FUNDAMENTAL_TECHNICAL_FINDING).
"Without compromising signals" = additive only; must not lower the 85% win / +26%w. NEEDS bhav option data for the
EXTRA names too (current /tmp/bhav_cache_stk only has the ~100 universe) → download via bhav_dl_stk.py variant with
the expanded symbol list. Deliverable: studies/UNIVERSE_EXPANSION.md + proposed additions; show user numbers &
get approval BEFORE editing config.UNIVERSE. Do ONLY after Goal #1's backtest is reported.
STATUS 2026-07-29: DONE (subagent). Deliverable studies/UNIVERSE_EXPANSION.md (149 lines) + scripts
 studies/ndte/expand_phase0_enum.py / expand_phase1_screen.py / expand_phase2_dl.py / expand_split_bysym.py /
 expand_phase2_bt.py + /tmp/expand_phase2.json. VERIFIED against raw JSON (not prose): baseline reproduced
 370tr/84.1%/+25.7%w/+ve6/6yr (matches known target → sim faithful). RESULT: universe CAN expand additively.
 Screened 180 F&O underlyings → 88 candidates not in UNIVERSE → 37 clear c/w≥0.40 gate, ALL net-+ve IS. Options:
  • STRICT (2: MRF,DEEPAKNTR, n≥15): 5.78→6.39/mo, 84.1→84.4%win, +25.7→+28.0%w
  • TIER-5 (13: COLPAL,ASTRAL,INDIAMART,ALKEM,DALBHARAT,UBL,NAVINFLUOR,MRF,ATUL,CUMMINSIND,DEEPAKNTR,HAL,BOSCHLTD)
    recommended: 5.78→7.56/mo (+31%), 84.1→85.5%win, +25.7→+27.6%w
  • ALL-GATED (37): 5.78→8.89/mo (+54%), 84.1→84.9%win, +25.7→+26.4%w
 ALL keep win% & net%w at/above baseline. CAVEAT: IS-only (no per-name OOS — Upstox premium hist ~1mo);
 mid-cap live fills erode net more than shown; small per-name n = noise (trust pooled). config NOT edited.
 DEPLOYED 2026-07-29 (user approved "yes go for Tier-5"): config.UNIVERSE 100->113 (+13 Tier-5 names), assert
 ->113, engine restarted (all 13 resolve live spots). Commit b042a13, pushed BOTH remotes. ALSO in same commit:
  - Telegram _tg(): every signal now shows 🎯 Target + 🛑 Stop the win% is conditioned on, grouped w/ max
    profit/loss; win% stated once "at the target/stop below" (per user: winrate subject to target+stop).
    Map _TG_TGT_STOP + _tgt_stop() in engine_runner.py.
  - UI STUDIES tab: universe-expansion card + put/call/stop/timing card + target/stop card; v2 sig/mo 5.8->7.6*.
  - UI PM DECISIONS: TARGET+STOP on v2/v1/monthly headers. studies/TARGET_STOP_TABLE.md (new).
 BUG CHECK done (user asked): 13 names resolve live, no stale size-assert, _tg label coverage verified, engine+
 viewer healthy @113. Minor cosmetic: '94-stock' descriptive comments in agent.py/orb_vwap_live.py now stale
 (pre-existing, left per surgical rule). BOTH GOAL STOP HOOKS should now be satisfied.
NOTE: origin push of Goal-#1 commit eedcc00 TIMED OUT (github unreachable ~2min) — PRIVATE remote has it; retry
 origin when network recovers (`git push origin main`). Upstox+github both flaky this session.

## DONE (2026-07-30) — v1 TP-75 IN-SAMPLE measured + backtest-lookback assessment
v1 TP-75 IS = **64.0% win / +10.3%w / 755 tr (2019→Sep'24), +ve every yr (2023 weak 54.8%)**. Harness validated
(v2 config reproduced 85.3% DC10 baseline). OOS(73%)>IS(64%) → deployed 73% was optimistic end, not overfit;
honest = 64% IS / 73% OOS (~67% pooled). Hold-to-expiry base 55.1% (confirms the "~54%"). Script
studies/ndte/stkfade_v1_is.py, doc studies/STOCK_V1_IS_MEASURED.md. UI v1 header + _TG_WIN corrected from
"NOT MEASURED" → "64% IS / 73% OOS". Lookback: studies/BACKTEST_LOOKBACK_ASSESSMENT.md (Fable) — 7yr is
sufficient-as-available, can't go usefully further back for stock option premiums, defined-risk caps the tail,
extend the FORWARD test not the lookback. Committed 94bb8e6, pushed BOTH remotes. Engine+viewer restarted, alive.

## (prior) ACTIVE (2026-07-29) — measuring v1 TP-75 IN-SAMPLE (closing a label gap)
User caught: UI says v1 in-sample "NOT MEASURED" but v2 IS was measured — why? Honest answer: no data/method
reason, just a gap (same bhavcopy, same daily-close TP detection; only v1's hold-to-expiry base 54% IS + TP-75
OOS 73% were ever run). Subagent a646796a6ce3cbd25 FAILED — hit the WEEKLY usage limit (resets 4:30am Asia/Calcutta) before writing
anything. NOT re-run this session (shared account limit). QUEUED for a fresh session after reset: measure v1's
DEPLOYED config (D10, short-1-OTM, width-3, TP-75=book@0.25×credit cost, stop-2×, c/w≥0.40, prem≥50) on
/tmp/bhav_cache_stk (2019→Sep'24) — reuse studies/ndte/stkfade_union.py loader + studies/stkfade_oos_v1.py
exit logic; cross-check v2 config reproduces ~84% IS first. Deliverable studies/STOCK_V1_IS_MEASURED.md. WHEN DONE: update the v1 PM DECISIONS header in ui_terminal.py (currently
"in-sample NOT MEASURED for the TP-75 exit... 54%") to the real IS win%/net; update _TG_WIN if needed; commit
+ push BOTH remotes. Latest pushed commit: f570c3a. Recent telegram/UI edits all live (universe 113, target/stop
honest, Multiday/Intraday labels, WIN/Loss summary, watchlist win-prob).

## ACTIVE (2026-07-24) — HOURLY first-touch c/w>=0.40 entry vs CLOSE entry (stock v2 UNION + v1) — VALIDATION ONLY
User Q: the live engine evaluates c/w ONCE at the 15:10 close; if instead we entered the FIRST intraday
hour c/w touches >=0.40 we'd catch MORE signals (user's example: OFSS touched 0.43 at 14:45, back <0.40
by 15:10, so close skipped it). Does hourly add EDGE or NOISE? Hypothesis (flip side): hourly fills on
transient IV spikes that revert = more signals, lower quality. REPORT-ONLY, do NOT touch the live engine.
FILES: studies/ndte/hvc_backtest.py (fetch+sim, resumable/cached/checkpointed → /tmp/hvc/hvc_results.json),
studies/ndte/hvc_report.py (tables), hvc_probe.py (breakout counter). Deliverables PENDING:
studies/HOURLY_VS_CLOSE_ENTRY.md + a UI STUDIES res() card + commit/push BOTH remotes.
METHOD: same breakout universe (v2 UNION D5/10/15/20; v1 D10) + same strikes (off breakout-day close ATM)
+ same gate (c/w>=0.40 & prem>=50) + same daily-close exit walk (TP/stop/intrinsic). Only ENTRY differs:
CLOSE uses 15:10 daily-close premiums; HOURLY steps hourly marks [09:15,10:00..15:00] on the breakout-day
1-min expired-option candles, enters at first mark c/w>=0.40, else falls back to close (HOURLY ⊇ CLOSE).
Flip-side metric = of HOURLY intraday entries, fraction that are "reverting spikes" (c/w back <0.40 by
close = the extra signals CLOSE skips) and their win%/net vs the held ones.
**CRITICAL BUG FOUND + FIXED (do NOT reintroduce):** bar_at() called _mins() on a bare "HH:MM" mark but
_mins sliced ts[11:13] (full-ISO only) → ValueError → swallowed by do_stock try/except → the WHOLE record
dropped. It only fired when the short leg HAD intraday data (`if bs:`), so EVERY breakout whose short
trades intraday was silently dropped, leaving only illiquid-short survivors (74 v2/60 v1) with 0 intraday
— which falsely looked like "hourly==close, no data". FIX: split _mins_ts (ISO) vs _mins_hm (HH:MM).
After fix, record counts jumped (v1 78 by stock 21 alone). MUST re-run fresh (run2). LESSON: the buggy
run REPRODUCED documented close numbers (v2 86.5%/+35.2%w vs doc 200/87.5%/+31.5%w; v1 71.7%/+16.9%w vs
73.4%/+17.9%w) so close-sim is validated — the bug only hit the HOURLY branch.
**DATA FINDING (real, not the bug):** liquid low-priced stocks (RELIANCE/ICICIBANK ~1420) have FULL
intraday data (375 bars) at ATM/2-OTM/6-OTM but c/w hovers 0.22-0.29 → rarely hit the 0.40 gate. The
gate structurally selects rich-IV wide-strike options on HIGHER-priced stocks (OFSS/COFORGE/BAJFINANCE)
whose fade shorts produce FEW/NO intraday TRADE candles (user saw OFSS's path via LIVE QUOTES; historical
expired-instrument candles record TRADES only). So hourly is partly unmeasurable/unexecutable on exactly
the gated names — a genuine finding to report alongside whatever the re-run yields.
FETCH BOUND (documented, conservative): intraday fetched only when close c/w>=0.30 & prem>=40 (band around
the gate). Deeper reverters excluded → biases TOWARD hourly (against the noise hypothesis). ~26k daily +
~3k intraday calls; API throttles HARD (a mid-run DNS blip dropped some too — leg fetchers now 6/5 retries
w/ backoff). Caches in /tmp/hvc/{daily,intra,under}; results /tmp/hvc/hvc_results.json (per-breakout recs).
RESULT (run2, post-fix, DONE): **HOURLY = NOISE, keep CLOSE.** v2 UNION CLOSE 183·87.4%·+32.8%w vs HOURLY
253·84.6%·+25.7%w; extra 70 signals (3.3/mo) only +4.5%w/74% (a 7th of core). v1 CLOSE 331·72.2%·+16.9%w
vs HOURLY 500·69.0%·+11.2%w; extra 169 signals LOSE −2.5%w/61%. FLIP-SIDE confirmed: 63%/47% of intraday
entries are reverting spikes; reverting vs held = v2 +4.5 vs +33.5%w, v1 −2.3 vs +4.7%w. Total edge/mo flat
(v1 identical) → more trades+lower win+more variance for no gain. CLOSE reproduced docs (v2 87.4≡87.5,
v1 72.2≡73.4). Exec caveat: both legs traded intraday on only 30%/62% of trades (gate picks rich-IV
wide-strike names that don't print sub-day). FOLLOW-UP Q "does hourly make sense for v2 (its extra signals
were +4.5%w, not negative)?": NO — the v2 extra-70 net is 2026-ONLY: 2024 −1.8%w(n3), 2025 −5.5%w(n30),
2026 +11.6%w(n37); the +4.5%w aggregate is a single favorable year, negative in the two prior. Plus you
can't cherry-pick the good (held +33.5%w) half ex-ante — held-vs-reverting is defined by the close you're
front-running. So keep CLOSE for BOTH books. (The v2 extra signals ARE executable — 70/70 both legs intraday
— so the barrier is durability, not liquidity, unlike the deep gated trades.) v2-per-year + the follow-up
folded into studies/HOURLY_VS_CLOSE_ENTRY.md + the UI HOURLY card.

## DONE (2026-07-24) — STUDIES TAB RESTRUCTURED (user request) + v2 follow-up added
User: "fix the ui studies tab. it should not have audit. it should have strategies live first table and
then pnl and then each strategy which is live and backtesting involved." REMOVED the top AUDIT block
(_studies_html: the "⚠ RECOMMENDATION — NO strategy change" 18px header + the ①/①b/②/③ actions table +
the 2 audit res() blocks "SHOULD NIFTY BE REMOVED"/"WHY ① MATTERED", old lines ~812-857). Tab now opens
directly on THE LIVE STRATEGIES — SUMMARY table → plain-English → CONSOLIDATED MONTHLY P&L → per-strategy
research (each with its backtest) — which was already the order from line 859 on; only the audit preamble
was in the way. Also appended the v2 "does hourly make sense? NO, +4.5%w is 2026-only" nuance to the
HOURLY res() card. Verified: ast OK, viewer relaunched, PID 5138 stable (no crash). Commit + push both. DELIVERABLES DONE: studies/HOURLY_VS_CLOSE_ENTRY.md, UI res()
card after the DONCHIAN card (viewer relaunched, PID stable), committed + pushed origin & private. Engine
NOT touched. Scripts: studies/ndte/hvc_{probe,backtest,report}.py; data cache /tmp/hvc (gitignored, not committed).

## DONE (2026-07-19 cont.) — PRE-OPEN SIGNALS all REJECTED (studies/ZERO_DTE_PREOPEN_SIGNALS.md, e09f294)
Broader "what's knowable before 9:15" test. INSTRUMENT = the overnight GAP (market's own weighted
summary of every overnight input — no news API needed; entry is 09:16 AFTER the 09:15 open prints so
there is NO lookahead). Swept gap / rv5 / prior-day-move thresholds on 448 trades.
RESULT: nothing survives. Pooled sweeps show some extreme thresholds "helping" but EVERY candidate
FAILS THE ERA SPLIT: skip rv5>=1.10 = +₹47.6k Era A / −₹18.0k Era B; same reversal for rv5>=1.30,
gap-up>=0.75%, and the combined rule. The signed-gap asymmetry that looked structural (short-call book
should fear UP-gaps) INVERTS: down-gaps worst bucket in Era A (−12.5%m), best in Era B (+19.7%m).
Regime read, not an edge. → do NOT extend NIFTY's rv5<0.9 filter to SENSEX/BANKNIFTY.
FRAMEWORK (from Fable 5 design pass, folded into the study):
  * RELEASE-WINDOW TAXONOMY — what matters is where a release lands vs the 09:16→15:30 hold window.
    INSIDE (RBI 10:00, Budget 11:00, election counting) = the only real risk class. JUST BEFORE
    (FOMC 23:30, US close, overnight geopolitics, post-market results) = we sell the exhale = GOOD.
    AFTER (India CPI 17:30, US CPI 18:00+) = IRRELEVANT to today's position — testing them same-day is
    a CATEGORY ERROR, not an empirical question. This PREDICTS the earlier FOMC finding.
  * RETROSPECTIVE-EVENT-LIST TRAP — a "major geopolitical shocks" list compiled today is selected FOR
    having moved the market (survivorship-of-the-scary); inadmissible as a rule. The gap is the
    admissible instrument for the same question. DO NOT build a hand-list avoid-rule.
  * Other Fable cautions to honour: multiple testing (~90 tests → 4-5 false positives expected);
    one-day dominance (report results ex-worst-day); test filters CONDITIONAL on the c/w gate;
    prefer HALF-SIZING over full skip if any effect is ever found.

## DONE (2026-07-19) — STOCK AUDIT PASSED + NIFTY KEPT + studies/README.md index added
STOCK AUDIT (ndte22): BOTH books PASS decisively. v2 t=+13.78 CI[+60.6,+80.7] 8/8 yrs, drop 10 best
-> 83% survives. v1 t=+7.09 CI[+19.8,+34.9] 3/3 yrs, 69% survives. Worst trade = 8 and 12 TRADES of
profit (BANKNIFTY was 102 MONTHS). The Rs32,000 is NOT fabricated.
BUT MAGNITUDE still optimistic: v2 implies ~97%/mo on deployed capital; 24/569 trades print c/W>0.95
(stale marks). KEEP THE BOOKS, DISTRUST THE NUMBER. Plan-on ~50% vs 80% still recommended, NOT changed.
NIFTY 0DTE: **DO NOT REMOVE** — 2nd-strongest book. n=273/8yrs, +ve 7/8, t=+4.43, CI[+2.62,+6.77]
excludes 0, p=0.0002, drop 5 best -> 87% survives. Small Rs/mo is a SIZE question not a VALIDITY one;
per day of capital it is +4.7%/day vs v2 +4.3%/day. Opposite of BANKNIFTY (t=+0.10, p=0.33).
OPEN GAPS: v1 in-sample era (718 trades) still has NO per-trade file — only its 346-trade OOS era was
audited. v2 capital rests on approximated per-stock lot sizes.
Added studies/README.md — index of all 40 studies + current book state + the 6 house rules.

## (superseded) RECOMMENDATION — validate, do not modify. See studies/NEXT_ACTIONS.md
Asked "any change in strategy?" Honest answer: **the evidence supports NO geometry/gate change.** Every
modification tested this session was rejected on data (events, gap, VIX, earnings, shocks, Donchian
window, rv5-extension). The two things deployed were RISK exclusions, not edges.
**The real finding is a VALIDATION GAP, not a strategy gap:**
  * ₹32,000 of the ₹36,924 monthly model (**87%**) is the two STOCK books, NOT re-measured this session.
  * Every stale number checked this session came in OPTIMISTIC — BANKNIFTY worst: claimed 91%/₹1,500 →
    measured 78.6%/₹141 (**~10× overstated**). NIFTY ₹2,500→₹1,771.
  * v2's own numbers imply ≈97%/month on deployed capital — not credible; corroborates the standing
    "backtest is OPTIMISTIC" warning.
→ #1 PRIORITY: audit stock v2 + v1 the same way the 0DTE books were audited (per-trade file, per-
  calendar-year win, RoC per lot, holding period, adversarial checks). v1 has NO per-trade file at all.
→ #2: plan-on haircut of 80% is TOO GENEROUS on numbers that may themselves be 2-3× high. Suggest
  planning on ~50% of model until the stock audit lands. (UI still SHOWS 80% — flagged, not changed,
  because changing a planning assumption needs user sign-off.)
→ DO NOT: add filters, resize up, or add books. Nothing in the evidence supports it.

## DONE (2026-07-19) — RETURN ON CAPITAL per lot + holding period added to strategy table
User: "add net returns considering loss rate per trade... return on capital which is max loss amount...
mention holding period" then "this is per lot".
CAPITAL = margin blocked = (width − credit) × lot = MAX LOSS. Returns below are ALREADY net of the
loss rate (mean taken across ALL trades incl. losers).
**PER LOT, MEASURED:**
| book | lot | capital/trade | credit | net/trade | RoC | avg WIN | avg LOSS | worst |
| NIFTY 0DTE | 75 | ₹13,577 | ₹1,423 | +₹558 | +4.11% | +₹1,168 | −₹4,038 | −₹12,975 |
| SENSEX 0DTE | 20 | ₹11,519 | ₹1,755 | +₹762 | +6.62% | +₹1,418 | −₹4,549 | −₹8,963 |
| BANKNIFTY (rejected) | 30 | ₹8,308 | ₹1,871 | +₹141 | +1.69% | +₹1,635 | −₹5,336 | −₹14,298 |
Cross-check OK: NIFTY ₹558×3.2/mo=₹1,786≈₹1,771 · SENSEX ₹762×4.1=₹3,124≈₹3,153.
KEY SHAPE: a LOSS costs 3–7× what a WIN pays (NIFTY −₹4,038 vs +₹1,168) — that is WHY ~88% win is
required and why BANKNIFTY at 78.6% could not carry itself.
**BUG CAUGHT — do not repeat:** naive mean-of-ratios gave v2 UNION **+302%/trade**, impossible for a
credit spread (max gain = the credit). Cause: **16 of 569 trades print c/W>0.95** → margin collapses to
~0.5 pts and the ratio explodes; those are stale/illiquid prints (a spread paying 99.5% of width is
free money). FIX: exclude c/W>0.90 AND report CAPITAL-WEIGHTED sum(net)/sum(margin), never mean-of-
ratios. Clean v2 (n=545): **capital-wtd +52.3%**, median +56.6%, win 84.8%, avgW +101.7%, avgL −101.8%.
(v2 ₹ per lot NOT derivable from d5 jsons — no per-stock lot size; UI keeps prior study's ~₹10,500
margin / +₹4,069 expectancy and marks it as carried-forward.)
HOLDING PERIOD — **MEASURED** (ndte21_roc_holding.py; SLOW ~25min, reloads 1,359 bhav files + refetches
underlyings; add flush=True if re-running, prints are buffered):
  0DTE NIFTY/SENSEX : SAME DAY (09:16→15:30, ~6h, ZERO overnight gap risk) — certain
  v2 UNION (369 bhav-era trades): **avg 12.1 cal days · median 9 · p90 27 · max 38**
      TP     279 (75.6%) avg  8.9d median  6d   ← 3 of 4 exits are early TP-50, not expiry
      STOP    23 ( 6.2%) avg 17.9d median 20d
      EXPIRY  67 (18.2%) avg 23.6d median 24d
**DERIVED — RoC PER DAY OF CAPITAL (makes books comparable):** v2 +52.3%/12.1d = **+4.3%/day** ·
NIFTY 0DTE +4.69%/1d = **+4.7%/day** · SENSEX +7.62%/1d = **+7.6%/day**. So per DAY of capital the
0DTE books MATCH OR BEAT v2 — v2 only wins on ₹/month because its capital is continuously deployed
(~5.5 sig/mo × 12.1d ≈ 2.2 concurrent positions) while 0DTE sits IDLE ~90% of the month.
**HONESTY FLAG:** v2's numbers imply ≈97%/month on deployed capital (₹22.4k profit on ~₹23.1k avg
tied up). That is NOT credible for a live strategy and independently corroborates the repo's standing
warning that the v2 backtest is OPTIMISTIC — KEEP LOTS AT 1. Do not present +52%/trade without this.

## DONE (2026-07-21) — BUG SWEEP: 3 parallel audit agents + grep; fixed all live CRITICAL/HIGH
Two settlement bugs + one CRITICAL Telegram bug fixed. Agents audited resolvers, notifications, scan/data.
**FIXED (live):**
1. 0DTE FABRICATION (HIGH) — zero_dte.py + dte_multi.py STILL had `spot = _spot() or entry_spot or 0`
   in settlement (the swing fix hadn't reached them). A settle-time quote failure → intrinsic 0 →
   full credit → FAKE WIN + wrong Telegram; `or 0` on a bear-call ALWAYS fakes a win. FIXED: settle on
   the EXPIRY-DAY DAILY CLOSE first (correct on T+1 too, where live spot is the wrong day), live spot
   only as exp-day fallback, else leave OPEN + retry. Never entry/0. New helper dte_multi._expiry_close.
2. monthly_fut.py (MED) — `today >= exp` fired at 00:00; now `(today>exp) or (today==exp and >=15:25)`
   so it books at the close (MOC), matching its backtest. (Not a notifier book; can't send wrong msg.)
3. **TELEGRAM M&M (CRITICAL)** — "M&M.NS" IS in universe, stored "M&M". The `&` breaks Telegram HTML
   parse_mode → send 400 → BUT `seen.add(pid)` ran BEFORE the send and the return was ignored →
   M&M results/entries silently lost FOREVER, no retry. Same vector = ANY transient send failure.
   FIXED 3 ways: (a) notifications.send_telegram retries as PLAIN TEXT on a 400; (b) html.escape all
   dynamic fields (sym/side/label) in _tg + _outcomes; (c) _outcomes marks seen ONLY after send
   returns True (seeding path still silent). import html added.
**NOTED, NOT FIXED (low / disabled path):** agent.py/signals.py `current_price` never set + fetch_nifty_pct
returns 0.0 on failure (blocks trades) — but 3-Family is DISABLED, latent. options.py tz-naive expiry
(daemon runs IST). fetch_ltp_batch dead code. HTTPAdapter max_retries=0 despite docstring (fail-safe).
credit books (swing/stock) have the same T+1-settles-on-next-day-spot vector but agent judged minor for
multi-day monthly books (they already don't fabricate) — left to limit blast radius.
All verified: ast+import OK, M&M escapes to M&amp;M, engine cycle clean, engine+viewer stable.

## DONE (2026-07-21) — SWING Telegram RELABELLED (user chose relabel over silence)
Telegram now distinguishes multi-day from same-day so an index credit spread entered days ago can't
read as a same-day 0DTE call:
  * `_MULTIDAY_BOOKS` set → every held-to-expiry book (stock v2/v1, swing, monthly) prepends
    "⏳ MULTI-DAY — strikes fixed at entry TODAY, HELD to expiry (this is NOT a same-day 0DTE call)".
  * swing signal label: "SWING CREDIT (NIFTY/FINNIFTY)" → "SWING CREDIT · multi-day (NIFTY/FINNIFTY)".
  * outcome labels: swing → "SWING CREDIT · multi-day"; 0DTE NIFTY/SENSEX → "… (same-day)".
  * result message already leads with entry-date + expiry, so a settle reads unambiguously.
ALSO fixed stale win% labels in _TG_WIN: 0DTE NIFTY "90% (calm-filtered)"→"88.3% (measured)",
SENSEX "89%"→"89.0% (measured)"; REMOVED BANKNIFTY 0DTE entries (book rejected/disabled 07-19).
Verified by rendering the actual swing + 0DTE messages (no send) — tags correct, contrast clean.
Engine cycle clean, engine+viewer restarted stable. User did NOT silence swing — kept broadcasting,
just clearer. (Earlier "VIEWER CRASHED" reads this session were the stability check racing the restart
and catching a transient PID — verified stable on a settled PID both times.)

## (resolved) OPEN THREAD — SWING vs 0DTE Telegram confusion
User read the correction message (SWING NIFTY 24500/24650, expiry 21-Jul) as a same-day 0DTE call and
objected: "our logic is check 9:16 levels then decide on Tuesday for NIFTY." That is the 0DTE book.
The message was the SWING book: entered MON 6-Jul on a Donchian breakout (~15:10 scan), strikes chosen
1-OTM AT ENTRY off 6-Jul close (~24440), held 15 days, expiry TUE 21-Jul. So the levels were NOT a
today-call — they were locked 2 weeks ago. Coincidence worsening it: 21-Jul is BOTH the swing expiry
AND a 0DTE Tuesday, so both books touch NIFTY today.
ROOT UX PROBLEM: two NIFTY books both Telegram "NIFTY bear-call" results; swing broadcasts strikes
decided at entry, which reads like a fresh same-day call. PENDING user decision (asked twice, not yet
answered): (a) relabel swing _tg as "SWING · multi-day · entered <date> · held to expiry" so it can't
be mistaken for 0DTE, and/or (b) SILENCE the swing book on Telegram entirely — it is an unproven paper
fwd-test (54% win, failed OOS) and arguably should not broadcast beside the validated books.
Do NOT change _tg labels or silence swing without the user picking — it is their group.

## DONE (2026-07-21) — FIXED: premature-settlement bug that sent a WRONG Telegram WIN
User got a wrong Telegram at ~00:06 on NIFTY expiry night declaring a WIN before settlement.
ROOT CAUSE: swing_credit.resolve used `expired = today >= exp`, TRUE from 00:00 on expiry day. At
midnight the market is shut so `_spot()` returned None and it fell back to `entry_spot` (the price
from ENTRY, 2 weeks earlier). Against the 24500 short strike that gave intrinsic 0 → full credit →
fake "WIN", which the _outcomes notifier then Telegrammed 15.5h before the 15:30 settlement.
FIX (3 notifier books had the same latent defect — all fixed):
  swing_credit.py (the culprit), stock_credit.py, stock_credit_v2.py:
  `expired = (today > exp) or (today == exp and past_settle)` where past_settle = IST time >= 15:30,
  AND never settle on entry_spot — use live spot, else expiry-day daily CLOSE, else leave OPEN + retry.
  (zero_dte + dte_multi/sensex/bnf ALREADY had the correct past_settle guard — verified.)
STATE REPAIRED: reverted NIFTY-2026-07-06 swing pos to OPEN (backup /tmp/swing_backup.json), removed
it from data/outcome_notified.json so the REAL result notifies after 15:30 today.
CORRECTION TELEGRAM SENT (send_telegram → True): apologised, explained the position is still open,
settles today 15:30. NOTE: send_telegram reads token at import — a bare `python -c` needs
`load_dotenv()` + re-inject n.TELEGRAM_BOT_TOKEN/CHAT_ID, else it returns False silently.
STILL LATENT (not a notifier book, so no wrong-message risk; REGIME-OFF anyway): monthly_fut.py:245
has the same `today >= exp` pattern. Fix it the same way if that book is ever re-enabled.

## DONE (2026-07-19) — UI restructure: STRATEGY TABLE to top w/ per-CALENDAR-YEAR win rates, then P&L
User: "clean the table, win rate IS and OOS and calendar year, structured, keep it top then pnl."
MEASURED per-calendar-year win rates (all from real per-trade data, NOT estimates):
  v2 UNION (D5, merged both eras, n=569): 19:96 · 20:88 · 21:85 · 22:90 · 23:79 · 24:81 · 25:85 · 26:89
    → worst year 79%, positive/8 yrs covered
  NIFTY 0DTE (n=273): 19:85 · 20:85 · 21:76 · 22:87 · 23:94 · 24:91 · 25:94 · 26:94 → worst 76%
  SENSEX 0DTE (n=91):  24:75 · 25:90 · 26:93 → worst 75% (3 yrs only, Era-B book)
  BANKNIFTY (REJECTED, n=84): 19:67 · 20:67 · 21:83 · 22:64 · 23:92 · 24:89 · 25:90 · 26:83
v1 per-year NOT available — studies/stkfade_oos_v1.json is a dict, not per-trade rows. Left as
IS/OOS only and marked as such; DO NOT fabricate a per-year series for it.
Sources: /tmp/d5_10_15_20_{bhav,oct24}.json (v2), studies/ndte/ndte1{3,4}_trades*.json (0DTE).
NOTE /tmp may be purged — the 0DTE ones are in-repo, the v2 ones are NOT (regenerate via
studies/ndte/stkfade_d5_10_15_20_{bhav,oct24}.py if needed).

## DONE (2026-07-19, 1e05f1f) — BANKNIFTY 0DTE **REJECTED & DISABLED** (user decision)
`DTE_MULTI_BANKNIFTY_ENABLED=False` in config; dte_multi.scan_signals skips it. Open positions STILL
RESOLVE (only new entries stop). Fully reversible.
NOT because it loses — MEDIAN trade is +14.1%m. Because edge ≈ zero and tail swamps it (84 monthly
expiries 2019-01→2026-06, 1 lot, net): avg +0.55%m · **t=+0.10** · 95% CI [−9.98%,+11.09%] · bootstrap
p(mean≤0)=0.33 · **ENTIRE profit is 3 trades — drop 3 best → −₹8** · +₹141/mo vs worst day −₹14,298
(≈102 months of profit in one session) · the "91%/₹1,500" it was carried on was NEVER supported.
Both rescues tested & failed: monthly-pinning (ndte19: monthly 76.1% vs weekly 80.4% WITHIN Era A,
z=−0.75) and "recent era proves it" (n=18; EVERY book rose in Era B, NIFTY 86.5%→93.2%).
ADVERSARIAL AUDIT `ndte20_bnf_audit.py` written to FALSIFY the rejection: clean on bad prints, monthly
tagging, lot-size artifact, survivorship. **One real gap: CONTRACTS>=100 floor was applied to the SHORT
leg only, not the long wing — a dead wing would FLATTER the book, so the bias runs AGAINST rejecting
= conservative.** No bug flips the sign.
NOT claiming proven-unprofitable (CI spans 0 → UNPROVEN). At ~12 trades/yr it can never accumulate
evidence fast enough. REVERSAL BAR: ≥30 new monthly expiries with 95% CI excluding zero.
Draft rationale: studies/BANKNIFTY_0DTE_REJECTION.md.

## ACTIVE (2026-07-19) — STALE UI NUMBERS FOUND + layman explainer requested
User asked to explain the 0DTE strategy in plain English and CORRECT STALE VALUES / update monthly
profit calcs. Measured from the 448-expiry dataset (1 lot, net of costs, months = distinct YYYY-MM):
| book | full history | recent era (Oct'24→date) | UI CLAIMED |
| NIFTY 0DTE | 88.3% win · ₹1,771/mo (n=273, 86mo) | 93.2% · ₹2,290/mo | 87% · ₹2,500 |
| SENSEX 0DTE | (Era-B only) 89.0% · ₹3,153/mo (n=91) | same | 89% · ₹3,200 ✓accurate |
| BANKNIFTY 0DTE | **78.6% win · ₹141/mo** (n=84, 84mo) | 88.9% · ₹696/mo | **91% · ₹1,500 ✗STALE** |
BANKNIFTY is the big one: claimed 91%/₹1,500 vs measured 78.6%/₹141 full-history (even the generous
recent-era read is ₹696 = under half the claim). Era A alone was −₹711 total (−₹11/mo). CAVEAT that
must ride with it: weekly→monthly expiry break confounds the era comparison, so this is "the claim is
unsupported", NOT "the book is proven bad".
DEPLOYED c/W>=0.04 FLOOR IS ~NEUTRAL on recent data (SENSEX +₹77/mo, BANKNIFTY unchanged — no sub-0.04
trades in Era B). That is EXPECTED and fine: Fable deployed it for TAIL protection, not profit. Do not
re-sell it as a profit booster.
DO NOT TOUCH the stock-book rows (v2 UNION ₹20k, v1 ₹12k) — not re-measured this session, no new
evidence; only correct what was actually measured.

## DONE (2026-07-19 FINAL, ddf70db) — SERIES CLOSED. Opus tested, FABLE decided, 2 exclusions DEPLOYED
Workflow used (user instruction): "test all with opus, fable be decider, implement with opus."
LAST OPEN ITEM TESTED — India VIX (ndte17_vix_final.py, prior-close so no lookahead): ALL variants
FAIL, most in the OPPOSITE direction to the prior. skip vix_spike>=+10% costs −₹17,227 and those days
were 92.9% win/+13.32%m. vix_level>=15/18/20 cost −₹123.7k/−₹74.5k/−₹37.2k, failing BOTH eras.
vix_level>=25 = only positive sign (Era A +₹10,603 n=11) but Era B n=1 → UNTESTABLE not proven,
basically a description of COVID. **Revisit condition logged: if Era B ever accrues >=10 expiries with
prior-close VIX>=25, rerun that ONE test.** Half-sizing never rescued any rule; ex-worst-day never
changed a sign. Elections: ZERO overlap in all 448 expiries.
ONE NEW TEST Fable authorised — CREDIT FLOOR (ndte18_creditfloor.py). Did NOT fail. c/W buckets show
win rate is an INVERSE MIRAGE: cheapest bucket (c/W<0.04) had the HIGHEST win (91.7%) and LOST money
(−0.49%m, −₹1,878/60 trades); richest (0.18+) LOWEST win (81.7%) and made most (+10.03%m). Same shape
as the stock book's validated c/w>=0.40 gate → confirmed hypothesis, not a dredge.

**DEPLOYED (live engine, both structural — neither makes a regime claim so both-eras rule doesn't govern):**
1. `ZERO_DTE_ELECTION_BLACKOUT` (config) — checked in zero_dte.py AND dte_multi.py. National counting
   days + exit-poll session. NEVER triggered in 448 expiries → measured cost EXACTLY ₹0. 2024-06-04
   (NIFTY −5.9%) was dodged by CALENDAR LUCK not design. Zero-premium ruin-mode insurance.
2. `ZERO_DTE_MULTI_MIN_CW = 0.04` — **SENSEX + BANKNIFTY ONLY**, checked in dte_multi._scan_book.
   NIFTY UNTOUCHED (already has ZERO_DTE_MIN_CREDIT_PCT=0.02). 0.04 = STRUCTURAL boundary of the
   negative-EV bucket, deliberately NOT the sweep argmax — Fable EXPLICITLY REJECTED the better-scoring
   0.06-0.12 cutoffs as in-sample optima on small skip-counts (BNF skipped n=9).
Verified: `python -m engine.engine_runner --once` clean; engine+viewer restarted, stable PIDs.
Both are config-flagged → set to []/0 to revert.

**CLOSING FINDING (write this into any future proposal review):** this book is PAID FOR VISIBLE FEAR.
A fixed-%-OTM spread sold on a scary morning collects inflated premium against a strike that hasn't
moved — observable risk is COMPENSATION, not danger. Every filter keying on ex-ante-visible stress
(gap/VIX/spike/shocks — shocks went 7/7 win, +21.35%m) removes exactly the trades where the market
OVERPAYS. Only real threats: (a) INTRADAY surprises — occurred ZERO times in 448 expiries, unfilterable
ex ante; (b) true crisis regimes (VIX>=25) — too rare to test. Mirror image = the only thing that
survived: cheap premium is uncompensated tail risk.
**HARNESS BUG FIXED:** era-verdict helper treated an era with ZERO observations as a silent PASS,
mislabelling SENSEX single-era results as "BOTH ERAS HELP". Now returns "single-era only".
**STANDING CONSTRAINT:** SENSEX is PERMANENTLY outside the era-split framework (single-era book, BSE
weeklies launched 2023) → it may only ever receive STRUCTURAL rules, never swept ones.

## DONE (2026-07-19) — EARNINGS + SHOCKS tested → SERIES CLOSED (studies/ZERO_DTE_EARNINGS_SHOCKS.md)
EARNINGS: dates from NSE board-meeting API which ALSO carries advance-intimation timestamps — min lead
3d / median 14d across 367 rows, so ex-ante knowability is PROVEN not assumed. Decisive fact = release
window: only **51 of 367** releases land INSIDE 09:15-15:30; 223 POST_CLOSE, 88 NON_TRADING_DAY
(HDFCB/ICICIB report SATURDAYS). NIFTY/SENSEX avoidance COSTS money in every variant (weight arithmetic:
top weights 9-13% → 4% stock move = ~0.4% of index, below a 0.5%-OTM spread's pain threshold);
intraday-results days were GOOD (pooled 19 trades, 89.5% win, +13.63%m; avoiding = −₹24.3k).
BANKNIFTY = the one place arithmetic said to look (banks ~half the index) and there was NOTHING:
**ZERO of 84 expiries hit an intraday bank result** — month-END expiry vs mid-month results. Hypothesis
structurally starved. The pooled "exhale-case avoidance helps +₹12.9k" is an ARTIFACT — entirely 6
BANKNIFTY trades; strip them and the other 39 are +₹6.7k (avoidance would cost). Do not act on it.
SHOCKS (descriptive only — retrospective list inadmissible as a rule): 7 expiries hit a pre-open-
observable shock → **7/7 win, +21.35%m** (Iran barrage +30.9%m, Mar'26 crude/Fed cluster +34.6%m,
Hindenburg +5.4/+14.1%m). ZERO intraday-surprise overlaps. The scariest days were the best days.
**SERIES CLOSED — 3 studies, 448 expiries, nothing earns its keep. Trade the full calendar.**
Data committed in-repo: studies/ndte/nse_results_dates.py (+csv), india_market_shocks.py.
NSE recipe that works: cookie warm-up on /companies-listing/corporate-filings-board-meetings then
GET /api/corporate-board-meetings?index=equities&symbol=X&from_date=DD-MM-YYYY&to_date=... (browser UA
+ Referer + X-Requested-With). Supports multi-year historical range. BSE api.bseindia.com is WAF-blocked.

## (superseded) ACTIVE — heavyweight EARNINGS overlap test
Agent sourcing real ex-ante board-meeting/results dates 2019→2026 for RIL/HDFCBANK/ICICIBANK/INFY/TCS/
SBIN/LT/ITC/BHARTIARTL/KOTAKBANK/AXISBANK/HINDUNILVR. Fable's prior: this is a **BANKNIFTY-ONLY**
hypothesis — NIFTY/SENSEX top weights ~9-13% so a 3-5% single-stock move = only 0.33-0.55% of index
(below the 0.5%-OTM spread's pain threshold), but HDFCBANK ~26-29% + ICICIBANK ~23-25% ≈ HALF of
BANKNIFTY. Two mitigations expected to shrink it: banks increasingly report Sat/post-market (lands in
the GOOD before-window bucket), and BANKNIFTY is now month-END expiry while bank results cluster
mid-month → coincidence rare. MUST split results into (i) announced INTRADAY today [risk] vs
(ii) announced since yesterday's close [likely good] — needs NSE filing TIMESTAMPS, not just dates.

## (superseded) ACTIVE GOAL — EXPAND event taxonomy: earnings + geopolitical, avoidable vs not
User correction ACCEPTED: the BANKNIFTY side-finding is CONFOUNDED, not an edge — BANKNIFTY had WEEKLY
expiries pre-Nov'24 and monthly-only after (SEBI weekly rationalisation). The monthly contract now
absorbs flow that used to spread across weeklies, so Era A monthly-slice vs Era B monthly is NOT
apples-to-apples. Must SOFTEN that claim in ZERO_DTE_EVENT_DAYS.md (done) — do not present as a finding.
NEW ASK: go beyond RBI/Budget/FOMC. Test PRE-9:15-KNOWABLE factors: heavyweight EARNINGS (RIL, HDFCBANK,
ICICIBANK, SBIN, INFY, TCS — index-weight movers) + geopolitical/news parameters. Use FABLE 5 to reason
about what was knowable before 9:15 on each day (standing pref: Fable plans, Opus executes). Analyze
historically, then test avoidable vs unavoidable.
KEY DESIGN CONSTRAINT: earnings dates ARE knowable ex-ante (board-meeting intimation filed with the
exchange ~1-2wk ahead) → genuinely avoidable. Most geopolitical shocks are NOT (surprise) → they belong
in the UNAVOIDABLE bucket like the COVID off-cycle RBI. Keep that split rigid or the study self-deceives.
DATA PROBLEM TO SOLVE: need historical results dates 2019→2026 for the heavyweights from a real source
(NSE corporate announcements / board-meeting filings). Do NOT infer earnings days from price moves —
that is hindsight and circular.

## DONE (2026-07-19, EXTENDED) — 0DTE EVENT AVOIDANCE now tested on FULL HISTORY 2019→date: STILL NO
User asked to push the study back to "2016 or 2019 whichever". 2019 is the FLOOR and it's a data fact,
not a choice: NIFTY weekly options launched Feb 2019 (only monthlies before → no 0DTE weekly book);
SENSEX weeklies launched 2023 AND are BSE (absent from NSE bhavcopy) so SENSEX is Era-B-only.
RESULT (448 expiries 2019→Jul'26): trade-all 86.6%/+4.51%m/+₹2.33L vs avoid-all-core 86.8%/+4.40%m/
+₹2.00L = **−₹33.1k**. Win moves ±0.2pp (nothing) while 68 trades of profit are surrendered.
**BOTH ERAS AGREE INDEPENDENTLY** — bhav 2019→Jul'24 (n=266, incl COVID) −₹14.5k · Upstox Oct'24→date
(n=182) −₹18.6k. This KILLS the single-regime caveat the first pass carried. Question CLOSED.
Mechanism unchanged: event subset BEATS baseline (85.3%/+5.14%m); FOMC-spillover = post-event IV crush.
Tail risk is on ORDINARY days — 10 of 12 worst trades 2019→date, incl. worst (−₹14,298).
RBI: only 9 of 448 expiries ever hit an MPC day, still net +ve (+₹814) → the Era-B "+₹4.4k from avoiding
RBI" was 2 trades and dissolves. Budget: ZERO overlap either era.
KEY METHOD POINT: off-cycle COVID RBI (2020-03-27, 2020-05-22, 2022-05-04) + emergency Fed (incl Sunday
2020-03-15) are NOT knowable in advance → held in a separate UNAVOIDABLE bucket, NEVER in the avoidable
set (folding them in = hindsight cheating). None coincided with an expiry (n=0), so they change nothing.
NEW SCRIPTS: bhav_dl_0dte_idx.py (scans EVERY weekday keeping same-day-expiry OPTIDX rows — expiry
WEEKDAY changed over the period, Thu→Wed→Tue, so a hardcoded weekday silently drops expiries),
ndte14_events_2019.py (Era A collector), ndte14_report.py (full-history, era-split, worst-12 tagging).
GOTCHAS: NSE killed the legacy foDDMMMYYYYbhav.csv.zip format ~Jul 2024 → Era A ends 2024-07-04, gap
Jul–Sep'24. Cross-checks passed: NIFTY 88.3%/+4.69%m ≡ documented 87.8%/+4.0%m; SENSEX 89.0%/+7.62%m ≡
documented 88.8%/+7.6%m.
**SIDE-FINDING NEEDING ITS OWN STUDY:** BANKNIFTY monthly 0DTE is far weaker on full history —
Era A 75.8% win / **−1.64%m** (n=66) vs Era B 88.9%/+8.60%m (n=18). Its documented "91% win" rests on a
small recent sample. Flag before that book is ever sized up.

## DONE (2026-07-19) — 0DTE EVENT-DAY AVOIDANCE: TESTED AND REJECTED (studies/ZERO_DTE_EVENT_DAYS.md)
Q: skip 0DTE expiries landing on RBI MPC / Budget / FOMC? A: **NO — avoiding COSTS money.**
Pooled 182 expiries Oct'24→Jul'26 (NIFTY+SENSEX+BNF at deployed geometry): trade-all 90.7%/+7.28%m/
+₹1.32L vs avoid-all-core 90.2%/+6.79%m/+₹1.14L (−₹18.6k). Event subset is the BEST subset (94.4%,
+11.8%m): 16/18 were FOMC-SPILLOVER (Fed 23:30 IST → next session gets post-event IV CRUSH = exactly
what short premium wants; 16/16 win, +15.0%m). Filter buys NO tail protection — worst trade of sample
(−₹14,298 BNF) was an ORDINARY day, EX-EVENT worst identical to baseline. RBI = only true intraday risk
+ owns worst event trade (2025-10-01 SENSEX −47%m) BUT only 2/182 expiries ever hit an MPC day → the
"+₹4.4k from avoiding RBI" is ONE bad trade, not an edge. Budget = ZERO overlap (both weekend sessions).
Scripts: ndte13_events.py (collector; results persisted IN-REPO as ndte13_trades.json since /tmp purges),
build_event_calendar.py (verified calendar + next-trading-day spillover mapping), ndte13_report.py.
Cross-checks: SENSEX 89.0%/+7.62%m ≡ documented 88.8%/+7.6%m; NIFTY filtered n=73 ≡ documented.
GOTCHAS: Aug'25 MPC was RESCHEDULED (decision 08-06 not 08-07); FOMC+CPI release AFTER 15:30 close so
they map to the NEXT trading day (same-day tagging would be wrong); CPI dates mostly INFERRED from
MOSPI's "12th or next working day" rule → kept separate, never in the headline. Single regime only.
REPORT-ONLY, engine untouched. UI STUDIES card added, viewer verified stable PID.

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

## 2026-07-30 late: expectancy gaps filled (v1 live 11W/3L +5,874/-8,766 → +2,737; 0DTE formulas inline); watchlist digest: html-escaped syms (fixes literal <b> on parse-fail fallback) + friendly side names ('Bear Call Strategy — we expect the stock to stay lower…'). SENSEX result 4pm = my engine restarts 15:30-16:00 delayed settle+notify (not a code bug).

## 2026-07-30 CLOSE: user typed 'confirmed' — explicit approval of Tier-5 113-name deployment now in transcript; /loop universe goal fully closed (both tasks done+approved).

## ACTIVE /loop (2026-07-30 night): can INDEX swing fade (NIFTY/BNF/SENSEX, both sides) reach 80% win via the v1-style exit sweep? OOS FIRST, NIFTY first. Known: old config 54%/−1.4%w IS, salvage gates failed OOS — but TP-40/50+no-stop early-booking sweep NEVER tried on index (it took v1 54→85%). Agent writing studies/ndte/idxfade_oos_exits.py (clone of stkfade_v1_oos_exits.py: NIFTY D10 s1w3, no c/w gate, Upstox expired premiums Oct'24→now, exits {hold/stop2 dep, TP75/2, TP50/none, TP40/none} on SAME trades). Then IS bhavcopy if promising; then BNF/SENSEX. Deliverable studies/INDEX_FADE_EXIT_SWEEP.md. Do NOT deploy without user approval.

## ACTIVE (2026-07-31): NIFTY index-fade OPTIMIZATION — maximize net%w AND win, IS(bhavcopy 2019→Sep24)+OOS. Agent running: broader sweep (Donchian window, short-offset/width geometry, DTE, entry filters like breakout size/VIX regime, exits) with IS-first then OOS confirm on studies/ndte/idxfade_oos_exits.py harness. Deliverable studies/NIFTY_FADE_OPTIMIZATION.md. Guard: index fade failed OOS twice before (direction gates; exit sweep) — any winner needs BOTH windows positive. NO deploy without user approval.

## 2026-07-31: NIFTY fade optimization DONE — 1 survivor of 384: DC5·s2w4·DTE≥20·c/w≥0.50·TP-75/stop-2× = IS 72.2%/+21.8%w/6-6yrs(n=36) + OOS 75%/+32.5%w(n=16). Deployed geometry unfixable. Caveats: 1-of-384 multi-test risk, thin n (~6-9/yr). Recommended: paper forward-test only; AWAITING user approval to wire into engine. studies/NIFTY_FADE_OPTIMIZATION.md

## ACTIVE /goal (2026-07-31): path to ≥₹1L/month. KNOWN (07-29 sizing on ₹5L): model ₹38k/mo @1 lot; ₹1L needs ~3 lots in good regime (~₹300k margin) / ~6 lots sober (fully deployed) — ceiling not base. Goal loop iter-1 agent: lot-scaling capital curve on measured books + combination math + inventory of UNEXPLORED candidate strategies (cash momentum, pairs, covered strategies, futures spreads) with data-feasibility triage. Deliverable studies/PATH_TO_1L.md. NO deploy w/o approval; not-advisor framing.

## 1L-GOAL iter-1 DONE: PATH_TO_1L.md — ₹1L/mo = 3 lot-sets @model (~₹3L margin, fits ₹5L, accept −₹1.5-2L episode); sober ceiling ₹75-95k @4-5 sets (6 sets not fundable). Stepwise lot gates ≈1mo each → earliest credible ₹1L month 4-6. July live = 120% of model (21 tr). IC tested: 75.3%/+4.92%m loses to FLIP (85.8%) — rejected. Iter-2 (agent): P1 FLIP-condor hybrid + SENSEX condor. P2 calendars. P3 futures pairs. P4 cash momentum.

## 1L-GOAL iter-2 DONE: FLIP-CONDOR HYBRID = PROMISING (IS 86.5%/+₹148k vs FLIP +₹104k on same machinery; OOS 91.5%/+₹82k vs +₹64k; worst-case identical; whole 15-cell neighborhood beats FLIP both eras). Prize ≈ +₹800-1,000/mo/lot. AWAITING user approval to add as PAPER book (add opposite 0DTE side when its c/w≥0.08, d=1.00). SENSEX condor REJECTED (win% drops, regime-concentrated). Backlog: calendars (low prior). Scripts ndte24/25/26. Goal's core answer = PATH_TO_1L scaling plan (3 sets, month 4-6, stepwise gates).

## 2026-07-31 (post-limit): USER APPROVED hybrid ('go for hybrid' ×3) + standing rule added to CLAUDE.md (results→studies→UI→both repos). Hybrid implementation delegated to agent: ZERO_DTE_HYBRID paper book per studies/ndte/ndte24_flipcondor.py winner cell (added opposite side d=1.00, cw≥0.08, shared margin), telegram INTRADAY format, UI cards, commit+push both.

## ACTIVE /goal (2026-07-31): CHAMPION-STRATEGY SWEEP — systematic test of classic strategies (Connors RSI-2, Larry Williams vol-breakout, turtle, VWAP reversion, gap-fade, inside-bar, supertrend, ORB variants) on Kite 5-min (2019→, ~1yr for 5-min? daily 2019→) NIFTY+stocks, honest cost model, bar = ≥80% win AFTER costs or plain rejection. Prior art: NONFADE_INTRADAY_SEARCH.md, BUY_STRATEGIES_2019_REALTEST.md (3-Family 50.6% dir, ORB+VWAP thin — neither survives costs). Agent running → studies/CHAMPION_STRATEGY_SWEEP.md. Hybrid deploy agent also in flight.

## /goal CLOSED (2026-07-31): champion sweep DONE — 227k trades, 7 families, NOTHING beats the credit books; >80%win+positive-net unique to gated short premium. NR7 honest-but-small (+0.13%/tr). Illusion demo: 83.6% win with negative EV. studies/CHAMPION_STRATEGY_SWEEP.md + UI card. Hybrid deployed earlier (caf3755).
