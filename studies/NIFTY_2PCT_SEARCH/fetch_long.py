import yfinance as yf, pandas as pd, warnings; warnings.filterwarnings("ignore")
T=pd.read_csv("ohlc.csv").sym.unique().tolist()
k=[t if t.startswith("^") else t+".NS" for t in T]+["^NSEBANK"]
d=yf.download(k,start="2008-01-01",end="2026-10-10",group_by="ticker",auto_adjust=True,progress=False,threads=True)
rows=[d[t][["Open","High","Low","Close","Volume"]].dropna().assign(sym=t.replace(".NS","")) for t in k if t in d.columns.get_level_values(0)]
df=pd.concat(rows); df.index.name="date"; df.to_parquet("daily_long.parquet")
print(df.groupby("sym").apply(lambda x:x.index.min().year).value_counts().sort_index().to_dict(), len(df))
