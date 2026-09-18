"""Report: DAILY BEAR CALL SPREAD on the SENSEX weekly — both legs opened 09:16, closed 15:29 the same
day, every trading day. The user's question is the NON-EXPIRY days (Fri->Wed under the Thursday
regime); expiry day is already the deployed 0DTE book. Win = net P&L > 0. Rs at 1 lot, Rs100 per
leg round trip (2 legs = Rs200/day)."""
import pandas as pd, numpy as np
import sys, os
df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "research/sensex_daily/daily_rows.csv"); COST = 200.0
df["month"] = df.day.str[:7]; df["year"] = df.day.str[:4]; df["dow"] = pd.to_datetime(df.day).dt.strftime("%a")
df["gross"] = (df.short_CE_pts + df.dwing_CE_pts) * df.lot; df["net"] = df.gross - COST
ok = df.gross.notna(); d = df[ok].copy()
def block(g, label):
    if not len(g): print(f"{label:<40} no days"); return
    n = len(g); mo = g.month.nunique(); dd = (g.net.cumsum() - g.net.cumsum().cummax()).min()
    print(f"{label:<40}{n:>6}{100*(g.net>0).mean():>7.1f}{g.gross.sum():>11,.0f}{g.net.sum():>11,.0f}{g.net.sum()/mo:>10,.0f}{g.net.mean():>9,.0f}{g.net.min():>9,.0f}{dd:>9,.0f}")
print(f"SENSEX weekly · DAILY BEAR CALL SPREAD (short ~0.5% OTM CE / long ~0.83% OTM CE) · 09:16 -> 15:29 same day")
print(f"{d.day.min()} -> {d.day.max()} · {len(d)} days priced · {d.expiry.nunique()} weeks · lot {int(d.lot.iloc[-1])} · cost Rs{COST:.0f}/day · win = net > 0\n")
print(f"{'':<40}{'days':>6}{'win%':>7}{'gross Rs':>11}{'net Rs':>11}{'Rs/month':>10}{'avg/day':>9}{'worst':>9}{'maxDD':>9}")
block(d[d.dte >= 1], "NON-EXPIRY DAYS (the new signals)")
block(d[d.dte == 0], "expiry day (what the 0DTE book does)")
block(d, "all days")
print("\nnon-expiry days by DTE:")
for dte, g in d[d.dte >= 1].groupby("dte"): block(g, f"  DTE {dte}")
print("\nnon-expiry days by weekday:")
for dow, g in d[d.dte >= 1].groupby("dow"): block(g, f"  {dow}")
print("\nnon-expiry days by year:")
for y, g in d[d.dte >= 1].groupby("year"): block(g, f"  {y}")
print("\nnon-expiry days, last 12 months:")
for k, g in list(d[d.dte >= 1].groupby("month"))[-12:]: print(f"  {k}: {len(g):>3} days · win {100*(g.net>0).mean():5.1f}% · net Rs{g.net.sum():>+8,.0f}")
print(f"\nentry credit on non-expiry days: median Rs{(d[d.dte>=1].short_CE_in - (d[d.dte>=1].short_CE_in - d[d.dte>=1].short_CE_pts + d[d.dte>=1].dwing_CE_pts*0)).median():.0f} short premium · "
      f"median spread credit/width: {((d[d.dte>=1].short_CE_in - (d[d.dte>=1].short_CE_in - d[d.dte>=1].short_CE_pts)) / (d[d.dte>=1].dwing_CE_strike - d[d.dte>=1].short_CE_strike)).median():.3f}" if False else "")
print(f"data integrity: {int((~ok).sum())} days dropped for a missing leg price out of {len(df)}")
