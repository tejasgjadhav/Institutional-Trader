# HOURLY first-touch c/w≥0.40 entry vs the deployed CLOSE entry — stock credit fade (v2 UNION + v1)

_2026-07-24 · VALIDATION ONLY (paper) · the live engine was NOT changed._

## The question

The live engine evaluates credit/width **once**, at the 15:10 close, and fires the fade if c/w ≥ 0.40
(+ short premium ≥ ₹50). The user asked: if instead we entered at the **first intraday hour** c/w touches
≥ 0.40, we would catch **more** signals — e.g. OFSS touched 0.43 at ~14:45 then fell below 0.40 by 15:10,
so the close rule skipped it. **Does the hourly rule add EDGE, or just NOISE?**

Hypothesis (the *flip side*): hourly first-touch fills on **transient IV/premium spikes that revert**, on
stocks the close does **not** confirm, and often when the underlying is moving **toward the short strike** —
so more signals but **lower quality**.

## Method (apples-to-apples; only the entry differs)

Same breakout universe (`engine.config.UNIVERSE`, 100 stocks), same strikes (fixed off the breakout-day
**close** ATM — the engine geometry), same gate (c/w ≥ 0.40 & short prem ≥ ₹50), same forward **daily-close
exit walk** (TP / stop / intrinsic-at-expiry). Costs 2.5% slippage per leg + ₹20×4/lot. Two configs:

- **v2 UNION** — short 2-OTM, width 4, TP 50% of credit, stop 3×, UNION Donchian(5,10,15,20)≡D5, minDTE 10, reentry 3d.
- **v1** — short 1-OTM, width 3, TP 75% of credit, stop 2×, Donchian 10, minDTE 10, reentry 3d.

Two entry rules:

- **CLOSE** (= deployed): enter using the breakout-day **close** premiums if c/w ≥ 0.40.
- **HOURLY first-touch**: step the breakout day's intraday option premiums at hourly marks
  [09:15, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00]; enter at the **first** mark c/w ≥ 0.40 (+ prem ≥ ₹50);
  if no intraday mark fires, fall back to the close mark. So **HOURLY signals are a strict superset of
  CLOSE signals** — the difference between the two rules is exactly the **extra** signals hourly adds.

A hourly position is genuinely live intraday, so its exit walk includes the breakout-day close as its first
mark (a spike that reverts by close shows up as an adverse first bar). Data = real Upstox expired-instrument
premiums, **Oct'24→date** (the only era with intraday option data). 1-minute candles for intraday, daily
candles for the exit walk.

