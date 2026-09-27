"""0.25-0.30 band, short leg Rs 30-50, per NAME x SIDE (user, 27-Sep-2026). v0 geometry (S=2, W=4,
TP-40, no stop), band (0.25, 0.30), per-book floor PREM (run at 30; the floor-50 set comes from
research/band25_*_rows_all.json filtered to c/w < 0.30). Incremental = the Rs 30-50 tranche.
Side stamped by wrapping eval_books. Study only - approval-first."""
import sys, os, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
PREM = float(os.environ.get("PREM", "30")); mode = sys.argv[1]
H.BOOKS = {"b25": dict(S=2, W=4, tp=0.40, stop=None, band=(0.25, 0.30), prem=PREM)}
_orig = H.eval_books
def _eb(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw):
    n = len(rows); r = _orig(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw)
    for x in rows[n:]: x["side"] = "BC" if typ == "CE" else "BP"
    return r
H.eval_books = _eb
rows = H.run_is() if mode == "IS" else H.run_oos()
out = f"research/premband25_{mode.lower()}_{int(PREM)}_rows.json"; json.dump(rows, open(out, "w"))
print(f"saved {len(rows)} rows -> {out}")
