"""Far-expiry OOS for v1 (user-approved 17-Sep-2026). 'Near expiry first, else next month':
run the deployed v1 config with MIN_DTE=25 so the harness picks the NEXT monthly, then union by
(sym, day) with the deployed DTE>=10 OOS rows - exactly the construction used for the in-sample
estimate (v1 566 -> 722 trades, 81.6 -> 83.0% win, 26.6 -> 29.2% ROM). One question to the
window: v1 only."""
import sys, json, socket
socket.setdefaulttimeout(30)   # 17-Sep: 109 sockets sat on unanswered reads for 13 min; make them raise
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
H.MIN_DTE = 25
H.BOOKS = {"v1": dict(S=1, W=3, tp=0.40, stop=None, band=(0.40, 99.0))}
H.OUT = "research/farexp_v1_oos_rows.json"
if __name__ == "__main__":
    rows = H.run_oos()
    json.dump(rows, open(H.OUT, "w"))
    print(f"saved {len(rows)} rows -> {H.OUT}")
