# Append UDiFF futures rows 2026-07-10 -> 2026-10-09 to a local panel copy. Zips from
# institutional-trader cache first, then NSE archives. Missing days are logged, never silent.
import os, io, zipfile, requests, pandas as pd, time
SRC="/Users/sayali/files/institutional-trader/data/bhavcopy/fo"; os.makedirs("fo_ext",exist_ok=True)
s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36","Accept":"*/*"})
try: s.get("https://www.nseindia.com",timeout=12)
except Exception: pass
rows=[]; miss=[]
for d in pd.bdate_range("2026-07-10","2026-10-09"):
    z=os.path.join(SRC,f"{d:%Y-%m-%d}.csv.zip"); loc=f"fo_ext/{d:%Y-%m-%d}.zip"
    if not os.path.exists(z) and not os.path.exists(loc):
        r=s.get(f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip",timeout=20); time.sleep(0.4)
        if r.status_code==200 and r.content[:2]==b"PK": open(loc,"wb").write(r.content)
        else: miss.append(f"{d:%Y-%m-%d}:{r.status_code}"); continue
    zf=zipfile.ZipFile(z if os.path.exists(z) else loc); df=pd.read_csv(zf.open(zf.namelist()[0]))
    df=df[df.FinInstrmTp.isin(["STF","IDF"])]
    rows.append(pd.DataFrame(dict(date=d,symbol=df.TckrSymb,expiry=pd.to_datetime(df.XpryDt),close=df.ClsPric,oi=df.OpnIntrst,open=df.OpnPric,high=df.HghPric,low=df.LwPric,settle=df.SttlmPric)))
E=pd.concat(rows); P=pd.read_csv("/Users/sayali/files/institutional-trader/studies/monthly_fut/panel.csv.gz",parse_dates=["date","expiry"])
P=pd.concat([P,E[E.symbol.isin(P.symbol.unique())]]); P.to_csv("panel_ext.csv.gz",index=False)
print("days added",E.date.nunique(),"| missing (holidays or failures):",miss)
