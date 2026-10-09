"""Offline tests for the 15:36 rejection record (9-Oct-2026). Runs in seconds, touches no network.

WHAT IT LOCKS. The four stock books (v2, v0, vlc share stock_credit_v2.py; v1 is stock_credit.py)
write one forward-record row per breakout name they do not open, with a reason code. This drives
every exit path of each book's scan_signals() with stubbed data and checks:
  (a) the right reason row lands in a TEMPORARY forward-record DB,
  (b) the opened positions and the saved book file are byte-identical with recording on and off,
  (c) a recorder that raises changes nothing and only logs a WARNING,
  (d) a re-run of the scan on the same day writes no second row for a name.

Run:  .venv/bin/python studies/ndte/test_rejections.py
"""
import sys, os, json, shutil, sqlite3, tempfile, logging
from datetime import date, timedelta
sys.path.insert(0, "/Users/sayali/files/institutional-trader")

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


# ── no network, anywhere ─────────────────────────────────────────────────────
def _no_net(*a, **k):
    raise RuntimeError("network call in an offline test")
for _m in (DF, V2, V0, VLC, V1):
    for _f in ("fetch_upstox_quote", "fetch_upstox_ltp", "fetch_upstox_historical",
               "fetch_upstox_intraday", "get_cached_ltp"):
        if hasattr(_m, _f):
            setattr(_m, _f, _no_net)
DU.market_is_trading_today = lambda: True

# ── log capture ──────────────────────────────────────────────────────────────
class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG); self.recs = []
    def emit(self, r):
        self.recs.append((r.levelno, r.getMessage()))
CAP = _Cap()
logging.getLogger().addHandler(CAP)
logging.getLogger().setLevel(logging.INFO)


# ── scenario plumbing ────────────────────────────────────────────────────────
# A name's spec: bk = breakout (direction, or None), spot, legs (None = no strikes), short/long
# quotes as (mid, bid, ask, oi), lot, raise_legs = make _pick_legs raise.
def spec(bk="LONG", spot=1000.0, legs=True, s=(60.0, 59.0, 61.0, 500), l=(40.0, 39.0, 41.0, 500),
         lot=100, width=40, raise_legs=False, dc=10):
    return dict(bk=bk, spot=spot, legs=legs, s=s, l=l, lot=lot, width=width,
                raise_legs=raise_legs, dc=dc)


def install(M, names, is_v1=False):
    """Point module instance M at stubbed data for `names` {sym: spec}."""
    def tb(ticker):
        sp = names[ticker.replace(".NS", "")]
        if not sp["bk"]:
            return None
        return sp["bk"] if is_v1 else (sp["bk"], sp["dc"], 999.0, "intraday")
    def spot(ticker):
        return names[ticker.replace(".NS", "")]["spot"]
    def pick(ticker, spot, opt):
        sym = ticker.replace(".NS", "")
        sp = names[sym]
        if sp["raise_legs"]:
            raise ValueError("boom in legs")
        if not sp["legs"]:
            return None
        k0 = 1000.0
        k1 = k0 + sp["width"] if opt == "CE" else k0 - sp["width"]
        return ({"key": f"{sym}|S", "strike": k0, "lot": sp["lot"]},
                {"key": f"{sym}|L", "strike": k1, "lot": sp["lot"]}, (TODAY + timedelta(days=20)).isoformat())
    def quote(key):
        sym, leg = key.split("|")
        q = names[sym]["s" if leg == "S" else "l"]
        return q
    M._todays_breakout, M._spot, M._pick_legs, M._quote = tb, spot, pick, quote
    M.UNIVERSE = [f"{n}.NS" for n in names]
    M.STOCK_CREDIT_ENABLED = True
    M._save_snapshot = lambda: None


def fresh_dir(book_rows=None, v1_rows=None, v2_rows=None, watch=None, M=None):
    """New temp DATA dir + DB for one run. Returns the dir."""
    d = tempfile.mkdtemp(prefix="rejtest_")
    FR.DB = os.path.join(d, "forward_record.db")
    os.makedirs(os.path.join(d, "watchlist_archive"))
    with open(os.path.join(d, "watchlist_archive", f"{TODAY.isoformat()}.json"), "w") as f:
        json.dump({"rows": watch or []}, f)
    for fn, rows in (("stock_credit_positions.json", v1_rows),
                     ("stock_credit_v2_positions.json", v2_rows)):
        if rows is not None:
            json.dump(rows, open(os.path.join(d, fn), "w"))
    return d


