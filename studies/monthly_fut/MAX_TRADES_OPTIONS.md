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

## ⚠ OOS VALIDATION — the gates and the 8-pick FAILED (2026-07-13, `opt_oos_gated.py`)

Ran the IS-winning configs on real Upstox premiums Oct'24→Jul'26 (the window the search never saw):

| Config | IS win / mo | **OOS win / mo** | OOS worst mo / DD |
|---|---|---|---|
| 5-pick, −5%, no gates (the SIMPLE base) | 70% / 5.5% | **67% / +6–7%** | −51% / — |
| 8-pick, −5%, no gates | 68% / 3.7% | **62% / +0.3%** | −62% / −73% |
| 8-pick + momentum gate + −3% stop ("improved") | 67% / 6.4% | **55% / −2.7% (LOSES)** | −64% / −83% |

**Every "improvement" made it WORSE OOS.** 5→8 picks killed the edge (+6-7%→+0.3%: picks 6-8 are
weaker names, dilution not diversification). The gates were overfit (+0.3%→−2.7%: the −3% stop
whipsaws in the choppy 2025-26 regime; the momentum gate was tuned to 2019-23). The gated 8-pick
that showed 6.4%/mo IS **lost money OOS**. Classic curve-fit — caught by validation before deploy.

**CONCLUSION: do NOT use 8 picks or the gates.** The ONLY long-call config that survives OOS is the
simple **5-pick, −5% early-exit, regime gate only** (+6-7%/mo, 67% win, −51% worst month). Entry
gates do NOT minimize the −51% tail without curve-fitting. Real loss-reducers are structural:
fewer picks (5), less capital deployed (cash buffer), or defined-risk credit spreads (capped loss).

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

## Win-rate lever sweep — IS AND OOS (2026-07-13, opt_winrate_is.py / opt_winrate_oos.py)

User: "test 5 long calls + add gates to improve WIN rate, use IS AND OOS." Tested TP {2/1.5/1%}
× strike {ATM/ITM-2%/ITM-4%}, −5% stop:

| 5-pick config | IS win | OOS win |
|---|---|---|
| ATM TP 2% (base) | 70% | 66% |
| ATM TP 1.5% | 70% | 68% |
| ATM TP 1% | 69% | 66% |
| ITM −2% TP 2% | 63% | (worse IS) |
| ITM −4% TP 2% | 53% | (worse IS) |

**Nothing lifts win rate above ~70% IS / ~68% OOS.** Deeper ITM LOWERS it (bigger premium → same
+2% move is smaller % gain, cost eats marginal wins); lower TP is flat. Reason: the win rate =
the SIGNAL's hit rate (how often the stock rises 2% before falling 5% in the month) — the option
strike/TP can't change that. Market-level gates (momentum/regime/vol) already failed OOS for
return; stock-level features don't separate winners (earlier pass). **No gate robustly raises the
long-call win rate.** The structurally higher-win-rate instrument is the DEFINED-RISK CREDIT SPREAD
(sell premium: profits from theta, wins without needing a directional move) — 85-88% win, already
live. Conclusion: long-call win rate is capped ~67-70%; to win more, change the STRUCTURE, not gates.
