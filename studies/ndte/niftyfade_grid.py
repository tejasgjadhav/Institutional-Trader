"""NIFTY index-fade IS optimization grid (bhavcopy 2019->Sep'24) — can the fade be fixed?

Data: /tmp/bhav_nifty_opt (niftyfade_dl.py, ALL NIFTY OPTIDX rows per day) +
/tmp/nsei_daily_2019_sep24.csv (Upstox NIFTY daily OHLC). Sim mirrors the OOS harness
studies/ndte/idxfade_oos_exits.py: daily Donchian breakout at close -> FADE (up-break ->
bear-call CE, down-break -> bull-put PE), entry at close, walk daily closes to expiry,
intrinsic settle from spot, spf slippage at entry+exit (none on settle), reentry 3d/side.

ONE chronological pass collects trades for 12 base combos: DC {5,10,20} x geometry
{(s1,w3),(s2,w4)} x MIN_DTE {10,20}; per-trade c/w and breakout size recorded. Then the
evaluator crosses each collection with c/w gates {none,.40,.45,.50} and exits
{hold/stop2, TP75/stop2, hold/stop3, hold/no-stop} -> grid of n / win% / net %width /
positive-years (2019..2024). Trades cached to scratchpad JSON so re-evals are free.

Success bar (set in advance): IS win>=70% AND net>=+10%w AND positive >=5/6 years."""
import os, sys, json, csv
from datetime import date, timedelta

CACHE = "/tmp/bhav_nifty_opt"
UND = "/tmp/nsei_daily_2019_sep24.csv"
SCRATCH = "/private/tmp/claude-501/-Users-sayali-files/d62dc509-cfa1-4925-8c10-c57a2151b1c9/scratchpad"
TRADES_JSON = os.path.join(SCRATCH, "niftyfade_is_trades.json")
START = date(2019, 1, 1); END = date(2024, 9, 30); REENTRY = 3
DCS = [5, 10, 20]; GEOS = [(1, 3), (2, 4)]; DTES = [10, 20]
GATES = [0.0, 0.40, 0.45, 0.50]
EXITS = [("hold/stop2", None, 2.0), ("TP75/stop2", 0.75, 2.0),
         ("hold/stop3", None, 3.0), ("hold/nostop", None, None)]

def spf(p): return min(6.0, max(1.0, 60.0 / p)) if p > 0 else 6.0

# ---------- underlying ----------
und = {}
with open(UND) as f:
    for row in csv.DictReader(f):
        d = date.fromisoformat(row["Timestamp"][:10])
        und[d] = (float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]))
days_all = sorted(und)
H = [und[d][1] for d in days_all]; L = [und[d][2] for d in days_all]; C = [und[d][3] for d in days_all]
bands = {}   # bands[dc][i] = (hi, lo) of prior dc days
for dc in DCS:
    b = [None] * len(days_all)
    for i in range(dc, len(days_all)):
        b[i] = (max(H[i - dc:i]), min(L[i - dc:i]))
    bands[dc] = b
closes_by_day = {d: und[d][3] for d in days_all}

def spot_on_or_before(d):
    if d in closes_by_day: return closes_by_day[d]
    prev = [x for x in days_all if x <= d]
    return closes_by_day[prev[-1]] if prev else None

# ---------- collect ----------
def load_day(d):
    """-> (chains, px): chains[(exp,typ)] = sorted strikes; px[(exp,typ,strike)] = close"""
    p = os.path.join(CACHE, d.isoformat() + ".csv")
    if not os.path.exists(p): return None
    chains = {}; px = {}
    with open(p) as f:
        r = csv.reader(f); next(r)
        for exp, k, typ, cl, vol in r:
            k = float(k); cl = float(cl)
            px[(exp, typ, k)] = cl
            chains.setdefault((exp, typ), set()).add(k)
    return {k: sorted(v) for k, v in chains.items()}, px

if os.path.exists(TRADES_JSON):
    ALL = {tuple(json.loads(k)): v for k, v in json.load(open(TRADES_JSON)).items()}
    print(f"loaded cached trades: { {k: len(v) for k, v in ALL.items()} }", flush=True)
