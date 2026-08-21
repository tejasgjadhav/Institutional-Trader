# The 30-trade decision rule — written 21-Aug-2026, BEFORE any of the data exists

The user asked for a forward record of 30 trades and then a judgement on whether to increase lots.
These criteria are fixed **now**, before a single trade is recorded, because a rule written after
seeing the result is not a rule. This repo has already been burned twice by the opposite habit: v1's
DTE-5 result looked decisive in-sample and inverted out-of-sample, and the take-profit slope reversed
between windows. Both were caught only because the test was specified first.

## What is being tested

The backtest is finished and it says, on the median cohort:

| book | in-sample | out-of-sample |
|---|---|---|
| v2 | +27.2% ROM [+18.4, +34.7], 6/6 yrs, n=217 | +27.2% [+16.4, +37.2], 2/2 full yrs, n=55 |
| v1 | +10.3% [+2.9, +17.1], 6/6 yrs, n=359 | +9.5% [+2.5, +15.9], 2/2 full yrs, n=179 |
| v0 | +14.4% [+5.9, +21.9], 5/6 yrs, n=237 | +3.0% [−6.2, +11.5], **1/2 full yrs**, n=93 |

It **cannot** say whether that survives real fills, because bhavcopy carries no bid/ask and the live
spread gate is unmodellable. The forward record answers exactly that and nothing else.

## The criteria, fixed in advance

Judged on the **stock books pooled (v2 + v1)** at 30 closed trades. v0 is excluded from the
lot-increase decision: its own out-of-sample interval spans zero and it is positive in one of two
full years, so it has not earned size regardless of what 30 pooled trades show.

**PASS — the evidence supports increasing lots — requires ALL FOUR:**

1. **Win rate ≥ 70%.** Backtest says 79–84%. Sampling error on n=30 is wide, so 70% is the floor at
   which the shape is intact, not a target.
2. **ROM-₹ > 0 and its 90% bootstrap lower bound > −5%.** Not "positive" — positive on 30 trades is
   luck. The interval has to be inconsistent with a real negative.
3. **Take rate ≥ 40%.** Of all candidates that reached the live gates, at least 40% became trades.
   Below that the strategy is mostly unfillable and backtested frequency is fiction. On 17-Aug the
   live gates rejected 10 of 17, a 41% take rate — this criterion says that must not get worse.
4. **No single trade loses more than 25% of the pooled net.** One tail event eating the record means
   the sample is too small to size on, whatever the average says.

**FAIL — do not increase lots — if ANY of:**
- Win rate < 60%, or ROM-₹ negative with a bootstrap upper bound below +5%.
- Take rate < 25%.
- The realised win rate sits below the backtest's 90% interval, which means the backtest is
  systematically optimistic rather than merely noisy.

**INCONCLUSIVE — hold at 1 lot and keep recording** in every other case, including any PASS on
fewer than 30 closed trades. At about 8 v1 signals a month, 30 trades is roughly three to four
months. There is no shortcut and no partial credit.

## What will NOT count as evidence

- **Intraday/0DTE trades placed by hand.** They are a different strategy on a different book with a
  different risk shape. They cannot vote on the stock books' lot size.
- **A run of winners.** These books win 79–84% of the time by design; six winners in a row is the
  base rate, not a signal. The money is decided by the losers, because every book here loses more on
  a loser than it makes on a winner.
- **Trades entered before 6-Aug-2026.** Those were T-1 signals off the previous session's breakout,
  a strategy no backtest describes.
- **Paper P&L alone.** It is computed from the same feed that produced the signal, so it inherits
  that feed's optimism.

## What the record captures that nothing else does

`data/forward_record.db`, written by `engine/forward_record.py`:
- **fills** — P&L on MIDS, the same basis as both backtest windows, so the comparison is like-for-like.
- **spread_pct** — where real spreads sit inside the 0–6% band the gate allows. At the 6% boundary
  crossing costs ~6% of credit and ~11% of ROM; at 1–2% it is negligible. Unknown today.
- **rejections** — every candidate the gates blocked, with the reason. This is the take rate, and it
  is the number that converts a backtested ROM into money an account can actually collect.

## Author's note

I set these criteria; the capital decision is the user's. I am not a licensed adviser and this is a
measurement standard, not investment advice.
