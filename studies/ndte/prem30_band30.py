"""Segregated premium floor (user, 26-Sep-2026): for names that never reach a Rs 50 short leg, does a
Rs 30 floor with c/w >= 0.30 work NAME-WISE? v0 geometry (S=2, W=4, TP-40, no stop), one band
(0.30, inf), MIN_PREM = $PREM (run at 30 and 50; the difference is what the Rs 50 floor removes).
Side is stamped by wrapping eval_books. Study only - nothing deploys without the OOS qualifier screen."""
import sys, os, json
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
PREM = float(os.environ["PREM"]); mode = sys.argv[1]
H.MIN_PREM = PREM
H.BOOKS = {"p30": dict(S=2, W=4, tp=0.40, stop=None, band=(0.30, 99.0))}
_orig = H.eval_books
def _eb(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw):
    n = len(rows); r = _orig(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw)
    for x in rows[n:]: x["side"] = "BC" if typ == "CE" else "BP"
    return r
H.eval_books = _eb
rows = H.run_is() if mode == "IS" else H.run_oos()
out = f"research/prem30_{mode.lower()}_{int(PREM)}_rows.json"; json.dump(rows, open(out, "w"))
print(f"saved {len(rows)} rows -> {out}")
