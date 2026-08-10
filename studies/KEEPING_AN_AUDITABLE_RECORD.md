# Logging a live system so you can answer questions later

## The question
Six months in, somebody asks why a particular trade was taken. Can you answer?

## What has to be written down at the moment of the decision
The inputs as they stood. The prices read, the time they were read, and the source they came
from. The rule version in force. The decision, and for a rejection, the specific condition that
rejected it. The contract chosen and the quote at that instant.

A log that records only the trades taken cannot answer the more useful question, which is what
the system passed on and why.

## What goes wrong without it
Three failures found here hid behind a single symptom because the handler swallowed them. A
network stall killed a scheduled scan silently and the day simply recorded no signal, which looks
exactly like a quiet day. A counter that watched one stage reported a clean run while a different
stage had skipped most of its work.

Every one of those was invisible in the output and obvious in a log that recorded intent as well
as outcome.

## What to take from it
Log the rejections, not just the fills. Never let an error handler swallow an error without
recording it. Put a marker on disk for each thing that is supposed to happen once a day, and
check at the end of the day that every marker is there. An absence has to look different from a
silence.

---

Study notes from the research trail behind *The Algo Trading Bible*. Not investment advice. If
you trade on this you do so at your own risk, and Tejas Jadhav accepts no responsibility for
your trades. See [DISCLAIMER.md](../DISCLAIMER.md).