**Flip-side metric:** of the hourly *intraday* first-touch entries, the fraction that are **reverting
spikes** (c/w back < 0.40 by that day's close — the trades CLOSE skips), and how they perform vs the ones
that **held** (c/w still ≥ 0.40 at close, which CLOSE also catches).

## Results

### v2 UNION (21 months, Oct'24→date, single regime · 43 stocks fired)

| rule | n | sig/mo | win% | net %width |
|---|---|---|---|---|
| **CLOSE** (deployed) | 183 | 8.7 | **87.4%** | **+32.8%** |
| HOURLY first-touch | 253 | 12.0 | 84.6% | +25.7% |

- **CLOSE per year:** 2024 94%/+45%w (n17) · 2025 86%/+34%w (n104) · 2026 89%/+26%w (n62)
- **HOURLY per year:** 2024 90%/+42%w (n20) · 2025 82%/+26%w (n134) · 2026 87%/+20%w (n99)
- **EXTRA signals HOURLY adds that CLOSE skips** (close did not fire): **n=70 (3.3/mo) · 74% win · +4.5%w** — a *seventh* of the core edge.
- **FLIP-SIDE** (of 111 intraday first-touch entries): **63% are reverting spikes.**
  - reverting: n=70 · **74.3% win · +4.5%w**
  - held: n=41 · **78.0% win · +33.5%w**

### v1 (21 months · 56 stocks fired)

| rule | n | sig/mo | win% | net %width |
|---|---|---|---|---|
| **CLOSE** (deployed) | 331 | 15.8 | **72.2%** | **+16.9%** |
| HOURLY first-touch | 500 | 23.8 | 69.0% | +11.2% |

- **CLOSE per year:** 2024 80%/+29%w (n30) · 2025 71%/+16%w (n174) · 2026 72%/+14%w (n127)
- **HOURLY per year:** 2024 74%/+25%w (n39) · 2025 70%/+12%w (n266) · 2026 66%/+6%w (n195)
- **EXTRA signals HOURLY adds:** **n=169 (8.0/mo) · 61% win · −2.5%w** — these signals **LOSE money**.
- **FLIP-SIDE** (of 351 intraday first-touch entries): **47% are reverting spikes.**
  - reverting: n=164 · **61.6% win · −2.3%w** (loses)
  - held: n=187 · **63.6% win · +4.7%w**

### Cross-check (CLOSE reproduces the documented close-based book)

v2 CLOSE 87.4% / +32.8%w ≈ documented D5 200/87.5%/+31.5%w · v1 CLOSE 72.2% / +16.9%w ≈ documented
73.4%/+17.9%w. The close baseline is faithful, so the HOURLY delta is a real comparison, not a re-implementation artifact.

## Verdict — NOISE, not edge. Keep the CLOSE rule.

1. **The extra signals are marginal-to-negative.** The trades hourly catches that the close skips earn
   **+4.5% of width (v2)** — a seventh of the +32.8%w core — and **−2.5% of width (v1)**, i.e. they lose.
2. **They are, specifically, reverting spikes.** 63% (v2) / 47% (v1) of intraday first-touch entries had c/w
   back below 0.40 by the close. Head-to-head, reverting spikes vastly underperform held entries
   (v2 **+4.5%w vs +33.5%w**; v1 **−2.3%w vs +4.7%w**). The mechanism the user proposed is confirmed: a
   transient premium spike (short premium jumps as the underlying pushes toward the short strike / IV
   flares) that the close does not confirm is a *worse* trade, not an extra good one.
3. **Adding them dilutes the book.** Win rate falls 87.4→84.6% (v2) and 72.2→69.0% (v1); net/trade falls
   +32.8→+25.7%w (v2) and +16.9→+11.2%w (v1); and every per-calendar-year cell is worse under HOURLY.
4. **No free lunch on total edge, either.** Frequency roughly offsets the lower per-trade quality: monthly
   edge ≈ 2.85 (CLOSE) vs 3.08 (HOURLY) width-units for v2, and **2.67 vs 2.67 — identical — for v1**. So
   hourly buys ~40–50% more trades, a lower win rate, and higher variance/correlated-gap exposure for **no
   net gain**. The "held" intraday entries — the ones the close would have taken anyway — carry essentially
   all of the edge (v2 +33.5%w ≈ the +32.8%w close book).

## Honesty caveats

- **Single regime.** Intraday option premiums only exist Oct'24→date (~21 months). One regime; the per-year
  split is the only robustness check available. Treat magnitudes as indicative.
- **Small subsets are noise.** The v2 extra-signal / reverting cells (n=70) and the v2 held cell (n=41) are
  thin — read the *direction* (extra ≪ core), not the second decimal.
- **The gated fade strikes are thinly traded intraday — a real execution limit.** Only **30% (v2)** and
  **62% (v1)** of even the *close-fired* trades had **both** legs producing intraday trade candles. The
  c/w ≥ 0.40 gate structurally selects **rich-IV, wide-strike options on higher-priced underlyings**
  (OFSS, COFORGE, BAJFINANCE…), whose far-OTM fade shorts barely trade sub-day; the liquid low-priced names
  that *do* trade every minute (RELIANCE, ICICIBANK) sit at c/w ~0.22–0.29 and rarely reach the gate. The
  user observed OFSS's intraday c/w path via **live quotes**; historical expired-instrument candles record
  **trades only**, so for exactly the strikes the gate wants, the intraday path often cannot be reconstructed
  — and in live trading those strikes would be hard to fill on an hourly touch anyway. This *strengthens* the
  verdict: the extra signals are not just low-quality, they are frequently unexecutable.
- **The fetch bound is conservative toward hourly.** Intraday was fetched only when the close c/w ≥ 0.30 &
  prem ≥ ₹40 (a band around the gate). A breakout that spiked ≥0.40 intraday yet closed below 0.30 (a deeper
  reverter, likely *worse*) is excluded — biasing the result *toward* hourly. Hourly still loses the quality
  argument, so the conclusion is robust.

## Reproduce

```
studies/ndte/hvc_probe.py       # counts breakouts (sizing the fetch)
studies/ndte/hvc_backtest.py    # fetch + both rules + flip-side, resumable/cached/checkpointed
studies/ndte/hvc_report.py      # the tables above (reads /tmp/hvc/hvc_results.json)
```

Needs `UPSTOX_ANALYTICS_TOKEN` in `.env`. Caches under `/tmp/hvc/{daily,intra,under}`; the API throttles
hard, so the fetchers use retries + backoff and the driver checkpoints every 3 stocks (resumable).
REPORT-ONLY — no engine tunable was touched.
