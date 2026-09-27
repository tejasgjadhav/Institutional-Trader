# Live strategies — one-table summary (updated 27-Sep-2026)

Every live paper book, on its own gates, as deployed. Stock books: harness of record run 5 (clean
pass, 0 dropped signals). IS = 2019→Sep-2024, 116-name basis, median cohort, ROM on rupee margin.
OOS = Oct-2024→Aug-2026 (23 months), median cohort, ROM in points. ₹ at 1 lot. Mirrored on the
STUDIES tab. July's version of this table is in git history.

| Book | Gate | Short leg | Exit | IS | OOS | OOS signals/mo | OOS ₹/mo |
|---|---|---|---|---|---|---|---|
| ★ Stock v2 UNION | c/w ≥ 0.40, no ceiling | ≥ ₹50 | book 50%, no stop | 213 · 77.9% · +21.2% | 79 · 86.1% · +26.6% | 3.4 | ₹12,417 |
| Stock v1 | c/w ≥ 0.40, Donchian-10, no ceiling | ≥ ₹30 | book 40%, no stop | 485 · 80.6% · +11.6% | 289 · 81.0% · +13.9% | 12.6 | ₹15,020 |
| Stock v0 | c/w 0.35–0.40 | ≥ ₹30 | book 40%, no stop | 311 · 86.2% · +15.2% | 145 · 82.1% · +2.6% | 6.3 | ₹7,598 |
| Sidewise low credit (vlc) | c/w 0.30–0.40, 21 name-sides | ≥ ₹50 | book 40%, no stop | 90.7% on its cells | 93.4% (cells chosen on OOS) | ~3.5 | not in total |
| vlc cells | c/w 0.25–0.30: ULTRACEMCO BC, HINDUNILVR BP, BAJAJFINSV BP | ₹30–50 | book 40%, no stop | 20 · 95% · +17.8% | 16 · 100% · +17.5% | ~0.7 | not in total |
| 0DTE NIFTY (Tue) | expiry-day spread | — | same day | 88% | 90% · 73 trades | ~4 | ₹2,775 |
| 0DTE SENSEX (Thu) | expiry-day spread | — | same day | n/a (weeklies from Oct-2024) | 88.8% · 89 trades | ~4 | ₹3,031 |
| **Total** | | | | | **675 trades** | **~30** | **₹40,841** (plan at 80%: ₹32,673) |

All stock books also need a two-sided quote on both legs, short-leg bid-ask ≤ 6%, open interest,
≥ 10 days to expiry and a 3-day cross-book re-entry gap. Trades above c/w 0.50 are taken by v2/v1 but
excluded from the plan: they add ~₹17,361/mo (69 trades, 91.3%) — the full-band ceiling is ₹52,396/mo
for the stock books. Figures are backtest ceilings; the live spread gate is not modelled.

**Off / rejected:** index swing fade (removed 24-Jul), T-1 EVE (disabled 17-Sep), monthly futures
(regime-off, needs ~₹15L), BANKNIFTY 0DTE (rejected 19-Jul).
