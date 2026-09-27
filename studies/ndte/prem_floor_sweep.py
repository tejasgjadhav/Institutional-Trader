"""Premium-floor sweep (user, 26-Sep-2026): does the Rs 50 short-leg floor cut signals we would want?
Runs the harness of record unchanged except MIN_PREM = $PREM. Compare row sets across floors:
trades present at floor 10 but absent at 50 are the ones the floor removes. IS = bhavcopy, OOS = Upstox."""
import sys, os, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
PREM = float(os.environ["PREM"]); mode = sys.argv[1]
H.MIN_PREM = PREM
rows = H.run_is() if mode == "IS" else H.run_oos()
out = f"research/premfloor_{mode.lower()}_{int(PREM)}_rows.json"; json.dump(rows, open(out, "w"))
print(f"saved {len(rows)} rows -> {out}")
