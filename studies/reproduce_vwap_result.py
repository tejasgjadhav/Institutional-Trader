"""Reproduce the VWAP example's published result.

This is the script that produced the table in studies/VWAP_EXAMPLE_STRATEGY.md. Run it and you should land
close to the published numbers. If you do not, one of us has a bug, and finding out which is
worth more than tuning a parameter.

It needs an Upstox market-data token in .env. Run it from the repository root:
    .venv/bin/python studies/reproduce_vwap_result.py

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os, sys, os, json, datetime as dt, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from engine.data_fetcher import fetch_upstox_historical

random.seed(7); np.random.seed(7)
NAMES = ["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
         "SBIN.NS","AXISBANK.NS","LT.NS","ITC.NS","BHARTIARTL.NS"]
YEARS = 2
STRETCH = 0.30      # config.EXAMPLE_VWAP_STRETCH
TURN_BARS = 1       # config.EXAMPLE_VWAP_TURN_BARS
FROM_T, TO_T = (9,45), (13,30)   # entry window
EXIT_T = (15,15)                 # config.EXAMPLE_VWAP_EXIT_AT

def pull(tkr):
    frames, end = [], dt.date.today()
    for _ in range(YEARS*13):
        start = end - dt.timedelta(days=29)
        df = fetch_upstox_historical(tkr, unit="minutes", interval=5,
                                     from_date=start.isoformat(), to_date=end.isoformat())
        if df is not None and len(df): frames.append(df)
        end = start - dt.timedelta(days=1)
    if not frames: return None
    out = pd.concat(frames).sort_index()
    return out[~out.index.duplicated(keep="first")]

def vwap(df):
    tp = (df.High + df.Low + df.Close) / 3.0
    return (tp * df.Volume).cumsum() / df.Volume.cumsum().replace(0, np.nan)

def mins(ts): return ts.hour*60 + ts.minute
W_FROM, W_TO, W_EXIT = FROM_T[0]*60+FROM_T[1], TO_T[0]*60+TO_T[1], EXIT_T[0]*60+EXIT_T[1]

sig_rows, rnd_rows, sessions_total = [], [], 0
for tkr in NAMES:
    df = pull(tkr)
    if df is None: print("no data", tkr); continue
    for day, d in df.groupby(df.index.date):
        d = d.sort_index()
        if len(d) < 30: continue
        sessions_total += 1
        v = vwap(d)
        exit_rows = d[[mins(t) >= W_EXIT for t in d.index]]
        exit_px = float(exit_rows.Close.iloc[0]) if len(exit_rows) else float(d.Close.iloc[-1])
        elig = [i for i,(t,_) in enumerate(d.iterrows()) if W_FROM <= mins(t) <= W_TO and i >= 1]
        # the rule
        fired = None
        for i in elig:
            w = v.iloc[i]
            if not np.isfinite(w): continue
            c = float(d.Close.iloc[i])
            if (w - c)/w*100.0 < STRETCH: continue
            if not all(float(d.Close.iloc[i-k]) > float(d.Close.iloc[i-k-1]) for k in range(TURN_BARS)): continue
            fired = i; break
        if fired is not None:
            e = float(d.Close.iloc[fired]); fwd = d.iloc[fired+1:]
            fwd = fwd[[mins(t) <= W_EXIT for t in fwd.index]]
            mfe = (float(fwd.High.max())-e)/e*100 if len(fwd) else 0.0
            mae = (float(fwd.Low.min())-e)/e*100 if len(fwd) else 0.0
            sig_rows.append(dict(tkr=tkr, day=str(day), move=(exit_px-e)/e*100, mfe=mfe, mae=mae))
            # random baseline: a random eligible bar, same exit
            j = random.choice(elig); rp = float(d.Close.iloc[j])
            rnd_rows.append(dict(move=(exit_px-rp)/rp*100))
    print("done", tkr, len(sig_rows), flush=True)

S = pd.DataFrame(sig_rows); R = pd.DataFrame(rnd_rows)
res = dict(
  names=len(NAMES), sessions_scanned=sessions_total, signals=len(S),
  signal_rate_pct=round(len(S)/max(1,sessions_total)*100,1),
  mean_move_pct=round(float(S.move.mean()),4), median_move_pct=round(float(S.move.median()),4),
  win_rate_pct=round(float((S.move>0).mean()*100),1),
  stdev=round(float(S.move.std()),4),
  t_stat=round(float(S.move.mean()/(S.move.std()/np.sqrt(len(S)))),2),
  mean_mfe_pct=round(float(S.mfe.mean()),3), mean_mae_pct=round(float(S.mae.mean()),3),
  baseline_mean_move_pct=round(float(R.move.mean()),4),
  baseline_win_rate_pct=round(float((R.move>0).mean()*100),1),
  first_day=str(S.day.min()), last_day=str(S.day.max()))
print(json.dumps(res, indent=1))
S.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals.csv"), index=False)
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "result.json"),"w"), indent=1)
