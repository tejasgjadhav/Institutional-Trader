"""REV1_L with capital recycling: 5 margin slots; when a position exits (close-based
TP +2% / SL -5%), the slot re-enters the next trading day's close with the then-best
pullback candidate (same filters/ranking). No new entries in the last 5 sessions before
expiry. IS/OOS split as bt.py."""
import sys
sys.path.insert(0, "/Users/sayali/files/institutional-trader/studies/monthly_fut")
import numpy as np
import pandas as pd
from bt import (load, near_month, cycles, build_features, asof, COST, STK_MARGIN,
                OOS_START, BASE)

TP, SL, SLOTS, DEAD = 0.02, 0.05, 5, 5

def rank_candidates(feats, reg, d, held):
    r = asof(reg, d)
    if r is None or not (r["px"] > r["ma200"]): return []
    rows = []
    for sym, f in feats.items():
        if sym in ("NIFTY", "BANKNIFTY", "FINNIFTY") or sym in held: continue
        x = asof(f, d)
        if x is None or np.isnan(x["mom1"]) or np.isnan(x["ma200"]): continue
        if x["px"] <= x["ma200"]: continue
        rows.append((sym, x["mom1"]))
    rows.sort(key=lambda t: t[1])
    return [s for s, _ in rows]

def run():
    p = load(); nm = near_month(p)
    cont = {s: g.set_index("date")["close"] for s, g in nm.groupby("symbol")}
    feats, reg = build_features(cont, cont["NIFTY"])
    cyc = cycles(nm)
    by_sym = {s: g.set_index("date") for s, g in nm.groupby("symbol")}
    all_dates = pd.Series(sorted(nm["date"].unique()))
    trades = []
    for entry_d, exp in cyc:
        days = all_dates[(all_dates >= entry_d) & (all_dates <= exp)].tolist()
        if len(days) < DEAD + 2: continue
        last_entry_day = days[-(DEAD + 1)]
        open_pos = {}                     # sym -> dict(entry_px, entry_d)
        free_slots = SLOTS
        pending_entries = 0               # slots freed today enter tomorrow
        for i, d in enumerate(days):
            # 1) entries at today's close (initial day or refills queued yesterday)
            want = free_slots if d == entry_d else pending_entries
            pending_entries = 0
            if want > 0 and d <= last_entry_day:
                cands = rank_candidates(feats, reg, d, set(open_pos))
                for sym in cands:
                    if want == 0: break
                    g = by_sym.get(sym)
                    if g is None or d not in g.index: continue
                    row = g.loc[d]
                    if row["expiry"] != exp or not np.isfinite(row["close"]) or row["close"] <= 0:
                        continue
                    open_pos[sym] = dict(entry_px=row["close"], entry_d=d)
                    free_slots -= 1; want -= 1
            elif want > 0:
                free_slots = free_slots  # past entry window: slot stays idle
            # 2) exits at today's close (not on the entry day itself)
            for sym in list(open_pos):
                pos = open_pos[sym]
                if d == pos["entry_d"]: continue
                g = by_sym[sym]
                if d not in g.index: continue
                row = g.loc[d]
                if row["expiry"] != exp: continue
                ret = row["close"] / pos["entry_px"] - 1
                is_exp = (d == days[-1])
                if ret >= TP or ret <= -SL or is_exp:
                    x_px = row["settle"] if is_exp and np.isfinite(row["settle"]) and row["settle"] > 0 else row["close"]
                    gross = x_px / pos["entry_px"] - 1
                    reason = "tp" if ret >= TP else ("sl" if ret <= -SL else "expiry")
                    trades.append(dict(entry=pos["entry_d"], exit=d, sym=sym, cycle=str(exp.date()),
                                       net=gross - COST, reason=reason))
                    del open_pos[sym]
                    free_slots += 1; pending_entries += 1
        # anything never exited (data hole): close at last seen close
        for sym, pos in open_pos.items():
            g = by_sym[sym]
            path = g.loc[(g.index > pos["entry_d"]) & (g.index <= exp)]
            path = path[path["expiry"] == exp]
            if path.empty: continue
            last = path.iloc[-1]
            x_px = last["settle"] if np.isfinite(last["settle"]) and last["settle"] > 0 else last["close"]
            trades.append(dict(entry=pos["entry_d"], exit=path.index[-1], sym=sym, cycle=str(exp.date()),
                               net=x_px / pos["entry_px"] - 1 - COST, reason="expiry"))
    return pd.DataFrame(trades)

if __name__ == "__main__":
    tr = run()
    tr["entry"] = pd.to_datetime(tr["entry"])
    tr.to_csv(f"{BASE}/trades_recycled.csv", index=False)
    for lbl, t in (("IS", tr[tr["entry"] < OOS_START]), ("OOS", tr[tr["entry"] >= OOS_START])):
        if t.empty: continue
        # monthly return on capital: capital = SLOTS * margin per equal-notional slot
        mo = t.groupby("cycle")["net"].sum() / (SLOTS * STK_MARGIN)
        eq = (1 + mo).cumprod(); dd = (eq / eq.cummax() - 1).min()
        print(f"{lbl}: n={len(t)} win={(t['net']>0).mean()*100:.1f}% "
              f"avg={t['net'].mean()*100:.3f}% trades/mo={len(t)/len(mo):.1f} "
              f"mo_cap={mo.mean()*100:.2f}% (median {mo.median()*100:.2f}%) "
              f"worst_mo={mo.min()*100:.2f}% bwin={(mo>0).mean()*100:.0f}% dd={dd*100:.1f}%")
        t2 = t.copy()
        yr = t2.groupby(t2["entry"].dt.year)["net"].agg(["count", "mean", lambda x: (x>0).mean()])
        print(yr.round(3).to_string())
        print(t["reason"].value_counts().to_dict())
