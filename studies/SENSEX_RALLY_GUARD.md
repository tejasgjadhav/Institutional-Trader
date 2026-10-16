# SENSEX 0DTE: limiting the cost of a big intraday rally (16-Oct-2026)

**Question (user, 16-Oct-2026):** SENSEX moved about 1,500 points in a day four times in two years, and
15-Oct-2026 cost the book a full-width loss (−Rs10,524). How can we avoid such moves?

**Verdict: nothing deploys yet.** No rule known at 09:16 picks out these days. Narrower wings cost
more than they save. A stop 0.5% beyond the short strike is the only candidate, and it is a
trade-off for the user, not a pass. The test is re-run once Upstox lists the 15-Oct expiry.
Pre-registration: research/rally_guard/prereg.json. Script: studies/ndte/ndte31_rally_guard.py.

## How often it happens (Oct-2024 to 15-Oct-2026, 505 trading days)

- 10 days moved 1,500 points or more from the open: 5 up and 5 down. Only 2 were Thursday expiries.
- A bear call is hurt only by a rise. On 95 expiry days SENSEX rose 1,000+ points from the open 6 times
  and 1,200+ points 3 times (22-Nov-2024, 2-Apr-2026, 15-Oct-2026). Those 3 are the book's biggest losses.
- India VIX the evening before was 13–16, which is normal, on 4 of the 6 days. The opening gap was
  small on 5 of 6. 8 of the 11 losing trades came after the market had fallen over the prior 4 days.
- On 15-Oct SENSEX was 73,166 at 09:16 and 73,771 by 10:15. Most of the move came in the first hour.

## Results (Oct-2024 to 8-Oct-2026, Rs per lot after costs; 15-Oct not yet listed by Upstox)

| Variant | n | Win | Total | Worst | Max DD | Oct-24 to Sep-25 | Oct-25 on |
|---|---|---|---|---|---|---|---|
| Deployed (wing ~600) | 94 | 89.4% | +31,862 | −10,628 | −14,180 | +12,858 | +19,004 |
| Wing 500 | 99 | 88.9% | +21,826 | −9,064 | −14,435 | +7,360 | +14,466 |
| Wing 400 | 102 | 87.3% | +16,284 | −7,206 | −13,181 | +4,598 | +11,686 |
| Wing 300 | 102 | 87.3% | +8,549 | −5,384 | −10,488 | +2,041 | +6,508 |
| Wing 200 | 103 | 84.5% | −1,563 | −3,637 | −9,080 | −1,832 | +269 |
| Stop at the short strike | 94 | 68.1% | −2,811 | −4,236 | −14,255 | −1,163 | −1,649 |
| Stop at short + 0.25% | 94 | 84.0% | +24,168 | −5,764 | −12,760 | +18,152 | +6,016 |
| Stop at short + 0.50% | 94 | 87.2% | +26,561 | −7,316 | −13,457 | +13,581 | +12,979 |
| Skip after a 4-day rise ≥ 1.5% (report only) | 81 | 87.7% | +17,813 | −10,628 | −16,935 | +3,746 | +14,067 |

- **Narrower wings fail.** Every narrower wing earns less, and NIFTY moves the same way (wing 150:
  +23,322 against +30,541 deployed).
- **A stop at the short strike fails badly.** SENSEX often trades through the strike and falls back.
- **Skipping after a rally fails.** Without 15-Oct it costs Rs14k, because the days it skips were mostly winners.
- **The stop at short + 0.5% is the only candidate.** It keeps 83% of the total and cuts the worst
  trade by 31%. It fails the pre-registered rule on the total and on the recent half (−Rs6.0k).
- **15-Oct under the stops (estimate from the index path only):** SENSEX crossed the short strike at
  09:47, short + 0.25% at 09:59 and short + 0.5% at 10:15. Option prices for that day are not
  available yet, so the exit cost is not measured. Re-run when Upstox lists the 15-Oct expiry.

## Part 2: an exit rule that caps the loss (ndte32, pre-registered in research/rally_guard/prereg32.json)

