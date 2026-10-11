# For each uptrend dip (NIFTY>200DMA) since Oct-2024: total futures OI (front+next) from Upstox 1-min candles.
# oi3_1520 = OI at 15:20 on T / OI at 15:29 on T-3 ; oi3_eod = OI 15:29 T / 15:29 T-3. Same source both sides.
import sys, time, pandas as pd, numpy as np
sys.path.insert(0,"/Users/sayali/files/institutional-trader")
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import to_instrument_key, encode_key
T=pd.read_parquet("/Users/sayali/files/nifty-2pct-study/deep_trades_ext.parquet")
T=T[(T.side==1)&(T.nreg==True)&(T.ent>="2024-10-01")].copy()
def get(url,params=None):
    for i in range(6):
        r=SESSION.get(url,params=params,timeout=25)
        if r.status_code==429: time.sleep(1.5*(i+1)); continue
        if r.status_code==200: return r.json()
        time.sleep(1)
    raise RuntimeError(f"{url} {r.status_code}")
EXP={}; KEY={}
def contracts(sym,d):
    uk=to_instrument_key(sym)
    if sym not in EXP: EXP[sym]=sorted(get(f"{UPSTOX_BASE}/v2/expired-instruments/expiries",{"instrument_key":uk})["data"])
    ex=[e for e in EXP[sym] if e>=d.strftime("%Y-%m-%d")][:2]; ks=[]
    for e in ex:
        if (sym,e) not in KEY:
            dd=get(f"{UPSTOX_BASE}/v2/expired-instruments/future/contract",{"instrument_key":uk,"expiry_date":e})["data"]
            KEY[(sym,e)]=dd[0]["instrument_key"] if dd else None
        ks.append(KEY[(sym,e)])
    return ks
rows=[]; fails=[]
for _,t in T.iterrows():
    d=t.ent; frm=(d-pd.Timedelta(days=8)).strftime("%Y-%m-%d"); to=d.strftime("%Y-%m-%d")
    try:
        tot=None
        for k in contracts(t.sym,d):
            if not k: continue
            c=get(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(k)}/1minute/{to}/{frm}")["data"]["candles"]
            s=pd.Series({pd.Timestamp(x[0]).tz_localize(None):x[6] for x in c}).sort_index()
            tot=s if tot is None else tot.add(s,fill_value=0)
        days=sorted(set(tot.index.normalize()))
        if len(days)<4 or days[-1]!=d: raise ValueError("days")
        eod=lambda dy: tot[tot.index.normalize()==dy].iloc[-1]
        t1520=tot[(tot.index.normalize()==d)&(tot.index.time<=pd.Timestamp("15:20").time())].iloc[-1]
        b=eod(days[-4]); rows.append(dict(sym=t.sym,ent=d,g=t.g,oi3_bhav=t.oi3,oi3_eod=eod(d)/b-1,oi3_1520=t1520/b-1))
    except Exception as e: fails.append((t.sym,str(d.date()),str(e)[:60]))
R=pd.DataFrame(rows); R.to_csv("/Users/sayali/files/nifty-2pct-study/oi_timing.csv",index=False)
print("dips",len(T),"measured",len(R),"failed",len(fails), fails[:5])
