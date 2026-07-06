# Intraday 90%-win study — the win rate exists, the money doesn't

**Question (user goal, 2026-07-06):** find an intraday strategy (closed same day) with a ~90% win
rate on all available historical data, report its average return, liquid enough for a retailer.

**Data:** the cached Zerodha Kite 5-min bars (`/tmp/k5m`), all 100 F&O universe stocks,
**2019-01-01 → 2026-07-03** (~7.5 years, ~139k bars/stock) — the same real dataset as
`BUY_STRATEGIES_2019_REALTEST.md`. Intraday option premiums do not exist historically
(`DATA_AVAILABILITY_LIMITS.md`), so this is measured on the **underlying** (intraday equity MIS /
stock futures — the retail-liquid vehicles).

**Method:** entry families × exit-geometry grid, split **TRAIN 2019–23 / TEST 2024–26**:
- Entries: **mean-reversion VWAP flush** (buy when price ≤ thr% below day-VWAP; mirror short;
  thr ∈ {0.75, 1.0, 1.5, 2.0}), **ORB momentum** (30-min range break + 1.2× volume surge),
  **no-signal baseline** (long at 10:00) to expose pure geometry. Signals 9:45–14:00, entry at
  signal-bar close, evaluation from the NEXT bar (no lookahead).
- Geometry: TP ∈ {0.20…0.75%} × SL ∈ {1.0…3.0%} × forced EOD close 15:20. Conservative
  intrabar resolution (SL first on ties).
- Costs: 0.10% round trip (discount brokerage + STT + txn + ~1-tick slippage on these liquid names).

## Result 1 — a genuine, stable 90% win rate exists

**Fade a 2% VWAP flush long, TP +0.20%, SL −3.0%, EOD close.** 7,688 trades:

| Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | ALL |
|---|---|---|---|---|---|---|---|---|---|
| Win% | 90.6 | 92.4 | 93.5 | 92.2 | 91.6 | 91.6 | 89.1 | 91.3 | **92.0** |
| Avg net %/trade | −0.12 | −0.10 | −0.05 | −0.07 | −0.13 | −0.12 | −0.09 | −0.07 | **−0.095** |

TRAIN 92.2% / TEST 90.8% — the win rate is real, out-of-sample, every year ≥89%.

## Result 2 — its average return is zero gross, negative net

**+0.005% gross / −0.095% net per trade.** Wins are +0.20%, the ~8% of losses are −3.0%
(9:1 the other way) plus mixed EOD closes — the expectancy nets to ~nothing before costs and
loses after. Not one of the 8 years is net-positive.

## Why (the structural point, now proven on 7.5 years)

- Geometry alone manufactures the win rate: the **no-signal baseline** at the same TP0.2/SL3.0 is
  already **82.7% win** (random-walk first-touch ≈ SL/(TP+SL) = 93.75%, diluted by EOD closes),
  at −0.042% gross. Win rate is bought by risking 15× the target, not by being right.
- The flush signal DOES add real value: +9pp win rate and +0.047% gross vs baseline — consistent
  with the durable-but-tiny directional edge of `BUY_STRATEGIES_2019_REALTEST.md` (+0.107%).
  **But the edge (~0.05%) is smaller than the retail cost (~0.10%).**
- **Nothing in the entire grid is net-positive**: 2,400 cells (3 families × thresholds × 30
  geometries), best TEST net = −0.083%/trade. Study B's conclusion (win rate and profit are
  mutually exclusive for intraday direction) reconfirmed on 26× more data.

## Honest answer to the goal

| | |
|---|---|
| 90% win intraday strategy? | **Yes** — VWAP-flush fade, TP 0.20% / SL 3.0% / EOD close; 92% IS, 91% OOS, 7,688 trades |
| Average return | **≈ 0.00% gross, −0.095% net per trade** (−0.5%/mo per slot at ~5 trades/day book) |
| Liquid for retail? | Yes (top-100 F&O names, intraday equity) — liquidity is not the problem; expectancy is |
| Deployable? | **No.** The 90% is exit geometry, not edge. |

**What actually pays ~90%-shaped win rates in this repo:** selling option premium with defined
risk — stock fade v2 (`STOCK_FADE_TP50_UPGRADE.md`): 85% win IS / 88% OOS with +24–32% of width
per trade — but it is **multi-day** (holds overnight; that's where the theta/IV-crush edge lives,
and intraday option history doesn't exist to prove an intraday version). The profitable *intraday*
shape is the opposite of high-win: asymmetric low-win/high-reward (`WIN_RATE_RESEARCH_LOG.md` §10).

## Reproduce
`studies/intraday90_bt.py` (self-contained, reads `/tmp/k5m`, ~90 s) → prints the grid and writes
`intraday90_acc.json` (per family/thr/TP/SL/year accumulators). Generated 2026-07-06.