else:
    ALL = {(dc, s, w, m): [] for dc in DCS for (s, w) in GEOS for m in DTES}
    last = {k: {} for k in ALL}          # last entry day per typ
    open_tr = {k: [] for k in ALL}       # open trades walking their paths
    n_days = 0
    for i, d in enumerate(days_all):
        if d < START or d > END: continue
        ld = load_day(d)
        if ld is None: continue
        chains, px = ld; n_days += 1
        c = C[i]
        # 1) advance open trades
        for key in ALL:
            still = []
            for t in open_tr[key]:
                sc = px.get((t["exp"], t["typ"], t["sk"]), t["_ls"])
                lc = px.get((t["exp"], t["typ"], t["lk"]), t["_ll"])
                t["_ls"], t["_ll"] = sc, lc
                t["path"].append([sc, lc])
                if t["exp"] <= d.isoformat():   # expiry day reached
                    es = spot_on_or_before(date.fromisoformat(t["exp"]))
                    intr = max(0.0, es - t["sk"]) if t["typ"] == "CE" else max(0.0, t["sk"] - es)
                    intl = max(0.0, es - t["lk"]) if t["typ"] == "CE" else max(0.0, t["lk"] - es)
                    t["settle"] = min(max(intr - intl, 0.0), t["w"])
                    for x in ("_ls", "_ll", "sk", "lk"): t.pop(x)
                    ALL[key].append(t)
                else:
                    still.append(t)
            open_tr[key] = still
        # 2) new signals
        for key in ALL:
            dc, S, W, M = key
            b = bands[dc][i]
            if b is None: continue
            typ = "CE" if c > b[0] else ("PE" if c < b[1] else None)
            if typ is None: continue
            if last[key].get(typ) and (d - last[key][typ]).days < REENTRY: continue
            exps = sorted({e for (e, ty) in chains if ty == typ and e >= (d + timedelta(days=M)).isoformat()
                           and e <= END.isoformat()})
            if not exps: continue
            exp = exps[0]
            ks = chains.get((exp, typ), [])
            if len(ks) < S + W + 2: continue
            atm = min(range(len(ks)), key=lambda j: abs(ks[j] - c))
            si, li = (atm + S, atm + S + W) if typ == "CE" else (atm - S, atm - S - W)
            if si < 0 or li < 0 or si >= len(ks) or li >= len(ks): continue
            sk, lk = ks[si], ks[li]
            se = px.get((exp, typ, sk)); le = px.get((exp, typ, lk))
            if se is None or le is None: continue
            credit = se - le; w = abs(sk - lk)
            if credit <= 0 or credit >= w: continue
            bo = (c - b[0]) / b[0] * 100 if typ == "CE" else (b[1] - c) / b[1] * 100
            last[key][typ] = d
            open_tr[key].append(dict(d=d.isoformat(), y=d.year, typ=typ, exp=exp, sk=sk, lk=lk,
                                     credit=credit, w=w, cw=credit / w, se=se, le=le, bo=bo,
                                     path=[], settle=None, _ls=se, _ll=le))
        if n_days % 250 == 0: print(f"  {d} … open={sum(len(v) for v in open_tr.values())} "
                                    f"closed={sum(len(v) for v in ALL.values())}", flush=True)
    # drop any still-open (expiry beyond cache)
    print(f"collection done: {n_days} days; dropped open: { {k: len(v) for k, v in open_tr.items() if v} }", flush=True)
    json.dump({json.dumps(list(k)): v for k, v in ALL.items()}, open(TRADES_JSON, "w"))
    print(f"saved -> {TRADES_JSON}", flush=True)

# ---------- evaluate ----------
def walk(t, tp, stop):
    credit = t["credit"]; w = t["w"]
    for s, l in t["path"][:-1]:          # last path day = expiry -> settle
        cost = s - l
        if tp is not None and cost <= credit * (1 - tp):
            return max(cost, 0.0) + (s * spf(s) + l * spf(l)) / 100.0
        if stop is not None and cost >= credit * stop:
            return min(cost, w) + (s * spf(s) + l * spf(l)) / 100.0
    # expiry-day close can still trip the stop before settlement
    if t["path"]:
        s, l = t["path"][-1]; cost = s - l
        if stop is not None and cost >= credit * stop:
            return min(cost, w) + (s * spf(s) + l * spf(l)) / 100.0
        if tp is not None and cost <= credit * (1 - tp):
            return max(cost, 0.0) + (s * spf(s) + l * spf(l)) / 100.0
    return t["settle"]

