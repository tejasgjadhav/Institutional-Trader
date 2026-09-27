"""The 8 names pruned on 24-Aug-2026 (whole-name net), re-run on the current harness (run 5, per-book
floor) so each SIDE can be judged on its own (user, 27-Sep-2026)."""
import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
P8 = ["HCLTECH", "SBILIFE", "OFSS", "TCS", "TECHM", "HDFCBANK", "DMART", "JINDALSTEL"]
H.UNIVERSE = [s + ".NS" for s in P8]
from engine.options import _load_index
from engine.instruments import to_instrument_key
for s in P8:
    if not H.LOTMAP.get(s):
        ch = _load_index().get(to_instrument_key(s + ".NS")) or []
        lots = [int(c.get("lot") or 0) for c in ch if c.get("lot")]
        if lots: H.LOTMAP[s] = max(set(lots), key=lots.count)
w = sys.argv[1]
rows = H.run_is() if w == "IS" else H.run_oos()
json.dump(rows, open(f"research/pruned8_{w.lower()}_rows.json", "w"))
print(f"DONE-PRUNED8-{w} {len(rows)} trades", flush=True)
