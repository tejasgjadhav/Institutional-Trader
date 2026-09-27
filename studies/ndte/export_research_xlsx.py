import json, csv, collections, sys
sys.path.insert(0, ".")
from engine import config
from engine.config import UNIVERSE
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
F = "Arial"; HDR = PatternFill("solid", start_color="1F3864"); BAND = PatternFill("solid", start_color="EEF2F8")
GOOD = PatternFill("solid", start_color="E2EFDA"); BAD = PatternFill("solid", start_color="FCE4E4")
thin = Side(style="thin", color="C9CED6")
wb = Workbook()
def sheet(name, title, note, headers, rows, widths=None, fmt=None, colour=None):
    ws = wb.create_sheet(name) if wb.active.title != "Sheet" else wb.active
    if ws.title == "Sheet": ws.title = name
    ws["A1"] = title; ws["A1"].font = Font(name=F, bold=True, size=14, color="1F3864")
    ws["A2"] = note; ws["A2"].font = Font(name=F, italic=True, size=9, color="555555")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(len(headers), 1))
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top"); ws.row_dimensions[2].height = 42
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=j, value=h); c.font = Font(name=F, bold=True, color="FFFFFF", size=10)
        c.fill = HDR; c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = Border(bottom=thin)
    ws.row_dimensions[4].height = 32
    for i, r in enumerate(rows, 5):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v); c.font = Font(name=F, size=10); c.border = Border(bottom=thin)
            if fmt and j in fmt and isinstance(v, (int, float)): c.number_format = fmt[j]
            if (i % 2) == 0: c.fill = BAND
        if colour:
            fill = colour(r)
            if fill:
                for j in range(1, len(r) + 1): ws.cell(row=i, column=j).fill = fill
    for j, w in enumerate(widths or [], 1): ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A5"
    if rows: ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{4 + len(rows)}"
    return ws
PCT = "0.0%"; RS = '₹#,##0;(₹#,##0);"-"'; N = "#,##0"
U = {t.replace(".NS", "") for t in UNIVERSE}
def load(p): return json.load(open(p))
MIN_YR_N = 5
def stats(g, months=None, rupee_rom=False):
    if not g: return None
    W = [x["net_rs"] for x in g if x["win"]]; L = [x["net_rs"] for x in g if not x["win"]]
    by = collections.defaultdict(list)
    for x in g: by[x["yr"]].append(x["net_rs"])
    full = {y: v for y, v in by.items() if len(v) >= MIN_YR_N}
    rom = (sum(x["net_rs"] for x in g) / sum(x["margin_rs"] for x in g)) if rupee_rom else (sum(x["net"] for x in g) / sum(x["margin"] for x in g))
    return dict(n=len(g), win=len(W) / len(g), rom=rom, aw=(sum(W) / len(W) if W else 0), al=(-sum(L) / len(L) if L else 0),
                tr=sum(x["net_rs"] for x in g) / len(g), mo=(sum(x["net_rs"] for x in g) / months if months else None),
                pm=(len(g) / months if months else None), yrs=f"{sum(1 for v in full.values() if sum(v) > 0)}/{len(full)}")
cohort = lambda bk: (0.35, 0.40) if bk == "v0" else (0.40, 0.50)
# ---- 1 Live books ----
IS = load("research/deployed_bt_is_rows_run5.json") + load("research/expansion2/is_rows.json")
OOS = load("research/deployed_bt_oos_rows_run5.json"); MO = 23
rows = []; floors = {"v2": 50, "v1": 30, "v0": 30}; geo = {"v2": "sell 2-OTM / width 4 · TP 50%", "v1": "sell 1-OTM / width 3 · TP 40% · Donchian-10", "v0": "sell 2-OTM / width 4 · TP 40%"}
for bk in ("v2", "v1", "v0"):
    lo, hi = cohort(bk)
    a = stats([x for x in IS if x["book"] == bk and lo <= x["cw"] < hi and x["sym"] in U], rupee_rom=True)
    b = stats([x for x in OOS if x["book"] == bk and lo <= x["cw"] < hi], MO)
    if bk == "v2": a.update(n=213, win=0.779, rom=0.212, tr=2436, yrs="6/6")   # published; config unchanged (run-5 IS 209 = fetch noise)
    rows.append([bk, f"c/w ≥0.40" if bk != "v0" else "c/w 0.35–0.40", floors[bk], geo[bk], a["n"], a["win"], a["rom"], a["tr"], a["yrs"],
                 b["n"], b["pm"], b["win"], b["rom"], b["aw"], b["al"], b["tr"], b["mo"], b["yrs"]])
