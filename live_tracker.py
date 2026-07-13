#!/usr/bin/env python3
"""LIVE-vs-MODEL tracker — answers "are the paper books hitting their backtest?" with REAL fills.

Reads every live book's position/trade log, computes realized win rate + net P&L, and prints them
next to each book's backtest MODEL so the ≥10%/month question is settled by data, not models.
Run weekly:  .venv/bin/python live_tracker.py   (add --json for machine output)

Books grouped as the user asked (2026-07-10): TIER A = the ≥80%-win books; TIER B = the
monthly-futures pair, kept separate.
"""
import os, json, sys
from datetime import date, datetime

DATA = os.path.join(os.path.dirname(__file__), "data")

# book -> (positions file, model win%, model ₹/mo at 1 lot, tier)
BOOKS = [
    ("Stock fade v2 UNION", "stock_credit_v2_positions.json", 88, 21500, "A"),
    ("NIFTY Tue 0DTE (FLIP)", "zero_dte_positions.json",        91, 2360,  "A"),
    ("SENSEX Thu 0DTE",       "sensex_dte_positions.json",      89, 3200,  "A"),
    ("BANKNIFTY mo 0DTE",     "bnf_dte_positions.json",         91, 820,   "A"),
    ("Stock credit v1 (control)", "stock_credit_positions.json", 73, 9000, "ctrl"),
    ("Monthly futures pullback", "monthly_fut_positions.json",   76, 43000,"B"),
]

def _pnl_rs(p):
    """Realised ₹ for a closed spread/credit position (pnl_pts × qty)."""
    pts = p.get("pnl_pts")
    qty = p.get("qty") or (p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1)
    if pts is None or not qty:
        return None
    return pts * qty

def load_book(fn):
    path = os.path.join(DATA, fn)
    if not os.path.exists(path):
        return []
    try:
        d = json.load(open(path))
    except Exception:
        return []
    return [p for p in d if isinstance(p, dict)] if isinstance(d, list) else []

def summarise(fn):
    book = load_book(fn)
    closed = [p for p in book if str(p.get("status", "")).upper() in ("WIN", "LOSS")]
    open_n = sum(1 for p in book if str(p.get("status", "")).upper() == "OPEN")
    if not closed:
        return dict(n=0, open=open_n, win=None, pnl=0.0, months=None, first=None, last=None)
    wins = sum(1 for p in closed if str(p["status"]).upper() == "WIN")
    pnl = sum(v for p in closed if (v := _pnl_rs(p)) is not None)
    dates = sorted(p.get("closed_date") or p.get("entry_date") or "" for p in closed)
    d0, d1 = dates[0][:10], dates[-1][:10]
    months = None
    try:
        a = datetime.fromisoformat(d0); b = datetime.fromisoformat(d1)
        months = max((b - a).days / 30.0, 1 / 30.0)
    except Exception:
        pass
    return dict(n=len(closed), open=open_n, win=100 * wins / len(closed), pnl=pnl,
                months=months, first=d0, last=d1)

def main():
    as_json = "--json" in sys.argv
    MIN_N = 10   # below this, a live ₹/mo extrapolation is noise — don't show it
    rows = []
    for name, fn, mwin, mpnl, tier in BOOKS:
        s = summarise(fn)
        # ONLY annualise to ₹/mo once the sample is meaningful; else show cumulative ₹ only
        live_pm = (s["pnl"] / s["months"]) if (s["months"] and s["n"] >= MIN_N) else None
        ratio = (live_pm / mpnl) if (live_pm is not None and mpnl) else None
        rows.append(dict(book=name, tier=tier, model_win=mwin, model_pm=mpnl, **s,
                         live_pm=live_pm, live_vs_model=ratio))
    if as_json:
        print(json.dumps(rows, indent=1, default=str)); return

    print(f"\nLIVE-vs-MODEL tracker — {date.today()}   (paper books; realised fills)\n" + "=" * 78)
    hdr = f"{'BOOK':26s} {'closed':>6} {'open':>4} {'liveWin':>7} {'modelWin':>8} {'cum₹':>9} {'live₹/mo':>9} {'model₹/mo':>9}"
    for tier, label in (("A", "TIER A — ≥80% win (priority group, ~₹2L)"),
                        ("ctrl", "control book"),
                        ("B", "TIER B — monthly futures pair (kept separate)")):
        print(f"\n{label}\n" + "-" * 82 + f"\n{hdr}")
        for r in rows:
            if r["tier"] != tier:
                continue
            lw = f"{r['win']:.0f}%" if r["win"] is not None else "—"
            cum = f"{r['pnl']:,.0f}" if r["n"] else "—"
            lpm = f"{r['live_pm']:,.0f}" if r["live_pm"] is not None else "n/a<10"
            print(f"{r['book']:26s} {r['n']:>6} {r['open']:>4} {lw:>7} "
                  f"{r['model_win']:>7}% {cum:>9} {lpm:>9} {r['model_pm']:>9,}")
    tA = [r for r in rows if r["tier"] == "A"]
    got = sum(r["n"] for r in tA)
    cum = sum(r["pnl"] for r in tA)
    model = sum(r["model_pm"] for r in tA)
    ready = all(r["n"] >= 10 for r in tA)
    print("\n" + "=" * 82)
    if got:
        print(f"TIER A so far: {got} closed trades · cumulative realised ₹{cum:,.0f}. "
              f"{'Sample OK — ₹/mo shown above.' if ready else 'STILL THIN — ₹/mo suppressed until ≥10 closed/book (~6-8 wks).'}")
    else:
        print("TIER A: no closed trades yet — the 10%/mo question needs ~6-8 weeks of fills to answer.")
    print(f"Model ≈ {model/2e5*100:.1f}%/mo on ₹2L; the 10%/mo bar = live net ≥ ₹20,000/mo. "
          f"Only realised fills decide it — re-run weekly.")
    print("=" * 82 + "\n")

if __name__ == "__main__":
    main()
