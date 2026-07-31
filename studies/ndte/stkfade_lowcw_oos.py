"""LOW-C/W RESCUE — OUT-OF-SAMPLE confirmation (Upstox expired options, Oct 2024 -> date).

Companion to stkfade_lowcw_geometry.py (in-sample, bhavcopy 2019->Sep'24). Same question:
of the UNION breakouts whose credit/width at the DEPLOYED v2 geometry (short-2-OTM / width-4)
lands in the blocked 0.30-0.40 band, does any alternative config make money out-of-sample?

Sweeps the SAME full grid as the in-sample script — the OOS window does not inherit an
IS-selected shortlist, so neither window picks the winner for the other; a config has to
stand up in both. Each signal's legs are fetched ONCE per strike and cached, so the full
grid costs little more than a single config.
Exit slippage IS charged here (as in stkfade_oos_union.py). Settlement = underlying intrinsic.
"""
import sys, warnings, json, threading, concurrent.futures
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
import pandas as pd
from datetime import datetime, timedelta, date
from engine.config import UNIVERSE
from engine.data_fetcher import fetch_upstox_historical, UPSTOX_BASE
from engine.instruments import encode_key
from engine.expired_options import get_expiries, get_contracts, _get_json as _gj

START = date(2024, 10, 1)
MIN_DTE, REENTRY, MIN_PREM = 10, 3, 50.0
REF_SHORT, REF_WIDTH = 2, 4
BAND = (0.30, 0.40)
GEOS  = [("step", S, W) for S in (0, 1, 2, 3) for W in (1, 2, 3, 4, 5)] + \
        [("pct", s, w) for s in (1.0, 2.0, 3.0, 4.0) for w in (2.0, 3.0, 4.0, 6.0)]
EXITS = [(tp, st) for tp in (0.40, 0.50, 0.75, None) for st in (None, 2.0, 3.0)]
CONFIGS = [g + e for g in GEOS for e in EXITS]
print(f"OOS sweeping {len(CONFIGS)} configs ({len(GEOS)} geometries x {len(EXITS)} exits)", flush=True)

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

LEGC = {}; LEGLK = threading.Lock()
def leg(key, d0, to):
    ck = (key, d0, to)
    with LEGLK:
        if ck in LEGC: return LEGC[ck]
    j = _gj(f"{UPSTOX_BASE}/v2/expired-instruments/historical-candle/{encode_key(key)}/day/{to}/{d0}")
    s = None
    if j.get("status") == "success":
        c = j.get("data", {}).get("candles", [])
        if c:
            df = pd.DataFrame(c, columns=["ts", "O", "H", "L", "C", "V", "OI"])
            df["ts"] = pd.to_datetime(df["ts"])
            s = df.set_index("ts").sort_index()["C"]
    with LEGLK: LEGC[ck] = s
    return s

def pick(ks, atm, c, typ, geo):
    if geo[0] == "step":
        S, W = int(geo[1]), int(geo[2])
        si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
        if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): return None
        return si, li
    sp, wp = float(geo[1]), float(geo[2])
    tgt_s = c * (1 + sp / 100) if typ == "CE" else c * (1 - sp / 100)
    si = min(range(len(ks)), key=lambda j: abs(ks[j] - tgt_s))
    tgt_l = ks[si] + c * wp / 100 if typ == "CE" else ks[si] - c * wp / 100
    cand = [j for j in range(len(ks)) if (ks[j] > ks[si] if typ == "CE" else ks[j] < ks[si])]
    if not cand: return None
    li = min(cand, key=lambda j: abs(ks[j] - tgt_l))
    return si, li

out = {i: [] for i in range(len(CONFIGS))}
band_n = [0]
EXPC = {}; CHC = {}; LK = threading.Lock(); DONE = [0]

