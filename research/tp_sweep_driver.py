"""Take-profit sweep over all 208 F&O names (user, 27-Sep-2026). Harness of record (run 5, per-book
floor) with EVERY book's take-profit set to TP (fraction of credit; 0.99 = hold to expiry).
Usage: tp_sweep_driver.py TP SET WINDOW   SET = main (universe) | outs (103 outsiders) | p8 (pruned 8)."""
import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
tp, st, w = float(sys.argv[1]), sys.argv[2], sys.argv[3]
for b in H.BOOKS.values(): b["tp"] = tp
if st == "outs":
    names = json.load(open("research/expansion2/outsiders.json")); H.IS_PICKLE = "research/expansion2/bhav_outsiders.pkl"
elif st == "p8":
    names = ["HCLTECH", "SBILIFE", "OFSS", "TCS", "TECHM", "HDFCBANK", "DMART", "JINDALSTEL"]
else:
    names = None
if names is not None:
    H.UNIVERSE = [s + ".NS" for s in names]
    from engine.options import _load_index
    from engine.instruments import to_instrument_key
    for s in names:
        if not H.LOTMAP.get(s):
            ch = _load_index().get(to_instrument_key(s + ".NS")) or []
            lots = [int(c.get("lot") or 0) for c in ch if c.get("lot")]
            if lots: H.LOTMAP[s] = max(set(lots), key=lots.count)
rows = H.run_is() if w == "IS" else H.run_oos()
out = f"research/tpsweep/tp{int(round(tp*100))}_{st}_{w.lower()}.json"; json.dump(rows, open(out, "w"))
print(f"DONE {out} {len(rows)} trades", flush=True)
