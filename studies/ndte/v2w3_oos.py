"""Width-3 v2 OOS (17-Sep-2026) - runs after the far-expiry v1 OOS so the two never compete for
the throttled Upstox feed. Same harness of record, deployed v2 alongside for a same-run control."""
import sys, json, socket
socket.setdefaulttimeout(30)   # 17-Sep: 109 sockets sat on unanswered reads for 13 min; make them raise
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
H.BOOKS = {"v2w3": dict(S=2, W=3, tp=0.50, stop=None, band=(0.40, 99.0)),
           "v2":   dict(S=2, W=4, tp=0.50, stop=None, band=(0.40, 99.0))}
H.OUT = "research/v2w3_oos_rows.json"
if __name__ == "__main__":
    rows = H.run_oos()
    json.dump(rows, open(H.OUT, "w"))
    print(f"saved {len(rows)} rows -> {H.OUT}")
