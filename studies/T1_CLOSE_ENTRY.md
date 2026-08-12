# T-1 CLOSE entry — sell at the expiry-eve close. IS/OOS validated, 3 indices (11-Aug-2026)

**Verdict: the strongest new candidate this repo has found since v0. BEAR CALL 0.5% OTM, width 6,
holds in BOTH windows on all three indices. NOT deployed — see "Before deploying".**

## What changed from the rejected T-1 09:16 test

Same idea, different entry instant. `T1_EXPIRY_EVE.md` rejected entering at 09:16 on expiry eve:
95-100% win rates on Rs3.7 credits, c/w 0.01-0.10, one loss erasing 30 wins. Entering at the T-1
**CLOSE** instead changes the trade completely: it skips the full session of drift the 09:16 entry
sits through, keeps the overnight gap plus expiry day, and — because the winning strike is 0.5% OTM
rather than 2.5% — collects real premium (Rs32.9 vs Rs3.7).

## IS / OOS — the test that decides it

IS = Oct-2024 -> Sep-2025. OOS = Oct-2025 -> Aug-2026, never inspected while choosing geometry.
Bar: positive Rs/trade in BOTH windows and OOS win >= 75%.

| index | geometry | IS n | IS win | IS Rs/tr | OOS n | OOS win | OOS Rs/tr | holds |
|---|---|---|---|---|---|---|---|---|
| NIFTY | BEAR 0.5% w6 | 52 | 84.6% | +32 | 43 | 90.7% | **+1,190** | **YES** |
| SENSEX | BEAR 0.5% w6 | 49 | 85.7% | +514 | 42 | 85.7% | **+590** | **YES** |
| BANKNIFTY | BEAR 0.5% w6 | 15 | 93.3% | +2,061 | 10 | 90.0% | **+2,251** | **YES** |

**BEAR CALL 0.5% w6 is the only geometry that holds on all three.** Note NIFTY's IS Rs/trade is
+32 — barely above zero — and several neighbouring NIFTY cells (0.75%, 1.0%) are NEGATIVE in-sample
while strongly positive OOS. That asymmetry is a warning, not a feature: it means NIFTY's result is
carried by the OOS window and is thinner than the headline suggests.

## Money and risk, full period, 1 lot

| index | n | WIN | Rs/trade | expiries/yr | **Rs/YEAR** | losses/yr | avg loss | worst |
|---|---|---|---|---|---|---|---|---|
| NIFTY | 95 | 87.4% | 556 | 51.8 | **28,827** | 6.5 | -10,559 | -20,600 |
| SENSEX | 91 | 85.7% | 549 | 49.6 | **27,249** | 7.1 | -6,681 | -10,530 |
| BANKNIFTY | 25 | 92.0% | 2,137 | 13.6 | **29,143** | 1.1 | -9,280 | -9,717 |
| **all three** | | | | | **85,219** | | | |

Deployed 0DTE books for comparison: NIFTY Rs21,252/yr + SENSEX Rs37,836/yr = **Rs59,088/yr**.

## Complementary or substitute? BOTH, and the distinction matters

**Complementary in TIME, correlated in RISK.**

- Different risk windows: T-1 is entered at the eve close and its P&L is dominated by the OVERNIGHT
  GAP; 0DTE is entered 09:16 on expiry day and its P&L is intraday drift only.
- But they OVERLAP: the T-1 position is still open on expiry morning when the 0DTE position opens.
  For a few hours you hold two short-premium spreads on the SAME index in the SAME direction.
- So they are not substitutes — running both roughly doubles gross income — but they are **not
  independent either**. A violent gap-and-trend expiry day hits both at once, and the combined worst
  case is the sum, not the max. Sizing must assume they lose together.

**BANKNIFTY is the genuinely additive slot**: its 0DTE book was REJECTED (t=+0.10), so nothing
occupies it. T-1 BANKNIFTY is new capacity, not an overlay.

## Before deploying — what is NOT yet established

1. **BANKNIFTY rests on n=25** (15 IS / 10 OOS), ~2 losses total. Its 0DTE book died on exactly this
   kind of thin sample. Treat 92% as unproven.
2. **NIFTY's IS leg is +Rs32/trade** — statistically indistinguishable from zero. The strategy is
   carried by SENSEX and by NIFTY's OOS window.
3. **No live liquidity gate applied.** These are daily closes; the 15:36-15:40 book is 2-4% wide
   (`NSE_SESSION_CHANGE_2026_08_03.md`), and no c/w or bid-ask filter was imposed. Real fills will
   come in below.
4. **Entry timing collides with the stock books.** The T-1 close entry wants the same 15:36-15:40
   window the v2/v1/v0 scan already occupies, on the same 3.5-minute placement budget.
5. **One regime.** Oct-2024 -> Aug-2026 is 22 months of a single market character.

## ⚠ THE FINDING THAT CHANGES THE VERDICT — it is a DIRECTIONAL bet, not a premium edge

Every surviving cell is BEAR_CALL. The put side is negative on all three indices:

| index | BEAR_CALL Rs/tr | BULL_PUT Rs/tr | BULL_PUT IS | BULL_PUT OOS |
|---|---|---|---|---|
| NIFTY | **+556** | **-176** | +6 | -391 |
| SENSEX | **+549** | **-233** | -532 | +122 |
| BANKNIFTY | **+2,137** | **-943** | -490 | -1,623 |

And the tape explains it: **NIFTY fell 4.1% then 1.1%; SENSEX fell 4.2% then 3.2%.** The entire
sample is a falling market. Selling calls into a market that only went down is not an edge — it is
a short-delta position wearing a credit-spread costume, and the "87% win rate" is the market
declining, not premium being harvested.

**This repo has already been destroyed by exactly this pattern once.** `CLAUDE.md` Part 11: a
down-only fade gate looked like +15.1%/78% win, positive all six years, bootstrap p5 +4.1% — and
FAILED out of sample when the direction asymmetry reversed. The lesson recorded then was "6 positive
years in ONE regime != out-of-sample". Here the IS/OOS split does NOT rescue us, because BOTH windows
are the same falling regime: splitting a downtrend in half gives two downtrends.

**So the IS/OOS test above is weaker than it looks.** It proves the result is stable across two
halves of one regime. It cannot prove the result survives a rising market — and the put-side numbers
say plainly what happens when direction runs the other way.

## FULL PERIOD 2019 -> 2026, TRUE IS/OOS — the test that settles it

IS = NSE F&O bhavcopy 2019 -> Sep-2024 (1,359 sessions, real option closes per strike, contains BULL
regimes). OOS = Upstox Oct-2024 -> Aug-2026. **1,405 trades.** BEAR CALL 0.5% OTM width 6, 1 lot.

| year | NIFTY win | NIFTY Rs/YEAR | | BANKNIFTY win | BNF Rs/YEAR |
|---|---|---|---|---|---|
| 2019 IS | 76.6% | +5,684 | | 80.8% | +44,387 |
| **2020 IS** | **64.2%** | **-39,007** | | **66.0%** | **-3,236** |
| 2021 IS | 67.3% | +8,237 | | 76.9% | +50,661 |
| 2022 IS | 75.0% | +32,082 | | 73.1% | +30,967 |
| 2023 IS | 82.4% | +31,325 | | 88.2% | +68,614 |
| 2024 IS | 68.9% | +2,419 | | 85.0% | +61,786 |
| 2025 OOS | 86.8% | +392 | | 90.9% | +19,191 |
| 2026 OOS | 86.7% | +32,349 | | 85.7% | +15,739 |

**NIFTY survives, but barely and unevenly: +Rs72/trade IS versus +Rs556 OOS, and a -Rs39,007 year in
2020.** Two of six in-sample years are near zero (2021 +8k, 2024 +2.4k). The 87% win rate seen in the
Oct-24 window is a *falling-market* number: across 2019-2024 the same geometry wins only **71.5%**.

**BANKNIFTY is the real finding: +Rs801/trade over 293 in-sample trades and +Rs2,137 over 25 OOS,
positive in 5 of 6 IS years.** That is a genuine, regime-spanning result on a real sample — not the
n=25 anecdote the earlier run showed.

### The direction asymmetry INVERTS out of sample — exactly as feared

| index | side | IS Rs/trade | OOS Rs/trade |
|---|---|---|---|
| NIFTY | BEAR_CALL | +72 | **+556** |
| NIFTY | BULL_PUT | **+226** | **-176** |
| BANKNIFTY | BEAR_CALL | +801 | +2,137 |
| BANKNIFTY | BULL_PUT | -95 | -943 |

**On NIFTY the better side FLIPS**: puts earn +226 in-sample and lose -176 out-of-sample; calls earn
+72 in-sample and +556 out. This is the `CLAUDE.md` Part 11 failure repeating precisely — a direction
edge that is a regime artifact, not structure. Any NIFTY T-1 book would have been fitted to whichever
window was looked at last.

**BANKNIFTY does NOT flip**: calls positive in both (+801 / +2,137), puts negative in both (-95 /
-943). A consistent sign across two different regimes is what an edge looks like.

### 2020 is the risk case, and it is the one to plan for

NIFTY -Rs39,007 in a single year at 1 lot, win rate collapsing to 64.2%. That is the COVID-crash
regime: gaps every session, and a T-1 position wears every one of them blind. Combined with the
measured gap frequency (a 0.5% OTM call breached AT THE OPEN on 9.8% of NIFTY sessions, worst
+4.86%), 2020 is not a tail — it is what this structure does when gaps cluster.

## Recommendation

If this is taken forward, take **SENSEX first**: it is the only index positive and consistent in BOTH
windows with a real sample (49 IS / 42 OOS, 85.7% both), and its edge does not depend on one window.
NIFTY second, sized small until its in-sample weakness resolves forward. BANKNIFTY last despite the
best headline — the sample cannot support it yet.