The user's goal changed to "we don't want zero loss but cap it". 31 exit rules were tested on the
cached 1-minute data: a rupee cap, a velocity exit, a confirmed breach (M minutes in a row) and a
time-gated breach. The rule was picked on Oct-24..Sep-25 only and tested on Oct-25 onwards.

**Pre-registered result: FAIL.** The H1 pick was the Rs5,000 rupee cap. It holds the cap in both halves
(worst −Rs5,840 and −Rs5,941), but out of sample it kept only Rs5,170 of the deployed Rs19,004.

The cap costs money in every form. These are the useful points on the curve (SENSEX, all 94 trades to 8-Oct):

| Rule | Total | Worst | Max DD | NIFTY total / worst |
|---|---|---|---|---|
| Deployed, no exit | +31,862 | −10,628 | −14,180 | +30,541 / −11,472 |
| Rupee cap Rs5,000 | +23,802 | −5,941 | −16,059 | +25,908 / −6,169 |
| 15 minutes in a row above the short strike | +24,528 | −4,596 | −7,636 | +16,828 / −6,700 |
| Above short + 0.25% before 14:00 | +23,950 | −5,764 | −12,760 | +18,491 / −6,028 |
| Above short + 0.5% before 14:00 | +31,744 | −7,316 | −10,027 | +26,109 / −8,282 |

- Capping through an exit rule costs about a quarter of the SENSEX profit. Capping through a narrower
  wing costs about three quarters (wing 300: worst −Rs5,384, total +Rs8,549).
- 15-Oct is not in these totals yet. Deployed loses Rs10,524 on it. Every rule above would have exited
  that morning, so the real gap to deployed is smaller than the table shows.
- The rupee cap is the only rule that caps both books at about Rs6,000 for a modest NIFTY cost (−15%).

## Part 3: deployed, and the leg-out idea tested (16-Oct-2026)

**Deployed:** the Rs5,000 rupee cap on both 0DTE books, closing both legs, with a Telegram EXIT alert
(`ZERO_DTE_LOSS_CAP_RS`, commit 34bba00, offline test studies/ndte/test_loss_cap.py). The user chose it
as a cap, knowing it failed the pre-registered profit test.

**Leg-out, rejected (ndte33).** The user asked whether, at the cap, we could buy back only the sold
option and hold the bought one until the close.
- On SENSEX it earns more in total (+Rs28.6k against +Rs23.8k for closing both), but the worst trade
  goes back to −Rs9.9k. That is almost the uncapped loss, so the cap stops working.
- The reason is that the index reversed after 6 of the 8 cap exits. On those days the held call lost
  its value, and that loss landed on top of the buy-back.
- On NIFTY it is worse on both counts: Rs1.1–1.5k less in total, and a worse worst trade (−Rs7.5k).
- Holding the long call after the buy-back is a bet that the rally continues. It won 2 times in 8 on
  SENSEX and once in 5 on NIFTY.

## Part 4: raising the net % of margin (ndte34) and the opening 7 minutes (ndte35), 16-Oct-2026

Return is measured as net rupees a month divided by the margin one trade blocks (its max loss).
Pre-registrations: research/rally_guard/prereg34.json and prereg35.json.

**The 95% early profit close costs money.** It was deployed on 4-Aug-2026 without a measurement. Closing a
spread that is almost worthless pays a full set of exit charges to save a few rupees of premium.
- NIFTY with the Rs5,000 cap: 9.0% a month with the early close, 12.7% without it. The worst trade is
  the same (−Rs5,920). It wins in both halves (5.1% → 9.2% and 12.4% → 15.8%). **Passes.**
- SENSEX with the cap: 9.1% → 10.2% overall, but the recent half falls from 3.7% to 1.4%. **Fails the
  both-halves rule.** 15-Oct is still missing from this data.
- Booking earlier (at 70% or 50% of the credit) is worse on both books.

**Selling the put side as well on SENSEX (condor) is worse** at every setting (best 10.4% against 14.9%).