def do_stock(sym0):
    sym = sym0.replace(".NS", "")
    try:
        u = fetch_upstox_historical(sym0, unit="days", interval=1,
                                    from_date="2024-06-01", to_date=date.today().isoformat())
    except Exception:
        u = None
    if u is None or u.empty or len(u) < 30:
        with LK: DONE[0] += 1
        return
    u = u.sort_index()
    cb = {ix.date().isoformat(): float(u["Close"].loc[ix]) for ix in u.index}
    HIS = {d: u["High"].rolling(d).max().shift(1) for d in (5, 10, 15, 20)}
    LOS = {d: u["Low"].rolling(d).min().shift(1) for d in (5, 10, 15, 20)}
    last = {}
    for i in range(20, len(u) - 1):
        day = u.index[i].date()
        if day < START: continue
        c = float(u["Close"].iloc[i]); typ = None
        if any(c > float(HIS[d].iloc[i]) for d in (5, 10, 15, 20)): typ = "CE"
        elif any(c < float(LOS[d].iloc[i]) for d in (5, 10, 15, 20)): typ = "PE"
        else: continue
        if last.get(typ) and (day - last[typ]).days < REENTRY: continue
        try:
            if sym not in EXPC: EXPC[sym] = get_expiries(sym)
            exps = [e for e in EXPC[sym] if e >= (day + timedelta(days=MIN_DTE)).isoformat()]
            if not exps: continue
            exp = exps[0]; ck = (sym, exp, typ)
            if ck not in CHC:
                CHC[ck] = sorted([ct for ct in get_contracts(sym, exp) if ct["instrument_type"] == typ],
                                 key=lambda ct: float(ct["strike_price"]))
            chain = CHC[ck]
        except Exception:
            continue
        ks = [float(ct["strike_price"]) for ct in chain]
        if len(ks) < REF_SHORT + REF_WIDTH + 2: continue
        atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
        to = min(datetime.fromisoformat(exp).date(), day + timedelta(days=45)).isoformat()

        # ── band membership at the REFERENCE (deployed) geometry ──
        ref = pick(ks, atm, c, typ, ("step", REF_SHORT, REF_WIDTH))
        if not ref: continue
        rsi, rli = ref
        rsp = leg(chain[rsi]["instrument_key"], day.isoformat(), to)
        rlp = leg(chain[rli]["instrument_key"], day.isoformat(), to)
        if rsp is None or rlp is None or len(rsp) < 1 or len(rlp) < 1: continue
        rse = float(rsp.iloc[0]); rle = float(rlp.iloc[0])
        rcredit = rse - rle; rw = abs(ks[rsi] - ks[rli])
        if rse < MIN_PREM or rcredit <= 0 or rcredit >= rw: continue
        ref_cw = rcredit / rw
        if not (BAND[0] <= ref_cw < BAND[1]): continue
        last[typ] = day
        with LK: band_n[0] += 1

        # ── evaluate each candidate config on this signal ──
        for ci, cfg in enumerate(CONFIGS):
            geo, tp, stop = (cfg[0], cfg[1], cfg[2]), cfg[3], cfg[4]
            sel = pick(ks, atm, c, typ, geo)
            if not sel: continue
            si, li = sel
            if si == li: continue
            sk, lk = ks[si], ks[li]
            sp_ = leg(chain[si]["instrument_key"], day.isoformat(), to)
            lp_ = leg(chain[li]["instrument_key"], day.isoformat(), to)
            if sp_ is None or lp_ is None or len(sp_) < 1 or len(lp_) < 1: continue
            se = float(sp_.iloc[0]); le = float(lp_.iloc[0])
            credit = se - le; w = abs(sk - lk)
            if se < MIN_PREM or credit <= 0 or credit >= w: continue
            close = None; m = min(len(sp_), len(lp_))
            for t in range(1, m):
                a = float(sp_.iloc[t]); b = float(lp_.iloc[t]); cost = a - b
                if tp is not None and cost <= credit * (1 - tp):
                    close = max(cost, 0.0) + (a * spf(a) + b * spf(b)) / 100.0; break
                if stop is not None and cost >= credit * stop:
                    close = min(cost, w) + (a * spf(a) + b * spf(b)) / 100.0; break
            if close is None:
                espot = cb.get(exp) or (cb[max(x for x in cb if x <= exp)] if any(x <= exp for x in cb) else c)
                intr = max(0.0, espot - sk) if typ == "CE" else max(0.0, sk - espot)
                intl = max(0.0, espot - lk) if typ == "CE" else max(0.0, lk - espot)
                close = min(max(intr - intl, 0.0), w)
            net = (credit - close) - (se * spf(se) + le * spf(le)) / 100.0
            margin = w - credit
            with LK:
                out[ci].append(dict(y=day.year, net=float(net), w=float(w),
                                    margin=float(margin), win=int(net > 0)))
    with LK:
        DONE[0] += 1
        if DONE[0] % 10 == 0:
            print(f"  …{DONE[0]}/{len(UNIVERSE)} stocks, band signals={band_n[0]}", flush=True)
            json.dump({str(k): v for k, v in out.items()}, open("/tmp/lowcw_oos.json", "w"))

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
    list(ex.map(do_stock, UNIVERSE))
