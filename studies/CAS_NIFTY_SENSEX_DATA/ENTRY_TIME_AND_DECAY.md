# Call-side decay by time of day, and the entry-time sweep to an auction exit

> ## ⚠ CORRECTION (2026-08-06, same day) — Question 1's auction figure was WRONG
>
> The −71.8 residual below was computed against the **index**, and the index is not a usable
> underlying after 15:15. It freezes at its last continuous value and then prints the auction
> equilibrium as a single tick at 15:29. NIFTY 3-Aug held 24573.35 flat from 15:15 through 15:28,
> then printed 24774.30 — while the call traded 64.70 → 78.34, about 14 points. The forward
> implied by put-call parity on the recorded CE/PE pair was **24583.7**, i.e. the index print sat
> **190 points above where derivatives were actually priced**. On 4-Aug and 5-Aug the auction print
> did agree with the forward (24612 vs 24615; 24613 vs 24625), so only 3-Aug's close is spurious.
>
> Redone against the parity forward (`scratchpad/tv_close.py`), ATM time value in the close window
> falls from 100% at 15:00 to **83% at 15:30**, recovering to 88% by 15:40 — about **−21 premium
> points** on average excluding 0DTE, not −72. Decay in this window is real but roughly a third of
> what was reported.
>
> **Unaffected:** every P&L number in this study, and the whole of Question 2. Those were computed
> from traded option premiums and never touched the index. The entry-sweep conclusion stands.
> **Affected:** the Question 1 residual table, the claim that "the whole day's bleed lands in the
> auction window", and any narrative describing 3-Aug as a +201-point close.

**Window:** 3, 4, 5 Aug 2026 (Mon–Wed) · NIFTY + SENSEX · 6 index-days, one of them 0DTE.
**Data:** 15-min bars. NIFTY 3/4-Aug from the expired-instruments API (4-Aug weekly), everything
else from the live historical feed. Strike band covers each day's full range; the "ATM call" is
re-picked at every entry time off the spot at that time.
**Run:** `scratchpad/fetch15.py` → `c15.json` → `decay.py`.

## Question 1 — when is call-side time decay minimum?

Measured as the **residual**: the premium change with the delta-explained move stripped out.
Black-Scholes IV solved per bar from the traded premium, r = 6.5%, delta = N(d1). Residual =
ΔC − Δ·ΔS. Negative = the call bled beyond what spot explains.

| bucket | all 6 sessions | excl the 0DTE session (5) |
|---|---:|---:|
| 09:15–09:30 | +108.8 | +126.0 | ← **artifact, discard** |
| 09:30–15:15 (23 buckets) | −5.6 … +9.1 | −5.2 … +10.6 |
| **15:15–close (auction)** | **−58.4** | **−71.8** |

**Decay is not spread through the day. It is flat noise from 09:30 to 15:15 and then the whole
day's bleed lands in the closing auction window.** The auction bucket is 7× the largest intraday
bucket. No intraday bucket is distinguishable from zero at this sample size — the residual there
is dominated by IV drift, not theta.

Per-session, the 15:15→close residual:

| session | DTE | strike | 15:15 | close | Δspot | delta | explained | **residual** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NIFTY 3-Aug | 1 | 24550 | 70.80 | 78.34 | +201.0 | 0.58 | +116.50 | **−108.96** |
| NIFTY 4-Aug | 0 | 24450 | 75.55 | 164.85 | +151.5 | 0.53 | +80.67 | +8.63 |
| NIFTY 5-Aug | 6 | 24550 | 179.20 | 158.05 | +54.5 | 0.55 | +29.99 | **−51.14** |
| SENSEX 3-Aug | 3 | 78700 | 343.80 | 339.25 | −38.1 | 0.51 | −19.48 | +14.93 |
| SENSEX 4-Aug | 2 | 78300 | 384.35 | 363.90 | +104.4 | 0.53 | +54.88 | **−75.33** |
| SENSEX 5-Aug | 1 | 78500 | 379.50 | 281.50 | +79.1 | 0.51 | +40.30 | **−138.30** |

4 of 5 non-expiry sessions bled hard. The one exception (SENSEX 3-Aug) is the only session where
spot **fell** into the close.

