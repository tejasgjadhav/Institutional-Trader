# Why live swing calls fell about 4× below the backtest: the strike grid, the side mix and IV (9-Oct-2026)

**Question (user, 8-Oct-2026, step 3 of SIGNAL_DROUGHT_LOW_VIX.md):** At the same India VIX, the backtest
took about 12 stock-credit trades a month in Jul–Dec 2025, and live has taken about 3 a month since
6-Aug-2026. What causes the gap?

**Answer:** The cause is in the market prices, not the code. Two things carry most of it. First, NSE ran
coarser strike ladders in the Aug and Sep 2026 series, so the short leg sat farther out of the money.
Second, breakouts turned mostly downward, and bull puts clear the c/w gate far less often than bear calls.
Lower implied volatility adds to that, especially against Jun–Jul 2026. Research only; nothing was
deployed. Scripts and outputs are in research/iv_gap/ (local only, research/ is not uploaded).

## The replica matches both the backtest and live

The same gates and the same close-price construct were run on NSE bhavcopy. The bhavcopy close equalled the
Upstox expired-candle close on 99.7% of 11,472 legs. The panel reproduced the backtest's c/w on 96% of the
70 trades from Jul–Dec 2025.

| Window | v1 | v0 | v2 | Candidates per 21 days | × 0.53 trade ratio |
|---|---|---|---|---|---|
| A: Jul–Dec 2025 | 14.0 | 6.5 | 2.0 | 22.5 | 11.9 (the backtest booked 11.8 a month) |
| J: Jun–Jul 2026 | 34.0 | 22.8 | 4.0 | 60.8 | about 32 |
| B: 6-Aug to 16-Sep 2026 | 3.0 | 0.75 | 2.25 | 6.0 | 3.2 (live took 3.3 a month) |

The drop is a cliff at the August 2026 series. Candidates per 21 days were 67 in June and 62 in July, then
8.4 in August and 1.9 in September. v2 shows no gap; the whole gap sits in v1 and v0.

## Factor by factor

1. **Breakouts did not fall.** The union scan found 24.1 a day in A and 24.6 in B. Donchian-10 breakouts
   were 16.5 and 18.7.
2. **The direction changed.** Bear calls were 50% of v1 candidates in A, 26% in B and 11% from 22-Sep to
   8-Oct. With both legs traded, a bear call passed v1's gate 6.9% of the time and a bull put 1.8%. Most of
   that gap is carry: the forward sits about 0.4% above spot, which adds about +0.02 c/w to a bear call and
   takes about −0.023 from a bull put. Put skew costs bull puts about another 0.01.
3. **The strike grid is the largest single factor.** The median strike step at about 18 days to expiry was
   1.32% of spot for the Sep-2025 series, about 1.04% for Oct–Dec 2025, 0.95–0.98% for Jun–Jul 2026, and
   1.21–1.23% for Aug–Sep 2026. Single names switch interval between monthly series. Example: LT used
   50-point strikes in Aug–Sep 2025, 10 and 20 in Oct–Dec 2025, 20 in Jun–Jul 2026 and 50 again in
   Aug–Sep 2026. The July 2026 ladder was finer than September's for 67 of 107 names. For the names that
   produced window A's passes, the step rose a median 22%. Lot sizes did not change. Why NSE changes the
   interval between series was not established.
4. **IV is a smaller factor against 2025, and a large one against Jun–Jul 2026.** ATM IV was 23.4% in A,
   27.0% in J and 22.6% in B. Against J, all 107 names were lower in B (median ratio 0.83).
5. **Days to expiry** fell from a median of 25 in A to 21 in B.

One number carries grid, IV and DTE together: **z = strike step ÷ (ATM IV × √T)**. v1's pass rate is
almost a function of z alone: 29–42% at z ≤ 0.10, 13–16% at 0.10–0.15, about 1.7% at 0.15–0.20, and about
0 above. z alone explains 68% of the drop from A to B and 86% of the drop from J to B.

