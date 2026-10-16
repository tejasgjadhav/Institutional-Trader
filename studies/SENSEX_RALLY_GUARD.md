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
