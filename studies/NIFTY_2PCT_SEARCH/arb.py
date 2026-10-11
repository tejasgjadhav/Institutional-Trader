# Cash-futures arbitrage: at the first session of each monthly cycle buy the stock and sell the current-month
# future at the close; hold to expiry (physical settlement, legs converge). Locked P&L = basis - costs.
# Dividends received during the cycle are ignored (conservative). Costs: STT 0.1% buy + 0.1% delivery,
# fut STT 0.02%, stamp/exchange ~0.03%, slippage 0.05% per leg -> 0.35% round trip.
import pandas as pd, numpy as np, yfinance as yf, os, warnings; warnings.filterwarnings("ignore")
COST=0.0035
P=pd.read_csv("panel_ext.csv.gz",parse_dates=["date","expiry"]); P=P[(P.close>0)&(P.expiry>=P.date)]
syms=sorted(set(P.symbol)-{"NIFTY","BANKNIFTY","FINNIFTY"})
if not os.path.exists("cash_raw.parquet"):
    d=yf.download([s+".NS" for s in syms],start="2017-12-01",end="2026-10-10",group_by="ticker",auto_adjust=False,progress=False,threads=True)
    pd.concat([d[t][["Close"]].dropna().assign(sym=t.replace(".NS","")) for t in d.columns.get_level_values(0).unique()]).rename_axis("date").to_parquet("cash_raw.parquet")
S=pd.read_parquet("cash_raw.parquet").reset_index().rename(columns={"Close":"spot","sym":"symbol"})
nm=P.loc[P.groupby(["symbol","date"]).expiry.idxmin()]          # current-month contract
exps=sorted(nm[nm.symbol=="RELIANCE"].expiry.unique())
rows=[]
for prev,ex in zip(exps[:-1],exps[1:]):
    days=sorted(nm.date[(nm.date>prev)&(nm.date<=ex)].unique())
    if len(days)<10: continue
    d0=days[0]; e=nm[(nm.date==d0)&(nm.expiry==ex)].merge(S,on=["date","symbol"])
    e=e[(e.spot>0)&((e.close/e.spot-1).abs()<0.05)]                # drop stale/split-mismatch rows
    for _,r in e.iterrows():
        b=r.close/r.spot-1; dte=(ex-d0).days
        rows.append(dict(sym=r.symbol,ent=d0,exp=ex,dte=dte,basis=b,net=b-COST,ann=(b-COST)*365/dte))
A=pd.DataFrame(rows); A.to_csv("arb_trades.csv",index=False)
print(f"all stock-cycles: {len(A)} | basis median {A.basis.median():.4f} | net>0 {(A.net>0).mean():.1%} | median net/cycle {A.net.median():.4f}")
for th in (0.006,0.008,0.010):
    q=A[A.basis>=th]; m=q.groupby("ent")
    print(f"enter only if basis >= {th:.1%}: {len(q)} trades ({len(q)/A.ent.nunique():.1f}/month) | positive {(q.net>0).mean():.1%} | avg net/cycle {q.net.mean():.4f} | avg annualised {q.ann.mean():.1%}")
y=A[A.basis>=0.008].groupby(A.ent.dt.year).agg(n=("net","size"),net=("net","mean"),ann=("ann","mean")); print(y.round(4).to_string())
