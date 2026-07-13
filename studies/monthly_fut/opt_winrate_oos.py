"""OOS win-rate test: 5-pick ATM call, TP {2%,1.5%,1%}, -5% stop, Upstox premiums Oct'24->date.
Fetch each pick's ATM call ONCE, evaluate all 3 TP levels on the same series (cheap multi-variant)."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader"); sys.path.insert(0, "studies/monthly_fut")
import numpy as np, pandas as pd
from datetime import datetime, timedelta
from bt import load, near_month, build_features, cycles, asof
from opt_bt2 import sel
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj
from engine.data_fetcher import UPSTOX_BASE

def spf(p): return (min(6.0,max(1.0,60.0/p))/100.0) if p>0 else 0.06
def oser(key,d0,to):
    j=_gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    if j.get("status")=="success":
        c=j.get("data",{}).get("candles",[])
        if c:
            df=pd.DataFrame(c,columns=["ts","O","H","L","C","V","OI"]); df["ts"]=pd.to_datetime(df["ts"]).dt.tz_localize(None)
            return df.set_index("ts").sort_index()["C"]
    return None

p=load(); nm=near_month(p); cont={s:g.set_index("date")["close"] for s,g in nm.groupby("symbol")}
feats,reg=build_features(cont,cont["NIFTY"]); cyc=cycles(nm); by_sym={s:g.set_index("date") for s,g in nm.groupby("symbol")}
EXP={}; CH={}; TPS=[0.02,0.015,0.01]; win={t:[] for t in TPS}
for entry_d,exp in cyc:
    entry_d=pd.Timestamp(entry_d)
    if entry_d<pd.Timestamp("2024-10-01"): continue
    for sym in sel(feats,reg,entry_d):
        g=by_sym.get(sym)
        if g is None or entry_d not in g.index: continue
        e=float(g.loc[entry_d]["close"]); r0=g.loc[entry_d]
        try:
            if sym not in EXP: EXP[sym]=get_expiries(sym)
            cand=[x for x in EXP[sym] if x>=exp.date().isoformat()]; oexp=cand[0] if cand else (max(EXP[sym]) if EXP[sym] else None)
            if not oexp: continue
            if (sym,oexp) not in CH: CH[(sym,oexp)]=sorted([c for c in get_contracts(sym,oexp) if c["instrument_type"]=="CE"],key=lambda c:float(c["strike_price"]))
            chain=CH[(sym,oexp)]
        except Exception: continue
        if not chain: continue
        ks=[float(c["strike_price"]) for c in chain]; ai=min(range(len(ks)),key=lambda i:abs(ks[i]-e))
        K=ks[ai]; key=chain[ai]["instrument_key"]
        to=min(datetime.fromisoformat(oexp).date(),entry_d.date()+timedelta(days=45)).isoformat()
        ser=oser(key,entry_d.date().isoformat(),to)
        if ser is None or ser.empty: continue
        prem0=float(ser.iloc[0])
        if prem0<=0: continue
        path=g.loc[(g.index>entry_d)&(g.index<=exp)]; path=path[path["expiry"]==r0["expiry"]]
        if path.empty: continue
        rets=(path["close"]/e-1)
        for tp_base in TPS:
            xp=None
            for i,(d2,rr) in enumerate(rets.items()):
                tp=(tp_base-0.01) if i+1>12 else tp_base
                if rr>=tp or rr<=-0.05:
                    v=ser[ser.index.normalize()==pd.Timestamp(d2).normalize()]
                    xp=float(v.iloc[-1]) if len(v) else max(0.0,float(path.loc[d2]["close"])-K); break
            if xp is None:
                last=path.iloc[-1]; se=float(last["settle"] if np.isfinite(last["settle"]) and last["settle"]>0 else last["close"]); xp=max(0.0,se-K)
            win[tp_base].append((xp-prem0-(prem0+xp)*spf(prem0))/prem0)
    print(f"  ...{entry_d.date()}",flush=True)
print("\nOOS Oct'24->date, 5-pick ATM:")
for tp in TPS:
    w=np.array(win[tp]); print(f"  TP {tp*100:.1f}%: n={len(w)} win={(w>0).mean()*100:.0f}% avg={w.mean()*100:+.0f}%")
print("DONE-WR-OOS")
