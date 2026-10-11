"""Offline test of the bull-put sub-floor (11-Oct-2026): v1 and v0 bull puts below the Rs30 floor are
taken when short >= Rs10 and credit x lot >= Rs3,000; bear calls, v2 and vlc keep their floors; the
switch off restores the old behaviour exactly. No network. Run: .venv/bin/python studies/ndte/test_bp_subfloor.py"""
import sys, os, json, shutil, sqlite3, tempfile
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import engine.config as C
import engine.data_fetcher as DF
import engine.data_utils as DU
import engine.forward_record as FR
import engine.stock_credit_v2 as V2
import engine.stock_credit_v0 as V0W
import engine.stock_credit_vlc as VLCW
import engine.stock_credit as V1
V0, VLC = V0W._impl, VLCW._impl
TODAY = date.today()
FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got {got!r}, want {want!r}"))
    if not ok:
        FAILED.append(name)


def _no_net(*a, **k):
    raise RuntimeError("network call in an offline test")
for _m in (DF, V2, V0, VLC, V1):
    for _f in ("fetch_upstox_quote", "fetch_upstox_ltp", "fetch_upstox_historical",
               "fetch_upstox_intraday", "get_cached_ltp"):
        if hasattr(_m, _f):
            setattr(_m, _f, _no_net)
DU.market_is_trading_today = lambda: True
DU.recent_entry_symbols = lambda gap_days=None: frozenset()


def spec(bk, s, l, lot=1100, width=15):
    return dict(bk=bk, s=s, l=l, lot=lot, width=width)


def install(M, names, is_v1=False):
    def tb(t):
        sp = names[t.replace(".NS", "")]
        return sp["bk"] if is_v1 else (sp["bk"], 10, 999.0, "intraday")
    def pick(t, spot, opt):
        sym = t.replace(".NS", ""); sp = names[sym]; k0 = 1000.0
        k1 = k0 + sp["width"] if opt == "CE" else k0 - sp["width"]
        return ({"key": f"{sym}|S", "strike": k0, "lot": sp["lot"]},
                {"key": f"{sym}|L", "strike": k1, "lot": sp["lot"]}, (TODAY + timedelta(days=20)).isoformat())
    def quote(key):
        sym, leg = key.split("|")
        return names[sym]["s" if leg == "S" else "l"]
    M._todays_breakout, M._spot, M._pick_legs, M._quote = tb, (lambda t: 1000.0), pick, quote
    M.UNIVERSE = [f"{n}.NS" for n in names]
    M.STOCK_CREDIT_ENABLED = True
    M.STOCK_CREDIT_MAX_OPEN, M.STOCK_CREDIT_MAX_NEW_PER_DAY = 20, 10
    M._save_snapshot = lambda: None


def run(M, names, is_v1=False, run_fn=None):
    d = tempfile.mkdtemp(prefix="bptest_")
    FR.DB = os.path.join(d, "forward_record.db")
    os.makedirs(os.path.join(d, "watchlist_archive"))
    json.dump({"rows": []}, open(os.path.join(d, "watchlist_archive", f"{TODAY.isoformat()}.json"), "w"))
    M.BOOK_PATH = os.path.join(d, "book.json"); M.SNAP_PATH = os.path.join(d, "snap.json")
    M.WATCHLIST_ARCHIVE_DIR = os.path.join(d, "watchlist_archive")
    json.dump([], open(M.BOOK_PATH, "w"))
    if is_v1:
        M.DATA_DIR = d
    V0W.DATA_DIR = d
    install(M, names, is_v1)
    new = (run_fn or M.scan_signals)()
    c = sqlite3.connect(FR.DB); c.executescript(FR.SCHEMA)
    rej = {r[0]: (r[1], r[2]) for r in c.execute("SELECT symbol, reason, detail FROM rejections")}
    bb = open(M.BOOK_PATH, "rb").read()
    shutil.rmtree(d, ignore_errors=True)
    return {p["symbol"]: p for p in new}, rej, bb


