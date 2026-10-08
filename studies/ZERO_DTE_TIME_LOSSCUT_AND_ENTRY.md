# 0DTE NIFTY and SENSEX: time-based loss cut, entry time and strike distance (7-Oct-2026)

**Question (user, 7-Oct-2026, after the 6-Oct NIFTY loss):**
1. Should a losing trade be closed at a set time, such as 3 pm, to cut the average loss? The time T and
   the loss threshold L are both variables.
2. Would a different entry time or strike distance raise the win rate?

The user asked for maximum weight on the period since the closing auction began on 3-Aug-2026.

**Verdict:** Keep both books exactly as deployed. No loss cut, entry at 09:16, short strike 0.5% OTM.
Nothing was deployed.

## Method

- Script `studies/ndte/ndte30_time_losscut.py`, with 13 offline tests in `studies/ndte/test_ndte30.py`.
- Results are in `studies/ndte/ndte30_results.json` and `studies/ndte/ndte30_summary.md`.
- The data is real Upstox 1-minute expired-contract candles, Oct 2024 to Sep 2026: 105 NIFTY expiries
  and 104 SENSEX expiries. The cache is in data/ndte30_cache/.
- The fetch integrity line was CLEAN: 569 requests, 0 failures, 0 HTTP 429.
- The deployed entry rules were replicated:
  - NIFTY: FLIP, the hybrid add, the rv5 < 0.9 filter, the election blackout and the thin-credit skip.
  - SENSEX: 0.5% OTM, a wing of 0.83% of spot, c/w ≥ 0.04.
  - Both: take profit at 5% of credit remaining.
- Strike audit against the live books: NIFTY matched 7 of 12 positions, SENSEX 10 of 11.
- The two legs are joined by timestamp.
- The loss cut is decided on the option spread value. The index print is frozen during the auction,
  so it cannot be used.
- Each table has three views: post-CAS only (from 3-Aug-2026); recency-weighted (45-day half-life, with
  post-CAS weighted at least 3×); and the full window. Settings were picked on pre-CAS data and tested
  on post-CAS data.

**Post-CAS sample is 8 trades per book.** NIFTY had one loser in it (25-Aug) and SENSEX had none. Treat
the post-CAS view as directional evidence only. The 6-Oct NIFTY expiry was not yet published as
expired, so it is not in the sample. A warm re-run needs about 20 requests.

## Baselines (per lot)

| Book | Post-CAS n / win% / total | Full window n / win% / total / worst |
|---|---|---|
| NIFTY (deployed) | 8 / 87.5% / +₹163 | 90 / 93.3% / +₹34,315 / −₹11,472 |
| SENSEX (deployed) | 8 / 100% / +₹6,902 | 93 / 89.2% / +₹31,107 / −₹10,628 |

## Study A: close a losing trade at time T

T ran from 10:30 to 15:25 in 15-minute steps. L was 0, 0.25, 0.5, 1, 1.5, 2 or 3 × credit.

- **NIFTY.** The recency pick was T=14:45 with L=0.25. It lowers the full-window total to +₹28,676 and
  makes the worst trade worse, at −₹12,411. A cut at 12:00 halves the worst trade to −₹4,895, but costs
  ₹3–7k of net and drops the win rate to 79–83%. The pre-CAS pick (14:30, L=3) never fired post-CAS.
  Rank correlation pre against post was 0.25. **No cut.**
- **SENSEX.** The recency pick ties the baseline. T=10:30 with L=1.5 adds about ₹13k over the full
  window and improves the worst trade to −₹9,614. It rests on 3 pre-CAS cuts and never fired post-CAS.
  Rank correlation was 0.61. **No cut. 10:30 / L=1.5 is a watch item.**

Most trades that are losing at 2–3 pm recover by the close. Cutting them turns small eventual wins into
booked losses.

## Study B: entry time × short-strike distance

Entry times were 09:16, 09:30, 09:45, 10:00 and 10:15. Strike distance was 0.5%, 0.75% or 1.0% OTM.

- **NIFTY.** The best post-CAS cell was 09:45 at 0.5%, which mostly avoids the 25-Aug loss. Over the
  full window the deployed 09:16 at 0.5% is the best cell. The wider distances trade far less often and
  lose money over the full window. **Keep 09:16 / 0.5%.**
- **SENSEX.** The deployed 09:16 at 0.5% is the pick on every view, with no flags. **Keep.**

## Two side findings, NOT yet audited (do not rely on them)

1. **The ndte7/ndte11 convention overstates NIFTY credit.** Those studies priced the wing at the 09:16
   bar close and the short leg at its open. With both legs priced at the same instant, the ndte7
   baseline falls from +₹49,527 to +₹37,573, about 24% less. The NIFTY 0DTE profit figures in
   INTRADAY_85PCT_0DTE_CE_SPREAD.md and ZERO_DTE_ENTRY_TIME.md are probably overstated by about a
   quarter. No trading decision changes.
2. **The 95% take-profit may cost money.** Against holding to expiry it cost about ₹11.0k on NIFTY and
   ₹6.8k on SENSEX over the full window. Win rate and worst trade were the same. About ₹6.6k of the
   NIFTY figure is the study's heavy ₹80 charge per early exit, so this is unproven.

Both findings need an independent refutation pass before any figure or rule changes. That is the
house rule for decision-relevant results.
