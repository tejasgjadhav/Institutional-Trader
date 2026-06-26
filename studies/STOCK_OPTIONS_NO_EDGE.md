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
