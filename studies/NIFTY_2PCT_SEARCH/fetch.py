import yfinance as yf, pandas as pd, warnings; warnings.filterwarnings("ignore")
T="ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK INDIGO INFY ITC JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN SUNPHARMA TATACONSUM TATASTEEL TCS TECHM TITAN TRENT ULTRACEMCO WIPRO TMPV".split()
d=yf.download([t+".NS" for t in T]+["^NSEI"],start="2025-09-01",end="2026-10-10",group_by="ticker",auto_adjust=False,progress=False,threads=True)
rows=[]
for t in T+["^NSEI"]:
    k=t if t.startswith("^") else t+".NS"
    try: x=d[k][["Open","High","Low","Close","Volume"]].dropna()
    except KeyError: continue
    if len(x)<100: print("short",t,len(x)); continue
    x=x.assign(sym=t); rows.append(x)
df=pd.concat(rows); df.index.name="date"; df.to_csv("ohlc.csv"); print(df.sym.nunique(), df.index.min(), df.index.max())
