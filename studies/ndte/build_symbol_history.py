"""Fold the harness row files into data/symbol_history.json, INCLUDING how many breakout signals
were SCANNED per name (the user's ask, 24-Aug-2026): a reader should see 'we scanned N breakouts of
this stock and took M trades'. Scanned = union-Donchian breakout days counted by the SAME
breakout_days() the harness of record uses, per window. Re-run after any backtest re-run.
"""
import sys, json, collections, importlib.util
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.argv = ["build_symbol_history", "OOS"]
spec = importlib.util.spec_from_file_location("dbt", "studies/ndte/deployed_backtest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
from engine.data_fetcher import fetch_upstox_historical
from engine.config import UNIVERSE

out = collections.defaultdict(lambda: {"is": None, "oos": None, "scanned_is": 0, "scanned_oos": 0})
def fold(files, key):
    rows = []
    for f in files:
        try: rows += json.load(open(f))
        except Exception: pass
    by = collections.defaultdict(list)
    for x in rows: by[x["sym"]].append(x["net_rs"])
    for s, v in by.items():
        w = [x for x in v if x > 0]; l = [x for x in v if x <= 0]
        out[s][key] = {"n": len(v), "win": round(100 * len(w) / len(v), 1),
                       "avg_win": round(sum(w) / len(w)) if w else None,
                       "avg_loss": round(sum(l) / len(l)) if l else None}
fold(["research/deployed_bt_is_rows.json", "research/expansion2/is_rows.json"], "is")
fold(["research/deployed_bt_oos_rows.json", "research/expansion2/oos_rows.json"], "oos")

# PER-BOOK SPLIT (user, 24-Aug-2026): v2/v1/v0 carry different exits (TP-50 vs TP-40) and
# geometries, so a signal must quote ITS OWN book's record, not a pool of three strategies.
# Windows pooled inside each book to keep n meaningful at per-name grain.
_all = []
for f in ("research/deployed_bt_is_rows.json", "research/expansion2/is_rows.json",
          "research/deployed_bt_oos_rows.json", "research/expansion2/oos_rows.json"):
    try: _all += json.load(open(f))
    except Exception: pass
_bb = collections.defaultdict(lambda: collections.defaultdict(list))
for x in _all: _bb[x["sym"]][x["book"]].append(x["net_rs"])
for s2, bks in _bb.items():
    for bk, v in bks.items():
        w = [z for z in v if z > 0]
        out[s2]["book_" + bk] = {"n": len(v), "win": round(100 * len(w) / len(v), 1),
                                 "net": round(sum(v))}

# SIDE SPLIT (user, 24-Aug-2026): the row files do not store the side, but the side IS the
# breakout direction - an up-break is faded with a BEAR CALL, a down-break with a BULL PUT -
# so map each (sym, day) to CE/PE with the same breakout_days() and join the trade rows on it.
ALL_ROWS = []
for f in ("research/deployed_bt_is_rows.json", "research/expansion2/is_rows.json",
          "research/deployed_bt_oos_rows.json", "research/expansion2/oos_rows.json"):
    try: ALL_ROWS += json.load(open(f))
    except Exception: pass
ROWS_BY_SYM = collections.defaultdict(list)
for x in ALL_ROWS: ROWS_BY_SYM[x["sym"]].append(x)

for n, tk in enumerate(UNIVERSE):
    sym = tk.replace(".NS", "")
    try:
        u = fetch_upstox_historical(tk, unit="days", interval=1,
                                    from_date="2018-11-01", to_date=None)
    except Exception:
        u = None
    if u is None or u.empty or len(u) < 30: continue
    u = u.sort_index()
    daymap = {}
    for d, c, typ, d10 in H.breakout_days(u):
        daymap[d] = typ
        if d <= "2024-09-30": out[sym]["scanned_is"] += 1
        elif d >= "2024-10-01": out[sym]["scanned_oos"] += 1
    side = {"BEAR_CALL": [], "BULL_PUT": []}
    # per-window side counts (user, 24-Aug-2026): the IS and OOS lines each state how many
    # bear calls and bull puts they contain
    wc = {"is": {"bc": 0, "bp": 0}, "oos": {"bc": 0, "bp": 0}}
    for x in ROWS_BY_SYM.get(sym, []):
        t = daymap.get(x["day"])
        if not t: continue
        side["BEAR_CALL" if t == "CE" else "BULL_PUT"].append(x["net_rs"])
        w = "is" if x["day"] <= "2024-09-30" else "oos"
        wc[w]["bc" if t == "CE" else "bp"] += 1
    for w in ("is", "oos"):
        if out[sym].get(w): out[sym][w]["bc"], out[sym][w]["bp"] = wc[w]["bc"], wc[w]["bp"]
    for k, v in side.items():
        out[sym][k.lower()] = ({"n": len(v), "win": round(100 * sum(1 for z in v if z > 0) / len(v), 1),
                                "net": round(sum(v))} if v else None)
    if n % 20 == 0: print(f"  {n}/{len(UNIVERSE)}", flush=True)
json.dump(dict(out), open("data/symbol_history.json", "w"))
print(f"DONE {len(out)} symbols", flush=True)