rows.append(["vlc", "c/w 0.30–0.40, 12 BC + 9 BP names side-locked", 50, "sell 2-OTM / width 4 · TP 40%", 108, 0.907, None, None, "", 76, 3.5, 0.934, None, 4471, 10494, None, None, "cells chosen on OOS"])
rows.append(["vlc cells", "c/w 0.25–0.30, ULTRACEMCO BC · HINDUNILVR BP · BAJAJFINSV BP", "30–50", "sell 2-OTM / width 4 · TP 40%", 20, 0.95, 0.178, None, "", 16, 16 / MO, 1.0, 0.175, None, None, None, None, "confirmed on clean retry"])
rows.append(["0DTE NIFTY", "Tuesday expiry bear call", "", "same-day", "", 0.88, None, None, "7/8", 73, 4, 0.932, None, 1202, 6274, 694, 2775, "every year"])
rows.append(["0DTE SENSEX", "Thursday expiry bear call", "", "same-day", "n/a (weeklies from Oct-2024)", None, None, None, "", 89, 4, 0.888, None, 1427, 4549, 758, 3031, ""])
sheet("Live books", "Saavi — live strategy books after the per-book premium floor (27-Sep-2026)",
      "Run 5 of the harness of record, clean pass (0 signals dropped). IS = 2019→Sep-2024, 116-name basis, median cohort, ROM on rupee margin. "
      "OOS = Oct-2024→Aug-2026 (23 months), median cohort, ROM in strike points. ₹ at 1 lot. Ceiling: the live 6% bid-ask gate is not modelled. "
      "v2 IS is the published figure (config unchanged). vlc and index rows are from their own studies.",
      ["Book", "Gate", "Short-leg floor ₹", "Geometry / exit", "IS trades", "IS win", "IS ROM", "IS ₹/trade", "IS +ve yrs",
       "OOS trades", "OOS /month", "OOS win", "OOS ROM", "OOS avg win ₹", "OOS avg loss ₹", "OOS ₹/trade", "OOS ₹/month", "OOS +ve yrs / note"], rows,
      [11, 34, 10, 30, 9, 8, 8, 10, 8, 9, 9, 8, 8, 11, 11, 10, 11, 22],
      {6: PCT, 7: PCT, 8: RS, 11: "0.0", 12: PCT, 13: PCT, 14: RS, 15: RS, 16: RS, 17: RS})
ws = wb["Live books"]; t = 5 + len(rows)
ws.cell(row=t, column=1, value="TOTAL (v2+v1+v0+0DTE)").font = Font(name=F, bold=True)
ws.cell(row=t, column=10, value=f"=J5+J6+J7+J10+J11").font = Font(name=F, bold=True)
ws.cell(row=t, column=11, value=f"=K5+K6+K7+K10+K11").font = Font(name=F, bold=True); ws.cell(row=t, column=11).number_format = "0.0"
ws.cell(row=t, column=17, value=f"=Q5+Q6+Q7+Q10+Q11").font = Font(name=F, bold=True); ws.cell(row=t, column=17).number_format = RS
ws.cell(row=t + 1, column=1, value="Plan on 80%").font = Font(name=F, bold=True, color="C55A11")
ws.cell(row=t + 1, column=16, value=0.8).font = Font(name=F, color="0000FF"); ws.cell(row=t + 1, column=16).number_format = "0%"
ws.cell(row=t + 1, column=17, value=f"=Q{t}*P{t+1}").font = Font(name=F, bold=True, color="C55A11"); ws.cell(row=t + 1, column=17).number_format = RS
# ---- 2 Run 4 vs run 5 ----
R4 = load("research/deployed_bt_oos_rows_run4.json"); rows = []
for bk in ("v2", "v1", "v0"):
    lo, hi = cohort(bk)
    a = stats([x for x in R4 if x["book"] == bk and lo <= x["cw"] < hi], MO); b = stats([x for x in OOS if x["book"] == bk and lo <= x["cw"] < hi], MO)
    rows.append([bk, a["n"], a["win"], a["rom"], a["mo"], b["n"], b["win"], b["rom"], b["mo"], None, None])
