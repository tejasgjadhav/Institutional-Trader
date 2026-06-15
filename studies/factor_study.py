"""
Index-option factor study (NIFTY + BANKNIFTY, buy-only).

Goal: find whether an UNCORRELATED set of technical factors, combined into a
statistical composite score, can lift the win rate of buying ATM index options
meaningfully above the ~50% baseline — validated OUT-OF-SAMPLE.

Method:
 1. Event set: every 5-min bar 9:30-13:00, both indices. Direction = sign(close-VWAP)
    on the futures. Buy the morning-ATM option in that direction. Label = win at a
    SYMMETRIC +20/-20 premium exit (baseline ~50%, so any lift is a real edge), plus
    a hold-to-EOD(-30% stop) outcome for reference.
 2. ~15 factors across families (VWAP/location, momentum, vol, participation,
    structure, time, cross-index breadth), each signed to favour the chosen direction.
 3. Split by DAY (train ~60% / test 40%). On TRAIN: correlation matrix -> greedily keep
    the highest-edge factor of each correlated cluster (|r|>0.7). Univariate edge =
    point-biserial corr(factor, win).
 4. Composite = sum(edge_i * zscore_i) over kept factors (z params from train).
    Sweep threshold on train for win rate; validate win rate + net on TEST (1 trade/day).
"""
import sys, json, gzip, requests
from datetime import datetime, timedelta
import numpy as np, pandas as pd
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
from engine.backtest120 import _fetch_5min_chunked
from engine.data_fetcher import fetch_upstox_historical
from engine.options import get_option_by_offset, fetch_option_premium_5min

URL="https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
def load_futs():
    raw=json.loads(gzip.decompress(requests.get(URL,timeout=60).content)); f={}
    for i in raw:
        if i.get("segment")=="NSE_FO" and i.get("instrument_type")=="FUT" and (i.get("name") or "") in ("NIFTY","BANKNIFTY"):
            f.setdefault(i["name"],[]).append({"key":i["instrument_key"],"expiry":int(i["expiry"])})
    return {k:sorted(v,key=lambda c:c["expiry"]) for k,v in f.items()}
def tdays(n):
    days,dd=[],datetime.now()-timedelta(days=1)
    while len(days)<n:
        if dd.weekday()<5: days.append(dd.date())
        dd-=timedelta(days=1)
    return sorted(days)
def bmin(ts): return ts.hour*60+ts.minute
def near_key(futs,nm,day):
    dm=int(datetime(day.year,day.month,day.day).timestamp()*1000)
    nr=[c for c in futs.get(nm,[]) if c["expiry"]>=dm]
    return nr[0]["key"] if nr else None

def rsi(close,n=14):
    d=close.diff(); g=d.clip(lower=0).rolling(n).mean(); l=(-d.clip(upper=0)).rolling(n).mean()
    return 100-100/(1+g/l.replace(0,1e-9))
