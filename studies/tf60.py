"""
Confirmation: re-run 10-min and 15-min over 60 days (double the sample), with a
per-day win distribution to check the edge isn't a few lucky days.
"""
import sys
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import tf  # reuse collect_tf/report/winrate/split from /tmp/tf.py
import importlib; importlib.reload(tf)
from collections import Counter

def perday(rows, key):
    byday={}
    for r in rows:
        v=r.get(key)
        if v is None: continue
        byday.setdefault(r["day"],[]).append(1 if v>0 else 0)
    return byday

for factor,orb,mom,name in [(2,3,6,"10-min"),(3,2,4,"15-min")]:
    print(f"\n\n#### {name} candles — 60 DAYS ####",flush=True)
    rows=tf.collect_tf(factor,orb,mom,n_days=60)
    tf.report(f"{name} 60d",rows)
    bd=perday(rows,"p2010")  # +20/-10 (2:1)
    ndays=len(bd); tot=sum(len(v) for v in bd.values()); wins=sum(sum(v) for v in bd.values())
    pos=sum(1 for v in bd.values() if sum(v)/len(v)>=0.5)
    print(f"  +20/-10 per-day: {ndays} trading days, {tot} trades, {wins} wins; "
          f"{pos}/{ndays} days were net-winning ({round(pos/ndays*100) if ndays else 0}%)")