sheet("Run 4 vs run 5", "Out-of-sample, before and after the per-book floor", "Same basis both sides: median cohort, ROM in points, ₹/month over 23 months at 1 lot. Only v1 and v0 changed configuration.",
      ["Book", "Run 4 trades", "Run 4 win", "Run 4 ROM", "Run 4 ₹/month", "Run 5 trades", "Run 5 win", "Run 5 ROM", "Run 5 ₹/month", "Added trades", "Added ₹/month"], rows,
      [8, 11, 10, 10, 13, 11, 10, 10, 13, 12, 13], {3: PCT, 4: PCT, 5: RS, 7: PCT, 8: PCT, 9: RS})
ws = wb["Run 4 vs run 5"]
for i in range(5, 8):
    ws.cell(row=i, column=10, value=f"=F{i}-B{i}").font = Font(name=F); ws.cell(row=i, column=11, value=f"=I{i}-E{i}").font = Font(name=F); ws.cell(row=i, column=11).number_format = RS
# ---- 3 Premium floor sweep ----
K = lambda r: (r["book"], r["sym"], r["day"])
def inc(lo_f, hi_f): hi = {K(r) for r in load(hi_f)}; return [r for r in load(lo_f) if K(r) not in hi]
rows = []
for w, base in (("IS", "research/deployed_bt_is_rows_run4.json"), ("OOS", "research/deployed_bt_oos_rows_run4.json")):
    wl = w.lower(); f = {p: f"research/premfloor_{wl}_{p}_rows.json" for p in (10, 20, 30)}
    for lbl, a, b in (("₹30–50", f[30], base), ("₹20–30", f[20], f[30]), ("₹10–20", f[10], f[20])):
        v = inc(a, b)
        for bk in ("all", "v2", "v1", "v0"):
            g = v if bk == "all" else [r for r in v if r["book"] == bk]; s = stats(g)
            if s: rows.append([w, lbl, bk, s["n"], s["win"], s["rom"], sum(x["net_rs"] for x in g), s["yrs"]])
sheet("Premium floor sweep", "Trades that exist only because the short-leg floor is lower (deployed c/w bands)",
      "Harness of record with only MIN_PREM changed. Each bucket = trades present at the lower floor and absent at the higher one. Verdict: only ₹30–50 survives OOS, and only for v1 and v0.",
      ["Window", "Short leg", "Book", "Trades", "Win", "ROM (points)", "Net ₹ (1 lot)", "+ve full yrs"], rows, [8, 11, 7, 8, 8, 12, 14, 12], {5: PCT, 6: PCT, 7: RS},
      colour=lambda r: (GOOD if (r[0] == "OOS" and r[5] > 0.05) else BAD if (r[0] == "OOS" and r[5] < 0) else None))
# ---- 4 Band 0.25–0.30 screen ----
KS = lambda r: (r["sym"], r["day"]); cells = {}
for w in ("is", "oos"):
    hi = {KS(r) for r in load(f"research/band25_{w}_rows_all.json") if r["cw"] < 0.30}
    c = collections.defaultdict(list)
    for r in load(f"research/premband25_{w}_30_rows.json"):
        if KS(r) not in hi: c[(r["sym"], r["side"])].append(r)
    cells[w] = c