**The opening 7 minutes (09:15–09:21).**
- Phase A, NIFTY index only, 2022-01 to 2024-07, 105 expiries: entering at 09:22 did not lower the
  breach rate (14.3% against 13.3% at 09:16). The breach rate rose with the opening range: 9% when the
  range was ≤ 0.2%, 22% at 0.3–0.4% and 30% above 0.4%. The 0.30% cut was chosen after reading this.
- Phase B, real option prices from Oct-2024: **every opening-window rule fails.**
  - Entering at 09:22 earns less: NIFTY 9.0% → 5.9% and SENSEX 9.1% → 5.2% a month. The six minutes cost premium.
  - Skipping days with a range ≥ 0.30% skips half of all days since Oct-2024, and those days were
    profitable. NIFTY falls to 3.1% and SENSEX to 1.5%.
  - Moving the short to 1.0% on wide-range days, or skipping after an early move away, are also worse.
- Markets since Oct-2024 open wider than in 2022–24. A range of 0.30% was a warning then; now it is a normal morning.

## Part 5: a later entry (ndte36, user asked about 09:45), 16-Oct-2026

Same strike rule (0.5% from the spot at the entry time), live exits from 16-Oct (hold to settle,
Rs5,000 cap), real option prices Oct-2024 onwards. **A later entry does not avoid the losses.**

| Entry | NIFTY losses / win / % a month | SENSEX losses / win / % a month |
|---|---|---|
| 09:16 (live) | 9 / 89.2% / 12.7% | 12 / 87.2% / 10.2% |
| 09:30 | 10 / 87.7% / 7.9% | 13 / 84.7% / 3.5% |
| 09:45 | 9 / 88.5% / 7.1% | 13 / 84.5% / 7.6% |
| 10:00 | 10 / 87.5% / 1.6% | 16 / 78.1% / −6.2% |

- The number of losing days does not fall. The strike moves with the 09:45 spot, so a rally that has
  already started carries the strike up with it, and most of these rallies keep going.
- The credit falls (NIFTY 20.2 → 16.0 points, SENSEX 71.3 → 64.5), so each win pays less.
- 15-Oct at 09:45: SENSEX was about 73,380, so the short would have been 73,700. It closed at 74,316,
  which is a full-width loss again before the cap.

## Part 6: the 09:15–09:45 window and every entry/exit combination (ndte37, ndte38), 16-Oct-2026

User goal: the most net profit; skipping days is acceptable. Pre-registrations prereg37.json and prereg38.json.

- **Older NIFTY data (index only, 2022-01 to 2024-07)** gave two hints. Days with a 09:15–09:44 range of 0.5% or
  more broke the short strike 28% of the time against 13%. After a rising half-hour the call side broke more
  often than the put side (29% against 14%, but on only 7 days).
- **On real option prices from Oct-2024 both hints fail.** Every 09:45 rule earns less than the 09:16 entry:
  - NIFTY: 09:16 +Rs36.6k. Then 09:45 +20.7k; skip wide mornings +4.6k; side from the half-hour +4.4k; both −3.5k.
  - SENSEX: 09:16 +26.7k. Then 09:45 +19.6k; skip +16.9k; side +8.5k; both +19.3k.
  - Exiting a 09:16 trade at 09:45 after a wide or adverse half-hour is also worse on both books.
- **28 combinations of entry, filter and exit per book (ndte38):** the highest net on both books is the
  plain 09:16 entry held to settle with no cap: NIFTY +Rs41,525 and SENSEX +Rs38,819 to 8-Oct.
  - The live Rs5,000 cap gives NIFTY +36,637 and SENSEX +26,701.
  - On SENSEX the cap cost Rs17.9k in the recent year alone (H2 +1,906 against +19,799), because it closed
    trades that recovered by the close.
  - 15-Oct is still missing. Uncapped it lost Rs10,524; the cap would have saved about Rs5k of that.
- No combination passes the pre-registered test. The only change that raised net was switching off the
  95% early close (part 4, deployed 16-Oct).
