# CAS NIFTY AND SENSEX DATA

Daily recording of the **15:15–15:40 close window** for NIFTY and SENSEX, started 5-Aug-2026.

## Why this exists

The 3-Aug-2026 NSE session change (see `../NSE_SESSION_CHANGE_2026_08_03.md`) split the close
in two. Cash and the index stop printing at **15:30**. Equity derivatives keep trading to
**15:40**. So there are now ten minutes at the end of every session where option premiums move
with no index reference — priced off futures, through the closing auction. Nothing in the engine
was capturing that, and it is exactly where `KILL_SWITCH_TIME` (15:36) and the 15:36 scan operate.

This recorder captures the window every session so the regime can be studied on real data
instead of assumed.

## What is recorded, per session, per index

- **Index**: OHLC, prev close, %chg, 15:15 spot, 15:15→close move, close-vs-high, last-60m move,
  India VIX at close.
- **ATM CALL and ATM PUT** for the nearest expiry on/after the day, strike picked off the
  **15:15 spot** (so CE and PE share a strike).
- Premium marks at **15:15 / 15:30 / 15:36 / close**, plus the 15:15→close high and low.
- **Gross P&L per 1 lot** for a 15:15 buy exited at each mark.
- Traded volume **before and after 15:30** — the liquidity question for any post-15:30 exit.
- Full **1-min OHLCV series** from 15:00 for the index and both option legs, in `raw/`.

### Fill convention

A mark at time T is that minute bar's **OPEN** — what you would pay entering at T. The closing
mark is the last bar's **CLOSE**. P&L is gross: no brokerage, STT, exchange charges or spread.
Budget roughly ₹55–65 per round trip per lot on top.

## Outputs

| Where | What |
|---|---|
| `data/engine.db` → `cas_index_close` | one row per (date, index) |
| `data/engine.db` → `cas_option_close` | one row per (date, index, CE/PE) |
| `cas_index.csv`, `cas_options.csv` | full-table dumps, rewritten from the DB every run |
| `raw/<date>_<index>.json` | 1-min series, 15:00 → close, index + both legs |

Writes are `INSERT OR REPLACE` keyed on the primary key, so re-running any day is safe and
overwrites rather than duplicates.

## Schedule

`com.sayali.cas-recorder` runs weekdays at **15:50** with a **16:20** retry pass
(plist in `deploy/`, loaded into `~/Library/LaunchAgents/`). Logs land in
`logs/cas_recorder.{out,err}.log`. Holidays record nothing and exit clean — the index intraday
feed simply returns empty.

## Manual use

```bash
cd ~/files/institutional-trader
./.venv/bin/python -m engine.cas_recorder                    # today
./.venv/bin/python -m engine.cas_recorder 2026-08-04         # one past day
./.venv/bin/python -m engine.cas_recorder 2026-08-03 2026-08-05   # backfill a range
```

Backfill works for any past session: expired contracts come from the Upstox
expired-instruments API, live ones from the normal historical feed. The `src` column records
which path served each row (`intraday` / `historical` / `expired-api`).

## Data on hand

Backfilled to **3-Aug-2026**, the first session of the new regime. There is no earlier CAS data
to fetch — before 3-Aug the derivatives close was 15:30 and 15:36 did not exist.

## Known limits

- **The index goes dark after 15:30.** `mv_1515_close` measures 15:15→15:30 only. Premium moves
  between 15:30 and 15:40 have no index to explain them; they track futures and the auction.
- **Gross P&L only.** No spread modelled. Spreads widen in the auction window, and the recorded
  volume columns are there to judge how much that matters on any given day.
- **VIX is a close-of-day single value**, not an implied vol per strike. It is a directional hint
  for why premium decayed, not a measurement of it.
