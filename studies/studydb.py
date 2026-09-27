"""Study database (user, 27-Sep-2026): every study write-up, every published result table and every
backtest trade row in one SQLite file, data/studies.db, so any study can be retrieved later.

  python studies/studydb.py build            rebuild everything from studies/ and research/
  python studies/studydb.py list             list studies
  python studies/studydb.py show SLUG        print a study's text
  python studies/studydb.py tables [SLUG]    list result tables
  python studies/studydb.py sql "SELECT ..." run a query

Tables: studies(slug, title, updated, path, text) · result_tables(slug, name, row_no, row_json) ·
trades(source, run, window, book, sym, side, day, cw, win, net, margin, net_rs, margin_rs, lot)."""
import sqlite3, json, glob, os, sys, csv, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "studies.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS studies (slug TEXT PRIMARY KEY, title TEXT, updated TEXT, path TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS result_tables (slug TEXT, name TEXT, row_no INTEGER, row_json TEXT);
CREATE TABLE IF NOT EXISTS trades (source TEXT, run TEXT, window TEXT, book TEXT, sym TEXT, side TEXT, day TEXT,
    cw REAL, win INTEGER, net REAL, margin REAL, net_rs REAL, margin_rs REAL, lot INTEGER);
CREATE INDEX IF NOT EXISTS ix_tr ON trades(source, book, sym, side, window);
CREATE INDEX IF NOT EXISTS ix_rt ON result_tables(slug, name);
"""
def conn():
    c = sqlite3.connect(DB); c.executescript(SCHEMA); return c
def add_docs(c):
    n = 0
    for p in sorted(glob.glob(os.path.join(ROOT, "studies", "*.md"))):
        text = open(p, encoding="utf-8").read()
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("#")), os.path.basename(p))
        c.execute("INSERT OR REPLACE INTO studies VALUES (?,?,?,?,?)", (os.path.basename(p)[:-3], title,
                  datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds"), os.path.relpath(p, ROOT), text)); n += 1
    return n
def add_table(c, slug, name, rows):
    c.execute("DELETE FROM result_tables WHERE slug=? AND name=?", (slug, name))
    c.executemany("INSERT INTO result_tables VALUES (?,?,?,?)", [(slug, name, i, json.dumps(r, default=str)) for i, r in enumerate(rows)])
def add_trades(c, source, run, window, path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p): return 0
    rows = json.load(open(p))
    c.execute("DELETE FROM trades WHERE source=?", (source,))
    c.executemany("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(source, run, window, r.get("book"), r.get("sym"), r.get("side"),
                  r.get("day"), r.get("cw"), r.get("win"), r.get("net"), r.get("margin"), r.get("net_rs"), r.get("margin_rs"), r.get("lot")) for r in rows])
    return len(rows)
TRADE_SOURCES = [  # source, run, window, file
    ("run5_is_main", "run5", "IS", "research/deployed_bt_is_rows_run5.json"),
    ("run5_oos", "run5", "OOS", "research/deployed_bt_oos_rows_run5.json"),
    ("run5_is_expansion", "run5", "IS", "research/expansion2/is_rows.json"),
    ("run4_is_main", "run4", "IS", "research/deployed_bt_is_rows_run4.json"),
    ("run4_oos", "run4", "OOS", "research/deployed_bt_oos_rows_run4.json"),
    ("run4_is_expansion", "run4", "IS", "research/expansion2/is_rows_run4.json"),
    ("outsiders_oos", "expansion2", "OOS", "research/expansion2/oos_rows.json"),
    ("pruned8_is", "run5", "IS", "research/pruned8_is_rows.json"),
    ("pruned8_oos", "run5", "OOS", "research/pruned8_oos_rows.json"),
    *[(f"premfloor_{w}_{p}", "premfloor", w.upper(), f"research/premfloor_{w}_{p}_rows.json") for w in ("is", "oos") for p in (10, 20, 30)],
    *[(f"prem30_band30_{w}_{p}", "prem30", w.upper(), f"research/prem30_{w}_{p}_rows.json") for w in ("is", "oos") for p in (30, 50)],
    *[(f"band25_{w}_floor50", "band25", w.upper(), f"research/band25_{w}_rows_all.json") for w in ("is", "oos")],
    *[(f"band25_{w}_floor30", "premband25", w.upper(), f"research/premband25_{w}_30_rows.json") for w in ("is", "oos")],
]
def build():
    c = conn()
    print(f"studies: {add_docs(c)} documents")
    tot = 0
    for src, run, w, path in TRADE_SOURCES:
        n = add_trades(c, src, run, w, path); tot += n
        if n: print(f"  trades {src:24s} {n:6d}")
    print(f"trades: {tot} rows")
    for slug, name, path in (("PREMIUM_FLOOR_SWEEP", "run5_publish", "research/run5_publish.json"),
                             ("PREMIUM_FLOOR_SWEEP", "run5_is_published", "research/run5_is_published.json"),
                             ("PREMIUM_FLOOR_SWEEP", "band25_qualifiers", "research/premband25_qualifiers.json"),
                             ("SIDE_SCREEN_208", "side_screen", "research/side_screen_208.json")):
        p = os.path.join(ROOT, path)
        if os.path.exists(p):
            d = json.load(open(p)); rows = d if isinstance(d, list) else [{"key": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in d.items()]
            add_table(c, slug, name, rows); print(f"  table {slug}/{name}: {len(rows)} rows")
    p = os.path.join(ROOT, "studies", "BOOK_SIDE_HISTORY.csv")
    if os.path.exists(p):
        rows = list(csv.DictReader(open(p))); add_table(c, "BOOK_SIDE_HISTORY", "per_stock_book_side", rows); print(f"  table BOOK_SIDE_HISTORY: {len(rows)} rows")
    c.commit(); c.close(); print(f"-> {DB}")
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "build": build(); sys.exit()
    c = conn()
    if cmd == "list":
        for s, t, u in c.execute("SELECT slug, title, updated FROM studies ORDER BY updated DESC"): print(f"{u[:10]}  {s:40s} {t[:70]}")
    elif cmd == "show": print(c.execute("SELECT text FROM studies WHERE slug=?", (sys.argv[2],)).fetchone()[0])
    elif cmd == "tables":
        q = "SELECT slug, name, COUNT(*) FROM result_tables" + (" WHERE slug=?" if len(sys.argv) > 2 else "") + " GROUP BY slug, name"
        for r in c.execute(q, tuple(sys.argv[2:3])): print(*r)
    elif cmd == "sql":
        for r in c.execute(sys.argv[2]): print(r)
