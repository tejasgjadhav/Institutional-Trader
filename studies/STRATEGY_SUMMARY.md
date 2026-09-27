# Strategy Summary — current structure (updated 27-Sep-2026)

The canonical view of the live system. July's version of this file is in git history.

**One strategy family carries the book: fade a Donchian breakout by selling a credit spread against
it, only when the market pays a rich credit for the risk.** Credit ÷ width is the edge; the premium
floor keeps the legs tradeable; no stop, because the bought wing caps the loss.

| Book | What it is | Why it exists |
|---|---|---|
| v2 UNION | short 2-OTM, width 4, c/w ≥ 0.40, ₹50 floor, book 50% | the leader; highest return per trade |
| v1 | short 1-OTM, width 3, Donchian-10, c/w ≥ 0.40, ₹30 floor, book 40% | the biggest earner; most signals |
| v0 | v2 geometry one band lower (0.35–0.40), ₹30 floor, book 40% | the watch book; thin return |
| vlc | 0.30–0.40 on 21 name-sides + 3 cells at 0.25–0.30 (₹30–50) | side-locked exceptions that held in both windows |
| 0DTE NIFTY / SENSEX | expiry-day index spreads | high win rate, small money |

Current figures: `LIVE_STRATEGIES.md`. Evidence: `PREMIUM_FLOOR_SWEEP.md` (floors, run 5),
`CW_BAND_BY_BOOK.md` (bands), `MIN_DTE_SWEEP.md` (10 days), `DONCHIAN_5_10_15_20.md` (union),
`STOCK_FADE_TP50_UPGRADE.md` and `TP_SWEEP_208.md` (exits), `SIDE_SCREEN_208.md` (per-side lists
rejected), `LAST_3_MONTHS_JUN_AUG_2026.md` (why not everything above 0.25).

**Settled — do not reopen without new data:** c/w below 0.35 (negative OOS), v2 below a ₹50 floor,
side-wise lists and outsider names (lower monthly profit), DTE 10, re-entry gap 3 days, no stops.
