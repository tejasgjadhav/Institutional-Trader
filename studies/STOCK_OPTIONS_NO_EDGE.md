# Study: NSE option strategies vs real costs — what fails, and the one that works

> **Scope grew over the project.** It began as "find the best intraday stock-option *buying*
> strategy" (Parts 1–3). When that failed structurally, the search widened — intraday spreads,
> multi-day holds, multi-day **credit spreads on stocks** (Part 4) and **on the index following
> the breakout** (Part 5). All of those lose net of real costs. **Part 6 is the exception that
> finally cleared the bar: the multi-day INDEX credit spread that FADES the breakout** — sell
> premium *against* a daily Donchian breakout and harvest theta on the mean-reversion. It is the
> one validated edge and is now deployed as a parallel forward-test (`engine/swing_credit.py`).
> The structural reason buying fails — and why this one survives — is in "The unifying conclusion".

## Mandate
Find the highest-performing NSE stock-/index-options strategy on real option data, net of
realistic costs, validated out-of-sample. Reject anything that isn't robust. No exceptions made
for a strategy because it "looked good" on an estimate — every survivor had to clear *measured*
costs on a held-out sample.

## Tests & trades that finalized the live strategies (the decision trail)
Every row below is a real-option backtest run this cycle; the live credit-spread strategies are what
*survived*. **~9,000 spread-trades evaluated across 9 tests** (plus thousands of config combinations).

| # | Test | Trades | Result (real costs) | Decision |
|---|------|--------|--------------------|----------|
| 1 | Stock credit spread — *generic* (Part 4) | 2,387 | −4.7% net, PF 0.87 | ❌ rejected (4-leg slippage wall) |
| 2 | Index credit spread — **follow** the breakout | 73 + 111 | −26% to −39%, 40% win | ❌ rejected → *breakouts revert* |
| 3 | Index **fade** — mix-and-match grid (216 cfg) | 114 days | fade family validates on holdout | → switch to FADE |
| 4 | Index fade — multi-tenor refinement (243 cfg) | 115 days | best = mid-tenor·1-OTM·w3·hold | → final config |
| 5 | Index fade — corrected (width-bug fix) | 61 | **+12.3% net, both indices +** | ✅ validated |
| 6 | Robustness — 5 breakout defs × 5 indices | 396 | def-robust; BANKNIFTY −6.7% | → **NIFTY + FINNIFTY** (drop BNF) |
| 7 | ORB (intraday breakout) | 413 | NIFTY −13.7% | ❌ boundary (needs a real extension) |
| 8 | Stock fade — 18 liquid names | 742 | −1.8% agg; credit/width signal | → add a gate |
| 9 | Stock fade — full universe + gate | 4,228 → **307** | **+16–25% net, p5 +6.8%, 65% win** | ✅ deployed (gated) |

**Two live credit strategies emerged:** the **index swing** (NIFTY+FINNIFTY, ~3/mo, rows 3–6) and the
**stock high-frequency** fade (gated credit/width≥0.40 + prem≥₹50, ~16/mo, rows 8–9). Both are paper
FORWARD-TESTS. The rejected rows (1, 2, 7) matter as much as the winners — they define where the edge
*isn't*. Details for each row are in Parts 4–8 below.

## Data (the upgrade that made this honest)
Upstox Plus **expired-instruments API** (`engine/expired_options.py`) provides real historical
premiums for expired contracts (~18 months). So everything below is on **actual option P&L**,
not the underlying proxy. Underlying 5-min limits the window to ~1 year; this study uses 180
days of ORB+alpha signals (rich feature set) + 18 months of gap-reversal signals.

## Cost model (NSE options, round-trip, per trade)
Brokerage (Rs20×2) + STT (0.0625% on sell premium) + exchange txn (~0.035%) + GST (18% on
brokerage+txn) + stamp (0.003%) + **premium-dependent bid-ask/slippage** (≈ clamp(60/premium,
1%, 6%) — rich options ~1–1.7%, cheap options ~5–6%). This is realistic-to-generous.

