# Small-width stocks at c/w 0.30–0.40 with cheaper premiums, by side (15-Oct-2026)

**Question (user, 11-Oct-2026):** "Have you tested BP and BC for less than 40 or 50 or 30 premium for
lower width on c/w > 0.3? I am looking at stocks where width is pretty lower."

**Verdict: FAIL.** Bull puts and bear calls at c/w 0.30–0.40 lose money out of sample on run 6. That holds
for short premiums from Rs10 up to Rs50 and above, at both geometries, at both small-width definitions,
and with or without the credit × lot ≥ Rs3,000 condition. Small-width stocks behave no better than wide
ones. Nothing was deployed. Scripts and outputs are in research/lowcw_side/ (local only).

## Method

- **Data:** the run-6 traded-legs records, research/run6/cands_{IS,OOSU,OOSB}.pkl, run offline with no
  Upstox requests. The replay matched run 6 exactly on every window (validate.py, ALL PASS).
- **Windows:** IS 2019–Sep 2024; OOSU (Upstox cache) and OOSB (complete NSE path) from Oct 2024;
  post-CAS from 3-Aug-2026 as noise. Friction 1.0x and 0.75x.
- **Design:** an incremental slice behind the live books. It fires only when no live book fires or holds
  the name, with the 3-day gap, TP-40 and no stop.
- **Grid:** bull put and bear call separately; v1 geometry (1-OTM, width 3) and v2/v0 geometry (2-OTM,
  width 4); c/w 0.30–0.35, 0.35–0.40, and ≥ 0.40 for comparison; short premium Rs10–20, 20–30, 30–40,
  40–50 and ≥ 50, each also with credit × lot ≥ Rs3,000.
- **Selection:** pre-registered in prereg.json before any outcome was read, then picked on IS only.
  A cell needs n ≥ 10, added win ≥ 75%, added ROM > 0, the system staying ≥ 75% win with positive ROM,
  and positive next-session ROM.

## Small width, defined before any result was read (sets.json)

- **Set A, 36 names:** strike step as % of spot in the bottom third (below 0.88%). Examples: LT, TITAN,
  SBIN, COALINDIA, ITC, RELIANCE, NTPC, ICICIBANK, MARUTI, ULTRACEMCO.
- **Set B, 52 names:** strike step of 10 points or less. Examples: IOC, PNB, SAIL, NMDC, IRFC (step 1);
  WIPRO, BHEL, ITC, NTPC (2.5); HDFCLIFE, RECLTD, PFC, SBIN (5); AXISBANK, CIPLA, RELIANCE (10).

Membership uses today's ladders for every window. Splits and NSE interval changes moved many names, so
Set B's in-sample result rests partly on names that were high-priced then (BAJFINANCE alone is 59 of its
312 IS trades).

## The IS picks out of sample (added slice, 1 lot, 1.0x)

| Pick | Window | Added a month | Win | ROM | Rs a month |
|---|---|---|---|---|---|
| Set A (11 cells) | IS | 6.3 | 82.9% | +5.6% | +4,127 |
| | OOSU | 7.9 | 72.6% | −6.4% | −6,299 |
| | OOSB | 8.4 | 73.4% | −7.0% | −7,579 |
| Set B (9 cells) | IS | 4.5 | 86.2% | +7.2% | +4,839 |
| | OOSU | 1.5 | 75.8% | −12.7% | −3,099 |
| | OOSB | 1.8 | 79.1% | −7.5% | −2,270 |

With the Set A pick, the OOSB system falls from +9.0% ROM / Rs27.2k a month to +4.8% / Rs19.6k. Its bull
puts were −1.7% and its bear calls −12.7% on OOSB. At 0.75x friction it is still −6.0%.

## What the grid shows

- **Below Rs30, every bucket with a real OOS sample loses.** Examples from Set A: bull put v1 at
  Rs20–30 −13.1%; bear call v1 at Rs10–20 −11.0%; bear call v2 at Rs10–20 −23.0%.
- **Rs30–50 is mixed and mostly flat to negative.** Rs50 and above is negative OOSB for Set A on both sides.
- **Bear calls lose in IS at almost every bucket,** at both widths.
- **Small width does not help.** Pooled across shorts of Rs10 and up, small-width books are about as bad
  as, or slightly worse than, the wider names (full table in research/lowcw_side/contrast.txt).
- **The mechanism:** at c/w 0.30–0.40 the credit is too thin for the risk. The average win is about
  Rs3,000 and the average loss about Rs11,000–12,000, so a 73% win rate loses money.
- **The live 6% bid-ask gate is not modelled.** It would block some of the cheap legs, so the real result
  would be worse.

## Post-hoc watch item (not a pass)

Set A bull puts at v1 geometry, c/w 0.30–0.40, short Rs40–50: IS 38 trades at 89.5% / +12.1%, OOSU 22 at
86.4% / +10.4%, OOSB 29 at 82.8% / +2.3%, with positive next-session entry in all three. That is about one
trade a month and Rs300–1,100 a month. It was found among about 740 books read after OOS, where around ten
survivors are expected by chance, so it is a watch item at most.

## Multiple testing

This is at least the 17th study to read the Oct-2024+ window. It read about 740 books on it. The forward
record is the only clean test left.
