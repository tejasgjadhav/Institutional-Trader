"""Calculated Constituents — live server.

Serves the UI and a /live endpoint that, every poll, batch-fetches LTPs for all NIFTY-50 (NSE)
and SENSEX-30 (BSE) constituents plus both index LTPs, computes the reconstructed index with
least-squares weights, and returns live-vs-calculated.

Weights: fit at startup from the most recent session's 1-min data (fit window 09:20-15:09).
The fit day is reported in every /live response; POST /refit re-fits (e.g. mid-morning once
today has enough bars). Binds the port immediately and warms in a background thread.

Run:  cd ~/files/institutional-trader && ./.venv/bin/python studies/CAS_NIFTY_SENSEX_DATA/live_calc_server.py
UI:   http://localhost:8787
"""
import os, sys, json, threading
from datetime import date, datetime, timedelta

PROJECT = os.path.expanduser("~/files/institutional-trader")
HERE = os.path.join(PROJECT, "studies", "CAS_NIFTY_SENSEX_DATA")
os.chdir(PROJECT)                      # engine config resolves .env relative to the repo
sys.path.insert(0, PROJECT)

import numpy as np
import pandas as pd
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine.config import IST
from engine.data_fetcher import fetch_upstox_historical, fetch_upstox_intraday, fetch_ltp_batch
from engine.instruments import to_instrument_key

PORT = 8787
BKEY = json.load(open(os.path.join(HERE, "bse_keys.json")))