**The 09:15 artifact.** The opening-auction print is recorded as the 15-min bar's open and lands
at the bar's low. SENSEX 3-Aug: index opened 78883 and closed the bar at 78638, −245 points, while
the call printed 198.30 → 264.25, *up* 66. Same shape on SENSEX 5-Aug (open == bar low both days).
That print is not transactable. Discard the 09:15 decay bucket **and** the 09:15 row of the sweep.

## Question 2 — buy the ATM call at time T, sell into the auction. Which T gains?

Exit = the closing print. Gross P&L per 1 lot, no costs. NIFTY lot 65, SENSEX lot 20.

| entry | NIF 3 | NIF 4 (0DTE) | NIF 5 | SEN 3 | SEN 4 | SEN 5 | avg ex-0DTE | win |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 09:15 | 939 | −2,899 | −98 | 1,113 | −2,065 | −1,149 | −252 | 2/5 | ← artifact
| 10:15 | −110 | −1,970 | −2,509 | −1,075 | −2,964 | −3,170 | **−1,966** | 0/5 |
| 11:00 | −432 | −861 | −2,824 | −1,148 | −2,424 | −3,187 | −2,003 | 0/5 |
| 12:30 | −695 | +4,056 | −978 | −1,321 | −900 | −1,864 | −1,152 | 0/5 |
| 13:45 | −166 | +8,145 | +777 | −876 | +676 | +45 | **+91** | 3/5 |
| 14:15 | +81 | +7,156 | +517 | −756 | +144 | +130 | +23 | **4/5** |
| 15:15 | +490 | +5,804 | −1,375 | −91 | −409 | −1,960 | −669 | 1/5 |

**No entry time gained, on any normal session.** Excluding the 0DTE day, the best entry in the
whole grid is 13:45 at **+₹91/lot** and 14:15 at **+₹23/lot** — indistinguishable from zero, and
both negative after the ~₹55–65 round-trip cost. The worst window is 10:15–11:15, about −₹2,000.

14:15 is the trap: it won **4 of 5** sessions and still averaged +₹23, because the single loss
(SENSEX 3-Aug, −₹756) cancels four small wins. High hit rate, no edge.

**The only session that paid was expiry day.** NIFTY 4-Aug 0DTE gained from every entry 11:45
onward, peaking +₹8,145 at 13:45. That is gamma on a 151-point close-side move with the strike
13 points away, not a repeatable entry-timing effect.

## What this says

Buying calls to hold into the auction was a losing trade on all five non-expiry sessions
regardless of entry time. The mechanism is visible in Question 1: the position accrues no
systematic decay advantage anywhere in the day, then surrenders 50–140 premium points in the
final 15:15→close window — the same window the earlier 15:15→15:36 analysis flagged.

If there is a trade here, the sign points at being **short** premium into the auction rather than
long, and the four-of-five consistency of the auction bleed is the thing worth testing. That is a
different strategy with different risk (short gamma into a close, on 0DTE it is the 4-Aug payoff
in reverse) and nothing here sizes or validates it.

## Limits

- **5 usable sessions.** This is the entire CAS regime to date. It is a hypothesis, not a result.
- Gross P&L; no spread modelled, and spreads widen in the auction window.
- The residual is decay **plus** IV change. Only the auction bucket is large enough to read through
  the noise; the intraday buckets should be treated as zero.
- 15-min granularity. The 1-min and 5-min Upstox feeds lag ~1 session so they could not cover 5-Aug
  at the time of the run.

---

# Question 3 — when is ATM time value minimum?

Time value = premium − intrinsic. For the ATM call that is nearly the whole premium.
Intraday uses the index (valid while it trades continuously) with the ATM strike re-picked each
bar. The close window uses the **parity-implied forward** and a fixed strike, per the correction
above. The two panels are different measures — read each on its own, do not splice the percentages.

## Panel A — 09:15 to 15:15, PER INDEX (parity forward, `scratchpad/intraday_tv.py`)

Superseded the first aggregate version. Now uses the **put-call-parity forward** at every bar
rather than the index, so "at the money" is measured against what the options are priced off, not
against spot. This also fixes the 09:15 opening-print artifact: the stale print biases the call and
put equally, so it cancels in `C − P` and the 09:15 reading becomes usable.

ATM time value as % of that session's own 09:30, non-expiry sessions only
(NIFTY n=2: 3-Aug 1D, 5-Aug 6D · SENSEX n=3: 3/4/5-Aug, all 6-Aug expiry):

