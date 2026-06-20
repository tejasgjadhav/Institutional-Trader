# Stock Option Exit Cap — should we remove the +10% target?

Stock options book at **+10% / −20%** on premium. The +10% is an upper cap on the winner.
We tested raising/removing it (let winners ride to the close), keeping the −20% stop and the
live gates. **Not deployed — live config stays at +10%.**

## Results (live gates, −20% stop, 1 lot, GROSS)

**30-day (45 trades):**
| Exit | Win % | P&L | On capital | Avg winner |
|------|-------|-----|------------|-----------|
| **+10% (current)** | **58%** | +₹13,114 | +1.5% | +9.4% |
| +20% cap | 49% | +₹13,292 | +1.5% | +13.6% |
| +30% cap | 47% | +₹15,532 | +1.8% | +14.4% |
| NO CAP (ride to EOD) | 47% | +₹4,663 | +0.5% | +11.8% |

**60-day (67 trades):**
| Exit | Win % | P&L | On capital | Avg winner |
|------|-------|-----|------------|-----------|
| **+10% (current)** | **61%** | +₹36,792 | +2.8% | +9.3% |
| +20% cap | 48% | +₹34,027 | +2.5% | +13.6% |
| +30% cap | 46% | +₹40,510 | +3.0% | +14.9% |
| NO CAP (ride to EOD) | 46% | +₹47,986 | +3.6% | +15.7% |

## What it says

1. **The +10% cap creates the ~60% win rate.** Raise/remove it and win rate falls to ~46–48%.
2. **Removing the cap is inconsistent** — NO CAP is the *worst* on 30-day (+0.5%) and the
   *best* on 60-day (+3.6%). Worst-to-best between overlapping windows = high variance, not a
   reliable edge (a few big EOD runners carry the 60-day number).
3. **+30% is the most *consistent* improvement** (slightly +rupees in both windows) but trades
   away the win rate and adds variance.

## Verdict

**No clean case to remove the +10% cap.** The convexity benefit shows up only on the 60-day
window, with much lower win rate and higher variance. The +10% cap gives the highest win
rate, consistent P&L, and lowest variance — kept as-is. If pursuing the bigger-tail idea,
**+30% (not no-cap)** is the version the data supports.

Reproduce: `studies/stock_option_exit_cap.py`. *Generated 2026-06-20. Gross of costs.*
