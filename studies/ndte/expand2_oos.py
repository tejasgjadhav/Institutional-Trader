"""OOS (Oct-2024 -> date) for the 103 outsider names, through the HARNESS OF RECORD.

Imports deployed_backtest per the no-copy rule (21-Aug-2026): its __main__ guard makes the import
safe, and every gate, fix and exit rule arrives by reference instead of by paste. Only two things
are overridden: the symbol list, and LOTMAP entries for names outside the 113 (missing lots would
make their trades weightless in ROM-Rs while still counting in n and win%).
"""
import sys, json, importlib.util
sys.path.insert(0, "/Users/sayali/files/institutional-trader")
sys.argv = ["expand2_oos", "OOS"]

spec = importlib.util.spec_from_file_location(
    "dbt", "/Users/sayali/files/institutional-trader/studies/ndte/deployed_backtest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)

OUTS = json.load(open("research/expansion2/outsiders.json"))
H.UNIVERSE = [s + ".NS" for s in OUTS]

# lot sizes for outsiders, from the Upstox instrument master
from engine.options import _load_index
from engine.instruments import to_instrument_key
added = 0
for s in OUTS:
    if H.LOTMAP.get(s): continue
    try:
        ch = _load_index().get(to_instrument_key(s + ".NS")) or []
        lots = [int(c.get("lot") or 0) for c in ch if c.get("lot")]
        if lots:
            H.LOTMAP[s] = max(set(lots), key=lots.count)
            added += 1
    except Exception:
        pass
missing = [s for s in OUTS if not H.LOTMAP.get(s)]
print(f"lots resolved for {added} outsiders · still missing {len(missing)}: {missing[:10]}", flush=True)

rows = H.run_oos()
json.dump(rows, open("research/expansion2/oos_rows.json", "w"))
print(f"DONE-EXPAND2-OOS {len(rows)} trades", flush=True)
if H.FETCHFAIL.get("dropped"):
    print(f"FETCH INTEGRITY: {H.FETCHFAIL['dropped']} dropped — counts are a FLOOR", flush=True)
else:
    print("FETCH INTEGRITY: 0 dropped — every candidate decided on real data", flush=True)
