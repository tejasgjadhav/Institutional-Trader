"""Name-wise c/w 0.25-0.35 study for the names on the 24-Sep-2026 watchlist (user, 25-Sep-2026).
v0 geometry (S=2, W=4, TP-40, no stop). Study only - the pooled band is negative OOS
(CW_BAND_BY_BOOK.md); this asks whether any of THESE names differ. Side is recorded by wrapping
eval_books, which the harness rows otherwise omit."""
import sys, json, collections
sys.path.insert(0, "."); sys.path.insert(0, "studies/ndte")
import deployed_backtest as H
import os
NAMES = (None if os.environ.get("BAND25_NAMES") == "ALL" else os.environ["BAND25_NAMES"].split(",")) if os.environ.get("BAND25_NAMES") else ["TATAELXSI", "IDFCFIRSTB", "MARUTI", "MCX", "RELIANCE", "ICICIGI", "INDUSINDBK",
         "HDFCLIFE", "ZYDUSLIFE", "INDIANB"]
H.BOOKS = {"b25": dict(S=2, W=4, tp=0.40, stop=None, band=(0.25, 0.35))}
H.UNIVERSE = [tk for tk in H.UNIVERSE if NAMES is None or tk.replace(".NS", "") in NAMES]
_orig = H.eval_books
def _eb(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw):
    n = len(rows); r = _orig(day, sym, typ, ks, atm, px, cb, exp, spot, d10, rows, open_until, *a, **kw)
    for x in rows[n:]: x["side"] = "BC" if typ == "CE" else "BP"
    return r
H.eval_books = _eb
def table(rows, label):
    cells = collections.defaultdict(list)
    for r in rows:
        sb = "0.25-0.30" if r["cw"] < 0.30 else "0.30-0.35"
        cells[(r["sym"], r["side"], sb)].append(r)
    print(f"\n=== {label}: v0 geometry, per name/side/sub-band ===")
    print(f"{'name':11s} {'side':4s} {'band':9s} {'n':>3s} {'win%':>6s} {'ROM%':>7s} {'+yrs':>5s}")
    for k in sorted(cells):
        v = cells[k]; yrs = collections.defaultdict(float)
        for r in v: yrs[r["yr"]] += r["net"]
        win = 100 * sum(r["win"] for r in v) / len(v); rom = 100 * sum(r["net"] for r in v) / max(sum(r["margin"] for r in v), 1e-9)
        print(f"{k[0]:11s} {k[1]:4s} {k[2]:9s} {len(v):3d} {win:6.1f} {rom:7.1f} {sum(1 for y in yrs.values() if y>0):2d}/{len(yrs)}")
if __name__ == "__main__":
    mode = sys.argv[1]
    print(f"{len(H.UNIVERSE)} names: {[t.replace('.NS','') for t in H.UNIVERSE]}", flush=True)
    rows = H.run_is() if mode == "IS" else H.run_oos()
    out = f"research/band25_{mode.lower()}_rows.json"; json.dump(rows, open(out, "w"))
    print(f"saved {len(rows)} rows -> {out}"); table(rows, mode)
