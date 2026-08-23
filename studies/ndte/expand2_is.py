"""IS (2019 -> Sep-2024) for the outsider names, through the harness of record (import, no copy)."""
import sys, json, importlib.util
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.argv = ["expand2_is", "IS"]
spec = importlib.util.spec_from_file_location(
    "dbt", "/Users/sayali/files/institutional-trader/studies/ndte/deployed_backtest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
OUTS = json.load(open("research/expansion2/outsiders.json"))
H.UNIVERSE = [s + ".NS" for s in OUTS]
H.IS_PICKLE = "research/expansion2/bhav_outsiders.pkl"
from engine.options import _load_index
from engine.instruments import to_instrument_key
for s in OUTS:
    if not H.LOTMAP.get(s):
        ch = _load_index().get(to_instrument_key(s + ".NS")) or []
        lots = [int(c.get("lot") or 0) for c in ch if c.get("lot")]
        if lots: H.LOTMAP[s] = max(set(lots), key=lots.count)
rows = H.run_is()
json.dump(rows, open("research/expansion2/is_rows.json", "w"))
print(f"DONE-EXPAND2-IS {len(rows)} trades", flush=True)
