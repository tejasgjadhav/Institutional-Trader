# Max-trades / max-return monthly OPTIONS on ₹2L (2026-07-13)

**User directive:** ₹2L capital, options route, 67% win acceptable, want MAX trades + MAX return.
So the win-rate constraint is dropped; optimize the REV1-v2-signal-as-long-calls for total return
on a fixed ₹2L. Script `opt_maxtrades.py`. IS = real bhav stock-option premiums 2019→Sep'24.

## Pick-count sweep (equal-weight ₹2L across each cycle's calls, early-exit +2%/−5%)

| Picks/cycle | Trades | Win% | Return/mo | Worst month | Max DD | ₹/mo on ₹2L |
|---|---|---|---|---|---|---|
| 3 | 115 | 70% | 3.4% | −101% | −100% | ₹6,855 |
| **5** | 211 | 70% | **5.5%** | −89% | −97% | ₹10,976 |
| 8 | 357 | 68% | 3.7% | −50% | −84% | ₹7,330 |
| 12 | 544 | 68% | 4.0% | −60% | −89% | ₹8,015 |
| 20 | 926 | 67% | 4.4% | −60% | −91% | ₹8,789 |

5 picks = max raw return (5.5%/mo, ~₹11k), but a **−89% month and −97% drawdown** — a crash
month (2020, 2022) nearly ZEROES the account. Long calls all die together in a selloff
(correlation→1) and a stopped/expired call keeps 0–50% of premium — no residual like a future.

## Cash-buffer circuit breaker (deploy only part of ₹2L, rest cash)

| Config | Return/mo | Worst month | Max DD | ₹/mo |
|---|---|---|---|---|
| 8 picks, deploy 60% | 2.2% | −30% | −63% | ₹4,398 |
| 8 picks, deploy 50% | 1.8% | −25% | −55% | ₹3,665 |
| 8 picks, deploy 40% | 1.5% | −20% | −46% | ₹2,932 |
| 12 picks, deploy 60% | 2.4% | −36% | −69% | ₹4,809 |

**The buffer just slides down the SAME line** — return and drawdown scale together, the
risk/return RATIO doesn't improve.

## The decisive finding — long calls are risk-adjusted WORSE than the futures

Match the risk (worst month ≈ −20%):
- **Futures REV1-v2:** 3.9%/mo at −20% worst month.
- **Long calls, 40% deploy:** only **1.5%/mo** at −20% worst month.

At any given drawdown budget, buying calls returns LESS than the future. The options' headline
"6–7%/mo on capital" is not extra edge — it is pure leverage, and it only exists if you accept
−50% to −100% crash months. There is no cash-buffer setting that gives futures-level return at
futures-level risk from long calls.

## Loss-minimizing gates (2026-07-13) — user picked 8 picks, "add gates to minimize losses"

The catastrophic months are CRASH months where every long call dies together, so the effective
gates are MARKET-level (NIFTY), not stock-level (stock-level entry features don't separate
winners from losers — confirmed earlier). Tested on the 8-pick book, `opt_gates.py`/`opt_gates2.py`:

| 8-pick config | Trades | Win% | Return/mo | Worst mo | Max DD | ₹/mo on ₹2L |
|---|---|---|---|---|---|---|
| base (NIFTY>200DMA only, −5% stop) | 357 | 68% | 3.7% | −50% | −84% | ₹7,330 |
| + momentum gate (−5% stop) | 288 | 69% | 5.6% | −50% | −76% | ₹11,136 |
| **+ momentum gate + −3% stop** ⭐ | 288 | 67% | **6.4%** | **−37%** | **−65%** | **₹12,781** |

- **Momentum gate** = skip the whole monthly cycle when NIFTY's 1-month return < −2% (don't buy
  calls into a falling market). Raised return AND cut drawdown — economically sound, not a
  data-mined threshold. (+50DMA gate also helps but less; slope/vol gates were neutral-to-worse.)
- **Tighter −3% underlying stop** (vs −5%): exits losing calls before theta+delta compound the
  loss. Lifts return to 6.4%/mo and pulls the worst month −50%→−37%. −2% overtightens (win 65%).
- **RECOMMENDED gated config:** 8 picks · NIFTY>200DMA AND NIFTY 1-mo return >−2% · TP +2%
  (decay +1% after d12) · **SL −3% underlying** · early-exit · equal-weight ₹2L.
  IS 2019-23: 67% win, 6.4%/mo (~₹12.8k), worst month −37%, DD −65%, ~6 trades/mo.
- **Still honest:** −37% worst month / −65% DD is STILL high risk (−₹74k / −₹1.3L on ₹2L). The
  gates REDUCE crash exposure, they don't remove it — no entry gate catches a market that's fine
  at entry then crashes mid-cycle. IS-tuned; **OOS validation (Upstox Oct'24→Jul'26) required
  before any live wiring.** For worst-month ≤ −20%, add the cash buffer (deploy ~55%) → ~3.5%/mo.

## Honest recommendation

- **If "max return" truly means accept ruin risk:** 5 picks/cycle long call = ~5.5%/mo IS
  (~6–7%/mo OOS Oct'24→Jul'26), **but −90% crash months are real** — size it as money you can
  lose entirely. MANDATORY damage control if deployed: cap premium at ≤60% of ₹2L + skip the
  cycle when NIFTY has just broken below its 200DMA (regime cutout already in the futures book).
- **The genuinely best return on ₹2L at survivable risk is NOT long calls** — it is the
  DEFINED-RISK credit-spread books (Tier A: stock fade v2 88% win, the 0DTE books 88–91%), whose
  per-trade loss is capped by construction, OR the futures pullback itself (3.9%/mo, −20%).
- Not deployed. approval-first: need the user's explicit pick (5 vs 8 picks; buffer %) before any
  live wiring, given the ruin exposure.
