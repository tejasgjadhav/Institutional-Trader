# The stale-bar incident — six weeks of T-1 signals, found, fixed, verified (5–6 Aug 2026)

The most consequential bug in this repo's history: **the daily stock-credit scan never read the
current day's close.** Every live signal from June onward was computed on the *previous* session's
close, so the system faithfully executed a strategy nobody had backtested — fade yesterday's
breakout today. This documents the discovery, the proof, the fix, and the first verified session.

## The defect

All three books took today's price as `df["Close"].iloc[-1]` from the Upstox **daily** endpoint.
The code is correct-looking; the defect is in the feed: **Upstox publishes no current-day daily bar
during the session** (at 18:15 on 4-Aug it still carried nothing for 4-Aug). So `iloc[-1]` silently
returned yesterday's close, which was then compared against a one-day-shifted Donchian band.

No scan time could fix this — 15:10, 15:36, any hour reads the same stale bar. The 3-Aug retiming
(15:10 → 15:36), justified as "+44% more breakouts on the official close", therefore changed nothing
in the running system: the counterfactual it priced never ran.

## The proof

**GRASIM (the user caught it, from the trade, before any log did):**

| | close | |
|---|---|---|
| Mon 03-Aug | 3,260.00 | breaks the D10 high 3,195.10 → CE breakout. **The signal.** |
| Tue 04-Aug | 3,138.00 | −3.74%. NOT a breakout (inside band [3,066, 3,260]). **We fired the bear call here.** |

A bear call, issued the day after the up-move, into a stock that had just fallen — "why on earth a
bear call?" was the question that broke the case open.

**The whole book reconstructs the same way.** Donchian verdicts recomputed for all 19 v1+v2 positions
ever booked, on entry day T and on T-1: **PREV-DAY only 14 · both days 5 · SAME-DAY only 0.** Every
trade is consistent with a T-1 signal; none requires T. The live record (15 closed, 11W/4L) is a
record of the *delayed* strategy and must not be compared to the 84–87% backtest figures.

**Why every bug sweep missed it:** the defect was in the DATA, not the code; every verification ran
after hours, when the bar HAD landed and matched bhavcopy; and the decisive evidence ("18:15, no
same-day data") was recorded in a study note without being connected to the scan path. Lesson now
binding in CLAUDE.md: a bug check is four layers — DATA at the real read-time, TIME, INVARIANTS,
UI — and a code-only sweep is never reported as "no bugs".

## The fix (all deployed 5-Aug, commits on both remotes)

1. **`data_utils.todays_close(ticker) -> (price, source)`** — reads the intraday 5-min series first
   (the only source carrying today during the session; the auction print lands in its last bar),
   daily bar only if dated today, else `(None, "stale")`. The Donchian band dropped its `.shift(1)`
   because `prior` now excludes today explicitly (verified arithmetically identical).
2. **Freshness guard** — a book that cannot get today's close SKIPS the name and logs a WARNING.
   It can never fall back to a prior session.
3. **Direction-vs-move audit** — a LONG break must close above yesterday's close, SHORT below. This
   is an *invariant*, not a filter: the Donchian window includes yesterday, whose high ≥ its own
   close, so a genuine break can never contradict the day's move — verified on 1,182 real breakouts,
   zero contradictions. A violation therefore proves bad data and suppresses the signal at ERROR.
4. **SIGNAL→LIVE on both UI surfaces** — every watchlist row and PM credit spread shows the price the
   signal was computed on next to the live price (amber ≥0.5% gap, red ≥1%), with an AUC tag when
   that price is the closing-auction value. A stale signal can no longer look like a fresh one.
5. **Schedule** — watchlist 15:17 (UI preview), **digest 15:31** (post-auction, final strikes — the
   15:17 message had staged wrong strikes on 4/14 names), scan 15:36, place by 15:40.

## First corrected session — verified against the exchange (6-Aug)

- **HAL v1 BEAR_CALL 4950/5100** (the day's only call): signal price **4,920.00 = official bhavcopy
  ClsPric 4,920.00, EXACT**. Breakout genuine on the day (+4.28% over the D10 band); direction right
  (HAL +5.92% on the day — the bear call arrived ON the up-day, the exact GRASIM inverse). The scan
  read the auction print: bars 15:10/15:15/15:20 frozen at 4,934, last bar 4,920 = the crossing.
- **15:31 watchlist vs bhavcopy: 19/20 exact.** One thin name (NAVINFLUOR, −0.36%) sampled before its
  auction print landed — the known edge of the system, matching UBL/ATUL on 3–4 Aug. No trade
  affected.
- **The stale guard fired in production** (RELIANCE, 15:36:40 — transient feed miss, skipped rather
  than scanned stale).

## Standing consequences

- **The forward record restarts 6-Aug-2026.** Prior live trades tested a different strategy.
- The 2019–2026 backtest series and the live scan now read the same field (official close; OOS
  Upstox closes verified ≡ bhavcopy 113/113). Alignment of inputs is done; alignment of RESULTS is
  what the forward record measures.
- Open, cheap to test: what the T-1 delay actually cost (both backtest legs enter at the option's
  daily close — `sp[1]` instead of `sp[0]` replays the delayed variant over the full history).
- Residual risk, measured daily by the session observer: the auction match closes at a random
  instant 15:28–15:30; if the print ever reaches the feed after 15:36, the scan would read the
  frozen 15:15 price (today's, so the stale guard passes). Observed margin ~5–7 min, n=2 sessions.