def bind(M, d, book_rows, is_v1=False):
    M.BOOK_PATH = os.path.join(d, "book.json")
    M.SNAP_PATH = os.path.join(d, "snap.json")
    M.WATCHLIST_ARCHIVE_DIR = os.path.join(d, "watchlist_archive")
    if book_rows is not None:
        json.dump(book_rows, open(M.BOOK_PATH, "w"))
    if is_v1:
        M.DATA_DIR = d                     # where v1 reads v2's book for the defer rule
    V0W.DATA_DIR = d                       # where v0 reads v1's book for the clash rule


def rows(d):
    c = sqlite3.connect(os.path.join(d, "forward_record.db"))
    c.executescript(FR.SCHEMA)
    return {(r[0], r[1]): (r[2], r[3], r[4], r[5], r[6])
            for r in c.execute("SELECT book, symbol, reason, cw, premium, spread_pct, oi FROM rejections")}


def wl(sym, dc=10, cw=0.33, prem=55.0, spread=3.3, oi=400, d="LONG"):
    return {"sym": sym, "dir": d, "dc": dc, "cw": cw, "prem": prem, "spread": spread, "oi": oi}


def pos(sym, days_ago, status="OPEN"):
    ed = (TODAY - timedelta(days=days_ago)).isoformat()
    return {"id": f"{sym}-{ed}", "symbol": sym, "entry_date": ed, "status": status}


# ── the four books' scenarios ────────────────────────────────────────────────
SC = {}

SC["v2"] = dict(
    M=V2, run=V2.scan_signals, is_v1=False, caps=(20, 2), recent={"GAP", "GAPNOWL"},
    names={
        "OK1": spec(), "HELD": spec(), "GAP": spec(), "GAPNOWL": spec(), "NOBK": spec(bk=None),
        "NOSPOT": spec(spot=None), "NOLEGS": spec(legs=False),
        "NOQ": spec(s=(None, 0.0, 0.0, 0)), "ONESIDE": spec(s=(60.0, 0.0, 61.0, 500)),
        "CWLOW": spec(s=(52.0, 51.0, 53.0, 500), l=(40.0, 39.0, 41.0, 500)),       # c/w 0.30
        "PREMLOW": spec(s=(40.0, 39.5, 40.5, 500), l=(20.0, 19.5, 20.5, 500)),     # c/w 0.50, prem 40
        "SPREAD": spec(s=(60.0, 55.0, 65.0, 500)),                                 # 16.7%
        "OILOW": spec(s=(60.0, 59.0, 61.0, 0)),
        "NOLOT": spec(lot=0), "ERR": spec(raise_legs=True),
        "OK2": spec(), "CAPA": spec(), "CAPB": spec()},
    book=[pos("HELD", 10)],
    watch=[wl("HELD"), wl("GAP"), wl("CAPA")],
    want={"HELD": "held_open", "GAP": "reentry_gap", "NOSPOT": "no_spot", "NOLEGS": "no_legs",
          "NOQ": "no_quote", "ONESIDE": "no_quote", "CWLOW": "cw_below", "PREMLOW": "prem_below",
          "SPREAD": "spread_wide", "OILOW": "oi_low", "NOLOT": "no_lot", "ERR": "error",
          "CAPA": "cap_reached"},
    opened=["OK1", "OK2"])

SC["v0"] = dict(
    M=V0, run=V0W.scan_signals, is_v1=False, caps=(1, 5), recent=set(),
    names={"V0CLASH": spec(), "V0ABOVE": spec(),                                    # c/w 0.50
           "V0OK": spec(s=(55.0, 54.5, 55.5, 500), l=(40.0, 39.5, 40.5, 500)),     # c/w 0.375
           "V0OPENCAP": spec()},
    v1_rows=[pos("V0CLASH", 0)],
    book=[], watch=[wl("V0CLASH"), wl("V0OPENCAP")],
    want={"V0CLASH": "clash", "V0ABOVE": "cw_above", "V0OPENCAP": "cap_reached"},
    opened=["V0OK"])

