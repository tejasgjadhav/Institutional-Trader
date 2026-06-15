import json, os
from engine.option_live_backtest import collect_option_trades, simulate_premium
CACHE="/tmp/rr_trades.json"
def prog(i,t,u):
    if i%30==0 or i==t: print(f"  {i}/{t}",flush=True)
if os.path.exists(CACHE):
    tr=json.load(open(CACHE))
    for t in tr: t['path']=[tuple(x) for x in t['path']]
    print(f"loaded {len(tr)} cached trades")
else:
    print("collecting 30 days (with premium paths)..."); tr=collect_option_trades(n_days=30, cutoff="13:00", progress=prog)
    json.dump(tr, open(CACHE,"w"), default=str); print(f"{len(tr)} trades cached")

days=sorted({t['day'] for t in tr}); split=days[int(len(days)*0.6)]
train=[t for t in tr if t['day']<split]; test=[t for t in tr if t['day']>=split]

def stats(trades,tgt,stp):
    res=[simulate_premium(t,tgt,stp) for t in trades]
    n=len(res)
    if not n: return (0,0,0)
    win=sum(1 for o in res if o[1]>0)/n*100; net=sum(o[1] for o in res)/n
    return (n,win,net)

print(f"\nRISK-REWARD SWEEP · 30 days · {len(tr)} signals (train {len(train)} / test {len(test)})")
print(f"{'tgt%':>5}{'stop%':>6}{'R:R':>6}{'ALLwin':>8}{'ALLnet':>8}{'TESTwin':>9}{'TESTnet':>9}")
rows=[]
for tgt in [5,8,10,12,15,20,25,30,40]:
    for stp in [3,5,8,10,15,20]:
        na,wa,nta=stats(tr,tgt,stp)
        nte,wte,ntte=stats(test,tgt,stp)
        rr=tgt/stp
        rows.append((tgt,stp,rr,wa,nta,wte,ntte,na))
# print all, mark profitable + high win
for tgt,stp,rr,wa,nta,wte,ntte,na in rows:
    mark=""
    if nta>0 and ntte>0: mark+=" $"        # profitable both
    if wa>=65: mark+=" W"                   # high win rate
    print(f"{tgt:>5}{stp:>6}{rr:>6.1f}{wa:>7.0f}%{nta:>+8.2f}{wte:>8.0f}%{ntte:>+9.2f}{mark}")
print("\n$ = net-positive on both all & test | W = >=65% win rate")
print("RRDONE")
