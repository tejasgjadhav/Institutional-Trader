# Live strategies — one-table summary (updated 16-Oct-2026: run 6 stocks, new 0DTE rules)

Every live paper book, on its own gates, as deployed. Stock books: harness of record run 6 of
11-Oct-2026 (`RUN6_TRADED_LEGS.md`), which counts a leg only on days it actually traded. All c/w, 107
live names, 1 lot, friction 1.0x. IS = 2019→Sep-2024 (69 months). OOS = Oct-2024→10-Aug-2026
(22.3 months, Upstox cache). ROM is on rupee margin. Mirrored on the STUDIES tab. Run-5 figures are
in git history and must not be quoted.

| Book | Gate | Short leg | Exit | IS trades · win · ROM | OOS trades · win · ROM | OOS signals/mo | OOS ₹/mo |
|---|---|---|---|---|---|---|---|
| ★ Stock v2 UNION | c/w ≥ 0.40, no ceiling | ≥ ₹50 | book 50%, no stop | 238 · 61.3% · +5.4% | 72 · 81.9% · +22.3% | 3.2 | ₹8,138 |
| Stock v1 | c/w ≥ 0.40, Donchian-10, no ceiling | ≥ ₹30, or BP sub-floor | book 40%, no stop | 624 · 77.4% · +10.7% | 313 · 79.9% · +11.1% | 14.0 | ₹16,865 |
| Stock v0 | c/w 0.35–0.40 | ≥ ₹30, or BP sub-floor | book 40%, no stop | 283 · 83.4% · +7.3% | 155 · 81.3% · +6.5% | 7.0 | ₹6,416 |
| Sidewise low credit (vlc) | c/w 0.30–0.40, 21 name-sides | ≥ ₹50 | book 40%, no stop | 90.7% on its cells | 93.4% (cells chosen on OOS) | ~3.5 | ~₹3,600 planning, not in total |
| vlc cells | c/w 0.25–0.30: ULTRACEMCO BC, HINDUNILVR BP, BAJAJFINSV BP | ₹30–50 | book 40%, no stop | 20 · 95% · +17.8% | 16 · 100% · +17.5% | ~0.7 | not in total |
| 0DTE NIFTY (Tue; Mon if Tue is a holiday) | expiry-day spread, FLIP side | — | hold to settle (since 16-Oct) | 88% | 91.6% · 83 expiries | ~3.4 | ₹1,716 |
| 0DTE SENSEX (Thu; Wed if Thu is a holiday) | bear call 0.5% above; **gap-up ≥ 0.25% → bull put 0.5% below** (since 16-Oct) | — | hold to settle | n/a (weeklies from Oct-2024) | 91.2% · 91 expiries | ~3.8 | ₹2,214 |
| **Total** | | | | | **714 trades** | **~31** | **₹35,349** (with vlc ~₹38,950; plan at 80%: ₹28,279) |

**BP sub-floor (permanent since 11-Oct-2026):** a v1 or v0 bull put with a short leg below ₹30 is
taken when the short leg is at least ₹10 and credit × lot is at least ₹3,000. It is tagged
`floor_rule="bp_subfloor"`. Bear calls and v2 keep their floors.

All stock books also need a two-sided quote on both legs, short-leg bid-ask ≤ 6%, open interest,
≥ 10 days to expiry and a 3-day cross-book re-entry gap. Trades above c/w 0.50 are included, because
run 6 no longer prices them off stale prints.

- Stock system: IS 75.5% win, +8.6% ROM, 16.6 a month, ₹12,789 a month; OOS 80.6%, +10.9%, 24.2 a
  month, ₹31,419 a month.
- Complete NSE path to 18-Sep-2026: 78.7% win, +9.0% ROM, 25.3 a month, ₹27,210 a month.
- At 0.75x friction OOS reads +12.8% and ₹36,695 a month.
- Average OOS win ₹3,899 and loss ₹9,479. Worst trade −₹22.0k. Max drawdown ₹140.7k.
- 0DTE rows are the 16-Oct-2026 re-test on real 1-minute prices to 8-Oct-2026, held to settle, SENSEX with
  the gap-up rule (`SENSEX_RALLY_GUARD.md`). 15-Oct is not in them yet.
- Figures are backtest ceilings. The live 6% spread gate is not modelled.

**Off / rejected:** index swing fade (removed 24-Jul), T-1 EVE (disabled 17-Sep), monthly futures
(regime-off, needs ~₹15L), BANKNIFTY 0DTE (rejected 19-Jul).