SC["vlc"] = dict(
    M=VLC, run=VLCW.scan_signals, is_v1=False, caps=(20, 5), recent=set(),
    whitelist={"BEAR_CALL": frozenset({"VOK", "VABOVE"}), "BULL_PUT": frozenset()},
    cells={("VCELL", "BEAR_CALL"): {"min_cw": 0.25, "max_cw": 0.30, "min_prem": 30.0, "max_prem": 50.0},
           ("VCELLP", "BEAR_CALL"): {"min_cw": 0.25, "max_cw": 0.30, "min_prem": 30.0, "max_prem": 50.0},
           ("VCELLX", "BEAR_CALL"): {"min_cw": 0.25, "max_cw": 0.30, "min_prem": 30.0, "max_prem": 50.0}},
    names={"VSIDE": spec(),
           "VCELL": spec(s=(54.0, 53.5, 54.5, 500), l=(40.0, 39.5, 40.5, 500)),    # c/w 0.35 off band
           "VCELLP": spec(s=(21.0, 20.8, 21.2, 500), l=(10.0, 9.9, 10.1, 500)),    # c/w 0.275, prem 21
           "VCELLX": spec(s=(61.0, 60.5, 61.5, 500), l=(50.0, 49.5, 50.5, 500)),   # c/w 0.275, prem 61
           "VABOVE": spec(),                                                       # c/w 0.50
           "VOK": spec(s=(54.0, 53.5, 54.5, 500), l=(40.0, 39.5, 40.5, 500))},     # c/w 0.35
    book=[], watch=[],
    want={"VSIDE": "side_not_whitelisted", "VCELL": "cell_band", "VCELLP": "prem_below",
          "VCELLX": "cell_band", "VABOVE": "cw_above"},
    opened=["VOK"])

SC["v1"] = dict(
    M=V1, run=V1.scan_signals, is_v1=True, caps=(20, 5), recent=set(),
    names={"V1CLASH": spec(), "V1CLASH5": spec(), "V1HELD": spec(),
           "V1CW": spec(s=(52.0, 51.0, 53.0, 500), l=(40.0, 39.0, 41.0, 500)),
           "V1PREM": spec(s=(25.0, 24.8, 25.2, 500), l=(5.0, 4.9, 5.1, 500)),      # c/w 0.50, prem 25
           "V1OK": spec()},
    v2_rows=[pos("V1CLASH", 5), pos("V1CLASH5", 5)],
    book=[pos("V1HELD", 9)],
    watch=[wl("V1CLASH", dc=10), wl("V1CLASH5", dc=5), wl("V1HELD", dc=20)],
    want={"V1CLASH": "clash", "V1HELD": "held_open", "V1CW": "cw_below", "V1PREM": "prem_below"},
    opened=["V1OK"])


def run(book, record=True, sabotage=False, d=None, reset_book=True):
    s = SC[book]
    M = s["M"]
    if d is None:
        d = fresh_dir(watch=s["watch"], v1_rows=s.get("v1_rows"), v2_rows=s.get("v2_rows"))
    else:
        FR.DB = os.path.join(d, "forward_record.db")
    bind(M, d, s["book"] if reset_book else None, s["is_v1"])
    install(M, s["names"], s["is_v1"])
    M.STOCK_CREDIT_MAX_OPEN, M.STOCK_CREDIT_MAX_NEW_PER_DAY = s["caps"]
    if "whitelist" in s:
        M.SIDE_WHITELIST, M.CELL_BANDS = s["whitelist"], s["cells"]
    DU.recent_entry_symbols = lambda gap_days=None, _r=frozenset(s["recent"]): _r
    M.RECORD_REJECTIONS = record
    saved = (FR.record_rejections, FR.RejectionLog._put)
    if sabotage:
        def _boom(*a, **k):
            raise RuntimeError("sabotaged recorder")
        FR.record_rejections = _boom
        FR.RejectionLog._put = _boom
    CAP.recs.clear()
    try:
        new = s["run"]()
    finally:
        FR.record_rejections, FR.RejectionLog._put = saved
    book_bytes = open(M.BOOK_PATH, "rb").read() if os.path.exists(M.BOOK_PATH) else b""
    return d, new, book_bytes, list(CAP.recs)


