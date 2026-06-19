import sys
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import studies.orbvwap as o
o.TGT = 20.0
N = 30
def summ(trades):
    n=len(trades)
    if not n: return "no trades"
    g=sum(1 for t in trades if t["pnl"]>0); net=sum(t["pnl"] for t in trades)/n
    rs={}
    for t in trades: rs[t["reason"]]=rs.get(t["reason"],0)+1
    aw=[t["pnl"] for t in trades if t["pnl"]>0]; al=[t["pnl"] for t in trades if t["pnl"]<=0]
    return (f"n={n:3} win={round(g/n*100):3}% net={net:+5.2f}%/tr  "
            f"avgW={sum(aw)/max(1,len(aw)):+5.1f} avgL={sum(al)/max(1,len(al)):+5.1f}  exits={rs}")
print(f"=== ORB+VWAP INDEX options · {N}-day · ATM · -20% stop ===\n")
for lbl,kw in [("OLD LIVE: fixed +20% target", dict(exit_mode="target", stop_pct=20, clean_filter=False)),
               ("NEW: trend-ride + clean filter", dict(exit_mode="breathe", stop_pct=20, clean_filter=True)),
               ("  (trend-ride, no clean filter)", dict(exit_mode="breathe", stop_pct=20, clean_filter=False))]:
    t=o.run(n_days=N, strike_off=0, **kw)
    print(f"  {lbl:32}: {summ(t)}")
