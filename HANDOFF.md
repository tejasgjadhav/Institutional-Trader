# HANDOFF — session state (2026-07-04)

## Where things stand (all committed/pushed unless noted)
- **Real-data verdicts are canonical in `studies/STRATEGY_SUMMARY.md`** (one-table view, linked ★ in README)
  and mirrored in the UI STUDIES tab (`_strategy_summary_table()` in `engine/ui_terminal.py`) and the wiki.
- **Gated STOCK fade credit spread = the one VALIDATED edge**: real NSE bhavcopy 2019→Sep'24, 718 trades,
  +5.3% of width (~+9%/trade on margin), 54% win, +ve 5/6 years (2023 −4.5%). Gate = credit/width≥0.40 +
  prem≥₹50 — strip it and it loses (−1.1%). Details `studies/STOCK_OPTIONS_NO_EDGE.md` Part 10.
- **Index fade (NIFTY/FINNIFTY) DOWNGRADED**: −1.4% real 2019→Sep'24; a PE-only+flush≥0.5% gate looked
  +15.1%/78% in-sample but FAILED OOS on Upstox Oct'24→date (−2.8%, direction asymmetry reversed) →
  gates reverted to neutral (`SWING_FADE_DOWN_ONLY=False`, `SWING_MIN_BREAKOUT_PCT=0.0`). Part 11.
- **MIDCPNIFTY fade REJECTED** (illiquid, opts only from mid-2022; ~20% win, −25/−28%).
- **BUY strategies tested to 2019 on real Kite 5-min** (`studies/BUY_STRATEGIES_2019_REALTEST.md`):
  3-Family FULL-GATE dir edge +0.107%/tr, +ve EVERY year, but −1.0% net as options; ORB+VWAP thin.
- **Wiki auto-push live**: `~/files/wiki/tools/wiki_push.sh` + `wiki-push` skill; ingest/lint call it;
  memory `always-push-wiki`. Wiki remote = PUBLIC github.io (authorized).

## Data assets (in /tmp — re-downloadable if wiped)
- `/tmp/bhav_cache/` (1,359 days, NIFTY+FINNIFTY option bhavcopy 2019→Sep'24)
- `/tmp/bhav_cache_stk/` (1,359 days, ~100-stock option bhavcopy 2019→Sep'24)
- `/tmp/bhav_cache_midcp/` (618 days, MIDCPNIFTY 2022→Sep'24)
- `/tmp/k5m/*.json` (Kite 5-min per stock 2019→date) · downloaders: `/tmp/bhav_download*.py`
- Kite access token `/tmp/kite_access.txt` EXPIRES DAILY (user must re-login; key/secret in gitignored .env)

## ACTIVE TASK (in progress — the /goal/loop)
Goal: win% >65% EVERY year 2019–2026 + net>0 every year, monthly deployable, honest reporting.
- **iter1 DONE** (`/tmp/stkfade_grid.py`): 27 of 96 configs hit goal in-sample on real bhavcopy. The
  lever is structural: TAKE-PROFIT 0.5 + stop 3× + short 2-OTM (whole neighborhood passes).
- **iter2a DONE** (`/tmp/stkfade_grid2.py`): exit slippage charged on TP/stop exits — all 8 top
  configs STILL pass. Best **DC10/s2/w4/TP0.5/st3 = 85% win, +24.5% width, worst-yr +9.3% (273tr)**;
  DC5/s2/w4 = 84%/+23.9%/worst +16.7% (369tr). Results `/tmp/stkfade_grid2_result.json`.
- **iter2b DONE — OOS PASSED** (`/tmp/stkfade_oos3.py` threaded, result `/tmp/stkfade_oos.json`):
  Config A (DC10/s2/w4/TP0.5/stop3, cw≥0.40+prem≥50) on Upstox Oct'24→Jul'26, 132 trades:
  **88% win, +31.9% of width net; 2024 87%/+19.5, 2025 86%/+34.9, 2026 91%/+31.3.**
  Combined with in-sample: 8 straight years positive, win ≥79% every year, 405 total trades.
- **DEPLOYED 2026-07-04**: v2 runs PARALLEL (engine/stock_credit_v2.py, own book stock_credit_v2*.json, 1 lot); ORB+VWAP RETIRED (ORB_VWAP_ENABLED=False); PM slot + gold-highlighted SWING TRADES section show v2 with win-rate banners. Loop ENDED. (superseded: awaiting-approval note) — `STOCK_CREDIT_*` → SHORT_OFFSET 2, WIDTH 4, TAKE_PROFIT 0.5,
  STOP_MULT 3.0 (DC stays 10) + kickstart engine + studies/UI/wiki updates. USER SAID: show results
  first, do NOT wire without explicit go. Loop STOPPED after presenting.
EXACT stats (per-trade dumps /tmp/stkfade_exact_trades.json + /tmp/stkfade_oos.json): IS 233W/40L=85.35%, win med +32/max+92, loss med −51/worst −72 (%width); 4/60 months negative (worst Nov23 −208); max streak 4L. OOS 116W/16L=87.88%.
HONESTY: never promise riches; 5%/mo infeasible (capital-curve memory); per-year gross→net always;
live fills unproven — keep 1 lot.

## Security constraints (permanent)
- `.env` (Upstox+Kite keys) NEVER committed. Check `git diff --cached --name-only | grep .env` pre-commit.
- Kite API secret was pasted in chat once — user advised to regenerate.
- No secrets in wiki (public). `wiki_push.sh` secret-scans before pushing.
