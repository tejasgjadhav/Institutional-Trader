"""BANKNIFTY monthly-vs-weekly expiry, WITHIN Era A (user question 2026-07-19).

Question: BANKNIFTY is now monthly-only. Does a MONTHLY expiry structurally deserve a higher
same-day win rate than a weekly one? Plausible mechanism: monthly contracts carry far larger open
interest, and heavy OI concentration produces strike "pinning" — the index gets held near a big
strike into settlement, which is exactly what an OTM seller wants.

Why this test and not the era comparison: comparing Era A (monthly slice) to Era B (monthly-only)
confounds expiry type with REGIME and with data source. Here both arms sit inside the SAME era, the
same years, the same bhavcopy pipeline — only the expiry type differs. That isolates the variable.

Same deployed geometry as ndte14: short CE 0.5% OTM, wing 0.83% of spot, entry at expiry-day OPEN,
settle intrinsic vs close, costs 2.5% + Rs20x4/lot, liquidity floor CONTRACTS>=100, lot 30.
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys, json, glob, time
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import numpy as np, pandas as pd
from engine.data_fetcher import SESSION, UPSTOX_BASE
from engine.instruments import encode_key

BHAV = "/tmp/ndte_bhav_idx"; C = "/tmp/ndte_ev"
SLIP, BROKER, LOT, MINC = 2.5, 20.0, 30, 100
OTM, WING = 0.005, 0.0083

spots = {}
p = f"{C}/spot2019_BANKNIFTY.json"
if os.path.exists(p): spots = json.load(open(p))
if not spots:
    r = SESSION.get(f"{UPSTOX_BASE}/v2/historical-candle/{encode_key('NSE_INDEX|Nifty Bank')}/day/2024-09-30/2018-11-01", timeout=30)
    for ts, o, h, l, c, *_ in r.json().get("data", {}).get("candles", []): spots[ts[:10]] = [o, h, l, c]
    json.dump(spots, open(p, "w"))

rows = []
for f in sorted(glob.glob(f"{BHAV}/*.csv")):
    ds = os.path.basename(f)[:-4]
    if ds not in spots: continue
    try: df = pd.read_csv(f)
    except Exception: continue
    df = df[(df.SYMBOL == "BANKNIFTY") & (df.OPTION_TYP == "CE")]
    if df.empty: continue
    ce = df.set_index("STRIKE_PR")
    st = sorted(ce.index)
    if len(st) < 10: continue
    s_open, s_close = spots[ds][0], spots[ds][3]
    near = lambda x: min(st, key=lambda k: abs(k - x))
    Ks = near(s_open * (1 + OTM)); Kl = near(Ks + s_open * WING)
    W = Kl - Ks
    if W < s_open * WING * 0.5: continue
    try: vs, vl = ce.loc[Ks], ce.loc[Kl]
    except Exception: continue
    if hasattr(vs, "OPEN") is False: continue
    try:
        so, lo = float(vs.OPEN), float(vl.OPEN); con = float(vs.CONTRACTS)
    except Exception: continue
    if so <= 0 or con < MINC: continue
    credit = so - lo
    if credit <= 0 or credit >= W: continue
    settle = min(max(max(0.0, s_close - Ks) - max(0.0, s_close - Kl), 0.0), W)
    net = credit - settle - ((so + lo) * SLIP / 100 + BROKER * 4 / LOT)
    rows.append(dict(date=ds, pm=net / (W - credit) * 100, rs=net * LOT, cw=credit / W))

# classify: an expiry day is MONTHLY if it is the LAST expiry day in its calendar month
bymonth = {}
for r in rows: bymonth[r["date"][:7]] = max(bymonth.get(r["date"][:7], ""), r["date"])
monthly = set(bymonth.values())
for r in rows: r["kind"] = "MONTHLY" if r["date"] in monthly else "WEEKLY"

def rep(lab, sel):
    if not sel: return print(f"  {lab:22s} n=0")
    pm = np.array([r["pm"] for r in sel]); rs = np.array([r["rs"] for r in sel])
    print(f"  {lab:22s} n={len(sel):4d}  win {(pm>0).mean()*100:5.1f}%  avg {pm.mean():+7.2f}%m  "
          f"tot Rs{rs.sum():+9,.0f}  worst Rs{rs.min():+8,.0f}  med c/W {np.median([r['cw'] for r in sel]):.3f}")

print(f"BANKNIFTY expiry days from bhavcopy: {len(rows)} ({rows[0]['date']} -> {rows[-1]['date']})\n")
print("=" * 104)
print("WITHIN ERA A (2019 -> Jul'24) — same years, same pipeline, only expiry TYPE differs")
print("=" * 104)
mo = [r for r in rows if r["kind"] == "MONTHLY"]; wk = [r for r in rows if r["kind"] == "WEEKLY"]
rep("MONTHLY expiries", mo)
rep("WEEKLY expiries", wk)
if mo and wk:
    dw = np.mean([r["pm"] > 0 for r in mo]) * 100 - np.mean([r["pm"] > 0 for r in wk]) * 100
    da = np.mean([r["pm"] for r in mo]) - np.mean([r["pm"] for r in wk])
    print(f"\n  DIFFERENCE (monthly - weekly): win {dw:+.1f}pp   avg {da:+.2f}%m")
    # crude significance: 2-proportion z-test on win rate
    p1 = np.mean([r["pm"] > 0 for r in mo]); n1 = len(mo)
    p2 = np.mean([r["pm"] > 0 for r in wk]); n2 = len(wk)
    pp = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = (pp * (1 - pp) * (1 / n1 + 1 / n2)) ** 0.5
    z = (p1 - p2) / se if se > 0 else 0
    print(f"  2-proportion z on win rate: z = {z:+.2f}  "
          f"({'SIGNIFICANT at 95%' if abs(z) > 1.96 else 'NOT significant — consistent with pure chance'})")

print("\n" + "=" * 104)
print("PER YEAR (monthly vs weekly) — is any gap persistent or one-off?")
print("=" * 104)
for y in sorted({r["date"][:4] for r in rows}):
    m = [r for r in mo if r["date"][:4] == y]; w = [r for r in wk if r["date"][:4] == y]
    if not m or not w: continue
    print(f"  {y}: MONTHLY n={len(m):2d} win {np.mean([r['pm']>0 for r in m])*100:5.1f}% "
          f"avg {np.mean([r['pm'] for r in m]):+7.2f}%m   |   "
          f"WEEKLY n={len(w):2d} win {np.mean([r['pm']>0 for r in w])*100:5.1f}% "
          f"avg {np.mean([r['pm'] for r in w]):+7.2f}%m")
print("\nDONE-NDTE19")