for book in ("v2", "v0", "vlc", "v1"):
    s = SC[book]
    print(f"\n{book}")
    d, new, bb, logs = run(book, record=True)
    got = rows(d)
    check(f"{book} opened", sorted(p["symbol"] for p in new), sorted(s["opened"]))
    check(f"{book} rejection reasons", {sym: r[0] for (b, sym), r in got.items()}, s["want"])
    check(f"{book} every row is labelled {book}", {b for (b, _s) in got}, {book} if got else set())
    check(f"{book} opened names have no rejection row",
          [n for n in s["opened"] if (book, n) in got], [])
    info = [m for lv, m in logs if lv == logging.INFO and m.startswith(f"{book} rejections today:")]
    check(f"{book} one INFO tally line", len(info), 1)
    if info:
        print(f"        {info[0]}")
    check(f"{book} no recorder warnings", [m for lv, m in logs if lv >= logging.WARNING
                                           and "rejection record" in m], [])

    # (b) decisions identical with recording off
    d0, new0, bb0, _ = run(book, record=False)
    check(f"{book} (b) same positions with recording off",
          json.dumps(new0, sort_keys=True, default=str), json.dumps(new, sort_keys=True, default=str))
    check(f"{book} (b) same book file bytes with recording off", bb0, bb)
    check(f"{book} (b) recording off writes no rows", len(rows(d0)), 0)

    # (c) a raising recorder changes nothing and only warns
    d1, new1, bb1, logs1 = run(book, record=True, sabotage=True)
    check(f"{book} (c) same positions with a raising recorder",
          json.dumps(new1, sort_keys=True, default=str), json.dumps(new, sort_keys=True, default=str))
    check(f"{book} (c) same book file bytes with a raising recorder", bb1, bb)
    check(f"{book} (c) raising recorder logged a WARNING",
          any(lv == logging.WARNING and "rejection record" in m for lv, m in logs1), True)

    # (d) dedupe: re-run the same day on the same DB (book restored so decisions repeat)
    run(book, record=True, d=d)
    got2 = rows(d)
    c = sqlite3.connect(os.path.join(d, "forward_record.db"))
    dup = c.execute("""SELECT book, symbol, COUNT(*) FROM rejections
                       GROUP BY trade_date, book, symbol HAVING COUNT(*) > 1""").fetchall()
    check(f"{book} (d) re-run adds no rows", len(got2), len(got))
    check(f"{book} (d) one row per (day, book, symbol)", dup, [])
    for x in (d, d0, d1):
        shutil.rmtree(x, ignore_errors=True)

# numbers on a post-breakout row, and the v1/v2 geometry rule for watchlist numbers
print("\nnumbers")
d, *_ = run("v2", record=True)
r = rows(d)
check("v2 cw_below row carries c/w 0.30", r[("v2", "CWLOW")][1], 0.3)
check("v2 cw_below row carries short premium 52", r[("v2", "CWLOW")][2], 52.0)
check("v2 spread_wide row carries spread 16.67%", r[("v2", "SPREAD")][3], 16.67)
check("v2 oi_low row carries OI 0", r[("v2", "OILOW")][4], 0)
check("v2 held_open row carries the 15:31 watchlist c/w", r[("v2", "HELD")][1], 0.33)
shutil.rmtree(d, ignore_errors=True)
d, *_ = run("v1", record=True)
r = rows(d)
check("v1 pre-breakout row carries no v2-geometry numbers", r[("v1", "V1CLASH")][1:], (None, None, None, None))
check("v1 ignores a watchlist row that only broke D5", ("v1", "V1CLASH5") in r, False)
shutil.rmtree(d, ignore_errors=True)

# record_rejection (the single-row API) dedupes too
d = fresh_dir()
FR.record_rejection("v2", "XYZ", "cw_below", "a")
FR.record_rejection("v2", "XYZ", "spread_wide", "b")
FR.record_rejection("v1", "XYZ", "cw_below", "c")
check("record_rejection keeps first row per day/book/symbol", rows(d),
      {("v2", "XYZ"): ("cw_below", None, None, None, None), ("v1", "XYZ"): ("cw_below", None, None, None, None)})
shutil.rmtree(d, ignore_errors=True)

print(f"\n{'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED: {FAILED}'}")
sys.exit(1 if FAILED else 0)
