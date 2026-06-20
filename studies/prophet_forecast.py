import warnings, logging, sys
warnings.filterwarnings("ignore")
logging.getLogger("prophet").setLevel(logging.CRITICAL)
logging.getLogger("cmdstanpy").setLevel(logging.CRITICAL)
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from prophet import Prophet
from engine.data_fetcher import fetch_upstox_historical

HORIZON = 20  # ~1 trading month forward

def prophet_fit(df, periods):
    m = Prophet(daily_seasonality=False, weekly_seasonality=True,
                yearly_seasonality=False, interval_width=0.80,
                changepoint_prior_scale=0.05)
    m.fit(df)
    fut = m.make_future_dataframe(periods=periods, freq="B")
    fc = m.predict(fut)
    return m, fc

# ---------- 1) INDEX PRICE FORECASTS ----------
def index_forecast(name):
    d = fetch_upstox_historical(name, unit="days", interval=1)
    d = d.tail(90)
    df = pd.DataFrame({"ds": d.index.tz_localize(None), "y": d["Close"].values})
    m, fc = prophet_fit(df, HORIZON)
    last = df["y"].iloc[-1]
    tail = fc.tail(HORIZON)
    end = tail["yhat"].iloc[-1]; lo = tail["yhat_lower"].iloc[-1]; hi = tail["yhat_upper"].iloc[-1]
    print(f"\n{name}: last close {last:,.0f}")
    print(f"  +{HORIZON}d forecast: {end:,.0f}  ({(end/last-1)*100:+.2f}%)   80% band [{lo:,.0f} .. {hi:,.0f}]  = {(lo/last-1)*100:+.1f}% / {(hi/last-1)*100:+.1f}%")
    return df, fc, name, last

# ---------- 2) STRATEGY EQUITY FORECAST ----------
def equity_forecast():
    try:
        p = pd.read_csv("/tmp/daily_pnl_3family.csv", parse_dates=["day"])
    except Exception as e:
        print("no pnl csv:", e); return None
    p = p.sort_values("day")
    # fill business days with 0, build cumulative equity
    rng = pd.bdate_range(p["day"].min(), p["day"].max())
    s = p.set_index("day")["pnl_inr"].reindex(rng, fill_value=0.0)
    eq = s.cumsum()
    df = pd.DataFrame({"ds": eq.index, "y": eq.values})
    m, fc = prophet_fit(df, HORIZON)
    last = df["y"].iloc[-1]; tail = fc.tail(HORIZON)
    end = tail["yhat"].iloc[-1]; lo = tail["yhat_lower"].iloc[-1]; hi = tail["yhat_upper"].iloc[-1]
    n_days = len(df); total = last
    print(f"\n3-FAMILY equity (aligned, gross): {n_days} backtest days, ended +Rs{last:,.0f}")
    print(f"  daily drift ~ Rs{last/n_days:+,.0f}/day")
    print(f"  +{HORIZON}d projected ADD: Rs{end-last:+,.0f}   80% band [Rs{lo-last:+,.0f} .. Rs{hi-last:+,.0f}]")
    print(f"  => projected equity in 1mo: Rs{end:,.0f}  (range Rs{lo:,.0f} .. Rs{hi:,.0f})")
    return df, fc, "3-Family equity (Rs)", last

# run
results = []
for ix in ("NIFTY", "BANKNIFTY"):
    try: results.append(index_forecast(ix))
    except Exception as e: print(ix, "failed:", e)
eq = equity_forecast()
if eq: results.append(eq)

# ---------- plot ----------
fig, axes = plt.subplots(len(results), 1, figsize=(11, 4*len(results)))
if len(results) == 1: axes = [axes]
for ax, (df, fc, title, last) in zip(axes, results):
    ax.plot(df["ds"], df["y"], "k.", ms=3, label="actual")
    ax.plot(fc["ds"], fc["yhat"], "b-", lw=1.2, label="forecast")
    ax.fill_between(fc["ds"], fc["yhat_lower"], fc["yhat_upper"], color="b", alpha=0.15, label="80% interval")
    ax.axvline(df["ds"].iloc[-1], color="r", ls="--", lw=0.8)
    ax.set_title(title); ax.legend(loc="upper left", fontsize=8); ax.grid(alpha=0.2)
plt.tight_layout()
plt.savefig("/tmp/prophet_forecast.png", dpi=110)
print("\nsaved chart -> /tmp/prophet_forecast.png")
