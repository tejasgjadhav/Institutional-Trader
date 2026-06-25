# Write the objective before the backtest

## The question
How do you stop a research run from drifting until it agrees with you?

## The method
Write the objective down first, in a file, before the first run. It has to say four things.

What is being measured. The exact number, defined well enough that two people compute it the
same way. Net money per trade after costs is a measurement. "Performance" is not.

Over what sample. The exact window, the exact universe and the exact data source, fixed in
advance. Also which part of it you are allowed to look at, and which part you are keeping back.

What counts as a pass. A threshold you commit to before you see the result.

What counts as a failure. The condition under which you drop the idea instead of adjusting it.
This is the line people leave out, and it is the only one that makes the exercise honest.

## Why it matters
Without a written objective, a run never fails. It just becomes the next question. You end up
with a result that fits the data because the data chose the question.

A written objective also makes a later reader able to check you. A study you cannot re-run from
its own notes is an opinion with a timestamp.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

