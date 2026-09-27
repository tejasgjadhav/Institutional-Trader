"""Per stock x live book x side x window, from data/name_history.json -> research/book_side_history.csv
(user, 27-Sep-2026). v2/v1/v0 = harness run 5 rows. vlc = the band evidence it was selected on:
whitelisted name-sides use the 0.30-0.40 cells, the three 0.25-0.30 cells use the Rs 30-50 screen."""
import json, csv, sys
sys.path.insert(0, ".")
from engine import config
nh = json.load(open("data/name_history.json"))
wl = config.STOCK_CREDIT_VLC_WHITELIST; cells = config.STOCK_CREDIT_VLC_CELLS
# the cells trade ONLY c/w 0.25-0.30 with a Rs 30-50 short leg: score them on exactly that slice
K = lambda r: (r["sym"], r["day"])
def _cell(v):
    return {"n": len(v), "win": 100 * sum(r["win"] for r in v) / len(v),
            "rom": 100 * sum(r["net"] for r in v) / sum(r["margin"] for r in v)} if v else None
CELLREC = {}
for (csym, cside) in cells:
    rec = []
    for w in ("is", "oos"):
        hi = {K(r) for r in json.load(open(f"research/band25_{w}_rows_all.json")) if r["cw"] < 0.30}
        sd = "BC" if cside == "BEAR_CALL" else "BP"
        rec.append(_cell([r for r in json.load(open(f"research/premband25_{w}_30_rows.json"))
                          if r["sym"] == csym and r["side"] == sd and K(r) not in hi]))
    CELLREC[(csym, cside)] = tuple(rec)
rows = []
for sym in sorted(nh):
    for side in ("BEAR_CALL", "BULL_PUT"):
        h = nh[sym].get(side, {})
        books = [("v2", h.get("v2_is"), h.get("v2_oos")), ("v1", h.get("v1_is"), h.get("v1_oos")), ("v0", h.get("v0_is"), h.get("v0_oos"))]
        if sym in wl.get(side, ()): books.append(("vlc 0.30-0.40", h.get("b30_is"), h.get("b30_oos")))
        if (sym, side) in cells: books.append(("vlc cell 0.25-0.30 Rs30-50", *CELLREC.get((sym, side), (None, None))))
        for bk, a, b in books:
            if not a and not b: continue
            f = lambda c: (c["n"], round(c["win"], 1), round(c["rom"], 1)) if c else ("", "", "")
            rows.append([sym, "BC" if side == "BEAR_CALL" else "BP", bk, *f(a), *f(b)])
with open("studies/BOOK_SIDE_HISTORY.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["symbol", "side", "book", "IS_n", "IS_win%", "IS_ROM%", "OOS_n", "OOS_win%", "OOS_ROM%"]); w.writerows(rows)
import collections
c = collections.Counter(r[2] for r in rows); print(f"{len(rows)} name x side x book rows · {len({r[0] for r in rows})} stocks · by book: {dict(c)}")
for s in ("LTM", "ULTRACEMCO", "MARUTI", "TATAELXSI"):
    for r in rows:
        if r[0] == s: print(f"  {r[0]:11s} {r[1]} {r[2]:19s} IS {r[3]}/{r[4]}%/{r[5]}%  OOS {r[6]}/{r[7]}%/{r[8]}%")