def evalrow(trades, tp, stop):
    nets = []; ys = {}
    for t in trades:
        close = walk(t, tp, stop)
        net = (t["credit"] - close) - (t["se"] * spf(t["se"]) + t["le"] * spf(t["le"])) / 100.0
        nets.append((net, t["w"])); ys.setdefault(t["y"], []).append((net, t["w"]))
    n = len(nets)
    if n == 0: return None
    win = sum(1 for a, _ in nets if a > 0) / n * 100
    netw = sum(a for a, _ in nets) / sum(b for _, b in nets) * 100
    ypos = sum(1 for y, g in ys.items() if sum(a for a, _ in g) > 0)
    ydet = {y: round(sum(a for a, _ in g) / sum(b for _, b in g) * 100, 1) for y, g in sorted(ys.items())}
    return n, win, netw, ypos, len(ys), ydet

rows = []
for key in sorted(ALL):
    dc, S, W, M = key
    trades = ALL[key]
    cws = sorted(t["cw"] for t in trades)
    med = cws[len(cws)//2] if cws else 0
    print(f"\n### DC{dc} s{S}w{W} DTE>={M}: n={len(trades)} c/w median {med:.2f}", flush=True)
    for g in GATES:
        sub = [t for t in trades if t["cw"] >= g]
        for lab, tp, stop in EXITS:
            r = evalrow(sub, tp, stop)
            if r is None: continue
            n, win, netw, ypos, ny, ydet = r
            rows.append((dc, S, W, M, g, lab, n, win, netw, ypos, ny, ydet))
            print(f"  cw>={g:.2f} {lab:12s} n={n:3d} win {win:5.1f}%  net {netw:+6.1f}%w  yrs+ {ypos}/{ny}  {ydet}", flush=True)

print("\n=== SURVIVORS (win>=70 & net>=+10%w & yrs+>=5/6 & n>=30) ===", flush=True)
surv = [r for r in rows if r[7] >= 70 and r[8] >= 10 and r[9] >= 5 and r[6] >= 30]
if not surv:
    print("NONE.", flush=True)
    print("\n--- near-misses (win>=65 & net>=+6%w & yrs+>=4, n>=25) ---", flush=True)
    for r in sorted(rows, key=lambda r: -r[8]):
        if r[7] >= 65 and r[8] >= 6 and r[9] >= 4 and r[6] >= 25:
            print(f"  DC{r[0]} s{r[1]}w{r[2]} DTE{r[3]} cw>={r[4]:.2f} {r[5]:12s} n={r[6]} win {r[7]:.1f}% net {r[8]:+.1f}%w yrs+{r[9]}/{r[10]} {r[11]}", flush=True)
else:
    for r in surv:
        print(f"  DC{r[0]} s{r[1]}w{r[2]} DTE{r[3]} cw>={r[4]:.2f} {r[5]:12s} n={r[6]} win {r[7]:.1f}% net {r[8]:+.1f}%w yrs+{r[9]}/{r[10]} {r[11]}", flush=True)

# breakout-size buckets on the base collection (DC10 s1w3 DTE10), hold/stop2, no gate
base = ALL[(10, 1, 3, 10)]
if base:
    bos = sorted(t["bo"] for t in base)
    qs = [bos[len(bos)//4], bos[len(bos)//2], bos[3*len(bos)//4]]
    print(f"\n=== breakout-size buckets, base DC10 s1w3 DTE10, hold/stop2 (quartile edges {qs[0]:.2f}/{qs[1]:.2f}/{qs[2]:.2f}%) ===", flush=True)
    labs = ["Q1 small", "Q2", "Q3", "Q4 big"]
    for qi in range(4):
        lo = -1e9 if qi == 0 else qs[qi-1]; hi = 1e9 if qi == 3 else qs[qi]
        sub = [t for t in base if lo <= t["bo"] < hi]
        r = evalrow(sub, None, 2.0)
        if r: print(f"  {labs[qi]:9s} n={r[0]:3d} win {r[1]:5.1f}%  net {r[2]:+6.1f}%w  yrs+ {r[3]}/{r[4]}", flush=True)
print("\nDONE-NIFTYFADE-GRID", flush=True)