def atr(df,n=14):
    pc=df.Close.shift(1)
    tr=pd.concat([(df.High-df.Low),(df.High-pc).abs(),(df.Low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()
def vwap_s(df):
    tp=(df.High+df.Low+df.Close)/3; return (tp*df.Volume).cumsum()/df.Volume.cumsum()

ENTRY_START,ENTRY_END=9*60+30,13*60

def sym_outcome(prem,ts,tgt,stp):
    sub=prem[prem.index<=ts]
    if sub.empty: return None
    e=float(sub.iloc[-1])
    if e<=0: return None
    T,S=e*(1+tgt/100),e*(1-stp/100); last=e
    for v in prem[prem.index>ts]:
        last=float(v)
        if last<=S: return -stp
        if last>=T: return tgt
    return round((last/e-1)*100,2)
def eod_outcome(prem,ts,stp=30):
    sub=prem[prem.index<=ts]
    if sub.empty: return None
    e=float(sub.iloc[-1])
    if e<=0: return None
    S=e*(1-stp/100); last=e
    for v in prem[prem.index>ts]:
        last=float(v)
        if last<=S: return -stp
    return round((last/e-1)*100,2)

def dir_map(f):  # ts -> sign(close - vwap) on futures
    vw=vwap_s(f); return {f.index[i]: (1 if float(f.Close.iloc[i])>float(vw.iloc[i]) else -1) for i in range(len(f))}

def collect(n_days=40):
    futs=load_futs(); days=tdays(n_days)
    a,b=days[0]-timedelta(days=3),days[-1]+timedelta(days=1)
    FUT={}; SPOT={}
    for nm in ("NIFTY","BANKNIFTY"):
        FUT[nm]=_fetch_5min_chunked(near_key(futs,nm,days[-1]),a,b)
        SPOT[nm]=_fetch_5min_chunked(nm,a,b)
    rows=[]
    for day in days:
        fday={nm:FUT[nm][FUT[nm].index.date==day] for nm in FUT}
        if any(len(fday[nm])<20 for nm in fday): continue
        dmap={nm:dir_map(fday[nm]) for nm in fday}
        # precompute per-index option series (morning ATM CALL & PUT)
        opts={}
        for nm in ("NIFTY","BANKNIFTY"):
            sp=SPOT[nm][SPOT[nm].index.date==day]
            if sp.empty: continue
            spot0=float(sp.Close.iloc[0]); opts[nm]={}
            for d,typ in [(1,"CE"),(-1,"PE")]:
                o=get_option_by_offset(nm,spot0,day,typ,0)
                pr=fetch_option_premium_5min(o["key"],day) if o else pd.DataFrame()
                opts[nm][d]=pr["Close"] if not pr.empty else pd.Series(dtype=float)
        for nm in ("NIFTY","BANKNIFTY"):
            f=fday[nm]
            if nm not in opts: continue
            other="BANKNIFTY" if nm=="NIFTY" else "NIFTY"
            # precompute series
            vw=vwap_s(f); R=rsi(f.Close); A=atr(f); e9=f.Close.ewm(span=9,adjust=False).mean()
            e21=f.Close.ewm(span=21,adjust=False).mean(); volavg=f.Volume.rolling(10).mean()
            ret30=f.Close.pct_change(6)*100; ret60=f.Close.pct_change(12)*100
            sv=np.sign(f.Close.diff()).fillna(0)*f.Volume; cvd=sv.rolling(6).sum()/f.Volume.rolling(6).sum().replace(0,1e-9)
            body=((f.Close-f.Open).abs()/(f.High-f.Low).replace(0,1e-9)).rolling(4).mean()
            persist=np.sign(f.Close.diff()).rolling(5).sum()
            orb=f.iloc[:3]; orb_hi=float(orb.High.max()); orb_lo=float(orb.Low.min())
            orb_rng=(orb_hi-orb_lo)/float(orb.Close.iloc[-1])*100
            day_open=float(f.Open.iloc[0])
            for i in range(3,len(f)):
                ts=f.index[i]; m=bmin(ts)
                if m<ENTRY_START: continue
                if m>ENTRY_END: break
                c=float(f.Close.iloc[i]); v=float(vw.iloc[i])
                if not np.isfinite(v): continue
                d=1 if c>v else -1
                prem=opts[nm].get(d,pd.Series(dtype=float))
                if prem.empty: continue
                y=sym_outcome(prem,ts,20,20);
                if y is None: continue
                yeod=eod_outcome(prem,ts,30)
                orb_lvl=orb_hi if d>0 else orb_lo
                hi=f.High.iloc[:i+1].max(); lo=f.Low.iloc[:i+1].min(); rng=(hi-lo) or 1e-9
                rrow={
                  "day":str(day),"idx":nm,"dir":d,"time":m,
                  "f_vwapdist": d*(c-v)/v*100,
                  "f_vwapslope": d*(v-float(vw.iloc[max(0,i-3)]))/v*100,
                  "f_mom30": d*(ret30.iloc[i] if np.isfinite(ret30.iloc[i]) else 0),
                  "f_mom60": d*(ret60.iloc[i] if np.isfinite(ret60.iloc[i]) else 0),
                  "f_rsi": d*((R.iloc[i] if np.isfinite(R.iloc[i]) else 50)-50),
                  "f_emaspread": d*(e9.iloc[i]-e21.iloc[i])/c*100,
                  "f_orbdist": d*(c-orb_lvl)/c*100,
                  "f_volsurge": (f.Volume.iloc[i]/volavg.iloc[i]) if np.isfinite(volavg.iloc[i]) and volavg.iloc[i]>0 else 1.0,
                  "f_cvd": d*(cvd.iloc[i] if np.isfinite(cvd.iloc[i]) else 0),
                  "f_atr": (A.iloc[i]/c*100) if np.isfinite(A.iloc[i]) else 0,
                  "f_rangepos": d*(c-(hi+lo)/2)/rng,
                  "f_body": body.iloc[i] if np.isfinite(body.iloc[i]) else 0.5,
                  "f_time": m,
                  "f_orbrange": orb_rng,
                  "f_persist": d*(persist.iloc[i] if np.isfinite(persist.iloc[i]) else 0),
                  "f_breadth": 1.0 if dmap[other].get(ts,0)==d else (-1.0 if dmap[other].get(ts,0)==-d else 0.0),
                  "f_daymove": d*(c-day_open)/day_open*100,
                  "win20": 1 if y>0 else 0, "pnl20": y, "pnleod": yeod if yeod is not None else 0,
                }
                rows.append(rrow)
    return rows

FACTORS=["f_vwapdist","f_vwapslope","f_mom30","f_mom60","f_rsi","f_emaspread","f_orbdist",
         "f_volsurge","f_cvd","f_atr","f_rangepos","f_body","f_time","f_orbrange","f_persist","f_breadth","f_daymove"]

from scipy.stats import pearsonr

def analyze(df, label):
    print(f"\n\n############ WINDOW = last {label} trading days ############")
    print(f"events={len(df)}  baseline win20={df.win20.mean()*100:.1f}%  net20={df.pnl20.mean():+.2f}/trade  "
          f"(NIFTY {sum(df.idx=='NIFTY')}, BANKNIFTY {sum(df.idx=='BANKNIFTY')})")
    days=sorted(df.day.unique()); cut=days[int(len(days)*0.6)]
    tr=df[df.day<cut].copy(); te=df[df.day>=cut].copy()
    print(f"train days={tr.day.nunique()} ({len(tr)} ev)  test days={te.day.nunique()} ({len(te)} ev)")

    edges={}
    for fct in FACTORS:
        x=tr[fct].values.astype(float); y=tr.win20.values.astype(float)
        if np.std(x)<1e-9: edges[fct]=0.0; continue
        r,_=pearsonr(x,y); edges[fct]=r if np.isfinite(r) else 0.0
    ranked=sorted(FACTORS,key=lambda k:abs(edges[k]),reverse=True)
    print("\n-- Univariate factor edge (TRAIN, corr with win) --")
    print("  "+"  ".join(f"{k.replace('f_','')}={edges[k]:+.2f}" for k in ranked[:8]))

    corr=tr[FACTORS].corr().abs(); kept=[]
    for k in ranked:
        if any(corr.loc[k,j]>0.7 for j in kept): continue
        kept.append(k)
    print(f"-- Decorrelated: kept {len(kept)}/{len(FACTORS)}: {[k.replace('f_','') for k in kept]}")

    mu={k:tr[k].mean() for k in kept}; sd={k:(tr[k].std() or 1.0) for k in kept}
    def comp(d):
        s=pd.Series(0.0,index=d.index)
        for k in kept: s=s+edges[k]*((d[k]-mu[k])/sd[k])
        return s
    tr["score"]=comp(tr); te["score"]=comp(te)

    print("\n-- Composite win rate by TRAIN threshold (sym +20/-20) --")
    print(f"{'thr':>6}{'TRAIN n/win%/net':>22}{'TEST n/win%/net':>22}{'TESTeod':>9}")
    def stat(s):
        return "0/-/-" if not len(s) else f"{len(s)}/{round(s.win20.mean()*100)}%/{s.pnl20.mean():+.2f}"
    for q in [0,50,60,70,80,90]:
        thr=np.percentile(tr.score,q); trs=tr[tr.score>=thr]; tes=te[te.score>=thr]
        eodn=f"{tes.pnleod.mean():+.2f}" if len(tes) else "-"
        print(f"{q:>4}%>{stat(trs):>22}{stat(tes):>22}{eodn:>9}")

    thr70=np.percentile(tr.score,70)
    best=te[te.score>=thr70].sort_values("score",ascending=False).groupby("day").head(1)
    if len(best):
        print(f"-- 1 trade/day on TEST (score>=train70pct): trades={len(best)} over {best.day.nunique()} days  "
              f"win20={best.win20.mean()*100:.0f}%  net20={best.pnl20.mean():+.2f}  eodnet={best.pnleod.mean():+.2f}")

print("collecting events (max depth ~60 trading days)...",flush=True)
rows=collect(60)
dfall=pd.DataFrame(rows)
alldays=sorted(dfall.day.unique())
print(f"TOTAL: {len(dfall)} events over {len(alldays)} trading days with data "
      f"({alldays[0]} .. {alldays[-1]})")

for window in [30,60]:
    keep=set(alldays[-window:])
    analyze(dfall[dfall.day.isin(keep)].copy(), min(window,len(alldays)))
