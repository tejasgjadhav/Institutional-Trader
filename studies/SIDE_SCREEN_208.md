# Per-side screen across all 208 NSE F&O names (27-Sep-2026)

**Question (user).** "If we devise a strategy per bear call and bull put for all 208 names, do we get
more names with higher net and at least 80% win? We rejected companies that failed even one side."

**Premise checked.** Yes — the 24-Aug prune removed eight names on their whole-name net (HCLTECH,
SBILIFE, OFSS, TCS, TECHM, HDFCBANK, DMART, JINDALSTEL); neither side was judged on its own. Only
ICICIGI and PIIND were ever admitted on one good side.

**Method.** Deployed gates and the per-book premium floor (run-5 harness). Universe names: run-5
rows. Pruned 8: re-run today on the same harness (`research/pruned8.py`). 103 outsiders: in-sample
and out-of-sample both re-run today on the same harness (0 failed fetches). Side = breakout direction on the entry day. Books pooled per name-side (one fires per
breakout). Script: `studies/ndte/side_screen_208.py`. All trades (full band), 1 lot, OOS 23 months.

## Result (final, 27-Sep-2026 18:25 — complete data, 0 failed fetches)

| selection | name-sides | OOS signals/mo | OOS win | OOS return | OOS ₹/mo |
|---|---|---|---|---|---|
| **Engine as it runs: today's universe, both sides** | 186 | **25.3** | 83.2% | +17.4% | **₹52,396** |
| All 208 names, both sides | 283 | 35.9 | 79.4% | +13.3% | ₹48,951 |
| User's rule: ≥80% win, ROM > +5%, ≥3 trades, BOTH windows | 34 (all in the universe) | 7.2 | 93.3% | +30.1% | ₹24,429 |
| — outsiders passing | 0 | | | | |
| — pruned-8 passing | 0 | | | | |
| Honest test: sides picked on IN-SAMPLE only | 100 | 12.4 | 85.3% | +18.6% | ₹29,244 |
| — of which outside today's universe | 9 | 0.6 | 76.9% | −7.5% | ₹458 |
| Sides NOT picked on in-sample | 183 | 23.5 | 76.3% | +10.5% | ₹19,707 |

## Verdict
- No rejected or never-admitted name has a hidden good side: every side that passes is already live.
- A side-wise book would cut signals from ~25 to 7–12 a month and roughly halve monthly profit.
  The sides that fail 80% still earn (+₹19.7k/mo), so dropping them costs money. Adding all
  outsiders and the pruned 8 raises signals to ~36/mo but LOWERS monthly profit (₹48,951 vs ₹52,396).
- Side selection does rank sides (85% vs 77% out-of-sample) but the rule's 93% is flattered by
  choosing on both windows. The outside names that looked good in history lost afterwards.
- **Keep both sides of the universe; keep outsiders and the pruned 8 out.** The only per-side
  exceptions that held up in both windows are the three vlc cells.

Figures are full-band backtest ceilings (the live 6% spread gate is not modelled); compare rows with
each other, not with the published median-cohort plan.

## Why this study says ₹52k/month and the P&L table says ₹41k (user, 27-Sep)
Two different baskets of the same run-5 trades:
- **₹52,396/mo** here = stock books only, **every** trade the gates allow (full band, 582 OOS trades).
- **₹40,841/mo** in the P&L table = stock books on the **median cohort** only (v2/v1 c/w 0.40–0.50,
  v0 0.35–0.40: 513 trades, ₹35,035/mo) **plus** the two index 0DTE books (₹5,806/mo).
- The gap is the 69 v2/v1 trades at c/w ≥ 0.50: 91.3% win, ₹17,361/mo. They are excluded from the
  published plan on purpose: out-of-sample cannot use put-call parity, the weaker guards only pulled
  the contaminated median c/w down to 0.54, so trades above 0.50 are where residual pricing error
  can still live — and all 21 real live fills sat inside 0.40–0.50. The engine does trade them; the
  plan just does not count on them.