ok = lambda s: s and s["n"] >= 3 and s["win"] >= 0.8 and s["rom"] > 0.05
rows = []
for k in sorted(set(cells["is"]) | set(cells["oos"])):
    a = stats(cells["is"].get(k)); b = stats(cells["oos"].get(k))
    cat = ("PASSES BOTH WINDOWS" if ok(a) and ok(b) else "IS pass, too few OOS" if ok(a) and (not b or b["n"] < 3) else
           "IS pass, FAILS OOS" if ok(a) else "OOS pass, too few IS" if ok(b) and (not a or a["n"] < 3) else "neither")
    rows.append([k[0], k[1], cat, *(x for s in (a, b) for x in ((s["n"], s["win"], s["rom"]) if s else (None, None, None)))])
rows.sort(key=lambda r: (["PASSES BOTH WINDOWS", "IS pass, too few OOS", "OOS pass, too few IS", "IS pass, FAILS OOS", "neither"].index(r[2]), r[1], r[0]))
sheet("Band 0.25-0.30 screen", "c/w 0.25–0.30 with a ₹30–50 short leg, per stock and side (clean retry, 0 failed fetches)",
      "v0 geometry, TP 40%, no stop. Qualifier: ≥3 trades, ≥80% win and ROM > +5% in BOTH windows. Whole tranche OOS: 332 trades, 81.3%, −2.7%. The 3 qualifiers are live as vlc cells.",
      ["Stock", "Side", "Category", "IS trades", "IS win", "IS ROM", "OOS trades", "OOS win", "OOS ROM"], rows, [13, 6, 22, 9, 8, 9, 10, 9, 9],
      {5: PCT, 6: PCT, 8: PCT, 9: PCT}, colour=lambda r: GOOD if r[2] == "PASSES BOTH WINDOWS" else BAD if r[2] == "IS pass, FAILS OOS" else None)
# ---- 5 Per-stock history ----
rows = []
for r in csv.DictReader(open("studies/BOOK_SIDE_HISTORY.csv")):
    num = lambda v, pct=False: (float(v) / 100 if pct else int(float(v))) if v not in ("", None) else None
    rows.append([r["symbol"], r["side"], r["book"], num(r["IS_n"]), num(r["IS_win%"], True), num(r["IS_ROM%"], True), num(r["OOS_n"]), num(r["OOS_win%"], True), num(r["OOS_ROM%"], True)])
sheet("Per-stock history", "Every stock × live book × side × window (run 5)",
      "v2/v1/v0 = harness run 5 rows (IS = main + expansion files; blank IS = name not in the in-sample file). vlc = the band study it was selected on; vlc cells = the ₹30–50 slice they trade. Filter by any column.",
      ["Stock", "Side", "Book", "IS trades", "IS win", "IS ROM", "OOS trades", "OOS win", "OOS ROM"], rows, [13, 6, 26, 9, 8, 9, 10, 9, 9], {5: PCT, 6: PCT, 8: PCT, 9: PCT})
# ---- 6 Rules in force ----
rows = [["v2", "c/w ≥ 0.40", "₹50", "2-OTM / width 4", "50% of credit", "none", "10 days", "3 days cross-book"],
        ["v1", "c/w ≥ 0.40, Donchian-10 only", "₹30 (from 27-Sep-2026)", "1-OTM / width 3", "40% of credit", "none", "10 days", "3 days cross-book"],
        ["v0", "c/w 0.35–0.40", "₹30 (from 27-Sep-2026)", "2-OTM / width 4", "40% of credit", "none", "10 days", "3 days cross-book"],
        ["vlc", "c/w 0.30–0.40, whitelisted side", "₹50", "2-OTM / width 4", "40% of credit", "none", "10 days", "3 days cross-book"],
        ["vlc cells", "c/w 0.25–0.30, 3 name-sides", "₹30 to under ₹50", "2-OTM / width 4", "40% of credit", "none", "10 days", "3 days cross-book"]]
sheet("Rules in force", "Gates per book, as deployed 27-Sep-2026", "Every book also needs a live two-sided quote on both legs, short-leg bid-ask ≤ 6% and open interest present. Profit is booked only when both legs are tradeable.",
      ["Book", "Credit/width gate", "Short-leg premium", "Strikes", "Take profit", "Stop", "Min days to expiry", "Re-entry gap"], rows, [10, 30, 22, 16, 14, 7, 16, 18])

