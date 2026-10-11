# Cash-futures arb with early unwind. Enter at cycle start if basis >= TH. Each later close, if the basis has
# fallen to <= X, unwind both legs (profit = b0 - b_t - costs) and free the capital; else hold to expiry.
# Early unwind costs more than delivery: 0.40% round trip vs 0.35%. Basis uses SETTLE where present (2024-07+),
# else close; a one-day basis drop that reverses next day is treated as a stale print and not traded.
import pandas as pd, numpy as np
P=pd.read_csv("panel_ext.csv.gz",parse_dates=["date","expiry"]); P=P[(P.close>0)&(P.expiry>=P.date)]
P["px"]=np.where(P.settle>0,P.settle,P.close)
S=pd.read_parquet("cash_raw.parquet").reset_index().rename(columns={"Close":"spot","sym":"symbol"})
A=pd.read_csv("arb_trades.csv",parse_dates=["ent","exp"])
F=P.merge(S,on=["date","symbol"]); F["b"]=F.px/F.spot-1
rows=[]
for TH in (0.006,0.008):
    for X in (None,0.0,0.001,0.002):
        out=[]
        for t in A[A.basis>=TH].itertuples():
            f=F[(F.symbol==t.sym)&(F.expiry==t.exp)&(F.date>t.ent)&(F.date<t.exp)].sort_values("date")
            b=f.b.values; d=f.date.values; ex=None
            if X is not None:
                for i in range(len(b)-1):
                    if b[i]<=X and b[i+1]<=X+0.002: ex=i; break      # confirmed, not a one-day stale print
            if ex is None: pnl=t.basis-0.0035; days=(t.exp-t.ent).days
            else: pnl=t.basis-b[ex]-0.0040; days=max((pd.Timestamp(d[ex])-t.ent).days,1)
            out.append((pnl,days,ex is not None))
        o=pd.DataFrame(out,columns=["pnl","days","early"])
        rows.append(dict(TH=TH,X=X,n=len(o),early=o.early.mean(),pos=(o.pnl>0).mean(),avg_pnl=o.pnl.mean(),avg_days=o.days.mean(),
                         ann_on_capital=o.pnl.sum()/o.days.sum()*365))
print(pd.DataFrame(rows).round(4).to_string(index=False))
