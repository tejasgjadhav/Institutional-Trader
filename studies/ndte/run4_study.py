"""RUN 4 (17-Sep-2026): the harness of record after the two adversarial audits - inverted-wing
guard, counted contract/underlying fetch failures, run-stamped legfails, walk to expiry.
Deployed books only. Writes research/run4_<window>_rows.json; compare against run 3
(research/deployed_bt_<window>_rows.json) before ANY published number moves."""
import sys, json, socket
socket.setdefaulttimeout(30)
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
win = sys.argv[1] if len(sys.argv) > 1 else "IS"
if __name__ == "__main__":
    rows = H.run_is() if win == "IS" else H.run_oos()
    out = f"research/run4_{win.lower()}_rows.json"
    json.dump(rows, open(out, "w"))
    print(f"saved {len(rows)} rows -> {out}")
    H.WINDOW = win
    H.print_integrity()
    import statistics
    R = sorted(H.WING_RATIOS)
    if R:
        q = lambda f: R[min(len(R)-1, int(f*len(R)))]
        print(f"WING RATIOS: n={len(R)} median {statistics.median(R):.3f} p90 {q(.90):.3f} p95 {q(.95):.3f} "
              f"p99 {q(.99):.3f} · >1.10: {sum(r>1.10 for r in R)} · >1.25: {sum(r>1.25 for r in R)} · "
              f">1.50: {sum(r>1.50 for r in R)} · >2.0: {sum(r>2.0 for r in R)}")
        json.dump(R, open(f"research/run4_{win.lower()}_wing_ratios.json","w"))
