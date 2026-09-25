"""data/name_history.json — per NAME x SIDE x WINDOW record for the 15:31 digest (user, 25-Sep-2026).
gate  = run-4 harness rows (every live book, c/w >= 0.35) split IS / OOS; side derived from the
        breakout direction on the entry day with the harness's own breakout_days() (rows omit side).
b30   = 0.30-0.40 band cells (research/band30_*_cells2.json, side recorded).
b25   = 0.25-0.35 band rows (research/band25_*_rows*.json, side recorded), split at 0.30.
Re-run after any harness re-run or band study. Each cell: n, win%, rom% (sum net / sum margin), net_rs.
"""
import sys, json, glob, collections, importlib.util
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.argv = ["build_name_history", "OOS"]
spec = importlib.util.spec_from_file_location("dbt", "studies/ndte/deployed_backtest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
from engine.data_fetcher import fetch_upstox_historical
from engine.config import UNIVERSE
def cell(v):
    if not v: return None
    n = len(v); w = sum(1 for r in v if r["net"] > 0); m = sum(r["margin"] for r in v) or 1e-9
    return {"n": n, "win": round(100 * w / n, 1), "rom": round(100 * sum(r["net"] for r in v) / m, 1),
            "net_rs": round(sum(r.get("net_rs", 0) for r in v))}
def load(files):
    rows, seen = [], set()
    for f in files:
        for p in glob.glob(f):
            try:
                for x in json.load(open(p)):
                    k = (x.get("book"), x["sym"], x["day"])
                    if k in seen: continue
                    seen.add(k); rows.append(x)
            except Exception: pass
    return rows
gate = load(["research/deployed_bt_is_rows.json", "research/expansion2/is_rows.json",
             "research/deployed_bt_oos_rows.json", "research/expansion2/oos_rows.json"])
by_sym = collections.defaultdict(list)
for x in gate: by_sym[x["sym"]].append(x)
out = collections.defaultdict(lambda: {"BEAR_CALL": {}, "BULL_PUT": {}})
names = sorted(set(by_sym) | {t.replace(".NS", "") for t in UNIVERSE})
for i, sym in enumerate(names):
    try:
        u = fetch_upstox_historical(sym + ".NS", unit="days", interval=1, from_date="2018-11-01", to_date=None)
    except Exception: u = None
    if u is None or u.empty or len(u) < 30: continue
    daymap = {d: typ for d, c, typ, d10 in H.breakout_days(u.sort_index())}
    # scanned breakouts per side x window: a dash in the digest must mean "0 of N", never "unknown"
    for d, typ in daymap.items():
        side = "BEAR_CALL" if typ == "CE" else "BULL_PUT"; win = "is" if d <= "2024-09-30" else "oos"
        out[sym][side][f"scanned_{win}"] = out[sym][side].get(f"scanned_{win}", 0) + 1
    buck = collections.defaultdict(list)
    for x in by_sym.get(sym, []):
        t = daymap.get(x["day"])
        if not t: continue
        side = "BEAR_CALL" if t == "CE" else "BULL_PUT"
        win = "is" if x["day"] <= "2024-09-30" else "oos"
        buck[(side, win)].append(x)
    for (side, win), v in buck.items():
        out[sym][side][f"gate_{win}"] = cell(v)
    if i % 25 == 0: print(f"  {i}/{len(names)}", flush=True)
# 0.30-0.40 band cells (side recorded, rom already computed)
for win, f in (("is", "research/band30_is_cells2.json"), ("oos", "research/band30_oos_cells2.json")):
    try:
        for k, c in json.load(open(f)).items():
            sym, sd = k.split("|"); side = "BEAR_CALL" if sd == "BC" else "BULL_PUT"
            out[sym][side][f"b30_{win}"] = {"n": c["n"], "win": c["win"], "rom": c.get("rom")}
    except Exception as e: print("band30 cells:", e)
# 0.25-0.35 rows (side recorded)
for win, pat in (("is", "research/band25_is_rows*.json"), ("oos", "research/band25_oos_rows*.json")):
    rows = load([pat]); b = collections.defaultdict(list)
    for x in rows:
        side = "BEAR_CALL" if x.get("side") == "BC" else "BULL_PUT"
        b[(x["sym"], side, "b25" if x["cw"] < 0.30 else "b3035")].append(x)
    for (sym, side, band), v in b.items():
        out[sym][side][f"{band}_{win}"] = cell(v)
json.dump(dict(out), open("data/name_history.json", "w"))
print(f"DONE {len(out)} names -> data/name_history.json")
for s in ("LTM", "MARUTI", "TATAELXSI", "RELIANCE"):
    print(s, json.dumps(out.get(s)))
