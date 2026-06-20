# Data Availability — what can and can't be backtested (Upstox)

How far back each data type is served decides how long a backtest can be. The binding
constraint is **option-premium history**.

| Data type | Depth (Upstox) | 180d? | 365d? |
|-----------|----------------|-------|-------|
| Daily price candles (stocks/index) | 2+ years | yes | yes |
| 5-min underlying candles (price) | ~365 days (chunked) | yes | borderline |
| **Option-premium intraday candles** | **~3–4 weeks** | no | no |

## Why options are the wall

`get_option_by_offset` builds strikes from Upstox's **live instruments master**, which only
lists contracts that haven't expired. So for any past date it can only resolve a
*currently-live* expiry — every probe returned the same live expiry even for a date months
back. That contract only has candles as far back as it started trading (~3–4 weeks).
**Expired options drop out of the master entirely**, and their intraday candles aren't served.

**Consequence:** the clean option-P&L backtest is only valid for ~1 month. The "30/60-day"
option windows are mostly the recent ~3–4 weeks plus a few methodologically-imperfect older
days — which is why every option result is flagged "small sample, ~1 month of usable data."

## Three ways to validate longer

1. **Underlying-proxy** (free, done): test the directional edge on the year of price data.
   Validates the signal's brain, not option P&L. → `UNDERLYING_VALIDATION_365D.md`
2. **Black-Scholes synthetic premiums** (approximate): price options off the underlying +
   modeled IV to extend the option-P&L backtest. No real spread/skew.
3. **Paid deep-history options vendor** (TrueData / GDFL / NSE dump): the only way to get a
   *real* 180/365-day option backtest. Costs money + a loader.

*Generated 2026-06-20.*