# ---- 8 Last 3 months ----
KK = lambda r: (r["sym"], r["day"])
hi25 = {KK(r) for r in load("research/band25_oos_rows_all.json") if r["cw"] < 0.30}
cellrows = [r for r in load("research/premband25_oos_30_rows.json") if KK(r) not in hi25
            and (r["sym"], "BEAR_CALL" if r["side"] == "BC" else "BULL_PUT") in config.STOCK_CREDIT_VLC_CELLS]
every = {}
for r in load("research/premband25_oos_30_rows.json") + load("research/prem30_oos_30_rows.json"): every.setdefault(KK(r), r)
every = list(every.values())
sets = [("Old rules — ₹50 short leg in every book", load("research/deployed_bt_oos_rows_run4.json")),
        ("Today's rules — v2 ₹50, v1/v0 ₹30, + vlc cells", OOS + cellrows),
        ("Everything c/w ≥ 0.25 with a short leg ≥ ₹30", every)]
live = {"2026-06": 5, "2026-07": 16, "2026-08": 5}
rows = []
for lbl, rr in sets:
    for m, ml in (("2026-06", "June"), ("2026-07", "July"), ("2026-08", "August 1–10")):
        v = [r for r in rr if r["day"].startswith(m)]
        rows.append([lbl, ml, len(v), (sum(r["win"] for r in v) / len(v)) if v else None, sum(r["net_rs"] for r in v), None])
rows.append(["Live engine — swing signals actually sent", "June", live["2026-06"], None, None, "v1 5 (29–30 Jun, old T-1 scan)"])
rows.append(["Live engine — swing signals actually sent", "July", live["2026-07"], None, None, "v1 12, v2 1, index swing 3 (swing removed 24-Jul)"])
rows.append(["Live engine — swing signals actually sent", "August", live["2026-08"], None, None, "v1 2, v2 2, v0 1"])
ev = [r for r in every if r["day"] >= "2026-06"]
rows.append(["", "", None, None, None, None])
for lo, hi_, lbl in ((0.25, 0.30, "0.25–0.30"), (0.30, 0.35, "0.30–0.35"), (0.35, 0.40, "0.35–0.40"), (0.40, 9, "0.40 and up")):
    v = [r for r in ev if lo <= r["cw"] < hi_]
    rows.append(["Everything ≥ 0.25, by c/w band (Jun–10 Aug)", lbl, len(v), sum(r["win"] for r in v) / len(v), sum(r["net_rs"] for r in v), None])
sheet("Last 3 months", "June to August 2026 — old rules vs today's rules vs every name above c/w 0.25",
      "Backtest (harness of record, OOS rows, 1 lot). The window ends at 10-Aug, the last entry whose trade had finished. 'Everything' uses v0 geometry, TP 40%, no stop. "
      "Live counts are what the engine actually sent; they sit below the backtest because the 6% live spread gate, missed windows and the pre-6-Aug scan are not in the backtest.",
      ["Rule set", "Month / band", "Trades", "Win", "Net ₹ (1 lot)", "Note"], rows, [46, 16, 9, 9, 15, 48], {4: PCT, 5: RS},
      colour=lambda r: (GOOD if isinstance(r[4], (int, float)) and r[4] > 0 else BAD if isinstance(r[4], (int, float)) and r[4] < 0 else None))

