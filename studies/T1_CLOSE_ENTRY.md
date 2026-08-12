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

## Recommendation

If this is taken forward, take **SENSEX first**: it is the only index positive and consistent in BOTH
windows with a real sample (49 IS / 42 OOS, 85.7% both), and its edge does not depend on one window.
NIFTY second, sized small until its in-sample weakness resolves forward. BANKNIFTY last despite the
best headline — the sample cannot support it yet.