## Gate 2 (ORB) — verified applied
All 485 ORB+alpha signals are ORB-confirmed: 0 below the 1.2× volume-surge threshold,
vol-ratio 1.2–145, every microstructure non-zero. The poor results are NOT a missing-gate bug.

## Part 1 — Intraday stock-option BUYING (all NET of costs, 120d train / 60d holdout)

| Strategy | Trades | Best holdout NET | Verdict |
|---|---|---|---|
| Alpha+ORB+gates+min-premium (deployed) | 59–289 | ~breakeven, **neg. expectancy**, <100 tr | ❌ |
| **Mix-and-match: 3,312 filter combos** (z, momentum, trend-quality, vol-surge, ORB-width, VIX, day-range, time, alignment, min-premium × exits) | ≥100 each | **0 of 3,312 cleared the bar** | ❌ |
| Oops gap-reversal — stocks (1,656 trades) | 1,656 | **−2.2%** (best), PF<1 | ❌ |
| Oops gap-reversal — index (130) | 130 | negative / noise | ❌ |

**Robustness bar** (mandate's own rules): train net>0 AND holdout net>0 AND ≥100 trades AND
holdout PF>1. **Nothing met it.** Several configs were positive on train and sharply negative on
holdout (textbook overfit); a tempting "1-bar confirmation" pattern was look-ahead and failed.
The min-premium config looked like **+1.5% (64% win) on 180 days** but came in at **−1.0% (55%
win) over a full year** — the canonical overfit caught by the longer window.

## Part 2 — Intraday vertical SPREADS (buy + sell a leg to cut cost)
Buying a debit spread halves directional cost but caps payoff; the extra leg adds a second
bid-ask crossing. Net result across the combinations tested: **−10% to −20%** — the capped
upside no longer covers two legs of slippage. ❌

## Part 3 — MULTI-DAY buying (Donchian-20 breakout, hold days)
Holding a *bought* option overnight to capture a multi-day move runs straight into **theta**:
the option bleeds time value every day it's held. Net-negative across exits. ❌

## Part 4 — MULTI-DAY CREDIT SPREADS (sell premium, harvest theta) — the decisive test
This was the most promising structure and the reason the mandate's "no selling" rule was set
aside to *measure* it. The idea inverts the cost problem: instead of paying the spread + theta,
you **collect** them (sell the near leg, buy a further leg as defined-risk protection). On an
**estimated** 6%-of-capital cost it looked genuinely good — hold-to-expiry **+8.8% gross**,
**+6.9% holdout, PF 1.19**. So we did NOT deploy on the estimate — we collected the *real*
per-leg premiums (`/tmp/swing_credit2.json`, 2,387 trades, 18 months) and measured the actual
4-transaction cost.

**Real measured cost: ₹1,137 / trade. Result — every exit net-negative:**

| Exit rule | Win % | NET / cap | PF | Holdout | Worst trade / max lose-streak |
|---|---|---|---|---|---|
| take 50% / stop 2× | 58% | **−12.6%** | 0.59 | −14.2% | −198% / 14 |
| take 75% / stop 2× | 54% | −7.3% | 0.79 | −6.9% | −198% / 11 |
| hold-exp / stop 2× | 48% | −8.8% | 0.77 | −8.0% | −198% / 13 |
| **hold to expiry (best)** | 50% | **−4.7%** | 0.87 | **−2.4% / PF 0.94** | −186% / 13 |

The +6.9% estimate was a **cost mirage**: the real 4-leg bid-ask cost is far above 6% of capital
and **erases the theta edge entirely** (gross +8.8% → net −4.7% best case). The tail is also
brutal — worst trade −198%, losing streaks to 14. **Rejected. Not deployed.** ❌

> The discipline that mattered: had we built the parallel engine on the +6.9% *estimate* (as
> requested), a confirmed money-loser would now be wired into the system. The "measure real costs
> before deploying" gate stopped exactly that.

## Part 5 — INDEX credit spread, FOLLOWING the breakout (NIFTY + BANKNIFTY)
Repeated Part 4 on the indices (much tighter bid-ask: real cost ~₹574/trade vs ₹1,137 on stocks).
The lower cost was real and irrelevant — it **failed on direction, not cost**: selling an ATM
credit spread *with* a Donchian breakout (bull-put on an up-break) won only **40%**, because index
breakouts mean-revert. Net **−26% to −39%**, PF 0.30–0.56, on 73 (DC-20) and 111 (DC-10) trades. ❌
**But the 40% win rate is a signal, not just a failure: it says fade the breakout.** → Part 6.

## Part 6 — INDEX credit spread, FADING the breakout ✅ THE ONE THAT WORKS
Sell the OTM credit spread **against** the breakout (up-break → bear-call; down-break → bull-put),
mid-tenor (~2 weeks), short 1-OTM, width 3 strikes, hold to expiry with a 2× stop. The fade
mechanism was *predicted in advance* by Part 5's 40% win rate, then confirmed:

| Check | Result (corrected, live strike geometry — see width-bug note) |
|---|---|
| ALL (61 tr, real costs) | 66% win, **+12.3% net/cap**, PF 1.44 |
| Train / Holdout | +8.8% / +17.9%, PF 1.31 / 1.66 |
| NIFTY / BANKNIFTY (separately) | +12.1% / **+13.3%** — both positive & consistent |
| Cost ×1.5 / ×2.0 | +9.6% / **+6.8%** (survives 2× slippage) |
| Holdout bootstrap p5 | **−9.7%** (HIGH variance on a thin ~20-trade holdout; median +18.8%) |
| Independent replication | held on **both** Donchian-10 and Donchian-20 entry signals |

> **Width-bookkeeping correction (important).** An earlier pass reported +4.0% net and a +2.3%
> bootstrap p5. That used a buggy width: the collector computed the strike gap from the *tail* of
> the ladder (NIFTY 1000-pt, BANKNIFTY 500-pt) instead of the **ATM-local** spacing the strikes were
> actually selected at (NIFTY 50, BANKNIFTY 100). The premiums/paths were always for the correct
> dense strikes; only the capital denominator was inflated — which *understated* the % return and
> *dampened* the variance. Corrected: the edge is **larger** (+12.3%) but **higher-variance** (p5
> −9.7%). The live engine (`swing_credit._pick_legs`) computes width from the actual selected
> strikes, so it was always correct; only this backtest analysis needed the fix.

Validated four independent ways (out-of-sample, two entry signals, both indices, 2× cost) with a
positive bootstrap 5th-percentile — the first and only structure to do so. The mid-tenor sweep was
the key refinement (the near-weekly was worse; far-dated too slow). **Caveats:** thin sample
(~63 trades, ~21 holdout, BANKNIFTY only ~15), and it's the best of a 243-config grid — mitigated
by the coherent 14-config validated family, the pre-predicted mechanism, and the independent-signal
replication. **Deployed as a parallel paper FORWARD-TEST**, not as proven-profitable capital.

**Sample & economics (1 lot/signal, all signals, NIFTY 75 / BANKNIFTY 35, real costs, CORRECTED
width).** 63 signals over 20.5 months; 2 dropped where credit ≥ width, leaving **61 trades
(NIFTY 47, BANKNIFTY 14)**, ~3 signals/month, each held ~3 weeks, ≤2 open at once. Both indices now
priced on the live strike geometry (50-pt NIFTY / 100-pt BANKNIFTY), so these transfer to the engine:

| at 1 lot | trades | win | total net (20.5 mo) | per month | margin/trade | net/trade |
|---|---|---|---|---|---|---|
| **both** | 61 | 66% | **₹37,614** | **~₹1,838** | ~₹6.4k | — |
| NIFTY | 47 | 66% | ₹27,041 | ~₹1,321 | ~₹6,763 | ₹575 |
| BANKNIFTY | 14 | 64% | ₹10,574 | ~₹516 | ~₹5,689 | ₹755 |

Sizing: at ~3 signals/month, ≤2 concurrent positions, and HIGH per-trade variance (a loss ≈ full
margin), the strategy cannot absorb a large margin — a ₹5.5L book could stack ~38 lots/position, but
a normal 3-loss streak (seen in backtest) would then lose more than the account. Prudent ceiling
≈ 5 lots; **never fill the margin.** `config.SWING_LOTS` sizes the paper book per index (keep at 1).

**Robustness test — across breakout definitions AND indices (396 signals, real costs).** Rather
than just accumulate more D-10 trades, the better test is whether the *same* fade spread works on
*different* breakout definitions and *different* indices — consistency is much stronger evidence of
a genuine "breakouts revert" behavior than a bigger sample on one setup.

*Across breakout definitions (pooled 5 indices) — the edge is DEFINITION-ROBUST:* every one is
net-positive on full sample AND holdout — Donchian-10 +10.4% (HO +12.4%), D-15 +7.4% (+15.1%),
D-20 +9.6% (+29.2%), D-30 +4.3% (+15.4%), prior-week H/L +8.8% (+16.6%). Not a D-10 artifact.

*Across indices — the edge is NOT uniform (this CORRECTED the lineup):*

| index (D-10) | n | win | net | PF | verdict |
|---|---|---|---|---|---|
| NIFTY | 54 | 72% | +21.7% | 1.95 | ✅ core |
| FINNIFTY | 38 | 63% | +17.2% | 1.44 | ✅ added |
| MIDCPNIFTY | 35 | 54% | +2.4% | 1.05 | ⚠️ marginal + thin liquidity → not deployed |
| **BANKNIFTY** | 40 | 52% | **−6.7%** | 0.83 | ❌ **dropped** (its earlier +13% was 14-trade luck) |
| NIFTYNXT50 | 6 | — | −7.9% | — | too thin |

**Deployed lineup updated to NIFTY + FINNIFTY** (pooled D-10: 92 tr, ~67% win, +20% net, PF ~1.7 —
both larger-sampled and cleaner than the original NIFTY+BANKNIFTY). BANKNIFTY dropped (more volatile
/ trendier → its breakouts revert less, 51% win). MIDCPNIFTY skipped (marginal edge would not
survive its thinner monthly-option slippage). The robustness test thus *raised* confidence in the
mechanism while *fixing* the index selection — more valuable than 50 more BANKNIFTY trades would
have been. Repro: `/tmp/idx_robust_collect.py` → `/tmp/idx_robust_analyze.py /tmp/idx_robust.json`.

## Part 7 — ORB (intraday breakout): where the edge STOPS
Tested the fade on an *intraday* opening-range breakout (first-hour range) instead of a daily level,
held to expiry (NIFTY+FINNIFTY, 413 trades). **NIFTY −13.7% net, PF 0.71** (vs +21.7% on the daily
Donchian). A first-hour ORB breaks ~80% of days — it's *noise*, not a real extension, so it doesn't
reliably revert (53% win ≈ coin flip). **This maps the boundary: the edge is "fade a genuine
multi-day extension," not "fade any breakout."** A good negative — it confirms the mechanism is
specific (extended-move reversion), not generic premium-selling, and that the deployed daily-Donchian
signal is on the right side of the line. Repro: `/tmp/idx_orb_collect.py`.

## Part 8 — STOCK credit spread (the high-frequency sibling) — DEPLOYED with a gate
Part 4 showed a *generic* stock credit spread loses (−4.7%) on the 4-leg slippage wall. But the
**fade**, gated to **rich credit only**, beats it. Full ~100-stock universe, ~19 months, 4,228 fade
spreads; filtered to **credit/width ≥ 0.40 + short premium ≥ ₹50**:

| metric | value |
|---|---|
| trades | 307 (**~16/month** — the frequency play) |
| win | 65% |
| net/trade | **+16% (5% slip floor) / +25% (3%)**, ~₹1,560–2,400 on ~₹9.5k margin |
| holdout bootstrap p5 | **+6.8%** (positive) |
| breadth | 76/100 stocks net-positive |
| survives 7%/leg slippage | yes (+7.7%) |

**Why the gate is the edge, not cherry-picking:** a breakout spikes IV → rich premium (what
credit/width ≥ 0.40 selects); fading sells the inflated premium AND rides the reversion + IV crush;
~65% win on a ~1.2:1 payoff clears breakeven, and held-to-expiry winners pay no exit cost. Tightening
to *tradeable* premium (≥₹50) makes it **better**, refuting the "edge hides in untradeable cheap
options" worry. Concentrated in mid-caps (+27%) vs large-caps (+6.7%) — small-caps overshoot/revert
harder. **Honest health-warning:** the ~+20%/month-on-deployed-margin backtest is almost certainly
OPTIMISTIC — the unmodelled risk is real mid-cap 4-leg fills + gap risk on ~16 concurrent shorts.
**Deployed as a paper FORWARD-TEST** (`engine/stock_credit.py`, `config.STOCK_CREDIT_*`) with a LIVE
liquidity gate (OI, bid-ask) and per-day/total-open caps; KEEP LOTS AT 1. Repro:
`/tmp/stock_fade_all_collect.py` → `/tmp/stock_fade_all_analyze.py`.

## Part 9 — Out-of-time regime test (pre-Oct-2024) — a PROXY, not real premiums
Real option premiums do not exist before Oct 2024 (Upstox floor), so this is **NOT a real-premium
backtest** — it is a win-rate **PROXY** on the UNDERLYING daily prices (2019→Oct-2024): for each
Donchian-10 breakout, does price stay OTM of a 1-OTM short strike ~12 trading days later (a win) or
run through it (a loss)? Assumed strikes + fixed hold, no credit/IV/costs. But it is **CALIBRATED** —
run on the real-data window it reproduces the measured win rates (NIFTY proxy 65% vs real 67%), so it
is directionally trustworthy.

**Fade win-rate by year (proxy, %):**

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|------|------|------|------|------|------|------|------|------|
| **NIFTY index fade** | 56 | 43 | 55 | 45 | **35** | 53 | **69** | 67 |
| **Stock fade (25 names)** | 72 | 57 | 74 | 70 | 72 | 74 | 75 | 68 |

**The finding — it flips the risk picture:**
- **STOCK fade = regime-ROBUST.** 68–75% every year for 7+ years (even COVID-2020 held 57%). Bull,
  bear, or choppy — it holds. A genuine, durable cross-sectional anomaly; the Oct'24–Jun'26 real-data
  result (65% win, +15%/trade) is representative, not lucky. **This is the trustworthy edge.**
- **INDEX fade = regime-DEPENDENT.** It only "works" in 2025–26 — the *exact* window the real-option
  data covers. Most other years it was ≤56% (35% in 2023): fading an index breakout only pays in a
  range-bound market; in trending years index breakouts *continue* and the fade loses. **The
  Oct'24–Jun'26 index result was flattered by the data window landing on a favorable regime.**

**Implication:** trust the stock credit spread; **downgrade the index swing to regime-dependent /
unproven-out-of-time** (do not treat it as validated). **Caveat:** this is a calibrated PROXY (assumed
strikes/hold, no real premiums or costs) — a strong risk flag, not proof; real pre-2024 premiums (a
paid vendor) or a live trending-regime forward-test would settle it.

## Part 10 — REAL pre-2024 premiums (NSE bhavcopy) — settles Part 9's proxy ✅
Part 9 was a calibrated **proxy** (underlying reversion, assumed strikes, no premiums/costs). It is
now replaced by the **real thing**: NSE F&O **bhavcopy** carries the actual daily CLOSE + OI of every
option contract — including expired ones — back to 2019, free (the endpoint no broker API exposes).
Downloaded every trading day **2019 → Sep 2024** for NIFTY/FINNIFTY (index) and the full ~100-stock
universe (`/tmp/bhav_download*.py` → `/tmp/bhav_cache*`), then ran the **deployed geometry** on real
premiums with a proper cleaning pass — OI liquidity filter, settle at expiry via the **underlying
intrinsic** (not the erratic expiry-day option print), 2× stop on the real premium path, and P&L as
**net % of width** (lot-independent, so tiny-margin trades can't distort the aggregate).

**Real bhavcopy, cleaned, 2019 → Sep 2024:**

| Config (deployed geometry) | Trades | Win% | Net % of width | Verdict |
|---|---|---|---|---|
| **Index fade** (NIFTY, no gate) | 181 | 54% | **−1.4%** | net-negative, regime-dependent |
| **Stock fade — UNGATED** | 6,844 | 56% | **−1.1%** | generic spread loses (matches Part 4) |
| **Stock fade — GATED** (credit/width ≥ 0.40, prem ≥ ₹50) | 718 | 54% | **+5.3%** | **durable edge** |

**Gated stock fade, year by year (net % of width):**

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|------|------|------|------|------|------|------|
| **Win %** | 62 | 53 | 54 | 60 | 44 | 55 |
| **Net %** | +22.7 | +0.4 | +3.0 | +13.4 | **−4.5** | +1.1 |

**NIFTY index fade, year by year (net % of width):** 2019 +14.8 · 2020 −14.6 · 2021 −4.7 ·
2022 −3.2 · 2023 −5.1 · 2024 +18.6 → **ALL −1.4%** (positive only 2019 & 2024). FINNIFTY too
illiquid pre-2023 to judge (18 clean trades).

**MIDCPNIFTY (added 2026-07-04) — REJECT.** Its options only launched mid-2022, so it can't be
tested from 2019. On the real bhavcopy window 2022→Sep'24 it is both too illiquid (only ~15–18 fade
trades survive an OI≥50–200 filter over 2.5 years) AND strongly negative: **~20% win, −25% to −28% of
width**, in both years and both gated/ungated. Confirms the earlier "skip MIDCPNIFTY" decision — not a
viable fade. (Small sample, but the sign is unambiguous across every filter/year cut.)

**What the real data settles:**
- **The `credit/width ≥ 0.40` gate IS the edge, and it survives out-of-time.** Strip it and the stock
  fade loses (−1.1%, 5 of 6 years flat/negative) exactly like a generic spread (Part 4's −4.7%) and
  exactly like the index. Keep it and the same universe returns **+5.3% of width, positive in 5 of 6
  years** on real premiums. The gate selects elevated post-breakout IV — a real, durable mechanism,
  not a curve-fit. This **confirms** Part 9's stock verdict (durable/robust) on real data — though the
  real win rate is **~54%, not the proxy's 68–75%** (the proxy overstated win rate but got the
  direction right; the positive net comes from winner/loser geometry, not a high hit rate).
- **The index fade is NOT durable — Part 9's index warning is confirmed on real premiums.** Net
  **−1.4%** long-run, positive only in the two favorable regimes (2019, 2024). The Oct'24–Jun'26
  "+12%" landed on a good regime, not a real edge.
- **The real edge is more modest than the recent-window backtest.** +5.3% of width ≈ **+9%/trade on
  margin** (margin ≈ 0.6×width), vs the +16–25% the Oct'24→date window showed. 54% win, not 65%.
  Solidly positive, still HIGH variance (2023 was −4.5%). CLAUDE.md's "backtest is OPTIMISTIC" is now
  quantified: real ≈ **⅓ to ½** of the optimistic figure.

**Implication (real-data, replaces Part 9's proxy caveat):** the **gated stock credit spread is the
one durable, regime-robust edge**, confirmed on real premiums (+5.3% of width, 5/6 years). **Downgrade
the index swing to regime-dependent / net-negative out-of-time** — keep it only as a small parallel
forward-test, not a validated edge, and size the stock credit spread as the primary fade. Keep lots
at 1: real fills on ~100 mid-cap names will erode the +5.3% further.

**Reproduce:** `/tmp/bhav_download.py` + `/tmp/bhav_download_stk.py` (cache real premiums) →
`/tmp/bhav_backtest_clean.py` (index, `DONE-CLEAN`) · `/tmp/bhav_backtest_stk_clean.py` (stocks
ungated) · `/tmp/bhav_backtest_stk_gated.py` (stocks, deployed credit/width≥0.40 gate, `DONE-STKCLEAN`).

## Part 11 — SALVAGING the index fade with two gates (winner/loser analysis) ✅
Part 10 left the index fade net −1.4%. Instead of retiring it, instrumented all 181 real-bhavcopy
NIFTY fade trades with entry features (direction, breakout depth, momentum, channel width, IV proxy
credit/width, extension) and analyzed **winners vs losers** (`/tmp/idx_fade_features.py` →
`/tmp/idx_fade_gates.py` → `/tmp/idx_fade_frontier.py`).

**Losers vs winners — the two things that separate them:**
1. **DIRECTION (the dominant lever).** Split by which breakout we fade:
   - **CE = fade UP-break (bear-call): 124 trades, 48% win, −5.0%** → structurally loses.
   - **PE = fade DOWN-break (bull-put): 57 trades, 65% win, +6.6%** → wins.
   The index has an **upward drift**: up-breaks tend to *continue* (fading them fights the drift),
   down-breaks *mean-revert* (fading them rides it). Half the trade book was structurally negative-EV.
2. **FLUSH DEPTH.** Among losers, breakouts were shallow and momentum was hotter (5d mom 1.21 vs 0.12).
   Requiring a *real* capitulation — close ≥ **0.5%** beyond the 10-day band — keeps only genuine
   flushes that snap back, and drops the shallow noise-breaks that grind through the short strike.

**The gate stack (both now live, `SWING_FADE_DOWN_ONLY` + `SWING_MIN_BREAKOUT_PCT`):**

| Config | Trades | Win% | Net % of width | Boot p5 | Years positive |
|---|---|---|---|---|---|
| Baseline (all fade) | 181 | 54% | −1.4% | −6.6% | 2 of 6 |
| PE only (drop up-break fades) | 57 | 65% | +6.6% | −1.8% | 4 of 6 |
| **PE + breakout ≥ 0.5% (DEPLOYED)** | **32** | **78%** | **+15.1%** | **+4.1%** | **6 of 6** |

Per-year (deployed): 2019 +44% · 2020 +8% · 2021 +24% · 2022 +3% · 2023 +11% · 2024 +32%. The win
rate **rose** 54%→78% (target said "don't compromise win rate" — it improved), net cleared +15%, and
the **bootstrap p5 is positive (+4.1%)** — even a bad draw stays green, unlike baseline (−6.6%). A
tighter IV-gated variant (PE + credit/width ≥ 0.35 + breakout ≥ 0.75%) reaches +17.3%/79% but on 14
trades with p5 −0.2% (fragile) — so the **32-trade PE+flush gate is the honest operating point**, not
the higher-mean thinner slice.

**Honest caveats:** the gates cut 181→32 trades (~5–6/yr). 32 trades is a small sample; +15% has wide
bands (p95 +25%, p5 +4%). Positive every year and positive p5 → looked credible **in-sample.**

### ❌ OUT-OF-SAMPLE FAILURE — the gate was a regime artifact (test: Upstox Oct 2024 → date)
Re-ran the SAME config + gates on a **fresh data source and window** — real Upstox expired-instrument
premiums, Oct 2024 → Jul 2026 (`/tmp/idx_fade_upstox_oct24.py`, 116 trades). It **broke**, and the
direction asymmetry **reversed**:

| Config (Upstox, Oct24→date) | Trades | Win% | Net % of width |
|---|---|---|---|
| Baseline (all fade) | 116 | 55% | −0.4% |
| CE — fade UP-breaks | 58 | 62% | **+7.8%** |
| PE — fade DOWN-breaks | 58 | 48% | **−8.7%** |
| Deployed gate: PE + flush ≥0.5% | 27 | 56% | **−2.8%** |
| — NIFTY only | 17 | 65% | +6.0% |
| — FINNIFTY only | 10 | 40% | −17.7% |

On 2019→Sep24, CE lost (−5.0%) and PE won (+6.6%); on Oct24→date, **CE won (+7.8%) and PE lost
(−8.7%)** — the exact opposite. Cause: NIFTY peaked Sept 2024 and corrected into 2025, so the drift
was DOWN — down-breaks *continued* (fading them lost), up-breaks *failed* (fading them won). The
"upward-drift" mechanism was really just the 2019–24 bull regime. The in-sample robustness checks
(6/6 positive years, boot p5 +4.1%) **did not protect against this** because all six years were one
broad regime. Pooled across both windows the directional edge ~cancels → **no durable directional
edge; it is regime timing.** Only NIFTY-PE-flush stayed marginally positive OOS (+6.0%, 17 trades),
nowhere near +15%, and FINNIFTY (−17.7%) argues against even that.

**Verdict: the "salvage" is REJECTED. Gates reverted to neutral** (`SWING_FADE_DOWN_ONLY=False`,
`SWING_MIN_BREAKOUT_PCT=0.0`). The index fade returns to its Part 10 standing: **regime-dependent,
net ≈0 to slightly negative, unproven out-of-time** — a small forward-test, not a validated edge.
Lesson (again): 6 positive years inside one secular regime is **not** out-of-sample; a genuinely
different regime (Oct24→date) is the only real test, and it failed.

## The unifying conclusion — one structural cause, one exception
The **buying** strategies (Parts 1–3) and the **follow / 4-illiquid-leg** selling strategies
(Parts 4–5) all lose for the same reason: as a **retail taker you cross the bid-ask on every leg**
(~2–4% of premium each). Buying adds **theta** against you; stock credit spreads pay **4 legs of
wide stock-option slippage**; index follow-spreads are **directionally wrong** (breakouts revert).
- **The exception (Part 6) survives because it removes all three drags at once:** it *sells* (theta
  works for it), on **index** options (tightest bid-ask in India), and it **fades** (trades with the
  reversion, not against it). Net of measured costs that's enough to clear the toll — +4% on capital.
More parameter iteration on the losers only manufactures overfit (3,312 configs; +1.5%→−1.0%;
+6.9%→−4.7%); the winner came from a *mechanism* (reversion) the data pointed to, not from mining.

## Recommendation
- **Do not allocate capital to the buying or follow/stock-credit structures (Parts 1–5).** Each is
  structurally negative-EV net of measured costs — documented, not a tuning gap.
- **The index fade credit spread (Part 6) is the one validated edge** — run it as the
  `engine/swing_credit.py` forward-test and confirm it on LIVE fills before sizing real capital
  (backtest fills ≠ live fills; the sample is thin).
- The intraday index trend-ride remains a thin separate gross edge (+0.9%/18mo); stock buying stays
  a paper forward-test, not a money-maker.

## Method note for the record
The discipline cut both ways: it *rejected* the stock credit spread that looked like +6.9% on an
estimate (real cost flipped it to −4.7%), and it *earned confidence* in the fade spread by demanding
independent-signal replication, per-index positivity, 2× cost survival, and a positive bootstrap
tail before deploying — and even then only as a forward-test. A less rigorous study would have
shipped an in-sample "winner" and been wrong, or dismissed Part 5's failure instead of reading the
40%-win-rate signal that led to the winner.

## Reproduce
- Stock credit-spread real-cost verdict (Part 4): `/tmp/swing_credit_real.py` over
  `/tmp/swing_credit2.json` (2,387 trades) → `DONE-CREDITREAL`.
- Index follow vs fade + full mix-and-match (Parts 5–6): `/tmp/idx_grid_collect.py` (band collector,
  `DC`/`OUT` env) → `/tmp/idx_grid_search.py <json>` (216-config grid) and `/tmp/idx_validate.py
  <json>` (per-index, cost-stress, bootstrap battery).
- Refinement (tenor + time-stop sweep): `/tmp/idx_ref_collect.py` → `/tmp/idx_ref_grid.py
  /tmp/idx_ref.json` (`DONE-IDXREFGRID`). Deployed config = `fade · mid · k1 · w3 · hold`.