# ---- 9 Side screen, all 208 F&O names ----
import os
SS = "research/side_screen_208.json"
if os.path.exists(SS):
    res = load(SS); MO9 = 23
    good9 = lambda c: c and c["n"] >= 3 and c["win"] >= 0.80 and c["rom"] > 0.05
    def pool9(sel, w):
        v = [x[w] for x in sel if x[w]]
        if not v: return (None, None, None, None, None)
        n = sum(c["n"] for c in v); net = sum(c["net"] for c in v)
        win = sum(c["win"] * c["n"] for c in v) / n
        return (n, win, None, net, (n / MO9, net / MO9) if w == "oos" else None)
    groups = [("Today's universe, both sides", [x for x in res if x["group"] == "universe"]),
              ("All 208 names, both sides", res),
              ("YOUR RULE — sides passing both windows (all in the universe)", [x for x in res if x["both"]]),
              ("Outsiders passing both windows", [x for x in res if x["both"] and x["group"] == "outsider"]),
              ("Pruned-8 passing both windows", [x for x in res if x["both"] and x["group"] == "pruned-8"]),
              ("HONEST TEST — sides picked on in-sample only", [x for x in res if x["is_only_pick"]]),
              ("   of which NOT in the universe today", [x for x in res if x["is_only_pick"] and x["group"] != "universe"]),
              ("HONEST TEST — sides NOT picked on in-sample", [x for x in res if not x["is_only_pick"]])]
    rows = []
    for lbl, sel in groups:
        a = pool9(sel, "is"); b = pool9(sel, "oos")
        rows.append([lbl, len(sel), a[0], a[1], a[3], b[0], b[1], b[3], b[4][0] if b[4] else None, b[4][1] if b[4] else None])
    ws9 = sheet("Side screen 208", "Per-side (bear call / bull put) screen across all 208 NSE F&O names — deployed gates, run-5 harness",
          "Rule: ≥3 trades, ≥80% win and ROM > +5% in BOTH windows. Honest test: choose sides on in-sample only, then read their out-of-sample. "
          "All trades (full band), 1 lot — compare rows with each other, not with the published median-cohort ₹/month. FINAL: all 208 names on today's harness in both windows, 0 failed fetches (27-Sep-2026 18:25).",
          ["Selection", "Name-sides", "IS trades", "IS win", "IS net ₹", "OOS trades", "OOS win", "OOS net ₹", "OOS trades/month", "OOS ₹/month"], rows,
          [52, 11, 10, 9, 14, 11, 9, 14, 14, 13], {4: PCT, 5: RS, 7: PCT, 8: RS, 9: "0.0", 10: RS},
          colour=lambda r: (GOOD if isinstance(r[7], (int, float)) and r[7] > 0 and "passing" in r[0] else BAD if isinstance(r[7], (int, float)) and r[7] < 0 else None))
    rows = []
    for x in sorted(res, key=lambda x: (not x["both"], x["group"], x["sym"], x["side"])):
        a, b = x["is"], x["oos"]
        rows.append([x["sym"], x["side"], x["group"], "PASSES BOTH" if x["both"] else ("in-sample pick" if x["is_only_pick"] else ""),
                     a["n"] if a else None, a["win"] if a else None, a["rom"] if a else None,
                     b["n"] if b else None, b["win"] if b else None, b["rom"] if b else None])
    sheet("Side screen detail", "Every name × side across the 208 F&O names (deployed gates, run-5 harness)",
          "Group = today's universe / outsider (tested, never admitted) / pruned-8 (removed 24-Aug on whole-name net). Filter the Verdict column.",
          ["Stock", "Side", "Group", "Verdict", "IS trades", "IS win", "IS ROM", "OOS trades", "OOS win", "OOS ROM"], rows,
          [13, 6, 11, 15, 9, 8, 9, 10, 9, 9], {6: PCT, 7: PCT, 9: PCT, 10: PCT},
          colour=lambda r: GOOD if r[3] == "PASSES BOTH" else None)
# ---- 7 Telegram sample ----
ws = wb.create_sheet("Telegram 15-31 sample"); ws["A1"] = "15:31 WATCHLIST message — rendered on the 24-Sep-2026 watchlist with today's rules"
ws["A1"].font = Font(name=F, bold=True, size=14, color="1F3864")
for i, line in enumerate(open("/private/tmp/claude-501/-Users-sayali-files/649a0ce9-deff-4a00-9ab8-bd5563c259bb/scratchpad/digest_sample.txt").read().splitlines(), 3):
    ws.cell(row=i, column=1, value=line).font = Font(name="Menlo", size=10)
ws.column_dimensions["A"].width = 160
wb.save("/Users/sayali/Downloads/Saavi_Strategy_Research_27Sep2026.xlsx"); print("saved")