| time | NIFTY | SENSEX | | time | NIFTY | SENSEX |
|---|---:|---:|---|---|---:|---:|
| 09:15 | 99% | 95% | | 12:30 | **105%** | 106% |
| 09:45 | 95% | 99% | | 12:45 | 101% | **111%** |
| 10:15 | **91%** | 98% | | 13:15 | 101% | 109% |
| 10:45 | 96% | 100% | | 14:00 | 98% | 108% |
| 11:15 | 96% | 100% | | 14:45 | 102% | 108% |
| 11:45 | 96% | 105% | | 15:00 | 93% | 102% |
| 12:00 | 102% | 105% | | 15:15 | **91%** | 104% |

| | min | max | 09:30 → 15:15 |
|---|---|---|---:|
| **NIFTY** | 15:15 = 91% (also 10:15 = 91%) | 12:30 = 105% | **−9pp** |
| **SENSEX** | 09:15 = 95% | 12:45 = 111% | **+4pp** |

**The two indices do not behave the same, and neither decays monotonically.** NIFTY drifts down
about 9pp across the session with a morning trough at 10:15 and its low at 15:15. SENSEX does the
opposite — its ATM time value *rose*, finishing 4pp above the 09:30 level.

**Both share a midday peak at 12:30–12:45.** That is almost certainly not a clock effect. It is
driven by the sessions where the index actually moved: SENSEX 5-Aug (770-point range) ran
+25% by 13:00, NIFTY 5-Aug +14%, while the quiet SENSEX 3-Aug fell 4% and NIFTY 3-Aug fell 11%.
The swings here are realised-vol repricing, not time of day.

**Practical reading, with n=2 and n=3 it is barely more than an anecdote:** there is no reliable
intraday decay to harvest between 09:15 and 15:15. The ±10% swings dwarf any theta, and their sign
tracks whether the index trended that day.

## Panel B — 15:00 to the close (parity forward, fixed strike)

As % of that session's 15:00 time value:

| session | DTE | 15:00 | 15:05 | 15:10 | 15:15 | 15:20 | 15:25 | **15:30** | 15:33 | 15:36 | 15:39 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NIFTY 3-Aug | 1 | 100% | 114% | 114% | 110% | 99% | 105% | 84% | 80% | 86% | 83% |
| NIFTY 5-Aug | 6 | 100% | 95% | 88% | 90% | 78% | 86% | 76% | 77% | 81% | 81% |
| SENSEX 3-Aug | 3 | 100% | 106% | 104% | 106% | 106% | 102% | 97% | 95% | 98% | 100% |
| SENSEX 4-Aug | 2 | 100% | 103% | 102% | 86% | 87% | 85% | 82% | 86% | 87% | 87% |
| SENSEX 5-Aug | 1 | 100% | 101% | 103% | 66% | 85% | 94% | 78% | 83% | 88% | 90% |
| **AVG (excl 0DTE)** | | **100%** | **104%** | **102%** | **92%** | **91%** | **94%** | **83%** | **84%** | **88%** | **88%** |
| NIFTY 4-Aug | **0** | 100% | 93% | 100% | 84% | 65% | 16% | 1% | 1% | 0% | 0% |

**Minimum at 15:30**, at 83% of the 15:00 level — then it *recovers* to 88% by 15:40. In points,
15:00 → close averages **−21** excluding 0DTE (NIFTY 3-Aug −7.9, NIFTY 5-Aug −26.4, SENSEX 3-Aug
+1.0, SENSEX 4-Aug −41.4, SENSEX 5-Aug −29.3).

The 15:30 dip and the recovery into 15:40 are worth flagging as **not yet explained**. Candidates:
the cash close striking at 15:30 while derivatives run on, a genuine vol re-mark once the auction
prints, or simply thin two-sided quotes at that moment. Five sessions cannot separate these.

## Answer

ATM time value is at its minimum **at 15:30**, and effectively flat everywhere from 09:30 to 15:00.
There is no intraday "cheap window" — the ATM premium does not bleed during the day. Everything
that happens, happens in the last half hour, and it is a ~17% dip that partly reverses by the close.

The 0DTE row is the exception and behaves nothing like the others: it holds ~100% until 15:10, then
collapses 84% → 65% → 16% → 1% between 15:15 and 15:30. On expiry day the last twenty minutes take
everything.