# Width 15 (Rs5 strike step, 3 strikes), HDFCLIFE-like. Quotes are (mid, bid, ask, oi).
V1NAMES = {
    "BPOK":  spec("SHORT", (13.1, 13.0, 13.2, 500), (6.9, 6.85, 6.95, 500)),             # c/w 0.413, 6,820/lot
    "BPLOT": spec("SHORT", (13.1, 13.0, 13.2, 500), (6.9, 6.85, 6.95, 500), lot=300),    # 1,860/lot
    "BP8":   spec("SHORT", (8.0, 7.95, 8.05, 500), (1.8, 1.75, 1.85, 500)),              # short < Rs10
    "BC13":  spec("LONG",  (13.1, 13.0, 13.2, 500), (6.9, 6.85, 6.95, 500)),             # bear call
    "BP35":  spec("SHORT", (35.0, 34.8, 35.2, 500), (28.8, 28.6, 29.0, 500)),            # above the floor anyway
}
V0NAMES = {  # v0 band c/w 0.35-0.40
    "V0BP":  spec("SHORT", (13.0, 12.95, 13.05, 500), (7.5, 7.45, 7.55, 500)),           # c/w 0.367, 6,050/lot
    "V0BC":  spec("LONG",  (13.0, 12.95, 13.05, 500), (7.5, 7.45, 7.55, 500)),
}
V2NAMES = {"V2BP": spec("SHORT", (13.1, 13.0, 13.2, 500), (6.9, 6.85, 6.95, 500))}       # c/w 0.413

print("switch ON")
C.STOCK_CREDIT_BP_SUBFLOOR_ENABLED = True
op, rj, _ = run(V1, V1NAMES, is_v1=True)
check("v1 opens BPOK and BP35", sorted(op), ["BP35", "BPOK"])
check("v1 BPOK tagged floor_rule=bp_subfloor", op.get("BPOK", {}).get("floor_rule"), "bp_subfloor")
check("v1 BP35 (above floor) not tagged", op.get("BP35", {}).get("floor_rule"), None)
check("v1 BPLOT rejected prem_below", rj.get("BPLOT", ("",))[0], "prem_below")
check("v1 BPLOT detail names the per-lot clause", "credit x lot" in rj.get("BPLOT", ("", ""))[1], True)
check("v1 BP8 rejected prem_below (short < Rs10)", (rj.get("BP8", ("",))[0], "below Rs10" in rj.get("BP8", ("", ""))[1]), ("prem_below", True))
check("v1 BC13 (bear call) rejected prem_below, no sub-floor text", (rj.get("BC13", ("",))[0], "sub-floor" in rj.get("BC13", ("", ""))[1]), ("prem_below", False))

op, rj, _ = run(V0, V0NAMES, run_fn=V0W.scan_signals)
check("v0 opens the bull put only", sorted(op), ["V0BP"])
check("v0 V0BP tagged", op.get("V0BP", {}).get("floor_rule"), "bp_subfloor")
check("v0 bear call rejected prem_below", rj.get("V0BC", ("",))[0], "prem_below")

op, rj, _ = run(V2, V2NAMES)
check("v2 keeps its Rs50 floor for bull puts", (sorted(op), rj.get("V2BP", ("",))[0]), ([], "prem_below"))

VLC.SIDE_WHITELIST = {"BEAR_CALL": frozenset(), "BULL_PUT": frozenset({"VLBP"})}
VLC.CELL_BANDS = {}
op, rj, _ = run(VLC, {"VLBP": spec("SHORT", (13.0, 12.95, 13.05, 500), (7.5, 7.45, 7.55, 500))}, run_fn=VLCW.scan_signals)
check("vlc keeps its floor for bull puts", (sorted(op), rj.get("VLBP", ("",))[0]), ([], "prem_below"))

print("digest / watchlist premium tick")
check("v0-band bull put at Rs13, Rs6,050/lot shows prem ok, floor 10", V2.prem_check("X", "BULL_PUT", 0.367, 13.0, 5.5, 1100), (True, 10.0))
check("v0-band bear call at Rs13 still crossed", V2.prem_check("X", "BEAR_CALL", 0.367, 13.0, 5.5, 1100)[0], False)
check("v2-band bull put at Rs13 still crossed (v2 floor)", V2.prem_check("X", "BULL_PUT", 0.42, 13.0, 6.3, 1100)[0], False)
check("bp_subfloor rejects credit x lot < 3000", V2.bp_subfloor("BULL_PUT", 13.0, 5.5, 300)[0], False)

print("switch OFF (old behaviour)")
C.STOCK_CREDIT_BP_SUBFLOOR_ENABLED = False
op, rj, bb_off = run(V1, V1NAMES, is_v1=True)
check("v1 opens only BP35 with the switch off", sorted(op), ["BP35"])
check("v1 BPOK detail has no sub-floor text when off", "sub-floor" in rj.get("BPOK", ("", ""))[1], False)
op, rj, _ = run(V0, V0NAMES, run_fn=V0W.scan_signals)
check("v0 opens nothing with the switch off", sorted(op), [])
check("digest crosses the v0 bull put with the switch off", V2.prem_check("X", "BULL_PUT", 0.367, 13.0, 5.5, 1100)[0], False)
C.STOCK_CREDIT_BP_SUBFLOOR_ENABLED = True

print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
