# Non-fade intraday search — long gamma falsified; the space is now mapped (2026-07-09)

**User goal loop:** same bar as before (maximize win rate, net profitability and margin intact,
intraday) but on something OTHER than the fade / short-premium family.

## What was tested this loop — LONG-GAMMA on NIFTY expiry day (the structural opposite of fade)

Real premiums: bhavcopy 2019-02→Sep'24 (282 expiries, IS) + Upstox 1-min era Oct'24→Jul'26
(92 expiries, OOS). Costs 2.5% slippage + ₹20×4. Return measured on debit paid (= capital at
risk). Subsets all / calm (rv5<0.9) / hot (rv5≥0.9). Script `studies/ndte/ndte12_longgamma.py`,
raw grid `/tmp/ndte12_results.json`.

| Structure | IS 2019→Sep'24 | OOS Oct'24→Jul'26 | Verdict |
|---|---|---|---|
| **Long ATM straddle @open** → settle | 33% win, −13.2%/trade, **−₹3.04L** | 34% win, −9.8%, −₹1.29L | DEAD — theta crush eats it |
| … hot weeks only (rv5≥0.9) | 27% win, **−23.2%** (n=77) | +11.1% (n=18, noise) | DEAD — IV already rich on hot weeks |
| **Gap-follow debit vertical** @open (gap ≥0.2/0.4%) | mixed avg%, **total ₹ negative everywhere** | 20–30% win, −24 to −38% | DEAD OOS |
| **Trend-follow debit vertical** @9:45/10:00/10:30 (move ≥0.15/0.3%) | n/a (no intraday data pre-Oct'24) | 29–37% win, −4 to −23%, best cell ≈ flat | DEAD — nothing net-positive |

**The hot-week complement hypothesis is rejected:** the calm filter works by *skipping* hot
weeks, but flipping to long gamma on those weeks does not pay — expiry-day option premium is
priced fair-to-rich even (especially) when the tape is hot. The theta crush is one-directional
edge: it can be sold (with the right gates), not bought.

## The full intraday search-space ledger (all falsified except the deployed books)

| Family | Where tested | Result |
|---|---|---|
| Underlying direction, stocks (234 strategies, 7.5y) | `INTRADAY_90PCT_WINRATE.md` | edge ~+0.05% < 0.10% cost |
| High-win exit geometry (2,400 cells) | same | 92% win, ₹0 gross, negative net |
| Index ORB+VWAP momentum (2019→26 real 5-min) | `BUY_STRATEGIES_2019_REALTEST.md` | +0.04%/trade, retired |
| 3-Family option BUYING (real premiums, 1y) | `STOCK_OPTIONS_NO_EDGE.md` | −1.0% net — direction real, costs kill |
| Intraday pairs mean-reversion (3,670 trades) | `DAILY_HIGHWIN_SEARCH.md` | 45% win, −0.14%/trade |
| Non-expiry same-day option selling | same | net negative (theta is expiry-day only) |
| **Long gamma / debit structures, expiry day** | **this study** | **all negative, both eras** |
| 0DTE CE spread + calm filter (fade family) | deployed | 90% win, +5.85%m — the edge |
| Stock credit fade v2 (gated) | deployed | 85/88% win IS/OOS |

## Verdict

**No retail-accessible non-fade intraday edge exists in the data we can test.** Intraday, net
of costs, the only things that clear the bar are the two deployed short-premium books. The
reason is structural, not a search failure: (a) directional edges on the underlying are
~0.05–0.11%/trade — real but smaller than retail friction; (b) option premium carries a
persistent seller's rent (theta/IV overpricing) that punishes every buyer-side structure —
even trend-following ones on the days trends happen.

If the goal loop continues, the honest directions left are NOT intraday: multi-day holds
(the shelved daily-ladder variant, overnight momentum) or new data (order-flow/depth,
event calendars) — different risk class, needs explicit user sign-off on overnight exposure.

Nothing deployed, nothing changed — report only.
