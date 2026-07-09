# 0DTE entry-time sweep — later entry buys win rate by selling the edge (2026-07-09)

**Question (user goal loop):** enter the NIFTY 0DTE CE spread at 9:45–10:00 "or any time
which does that" to maximize win rate while keeping profitability/margin intact.

**Method:** real 1-min expired-contract premiums, 92 expiries Oct'24→Jul'26 (the only window
with intraday option data — 2019–24 bhavcopy has open prints only, so this is single-regime
evidence). Same harness as the stop study (`ndte7`): entry = first 1-min bar ≥ T, costs 2.5%
of (s0+l0) + ₹20×4, settle intrinsic vs NIFTY close. Spot at T from Upstox v3 5-min index
candles. Two variants per time: **RESTRIKE** (short = 0.5% OTM of spot at T, wing +200) and
**SAMESTRIKE** (open-based strikes, entered at T). Script `studies/ndte/ndte11_entrytime.py`,
results `/tmp/ndte11_results.json`. The 09:16 row reproduces `ndte7`'s deployed baseline
exactly (90.4% / +5.85%m / ₹49,527) — harness validated.

## Results (rv5<0.9 calm filter ON — the deployed book), 1 lot

| Entry | RESTRIKE win / avg%m / tot₹ | SAMESTRIKE win / avg%m / tot₹ | med credit (restrike) |
|---|---|---|---|
| **09:16 (deployed)** | **90.4 / +5.85 / +49,527** | same | 13.2 |
| 09:30 | 90.4 / +3.41 / +35,898 | 91.8 / +2.68 / +26,662 | 12.5 |
| 09:45 | 93.2 / +2.88 / +31,378 | 87.7 / +4.53 / +35,656 | 12.1 |
| 10:00 | 94.5 / +2.48 / +28,747 | 87.7 / +4.48 / +37,346 | 11.1 |
| 10:30 | 91.8 / +0.12 / +4,982 | 86.3 / +2.73 / +26,342 | 8.8 |
| 11:00–12:00 | 86–90 / NEGATIVE | 73–84 / ~flat | 5–7 |
| 13:00–14:00 | thin credits, noise | <55 win unfiltered | ≤3 |

Unfiltered ("all") rows: only 09:16 is meaningfully positive (+2.21%m); every later entry is
flat-to-negative. Small-n oddities (e.g. 14:00 rv5+credit-gate, n=9, 100% win) are the credit
gate cherry-picking rare fat-premium afternoons — not tradeable evidence.

## Findings

1. **Win rate does rise with later entry** — RESTRIKE 09:45 = 93.2%, 10:00 = 94.5% (vs 90.4%
   at the open). Mechanism: by 10:00 the day's direction is partly revealed and the restrike
   moves the short strike above the morning's move, dodging small adverse drifts.
2. **But it costs ~35–45% of total profit** (₹49.5k → ₹28–31k) because the strategy's edge IS
   the opening theta/IV crush: median credit decays 13.2 → 11.1 pts by 10:00 and the first
   30–45 min of decay is the richest. On the *same* strikes, entering later is strictly
   giving away collected theta (SAMESTRIKE monotonically worse).
3. **The tail is NOT reduced.** Worst trade at 10:00 restrike = −₹11,771 vs −₹11,703 at the
   open. Full-width disaster days trend all day; restriking higher at 10:00 doesn't escape
   them. So later entry does not buy the risk reduction that would justify the profit give-up.
4. **The win-rate difference is ~3 trades on n=73** — not statistically significant, while the
   profit difference is large and monotonic across every time step. Margin/lot is unchanged
   (~₹14k; credit is small vs the 200-pt width) — return ON that margin is what halves.
5. **Better lever for max win rate already exists:** the d=0.75% sibling at the open — 94.5%
   OOS win with the filter, +3.33%m (validated IS 2019–24 too, unlike this sweep) — dominates
   the 10:00-entry route to the same win rate.

## Verdict — keep 09:16 entry; one actionable nugget

**Do not move the entry to 9:45–10:00.** It fails the stated goal: win rate +3–4pp (noise-level)
for a 35–45% profit haircut, no tail benefit, and single-regime evidence only.

**Nugget (not deployed):** `ZERO_DTE_ENTRY_CUTOFF` is 09:45 — the engine skips the day entirely
if it misses the open (restart/feed outage). This sweep says a missed open is still worth
+2.5–2.9%m (93–94% win) entered as late as 10:00 **with a restrike at entry spot**. Extending
the cutoff to ~10:00 (restriked) would recover otherwise-skipped days. Needs user approval;
after ~10:15 the credits no longer clear costs — never enter later than that.
