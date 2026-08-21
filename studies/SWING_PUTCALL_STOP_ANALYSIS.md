# Stock Fade v2 UNION — Put/Call, Stop-Loss & Timing analysis

**Why this study exists.** The v2 fade was validated as a single rule, but three things inside it had never been tested separately: whether puts and calls behave the same, whether a stop helps or hurts, and whether entry timing matters. This separates them so each is decided on its own evidence.


Extends the validated v2 UNION credit-spread fade (see `studies/ndte/stkfade_union.py`, `STOCK_OPTIONS_NO_EDGE.md` Part 10). Strategy held fixed except the swept parameter: UNION Donchian(5/10/15/20) daily breakout → SELL a credit spread AGAINST it (up→bear-call short 2-OTM CE +4 wide; down→bull-put short 2-OTM PE −4), gates credit/width≥0.40, short prem≥₹50, OI≥1, min-DTE 10, reentry 3d, TP 50% of credit, hard stop 3× credit, else settle intrinsic at monthly expiry.

- **IS** = NSE bhavcopy 2019→Sep 2024 (close-only sim), **n=387 trades**.
- **OOS** = real Upstox expired-option premiums Oct 2024→2026-07-29 (single regime), **n=222 trades**.
- Net = % of spread width; 2.5%/leg **entry** slippage charged (matches the validated v2 sim); GROSS of taxes. Small ₹20×4/lot commission omitted as in the base sim.

---

## 1. PUT (bull-put / down-break) vs CALL (bear-call / up-break)

**In-sample 2019→Sep'24**

| side | n | win% | net %width | avg win %w | avg loss %w |
|---|--:|--:|--:|--:|--:|
| CALL (bear-call, up-break) | 281 | 80.8% | +25.0% | +39.1% | -49.1% |
| PUT  (bull-put, down-break) | 106 | 92.5% | +24.9% | +33.0% | -45.0% |

**Out-of-sample Oct'24→date**

| side | n | win% | net %width | avg win %w | avg loss %w |
|---|--:|--:|--:|--:|--:|
| CALL (bear-call, up-break) | 137 | 73.7% | +23.7% | +37.9% | -54.2% |
| PUT  (bull-put, down-break) | 85 | 74.1% | +9.1% | +30.4% | -45.5% |


## 2. Stop-loss sweep (rest of v2 fixed)

**In-sample 2019→Sep'24**

| stop | n | win% | net %width | worst single loss %w | net after ⅓ slip haircut |
|---|--:|--:|--:|--:|--:|
| 2.0x | 387 | 79.3% | +19.5% | -64.8% | +17.7% |
| 2.5x | 387 | 82.7% | +22.0% | -64.8% | +20.2% |
| 3.0x (deployed) | 387 | 84.0% | +25.0% | -64.8% | +23.3% |
| 3.5x | 387 | 84.8% | +26.1% | -64.8% | +24.5% |
| no-stop | 387 | 87.3% | +30.4% | -63.0% | +29.0% |

**Out-of-sample Oct'24→date**

| stop | n | win% | net %width | worst single loss %w | net after ⅓ slip haircut |
|---|--:|--:|--:|--:|--:|
| 2.0x | 222 | 70.7% | +17.6% | -60.7% | +16.5% |
| 2.5x | 222 | 73.0% | +17.7% | -62.3% | +16.7% |
| 3.0x (deployed) | 222 | 73.9% | +18.0% | -62.3% | +17.0% |
| 3.5x | 222 | 74.3% | +18.4% | -62.3% | +17.5% |
| no-stop | 222 | 74.3% | +18.4% | -62.3% | +17.5% |

_Haircut = base net minus one-third of modeled round-trip (entry+exit) slippage, i.e. assumes real fills are ~⅓ worse than the 2.5%/leg model._

## 3. Timing

### 3a. Win% by day-of-week of the breakout/entry

**In-sample 2019→Sep'24**

| entry DOW | n | win% | net %width |
|---|--:|--:|--:|
| Mon | 89 | 82.0% | +21.7% |
| Tue | 76 | 84.2% | +19.3% |
| Wed | 69 | 87.0% | +28.9% |
| Thu | 79 | 82.3% | +28.5% |
| Fri | 74 | 85.1% | +27.4% |

**Out-of-sample Oct'24→date**

| entry DOW | n | win% | net %width |
|---|--:|--:|--:|
| Mon | 60 | 71.7% | +11.6% |
| Tue | 48 | 81.2% | +27.5% |
| Wed | 48 | 70.8% | +10.2% |
| Thu | 34 | 73.5% | +25.9% |
| Fri | 30 | 70.0% | +18.9% |

### 3b. Entry-at-close vs entry-at-next-open

_'Next-open' proxied by the NEXT trading day's option CLOSE (historical intraday option opens don't exist in bhavcopy/expired-candle data) and RE-GATED at the delayed credit, so its n is lower — trades that no longer clear credit/width≥0.40 a day later are dropped._

**In-sample 2019→Sep'24**

| entry | n | win% | net %width |
|---|--:|--:|--:|
| at breakout close (deployed) | 387 | 84.0% | +25.0% |
| wait one session (next close) | 217 | 77.9% | +24.6% |

**Out-of-sample Oct'24→date**

| entry | n | win% | net %width |
|---|--:|--:|--:|
| at breakout close (deployed) | 222 | 73.9% | +18.0% |
| wait one session (next close) | 135 | 70.4% | +19.7% |

---

### Caveats

- OOS is a **single ~21-month regime** (Oct'24→now); IS-vs-OOS agreement is the real test of stability, not either number alone.

- Close-only IS sim: TP/stop touches are detected on **daily option closes**, so intraday stop hits are understated (real stops trigger a bit more often, slightly fattening the loss tail).

- All figures GROSS of taxes/STT; entry-slippage only in the base column (exit slippage enters only via the analysis-2 haircut).
