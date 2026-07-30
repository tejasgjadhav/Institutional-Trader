# v1 win-rate sweep — raise win% with ZERO signal loss (2026-07-30)

**Goal (user):** better v1's win rate (64% IS / 73% OOS) **without compromising signal count**, sweeping
all technical parameters.

## Constraint handling
Entry gates (DC10, c/w≥0.40, prem≥₹50, min-DTE 10, reentry 3d, 113-name universe) stay FIXED — anything
touching them cuts signals. The n-preserving levers are the **exit** (TP fraction, stop) and, tested but
rejected, geometry: s2w4→286, s2w3→390, s1w4→571 trades (vs 755) — all violate the constraint despite
better per-trade stats.

## Method
- IS: `studies/ndte/stkfade_v1_sweep.py` on NSE bhavcopy 2019→Sep'24 (755 trades). Faithfulness: reproduced
  deployed v1 (755 / 64.0% / +10.3%w) and the v2 cross-check (85.3%) before trusting the grid.
- OOS: `studies/ndte/stkfade_v1_oos_exits.py` — fetched each v1-geometry trade's REAL Upstox premium path
  once (Oct'24→2026-07-30, 242 trades after gates), then evaluated all four exits on the SAME trades.
  Deployed exit reproduces its known OOS (73.6% vs 73.4% ledger). Entry+exit slippage charged.

## Result — same trades, four exits

| Exit | IS win (n=755) | IS net %w | OOS win (n=242) | OOS net %w | OOS by year win% |
|---|--:|--:|--:|--:|---|
| deployed TP-75 stop2× | 64.0% | +10.3% | 73.6% | +15.1% | 78 / 74 / 72 |
| TP-40 stop3× | 82.0% | +15.9% | 84.3% | +15.8% | 96 / 85 / 81 |
| TP-50 no-stop | 82.4% | +18.8% | 83.9% | **+19.0%** | 93 / 84 / 82 |
| **TP-40 no-stop** | **85.0%** | +18.2% | **86.0%** | +17.6% | 96 / 85 / 84 |

Time-exit overlays (book day-N if profitable) were marginal (~73–74%) — not competitive.

## Verdict
- **TP-40/no-stop**: best win rate in BOTH windows (85.0/86.0 — near-identical, the signature of a real
  mechanism, not a fit), net ~+7–8%w above deployed in IS and +2.5%w in OOS, positive every year, worst
  year 71.8% (IS) / 84% (OOS). **n unchanged at 755/242 — zero signals dropped.**
- **TP-50/no-stop**: ~2 pts less win, best OOS net (+19.0%w) — the net-optimal alternative.
- Mechanism = v2's recipe on v1's geometry: book the IV-crush early; the 2× stop was realizing losses that
  recover (same finding as `SWING_PUTCALL_STOP_ANALYSIS.md`); "no stop" stays defined-risk — max loss is
  capped by the bought wing at (width − credit).

## Honest caveats
- Win% gains from earlier TP are partly mechanical (smaller banked wins) — but here net%w ALSO rises, so it
  is not cosmetic.
- Gross of taxes; entry+exit slippage modeled (2.5%-scaled/leg); mid-cap live fills still erode net.
- OOS is the single Oct'24→now regime; IS↔OOS agreement is the defense.
- Changing v1 loses the TP-75 "control" benchmark unless a shadow control is kept.

**Not deployed — awaiting user decision.**
