# Trading around a scheduled event

## The question
A company reports results on a known date. Is there anything tradeable in the days around it?

## What makes it different from other signals
The date is known in advance, which is rare and useful. You are not predicting whether something
will happen, only how the price responds to something that definitely will.

It also makes the instrument choice sharp. Implied volatility rises into a scheduled event and
falls immediately after. Anyone buying an option into results is paying for that rise and will
watch it disappear the next morning regardless of which way the stock went.

## What to check
**Separate the jump from the drift.** The move on the day is one thing and any continuation over
the following days is a different thing with a different cause. Test them separately. Mixing them
gives you a number that describes neither.

**Use the event date as it was known then.** Companies move results dates. Using the date as finally
reported, rather than as announced at the time, is a quiet look-ahead. See
[LOOK_AHEAD_BIAS.md](LOOK_AHEAD_BIAS.md).

**Price the volatility, not just the direction.** If your expression is an option, the volatility
collapse after the event is usually larger than the directional edge you are trying to capture.
Measure both.

**Count the events.** A hundred names reporting four times a year is four hundred events, and a
rule that only fires on a subset of them has far fewer. [SAMPLE_SIZE.md](SAMPLE_SIZE.md) applies.

## The honest caveat
No result is published here. A related finding does appear elsewhere in this trail: keyword-based
news sentiment, tested as a scoring input over thirty days, did not lift the win rate, and its
weight in that system was cut because of it. That is a narrow finding about crude sentiment
scoring, not a verdict on event trading.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