json.dump({str(k): v for k, v in out.items()}, open("/tmp/lowcw_oos.json", "w"))

def lbl(cfg):
    g = f"S{int(cfg[1])}/W{int(cfg[2])}" if cfg[0] == "step" else f"{cfg[1]:.0f}%/{cfg[2]:.0f}%"
    return f"{g:>9} TP{'hold' if cfg[3] is None else int(cfg[3]*100):>4} stop{'--' if cfg[4] is None else cfg[4]:>4}"

rows = []
for ci, cfg in enumerate(CONFIGS):
    t = pd.DataFrame(out[ci])
    if len(t) < 10: continue
    yrs = {int(y): float(g.net.sum() / g.margin.sum() * 100) for y, g in t.groupby("y")}
    rows.append(dict(ci=ci, cfg=cfg, n=len(t), win=float(t.win.mean() * 100),
                     rom=float(t.net.sum() / t.margin.sum() * 100),
                     netw=float(t.net.sum() / t.w.sum() * 100),
                     pos=sum(1 for v in yrs.values() if v > 0), nyr=len(yrs), yrs=yrs))

print(f"\n=== OOS Oct'24->date — band (0.30-0.40 c/w at deployed geometry) signals seen: {band_n[0]} ===")
ref = [r for r in rows if r["cfg"][:3] == ("step", REF_SHORT, REF_WIDTH) and r["cfg"][3] == 0.50 and r["cfg"][4] == 3.0]
if ref:
    r = ref[0]
    print(f"BAND @ DEPLOYED v2 config (S2/W4 TP-50 stop-3x): n={r['n']} win {r['win']:.1f}%  "
          f"ROM {r['rom']:+.1f}%  net {r['netw']:+.1f}% of width")

print(f"\n--- TOP 20 by pooled RETURN ON MARGIN ---")
print(f"{'config':<30} {'n':>5} {'win%':>6} {'ROM%':>7} {'net%w':>7} {'+yrs':>6}")
for r in sorted(rows, key=lambda x: -x["rom"])[:20]:
    print(f"{lbl(r['cfg']):<30} {r['n']:>5} {r['win']:>6.1f} {r['rom']:>+7.1f} {r['netw']:>+7.1f} {r['pos']}/{r['nyr']:>4}")

print(f"\n--- TOP 20 by WIN RATE (n>=25, ROM>0) ---")
for r in sorted([x for x in rows if x["n"] >= 25 and x["rom"] > 0], key=lambda x: -x["win"])[:20]:
    print(f"{lbl(r['cfg']):<30} {r['n']:>5} {r['win']:>6.1f} {r['rom']:>+7.1f} {r['netw']:>+7.1f} {r['pos']}/{r['nyr']:>4}")

json.dump([{**r, "cfg": list(r["cfg"]), "yrs": {str(k): v for k, v in r["yrs"].items()}} for r in rows],
          open("/tmp/lowcw_oos_summary.json", "w"), indent=1)
print("\nwrote /tmp/lowcw_oos_summary.json")
print("DONE-LOWCW-OOS")