## Decomposition (Shapley, candidates per 21 days)

| Factor | v1, A → B (14.0 → 3.0) | v0, A → B (6.5 → 0.75) | v1, J → B (34 → 3) |
|---|---|---|---|
| Strike grid | −4.0 | −2.9 | −13.7 |
| Side mix | −3.4 | −1.2 | −4.8 |
| Days to expiry | −2.0 | −1.0 | −0.6 |
| IV level | −1.5 | −0.9 | −11.8 |
| Both legs traded | −0.4 | −0.4 | −1.5 |
| Skew residual | −0.4 | −0.2 | −2.6 |
| Breakout-day IV lift | +0.2 | +0.1 | +0.5 |
| Breakout count | +1.2 | +0.1 | +3.0 |

Against H2 2025, the grid carries about 35–40% of the gap, side mix about 30%, DTE about 18% and IV about
13%. Against Jun–Jul 2026, grid and IV share the drop about equally. The forward and reverse orders differ,
and window B holds only 4 v1 passes, so the exact shares are medium confidence.

## What this means for the edge (important)

**The c/w gate does not select rich IV.** Within a z bucket, names that pass have the same IV/RV as names
that fail (1.10 against 1.10). What separates them is a lower z, the bear-call side (76% of passes against
54% of candidates) and a cheap long leg. With strikes chosen by ladder position, the 0.40 gate mostly
measures how fine the grid is, which side broke and how the wing is priced. It does not measure the "rich
post-breakout IV" the edge is said to rest on. Breakout-day IV was only 0–4% above each name's own normal
level, so there was no measurable post-breakout IV spike in any window.

This does not show the edge is false. The backtest's profits are real on its own data. It shows the
explanation of where the edge comes from is probably wrong, and that its frequency depends on how NSE sets
strike intervals.

## Checks on the backtest itself

- Close-price staleness at the 0.40 threshold: of 79 v1 passes from window A in the 0.35–0.50 band, 68 still
  clear 0.40 on last-trade prices and 52 of 75 at the next morning's open. A stale-wing signature appears in
  11% of passes and 31% of bull-put passes. Six of the 70 real backtest trades carry it, and all 6 won.
- The look-ahead from using expired ladders is negligible: 14.3 against 14.0 v1 candidates per 21 days.

## Live against bhavcopy in window B

Bhavcopy found 8 candidates where live took 5. Most of the difference is names already held (v1 held GRASIM
from 4-Aug and HAL from 6-Aug). Two are unexplained: LTM on 21-Aug (v2 at 0.427 on the close) and GRASIM on
7-Aug (v2 at 0.409). Rejection logging went live on 9-Oct, so such cases will now be recorded.

In the 22-Sep to 8-Oct tail, the drought eased as IV rose (VIX about 14). ZYDUSLIFE passed on 24, 25 and
28-Sep at 0.407–0.408. LTM passed on 23-Sep (already held) and on 7-Oct (taken). PIIND's 0.534 on 8-Oct is a
stale-wing artefact: the 2040 put closed at 22.95, almost level with the 2020 put at 22.80.

## Proposed next tests (not done, need IS and OOS both)

1. Choose the short strike by sigma distance or delta instead of by ladder position.
2. Measure strike distance from the forward (futures) price instead of spot, which removes the bull put's
   0.04 c/w handicap.

Caution: the backtest's profit may depend on near-the-money placement. A fixed-distance rule could raise
frequency and lower the edge, so both windows must be measured before anything changes.

## Caveats

Bhavcopy is missing for 14-Aug, 14-Sep, 17-Sep and everything after 16-Sep. The tail uses v1 legs only and
the auction close as spot. IV assumes a 6% rate and no dividends. Candidates were converted to trades with
window A's 0.53 ratio, not by re-running the position rules. API use: 775 requests, 0 failures, 0 HTTP 429,
12:22–12:55 IST on 9-Oct, at least 2 s apart.
