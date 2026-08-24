"""Daily report of the forward record — every signal taken, every candidate rejected.

Run:  .venv/bin/python studies/ndte/daily_record.py [YYYY-MM-DD]

The engine writes to data/forward_record.db on every cycle. This reads it back so the day can be
checked against what was reported in chat, and so the 30-trade counter is never guessed at.
"""
import sys, os, sqlite3
from datetime import date
sys.path.insert(0, "/Users/sayali/files/institutional-trader")

DB = "/Users/sayali/files/institutional-trader/data/forward_record.db"
DAY = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
c = sqlite3.connect(DB)

print(f"=== FORWARD RECORD · {DAY} ===\n")

took = list(c.execute("""SELECT book, symbol, side, short_strike, long_strike, credit, cw,
                                spread_pct, qty, status, pnl_rs
                         FROM fills WHERE entry_date=? ORDER BY book, symbol""", (DAY,)))
print(f"SIGNALS TAKEN: {len(took)}")
for r in took:
    sp = f"{r[7]:.2f}%" if r[7] is not None else "n/a"
    pnl = f"  pnl Rs{r[10]:+,.0f}" if r[10] is not None else ""
    print(f"  {r[0]:<12} {r[1]:<12} {r[2] or '':<10} {r[3]:.0f}/{r[4]:.0f}  "
          f"credit {r[5]}  c/w {r[6]}  spread {sp}  qty {r[8]}  [{r[9]}]{pnl}")

rej = list(c.execute("""SELECT book, symbol, reason, detail FROM rejections
                        WHERE trade_date=? ORDER BY book, symbol""", (DAY,)))
print(f"\nCANDIDATES REJECTED BY THE LIVE GATES: {len(rej)}")
for r in rej:
    print(f"  {r[0]:<12} {r[1]:<12} {r[2]:<14} {r[3]}")

tot = len(took) + len(rej)
if tot:
    print(f"\nTAKE RATE TODAY: {100.0*len(took)/tot:.0f}%  ({len(took)} of {tot} candidates)")
    print("  This is the number no backtest can produce: what fraction of signals are actually")
    print("  fillable under the live gates. It converts a backtested ROM into money you can collect.")

n = c.execute("""SELECT COUNT(*) FROM fills WHERE book IN ('v2','v1')
                 AND entry_date>='2026-08-06' AND status='CLOSED' AND advisory=0""").fetchone()[0]
print(f"\n>>> 30-TRADE COUNTER: {n}/30 closed  (v2+v1, post 6-Aug)")
print("    Criteria fixed in studies/FORWARD_RECORD_DECISION_RULE.md before any data existed.")
if n >= 30:
    print("    *** TARGET REACHED — run the decision rule. ***")

sp = c.execute("SELECT COUNT(*), AVG(spread_pct), MAX(spread_pct) FROM fills WHERE spread_pct IS NOT NULL").fetchone()
if sp[0]:
    print(f"\nSPREADS SEEN SO FAR: n={sp[0]}  avg {sp[1]:.2f}%  worst {sp[2]:.2f}%  (gate allows 6%)")
