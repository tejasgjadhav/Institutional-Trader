# Why this repository does not match the screenshots in the book

The book carries screenshots of this repository as it stood while the book was being written. The
folder listing in those images does not match what you will find here now. This note says why, so
you are not left wondering whether you cloned the wrong thing.

## The research shown in those screenshots is not in this edition

Several of the strategies documented in that older research **failed**, and they were taken out of
the live system. In each case the failure was measured, not suspected.

**A multi-day index strategy.** It looked strong on one window and came back net negative out of
sample, positive only in favourable regimes. A salvage attempt that added two further conditions
also failed out of sample, and the asymmetry it relied on reversed on fresh data. The book is
honest about this one, and it is now switched off.

**The intraday index breakout system.** Tested on real five-minute history back to 2019 it came in
thin and inconsistent, negative in roughly two years out of eight. Retired.

**The three-family option-buying system.** This one is published here in full, because it is the
most instructive failure in the set. It has a real directional edge of about eleven basis points a
signal, positive in every year since 2019, and a full year on real option premiums still came in
at minus one percent. The edge is smaller than the cost of buying the option to express it. See
[studies/THE_THREE_FAMILY_SYSTEM.md](studies/THE_THREE_FAMILY_SYSTEM.md).

**The monthly futures book.** Shelved as gap-dependent and capital-hungry.

Those write-ups were not simply deleted. The method and the verdict from each of them have been
rewritten into the notes in [studies/](studies/), which is the part that transfers to your own
work. What is gone is the parameter detail, which was specific to those strategies and is of no
use to you.

## The rest is withheld, and that is a separate thing

Not everything in those screenshots failed. Some of it documents strategies the author still
trades, and those are not published, here or anywhere. No file name, no parameter, no screen, no
threshold. The book explains how the research was done. It does not hand over the answers, and
neither does this repository.

Please do not read this note as "all of that research was worthless". Some of it failed and is
documented as failing. The rest works and is private. You cannot tell which is which from here,
and that is deliberate.

## What ships instead

Four strategies, all of them runnable, all of them measured, and **all of them losing money**:

| Strategy | Measured result |
|---|---|
| VWAP pullback | 2,362 signals, mean −0.047% per trade, t = −2.69 |
| Moving-average crossover | 431 trades, 42.5% win, +2.56% mean, −1.27% median |
| Oversold dip buy | 946 trades, 65.5% win, +0.20% per trade, t = 1.84 |
| Gap fill | 2,238 trades, 50.8% win, +0.08% per trade, t = 1.57 |
| Three-family scorer | 19,454 signals, +0.107% on direction, −1.0% as a bought option |

They are here so the machine has something to run and so you can read a complete strategy end to
end. None of them is a recommendation.

## What you have to do before you trade anything

**Run your own backtest.** Not a re-read of the numbers above, your own, on data you pulled
yourself. The notes in [studies/](studies/) set out the method: write the objective first, charge
full costs, build a random baseline, hold a window back, and judge on money rather than win rate.

**Then paper-trade it.** For long enough to learn whether the machine behaves, not long enough to
believe the sample proves an edge. [studies/WHAT_A_FORWARD_TEST_IS_FOR.md](studies/WHAT_A_FORWARD_TEST_IS_FOR.md)
explains the difference.

**Then decide for yourself, and own the decision.** Anything you run from this repository, you run
at your own risk. Nothing here is investment advice, a recommendation or a signal service. The
author accepts no responsibility and no liability for any trade you place or any loss you suffer.
Speak to a licensed advisor before you trade. See [DISCLAIMER.md](DISCLAIMER.md) in full.
