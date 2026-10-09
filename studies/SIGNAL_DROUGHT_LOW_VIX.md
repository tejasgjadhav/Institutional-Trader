# Few swing calls and the same names, Aug–Oct 2026 (8-Oct-2026, corrected after an independent audit)

**Question (user, 8-Oct-2026):** For about two months the stock-credit books (v2, v1, v0, vlc) have
traded only a few names, LTM, TATAELXSI, COFORGE and INDIANB, and very rarely. Find the bug.

**Verdict after the audit: partly explained, not solved.** The drought is real in the live option
prices for all four books, and no bug was found in the trading path that suppresses signals. **But low
VIX does not explain it.** At the same VIX level in Jul–Dec 2025, the backtest took about 12 trades a
month on 42 different names. Live has taken about 3 a month on 6 names since the 6-Aug fix. That gap is
not yet explained. The likely place to look is stock-level implied volatility and strike grids, not
the code.

The audit also found three real problems:

1. **Nine universe names can never trade.** ACC, BALKRISIND, INDIAMART, DALBHARAT, UBL, NAVINFLUOR,
   MRF, ATUL and DEEPAKNTR have no option contracts in the current Upstox contract master. The master
   was refreshed on 8-Oct and holds 0 contracts for each. They show NO_STRIKE every day. Their last
   backtest trade was on 8-Apr-2026, which looks like an F&O exit. So the real universe is 107 names,
   not 116, and two vlc cells are dead: ACC bull put and INDIAMART bear call. Nothing logged it.
2. **About a third of September's scans were impaired.** 7 of 21 trading days had no scan, failed on
   HTTP 429, or ran late as record-only. 22-Sep and 25-Sep had no scan because the Mac was asleep;
   23-Sep and 30-Sep were wiped by 429s; 29-Sep left about 50 names unread; 11-Sep and 28-Sep ran late.
   On the days with a watchlist, the highest c/w was 0.29–0.31 (v2 geometry), so probably 0–2 trades
   were lost, including ZYDUSLIFE on 28-Sep. Both causes have since been fixed: the engine moved to
   the AWS server on 28-Sep, and Upstox calls have been paced since 1-Oct.
3. **Gate rejections are not recorded.** The forward record's `rejections` table has 0 rows since it
   was wired in on 21-Aug. Every exit from the 15:36 scan (missing quote, c/w, premium, spread) is a
   silent `continue`. So the CLAUDE.md figure that the spread gate blocks ~59% of candidates is not
   backed by the live record.

One real fault turned up before the audit: the 15:31 digest starred COFORGE on 5-Oct while vlc already
held it. That was fixed on 6-Oct (commit fd98f34).

## 1. Live signals since the 6-Aug stale-bar fix

| Month | Stock fills | Names |
|---|---|---|
| Jun 2026 | 5 | five different names |
| Jul 2026 | ~16 | many names (the T-1 era, before the 6-Aug fix) |
| Aug 2026 | 5 (4 after the 6-Aug fix) | GRASIM ×2, HAL, BOSCHLTD, ULTRACEMCO |
| Sep 2026 | 2 | LTM ×2 |
| 1–7 Oct 2026 | 2 | COFORGE, LTM |

Source: data/forward_record.db `fills`. Every live fill before 6-Aug-2026 was a T-1 signal, so the
June and July counts are not comparable with the months after.

## 2. The saved 15:31 watchlists show the gate is the binding constraint (v2 geometry)

16 saved watchlists (data/watchlist_archive, 11-Sep to 7-Oct) held 10–70 breakouts a day, and 116
distinct names broke out over the period. **Not one row reached c/w 0.40.** About seven rows a month
reached 0.35–0.40, and about twenty reached 0.30–0.35. Most rows also failed the short-leg premium
floor. The highest value on any of the 16 days was 0.39.

The watchlist prices every stock at v2's geometry only. The audit rebuilt v1's geometry (1 strike OTM,
width 3, Donchian-10 breakouts) from daily option closes for 21-Sep to 7-Oct: 74 rows. v1 c/w ran at a
median of 1.32× v2's. Only four rows reached 0.40:
- LTM on 7-Oct (0.441), which was taken.
- ZYDUSLIFE on 24-Sep (0.407), on a healthy scan day. It was not taken, and nothing records why. It
  sits within close-versus-mid noise.
- ZYDUSLIFE on 28-Sep (0.407), on a late, record-only scan day.
- BHEL on 6-Oct (0.40), whose Rs16 short leg is below the Rs30 floor.

## 3. The backtest's trade count rises with VIX, but VIX does not explain live