SENSEX30 = """ADANIPORTS ASIANPAINT AXISBANK BAJFINANCE BAJAJFINSV BEL BHARTIARTL ETERNAL
HCLTECH HDFCBANK HINDUNILVR ICICIBANK INDIGO INFY ITC KOTAKBANK LT M&M MARUTI NTPC
POWERGRID RELIANCE SBIN SUNPHARMA TCS TATASTEEL TECHM TITAN TRENT ULTRACEMCO""".split()
NIFTY50 = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE
BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH
HDFCBANK HDFCLIFE HINDALCO HINDUNILVR ICICIBANK INDIGO INFY ITC JIOFIN JSWSTEEL
KOTAKBANK LT M&M MARUTI MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE
SHRIRAMFIN SBIN SUNPHARMA TCS TATACONSUM TMPV TATASTEEL TECHM TITAN TRENT ULTRACEMCO
WIPRO""".split()

CFG = {"SENSEX": (SENSEX30, lambda s: BKEY.get(s), "BSE_INDEX|SENSEX"),
       "NIFTY": (NIFTY50, to_instrument_key, "NSE_INDEX|Nifty 50")}

STATE = {"status": "warming", "fit_day": None, "weights": {}}   # idx -> (keys[], w[])


def _minutes(key, day):
    """1-min bars for one day. Today MUST come from the intraday endpoint — the 1-min
    historical feed lags about a session (verified 6-Aug: no 5-Aug 1-min on the morning after)."""
    if day == datetime.now(IST).date():
        return fetch_upstox_intraday(key, interval=1)
    m = fetch_upstox_historical(key, unit="minutes", interval=1,
                                from_date=day.isoformat(),
                                to_date=(day + timedelta(days=1)).isoformat())
    return m[m.index.date == day] if not m.empty else m


def _fit_one(name, members, keyfn, idx_key, day):
    px = {}
    for s in members:
        k = keyfn(s)
        if not k:
            continue
        m = _minutes(k, day)
        if not m.empty:
            px[(s, k)] = m.Close
    im = _minutes(idx_key, day)
    if im.empty or len(px) < len(members) - 2:
        return None
    P = pd.DataFrame({sk: v for sk, v in px.items()}).dropna()
    y = im.Close.reindex(P.index).dropna()
    P = P.reindex(y.index)
    mins = P.index.hour * 60 + P.index.minute
    m = (mins >= 9 * 60 + 20) & (mins <= 15 * 60 + 9)
    if m.sum() < 60:
        m = mins >= 9 * 60 + 20          # partial session (intraday refit)
    if m.sum() < 30:
        return None
    w, *_ = np.linalg.lstsq(P[m].values, y[m].values, rcond=None)
    resid = P[m].values @ w - y[m].values
    return {"keys": [k for _, k in P.columns], "syms": [s for s, _ in P.columns],
            "w": w.tolist(), "rmse": float(np.sqrt((resid ** 2).mean())), "n": int(m.sum())}


def fit_weights():
    d = datetime.now(IST).date()
    for back in range(6):
        day = d - timedelta(days=back)
        if day.weekday() >= 5:
            continue
        got = {}
        for name, (mem, kf, ik) in CFG.items():
            r = _fit_one(name, mem, kf, ik, day)
            if r:
                got[name] = r
        if len(got) == 2:
            STATE["weights"] = got
            STATE["fit_day"] = day.isoformat()
            STATE["status"] = "ok"
            print(f"[fit] day={day} " + " ".join(
                f"{n}: rmse {got[n]['rmse']:.2f} on {got[n]['n']} bars" for n in got), flush=True)
            return
    STATE["status"] = "fit-failed"


def live_snapshot():
    if STATE["status"] != "ok":
        return {"status": STATE["status"]}
    keys = ["NSE_INDEX|Nifty 50", "BSE_INDEX|SENSEX"]
    for n in STATE["weights"]:
        keys += STATE["weights"][n]["keys"]
    ltp = fetch_ltp_batch(keys)
    now = datetime.now(IST)
    rows = []
    for name, ik in (("SENSEX", "BSE_INDEX|SENSEX"), ("NIFTY", "NSE_INDEX|Nifty 50")):
        wrec = STATE["weights"][name]
        missing = [s for s, k in zip(wrec["syms"], wrec["keys"]) if k not in ltp]
        pv = np.array([ltp.get(k, np.nan) for k in wrec["keys"]])
        w = np.array(wrec["w"])
        ok = ~np.isnan(pv)
        calc = float(pv[ok] @ w[ok]) if ok.all() else (float(np.nansum(pv * w)) if ok.sum() >= len(w) - 2 else None)
        live = ltp.get(ik)
        rows.append({"idx": name, "live": live, "calc": round(calc, 2) if calc else None,
                     "diff": round(live - calc, 2) if (live and calc) else None,
                     "diff_pct": round(100 * (live - calc) / calc, 4) if (live and calc) else None,
                     "missing": missing})
    mkt = (now.weekday() < 5 and (9, 15) <= (now.hour, now.minute) <= (15, 40))
    return {"status": "ok", "fit_day": STATE["fit_day"], "ts": now.strftime("%H:%M:%S"),
            "market_open": mkt, "rows": rows}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "calculated_constituents.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/replay":
            p = os.path.join(HERE, "replay_days.json")
            if os.path.exists(p):
                with open(p, "rb") as f:
                    self._send(200, f.read())
            else:
                self._send(404, "{}")
        elif self.path == "/summary":
            try:
                import sqlite3
                conn = sqlite3.connect(os.path.join(PROJECT, "data", "engine.db"), timeout=5)
                cur = conn.execute(
                    "SELECT date, idx, print_1515, calc_1515, calc_1518, official_close, "
                    "auction_gap, fit_rmse, recorded_at FROM cas_calc_vs_print ORDER BY date, idx")
                cols = [c[0] for c in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                conn.close()
                self._send(200, json.dumps({"status": "ok", "rows": rows}))
            except Exception as e:
                self._send(500, json.dumps({"status": "error", "error": str(e)}))
        elif self.path == "/live":
            try:
                self._send(200, json.dumps(live_snapshot()))
            except Exception as e:
                self._send(500, json.dumps({"status": "error", "error": str(e)}))
        else:
            self._send(404, "{}")

    def do_POST(self):
        if self.path == "/refit":
            threading.Thread(target=fit_weights, daemon=True).start()
            self._send(200, json.dumps({"status": "refitting"}))
        else:
            self._send(404, "{}")

    def log_message(self, *a):
        pass


def race_logger():
    """WHO PRINTS FIRST at the auction — the exchange index or our constituent calc?
    1-min bars can't resolve it, so during 15:26-15:34 sample /live once a second and append
    to race_log.jsonl. After the close, the file shows second-by-second which side moved off
    the frozen level first and by how much."""
    import time
    path = os.path.join(HERE, "race_log.jsonl")
    while True:
        now = datetime.now(IST)
        in_window = now.weekday() < 5 and (15, 26) <= (now.hour, now.minute) <= (15, 34)
        if in_window and STATE["status"] == "ok":
            try:
                snap = live_snapshot()
                with open(path, "a") as f:
                    f.write(json.dumps({"ts": datetime.now(IST).isoformat(timespec="milliseconds"),
                                        "rows": snap.get("rows")}) + "\n")
            except Exception as e:
                print(f"[race] {e}", flush=True)
            time.sleep(1)
        else:
            time.sleep(20)


def auto_refit():
    """Refit every 30 min during market hours so live weights come from TODAY's session,
    not yesterday's. Measured 6-Aug ~12:00: yesterday-weights diff −1.31 pts, today-weights
    −0.30 pts — the refit removes ~75% of the live error."""
    import time
    while True:
        time.sleep(1800)
        now = datetime.now(IST)
        if now.weekday() < 5 and (9, 50) <= (now.hour, now.minute) <= (15, 45):
            try:
                fit_weights()
            except Exception as e:
                print(f"[auto-refit] failed: {e}", flush=True)


if __name__ == "__main__":
    threading.Thread(target=fit_weights, daemon=True).start()
    threading.Thread(target=auto_refit, daemon=True).start()
    threading.Thread(target=race_logger, daemon=True).start()
    print(f"Calculated Constituents server on http://localhost:{PORT} (warming weights…)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
