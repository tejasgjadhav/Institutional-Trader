import warnings, logging, sys
warnings.filterwarnings("ignore")
for n in ("prophet","cmdstanpy"): logging.getLogger(n).setLevel(logging.CRITICAL)
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd, numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from engine.data_fetcher import fetch_upstox_historical

def cv_index(name):
    d = fetch_upstox_historical(name, unit="days", interval=1).tail(90)
    df = pd.DataFrame({"ds": d.index.tz_localize(None), "y": d["Close"].values})
    last = df["y"].iloc[-1]
    m = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False,
                interval_width=0.80, changepoint_prior_scale=0.05)
    m.fit(df)
    # rolling-origin CV: train on ~45d, predict 20d ahead, step 5d
    cv = cross_validation(m, initial="45 days", period="5 days", horizon="20 days", parallel=None)
    cv["err"] = cv["yhat"] - cv["y"]
    cv["ape"] = (cv["err"].abs() / cv["y"]) * 100
    cv["h"] = (cv["ds"] - cv["cutoff"]).dt.days
    pm = performance_metrics(cv, rolling_window=1)
    # baseline: naive "tomorrow = today" persistence error over same horizons
    print(f"\n===== {name} (last close {last:,.0f}) =====")
    print(f"  CV folds: {cv['cutoff'].nunique()}  predictions: {len(cv)}")
    overall_rmse = np.sqrt((cv['err']**2).mean())
    overall_mae = cv['err'].abs().mean()
    overall_mape = cv['ape'].mean()
    print(f"  Overall  RMSE=Rs{overall_rmse:,.0f}  MAE=Rs{overall_mae:,.0f}  MAPE={overall_mape:.1f}%  (=±{overall_mape/100*last:,.0f} pts on {last:,.0f})")
    # error by horizon bucket
    for lo,hi in [(1,5),(6,10),(11,15),(16,20)]:
        sub = cv[(cv['h']>=lo)&(cv['h']<=hi)]
        if len(sub):
            print(f"   {lo:>2}-{hi:>2}d ahead: MAE=Rs{sub['err'].abs().mean():,.0f}  MAPE={sub['ape'].mean():.1f}%  bias(mean err)=Rs{sub['err'].mean():+,.0f}")
    # directional hit-rate: did Prophet get the SIGN of the move right vs the cutoff price?
    hits=tot=0
    for cutoff, g in cv.groupby("cutoff"):
        base = df[df["ds"]<=cutoff]["y"].iloc[-1]
        g2 = g[g["h"]>=16]  # ~20d-ahead point
        for _,r in g2.iterrows():
            pred_dir = np.sign(r["yhat"]-base); act_dir = np.sign(r["y"]-base)
            if pred_dir!=0 and act_dir!=0:
                tot+=1; hits += (pred_dir==act_dir)
    if tot: print(f"  20d directional hit-rate: {hits}/{tot} = {100*hits/tot:.0f}%  (50% = coin flip)")

for ix in ("NIFTY","BANKNIFTY"):
    try: cv_index(ix)
    except Exception as e: print(ix,"CV failed:",e)