| Month | India VIX (median) | Backtest trades, live-universe names only |
|---|---|---|
| Jul–Dec 2025 | 10.1–12.2 | 9–18 a month (73 trades on 42 names in total) |
| Jan 2026 | 11.4 | 43 |
| Mar–May 2026 | 17.9–21.6 | 43–68 |
| Jun–Jul 2026 | 12.9–14.3 | 39 and 36 |
| Aug 2026 (to 10-Aug) | 11.4 | 5 |

The first draft of this table merged research/expansion2/oos_rows.json, whose ~40 outsider names are
not in UNIVERSE. That inflated the counts to 50–97. The table above uses live-universe names only.

**At matched VIX the backtest still took about four times as many trades as live.** In Jul–Dec 2025 it
took about 12 a month on 42 names (v1 53, v0 13, v2 7), led by TITAN, MARUTI, DIVISLAB and LT. Live
has taken 7 non-vlc fills in about 2.1 months. Even allowing for the impaired September scans, the
Poisson chance of so few is about 0.2%. The rebuilt v1 c/w shows the live option prices really lacked
credit, so the gap sits in market data nobody has measured yet.

## 4. Ruled out: a pricing difference between the backtest and the live engine

The backtest prices both legs at the day's closing trade. The live engine prices them at the bid/ask
mid at 15:31. A stale wing price could make backtest c/w run higher than live c/w. The check
(`research/cw_construct_check.py`, results in `research/cw_construct_check.json`) re-priced 121
stock-days from the 15:31 watchlists, 21-Sep to 7-Oct, at their daily close. The median difference
was −0.001. Neither construct found a single row at 0.40.

**Limit of this check (from the audit):** it sampled only the top 15 rows a day, October expiry and v2
geometry. Only 1 of the 121 rows was at 0.35 or above, so it never tested the region near the 0.40
threshold. It also compares 15:31 quotes with 15:40 closes.

## 5. Why the same names repeat (partly refuted)

In the live record only a few high-volatility names (IT midcaps and PSU banks) pay rich relative
premium. Across 107 names, short-strike distance as a % of price correlates −0.52 with c/w. **The
audit refuted the idea that low VIX alone limits trading to these names.** At the same VIX in H2 2025
the backtest spread its trades over 42 names.

## 6. Checked, no bug found (config ledger checked by me, the rest by the audit)

- No configuration change touched the gates or the geometry. `STOCK_CREDIT_MIN_CW` is 0.40. The
  config ledger shows only whitelist edits, the 27-Sep per-book premium floors and the OI change of
  17-Aug.
- The scan read every name it could on 1, 5, 6 and 7 Oct, with 0 HTTP 429 after the 1-Oct pacing fix,
  but nine names have no contracts (see above). No breakout appeared only at the close.
- Position caps were never reached (open counts 1, 0, 1, 1 against caps of 20, 20, 10, 10), so
  universe order and the early `break`s have no effect.
- The cross-book re-entry gap and the per-book already-open rule work as designed. Example: v1 skipped
  LTM on 24-Sep because it held LTM from 7-Sep, and v0 took it.
- The 1-Oct caches serve no stale data. Daily history holds only bars before today, the 90 s close
  cache cannot reach from 15:31 to 15:36, and the 60 s quote cache is shared from v2 to v0 to vlc as
  intended.
- Strikes are chosen by position in the ladder, and LTM's October ladder mixes 50- and 100-point steps,
  so widths shift with the ladder. This does not suppress signals.

Audit scripts and outputs are in research/audit_drought/.

## Follow-up (9-Oct-2026)

Steps 1 and 2 below are DONE and live: rejection logging (commit 008734e) and the universe cleanup to 107
names (commit 86f30a4). Step 3 is answered in [STRIKE_GRID_IV_GAP.md](STRIKE_GRID_IV_GAP.md): the gap sits
in coarser strike ladders in the Aug and Sep 2026 series, a shift to bull puts, and lower IV. No code bug.

## Next steps (proposed on 8-Oct)

1. Remove the nine no-contract names from UNIVERSE and the two dead vlc cells. This is a config
   change, so it needs approval.
2. Record every 15:36 gate rejection with its reason in the forward record's `rejections` table.
   This is logging only; it does not change trading.
3. Measure stock-level IV and strike grids for H2 2025 against Aug–Oct 2026, to explain the 4× gap
   at matched VIX.

## What would add calls, and why each was already rejected

- c/w below 0.35: dead out of sample (CW_BAND_BY_BOOK.md, LOWCW_BAND_RESCUE.md).
- All 208 F&O names: more signals and less profit (SIDE_SCREEN_208.md).
- A side-wise book: halves profit (SIDE_SCREEN_208.md).

Part of a quiet month is the strategy declining thin trades. The rest is unexplained until step 3 is done.
