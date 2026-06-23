"""Collect ONCE: every aligned+Gate4 stock signal over 90 days, with its signal-time
FEATURES and its full OPTION PREMIUM PATH (so any target/stop combo + any Gate-5 filter can
be replayed in-memory). Saves /tmp/g5_trades.json. Gates 1-4 = the current live system."""
import sys, warnings, json
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.path.insert(0, "/Users/sayali/files/institutional-trader/studies")
import align_bt as A
from datetime import timedelta
from engine.config import (UNIVERSE, TRADING_START, NO_NEW_TRADES_AFTER,
                           OPTION_STRIKE_OFFSET, MAX_ENTRY_EXTENSION_PCT)

N = 90
def collect():
    days = A.tdays(N)
    a, b = days[0]-timedelta(days=3), days[-1]+timedelta(days=1)
    sm, cm = A.hhmm(TRADING_START), A.hhmm(NO_NEW_TRADES_AFTER)
    nifty5 = A._fetch_5min_chunked("NIFTY", a, b)
    out = []
    for k, under in enumerate(UNIVERSE):
        if (k+1) % 20 == 0: print(f"  ...{k+1}/{len(UNIVERSE)}", flush=True)
        try:
            daily = A.fetch_upstox_historical(under, unit="days", interval=1,
                from_date=(days[0]-timedelta(days=60)).strftime("%Y-%m-%d"), to_date=b.strftime("%Y-%m-%d"))
            five = A._fetch_5min_chunked(under, a, b)
        except Exception: continue
        if five.empty or daily.empty: continue
        for day in days:
            d5 = five[five.index.date == day]
            if len(d5) < 8: continue
            dfd = daily[daily.index.date < day]
            if len(dfd) < 20: continue
            prev_close = float(dfd["Close"].iloc[-1])
            nday = nifty5[nifty5.index.date == day]
            nopen = float(nday.Open.iloc[0]) if not nday.empty else 0
            d_open = float(d5.Open.iloc[0])
            orb_hi = float(d5["High"].iloc[:6].max()); orb_lo = float(d5["Low"].iloc[:6].min())
            for i in range(6, len(d5)):
                ts = d5.index[i]; m = A.bmin(ts)
                if m < sm: continue
                if m > cm: break
                part = d5.iloc[:i+1]
                sig = A.compute_all_families(under, part, dfd, vix=14.0, nifty_pct=0.0)
                if not sig["passes_gate_1"]: continue
                ok, od, vr = A.is_orb_confirmed(part)
                if not (ok and od == sig["direction"]): continue
                direction = sig["direction"]
                nd = 0
                if not nday.empty and nopen:
                    ns = nday[nday.index <= ts]
                    if not ns.empty:
                        nc = float(ns.Close.iloc[-1]); nd = 1 if nc>nopen else (-1 if nc<nopen else 0)
                if not ((direction=="LONG" and nd==1) or (direction=="SHORT" and nd==-1)): continue  # Gate3
                spot = float(part.Close.iloc[-1])
                ext = (spot-d_open)/d_open*100; ext = ext if direction=="LONG" else -ext
                if ext > MAX_ENTRY_EXTENSION_PCT: continue                                            # Gate4
                opt = A.get_option_by_offset(under, spot, day, "CE" if direction=="LONG" else "PE", OPTION_STRIKE_OFFSET)
                if not opt: break
                prem = A.fetch_option_premium_5min(opt["key"], day)
                if prem.empty: break
                psub = prem["Close"][prem.index <= ts]
                if psub.empty: break
                entry = float(psub.iloc[-1])
                if entry <= 0: break
                path = [float(x) for x in prem["Close"][prem.index > ts]]   # premium AFTER entry
                if not path: break
                # features
                nstr = abs((nc-nopen)/nopen*100) if (not nday.empty and nopen) else 0
                gap = (d_open-prev_close)/prev_close*100
                orb_w = (orb_hi-orb_lo)/spot*100
                cum_vol = float(part["Volume"].sum())
                out.append({"day": str(day), "under": under, "dir": direction,
                    "entry": entry, "lot": int(opt.get("lot",0) or 0), "path": path,
                    "az": round(abs(sig.get("alpha_z",0)),3), "vr": round(float(vr),2),
                    "ext": round(ext,3), "tod": m, "nstr": round(nstr,3),
                    "gap": round(gap,3), "orb_w": round(orb_w,3), "dow": day.weekday(),
                    "cum_vol": cum_vol})
                break
    return out

rows = collect()
json.dump(rows, open("/tmp/g5_trades.json","w"))
print(f"saved {len(rows)} trades with features + premium paths over {N} days")
if rows:
    ds = sorted({r['day'] for r in rows})
    print(f"span {ds[0]} .. {ds[-1]} ({len(ds)} trading days)")
