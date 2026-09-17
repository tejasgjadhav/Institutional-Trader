"""Width-3 variant of v2 (user goal 16-Sep-2026: more signals without lowering c/w 0.40).
Same short strike (2-OTM), same TP-50, no stop; the long wing one strike closer. Narrower width
raises credit/width mechanically, so more names clear the unchanged 0.40 gate. IS only here."""
import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
H.BOOKS = {"v2w3": dict(S=2, W=3, tp=0.50, stop=None, band=(0.40, 99.0)),
           "v2":   dict(S=2, W=4, tp=0.50, stop=None, band=(0.40, 99.0))}   # deployed, same run = same data
if __name__ == "__main__":
    rows = H.run_is()
    json.dump(rows, open("research/v2w3_is_rows.json", "w"))
    print(f"saved {len(rows)} rows")
