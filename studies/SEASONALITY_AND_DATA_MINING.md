# Day-of-week effects and other things you will find if you look

## The question
Returns look different on Mondays, or in a particular month, or in the week before expiry. Is any
of that tradeable?

## The arithmetic of looking
There are five weekdays, twelve months, and a handful of ways to slice a month. Test all of them
and you have run perhaps fifty tests. At the usual significance level, two or three will look
significant on noise alone, and they will look convincing, because a calendar effect comes with a
ready-made story.

The story is the dangerous part. Every calendar pattern has a plausible explanation available after
the fact: fund flows, salary dates, expiry positioning, holiday thinness. The explanation arrives
after the pattern is found, which means it is not evidence.

## What survives, generally
Very little, and less every decade. Most of the classic calendar anomalies in the literature have
weakened or reversed since they were published, which is what you would expect of something widely
known and easy to trade.

The effects that persist tend to be structural rather than calendrical: something about how a
market is built, such as settlement, expiry mechanics or when an auction runs, rather than
something about what day it is.

## What to do if you find one
Pre-register it. Write down the effect, the direction and the threshold, then test it on a window
you have not looked at. See [IN_SAMPLE_VS_OUT_OF_SAMPLE.md](IN_SAMPLE_VS_OUT_OF_SAMPLE.md).

Count every slice you tried, including the ones you abandoned, and raise your bar accordingly.

Then ask the question that settles most of these: if this were real and this easy to find, who is
on the other side of it, and why have they not noticed?

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
