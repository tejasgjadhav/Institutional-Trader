# Depth data: what it is, and what has not been established

## The question
Order book depth shows resting quantity on both sides. Does it predict the next move?

## What is honestly known here
**Not enough to say.** Three weeks of depth recordings exist in this research trail, and three
weeks is nowhere near a sample that can settle the question. A year would be the minimum. This
note exists so that the gap is written down rather than quietly forgotten.

That matters, because four separate classes of chart-based entry have been falsified in this trail
and order flow has not. It would be easy to conclude from the falsifications that nothing works.
The honest position is narrower: patterns built from completed candles have been tested and failed,
and a different class of input has not been tested at all.

## What makes it hard
**Recording it is the project.** Depth is not sold as history in any form you can afford. If you
want a year of it, you start recording today and you have a year of it next year. There is no
shortcut, and that cost is why the question stays open for most people.

**It is the easiest data to fool yourself with.** Resting quantity is not committed quantity.
Orders are cancelled faster than they are filled, and a large resting size can be there precisely
because somebody wants it seen. Any result has to survive the possibility that the thing you are
reading is intended to be read.

**Latency decides whether a finding is usable.** An edge that exists for two seconds belongs to
whoever is closest to the exchange. Before you test a depth signal, decide how fast you could act
on it, and test only at that speed.

## What to do
Start recording, timestamped, from the first day you are curious. Store it raw. Do not aggregate
it into a feature until you know what you want to ask, because the aggregation throws away the
part you will want later.

Then leave the question alone for a year, and do not let a three-week sample talk you into
anything in the meantime.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. Test
anything you build on your own data before you risk money on it, and understand that you do so at
your own risk. Tejas Jadhav accepts no responsibility for your trades. See [DISCLAIMER.md](../DISCLAIMER.md).
