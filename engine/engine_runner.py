"""
Headless engine runner — the trading engine, decoupled from the GUI.

Runs the FULL daily schedule independent of whether the desktop app is open:
  - every 5 min during market hours: scan (3-Family stocks + ORB+VWAP indices),
    fire ready signals, record to the signal DB + daily engine DB, resolve paper trades;
  - at the 15:30 close (Mon-Fri): force-book every open paper trade;
  - every cycle: write a market snapshot + the latest scan to disk for the read-only UI.

Launched by launchd (com.sayali.institutionaltrader.engine). The GUI is a read-only
viewer of what this writes (data/latest_scan.json, data/market_snapshot.json, the DBs,
and trade_log.json). All data is saved locally daily; trade outcomes stay in trade_log.json.
"""
import os
import sys
import json
import time
import html
import logging
import subprocess
import threading
from datetime import datetime

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import IST, DATA_DIR, LOG_DIR
from engine.agent import Agent
from engine.paper_resolver import resolve_pending
from engine.data_utils import get_market_snapshot
from engine import signal_db, store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(os.path.join(LOG_DIR, "engine.log"))],
)
logger = logging.getLogger("engine_runner")

LATEST_SCAN = os.path.join(DATA_DIR, "latest_scan.json")
MARKET_SNAP = os.path.join(DATA_DIR, "market_snapshot.json")
SCAN_INTERVAL = 300   # 5 min — full 100-stock scan + fire new signals
TICK = 5              # wake every 5 s in market hours (tight scan timing + live bar)
RESOLVE_INTERVAL = 20 # resolve OPEN trades every 20 s (low-latency win/loss booking,
                      # decoupled from the 5-min scan; only runs while trades are open)


def _watchlist_mins() -> int:
    """config.WATCHLIST_AFTER as minutes-since-midnight. Was a bare `15 * 60 + 17` in two places."""
    from engine import config as _cfg
    h, m = map(int, _cfg.WATCHLIST_AFTER.split(":"))
    return h * 60 + m


class EngineRunner:
    def __init__(self):
        self.agent = Agent()
        self._last_scan = 0.0
        self._last_resolve = 0.0
        self._notified = set()
        self._notified_day = None
        self._caffeinate = None   # power assertion held while the market is open
        self._last_swing_resolve = 0.0
        self._swing_scan_day = None
        self._last_stockcr_resolve = 0.0
        self._csv_day = None
        self._stockcr_scan_day = None
        # SCAN SENTINEL (25-Aug-2026, user: "i want signals max by 15:37"). The main loop is
        # single-threaded and today it stalled on network retries straight through the
        # 15:36-15:40 window, so the day's scan never ran. This daemon thread does nothing all
        # day; from 15:36:20 it checks every 5s whether the scan has fired, and if the main loop
        # has not done it, it calls the SAME method itself. The once-a-day marker swap is atomic
        # under _scan_lock, so the two paths can never both scan. The signal therefore goes out
        # by ~15:37 even when the main loop is wedged inside a dead HTTP call.
        self._scan_lock = threading.Lock()
        threading.Thread(target=self._scan_sentinel, daemon=True).start()
        # PERSISTED ONCE-A-DAY MARKERS (26-Aug-2026). The markers were in-memory only, so ANY
        # restart reset them — the freeze-rule mechanism. Today it bit again in a new way: a 15:50
        # restart cleared the scan marker, the late-catch-up re-ran an already-done scan, found
        # nothing new (ULTRACEMCO was already held) and sent a spurious no-signal notice AFTER the
        # real EXECUTE message. Markers now load from disk at start and save on set.
        self._load_day_markers()
        self._watchlist_tg_day = None
        self._watchlist_build_day = None
        self._last_monthly_resolve = 0.0
        self._monthly_scan_day = None
        self._last_monthly_call_resolve = 0.0
        self._monthly_call_scan_day = None
        self._last_zdte_resolve = 0.0
        self._zdte_scan_day = None

    # ── persistence helpers ──────────────────────────────────────────────────
    @staticmethod
    def _write_json(path, obj):
        try:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(obj, f, default=str)
            os.replace(tmp, path)   # atomic — the UI never reads a half-written file
        except Exception as e:
            logger.warning(f"write {path}: {e}")

    def _market(self, now):
        try:
            from engine.data_utils import market_is_trading_today, _market_is_open
            snap = get_market_snapshot()
            trading = market_is_trading_today()
            holiday = _market_is_open() and not trading   # weekday + hours but no data = holiday
            self._write_json(MARKET_SNAP, {**snap, "ts": now.isoformat(),
                                           "trading": trading, "holiday": holiday})
            store.save_market(snap, now)
        except Exception as e:
            logger.warning(f"market snapshot: {e}")

    def _record_stock_db(self, ready, now):
        from engine.options import build_live_option_order
        from engine.data_fetcher import get_cached_ltp
        for s in ready:
            try:
                spot = get_cached_ltp(s["ticker"]) or 0
                order = build_live_option_order(s["ticker"], spot, s.get("direction", "LONG"))
                o = order or {}
                signal_db.record_signal(
                    time=now.strftime("%H:%M:%S"), strategy="3-Family",
                    symbol=s["ticker"].replace(".NS", ""), direction=s.get("direction"),
                    opt_type=o.get("instrument"), strike=o.get("strike"), expiry=o.get("expiry"),
                    entry_premium=o.get("premium"), target_premium=o.get("target_premium"),
                    stop_premium=o.get("stop_premium"), lot=o.get("lot_size"),
                    capital=o.get("capital"), alpha_z=s.get("alpha_z"),
                    breadth=s.get("breadth"), vol_ratio=s.get("vol_ratio"), status="OPEN")
            except Exception as e:
                logger.warning(f"signal_db stock {s.get('ticker')}: {e}")

    def _record_index_db(self):
        for s in (getattr(self.agent, "orbvwap_signals", []) or []):
            if not s.get("entry"):
                continue
            try:
                signal_db.record_signal(
                    time=s.get("time"), strategy="ORB+VWAP", symbol=s.get("index"),
                    direction=s.get("direction"), opt_type=s.get("kind"),
                    strike=s.get("strike"), expiry=s.get("expiry"),
                    entry_premium=s.get("entry"), target_premium=s.get("target"),
                    stop_premium=s.get("stop"), lot=s.get("lot"),
                    capital=s.get("capital"), status=s.get("status"))
            except Exception as e:
                logger.warning(f"signal_db index {s.get('index')}: {e}")

    # ── the work ─────────────────────────────────────────────────────────────
    def _scan(self, now):
        scored = self.agent.run_scan()   # stock scan + index ORB+VWAP; logs index trades
        self._write_json(LATEST_SCAN, {
            "ts": now.isoformat(),
            "results": scored,
            "orbvwap": getattr(self.agent, "orbvwap_signals", []),
        })
        store.save_scan(scored, now)

        if self._notified_day != now.date():        # reset the daily fired set
            self._notified_day = now.date()
            self._notified = set()

        if self.agent.is_trading_window():
            ready = [s for s in scored if s.get("trade_ready")]
            new = [s for s in ready if s.get("ticker") not in self._notified]
            for s in new:
                self._notified.add(s["ticker"])
            if new:
                try:
                    self.agent.execute_signals(new)      # -> trade_log + notifications
                except Exception as e:
                    logger.warning(f"execute_signals: {e}")
                self._record_stock_db(new, now)

        self._record_index_db()
        try:
            n = resolve_pending(self.agent.trade_log)    # close PENDING paper trades
            if n:
                logger.info(f"resolved {n} paper trade(s)")
        except Exception as e:
            logger.warning(f"resolve_pending: {e}")
        rdy = sum(1 for s in scored if s.get("trade_ready"))
        logger.info(f"scan done: {len(scored)} scored, {rdy} trade-ready")

    def _maybe_eod(self, now):
        """Force-book every open paper trade once its session is over.

        Runs EVERY cycle after the 15:30 close (and on weekends) and KEEPS RETRYING until
        nothing is left PENDING — so a transient data glitch at 15:30 can no longer orphan a
        trade in the log forever (that's exactly what stranded a BankNifty trade). The
        trade log is the critical record; no trade may be left unbooked once the day is done.
        """
        m = now.hour * 60 + now.minute
        from engine.config import FNO_CLOSE
        _fc = FNO_CLOSE.split(":")
        after_close = now.weekday() >= 5 or m >= int(_fc[0]) * 60 + int(_fc[1])
        if not after_close:
            return
        # The daily CSV snapshot of signals.db belongs to the ENGINE. It used to run in the viewer,
        # which made the read-only viewer a writer and broke the decoupling (audit 17-Aug-2026).
        if self._csv_day != now.date():
            self._csv_day = now.date()
            try:
                from engine import signal_db
                signal_db.export_csv()
            except Exception as e:
                logger.warning("daily signals CSV export failed: %s", e)
        pending = [t for t in self.agent.trade_log.trades if t.get("outcome") is None]
        if not pending:
            return
        logger.info(f"EOD booking — {len(pending)} open paper trade(s) pending; force-closing")
        try:
            resolve_pending(self.agent.trade_log)
            still = sum(1 for t in self.agent.trade_log.trades if t.get("outcome") is None)
            if still:
                logger.warning(f"EOD booking: {still} still pending — will retry next cycle")
            else:
                logger.info("EOD booking — all trades booked")
        except Exception as e:
            logger.warning(f"EOD booking: {e}")

    def _fast_resolve(self):
        """Low-latency win/loss booking: while any trade is OPEN, resolve every RESOLVE_INTERVAL
        seconds instead of waiting for the 5-min scan — so the trade log + PM DECISIONS update
        within ~20 s of a target/stop/EOD candle, not minutes. Cheap (only the open trades hit
        the API) and fully guarded so it can never crash the loop."""
        if not self.agent.is_market_open():
            return
        if (time.time() - self._last_resolve) < RESOLVE_INTERVAL:
            return
        if not any(t.get("outcome") is None for t in self.agent.trade_log.trades):
            return
        self._last_resolve = time.time()
        try:
            n = resolve_pending(self.agent.trade_log)
            if n:
                logger.info(f"fast-resolved {n} trade(s)")
        except Exception as e:
            logger.warning(f"fast resolve: {e}")

    # (target, stop) the backtest win% is CONDITIONED ON — stated on every signal so the win rate
    # is never read in isolation (user 2026-07-29: "the winrate is subject to target and stop loss").
    _TG_TGT_STOP = {"STOCK CREDIT v2 UNION": ("book at 50% of credit", "none — wing caps the loss"),
                    "STOCK CREDIT v0 (c/w 0.35-0.40)": ("book at 40% of credit", "none — wing caps the loss"),
                    "STOCK CREDIT v1": ("book 40% of credit", "none — wing caps the loss"),
                    "0DTE NIFTY": ("hold to same-day expiry", "none — bought wing caps the loss"),
                    "0DTE SENSEX": ("hold to same-day expiry", "none — bought wing caps the loss"),
                    "SWING CREDIT · multi-day (NIFTY/FINNIFTY)": ("hold to expiry", "2× credit"),
                    "MONTHLY FUTURES PULLBACK": ("+2% on close (→+1% late)", "−5% on close"),
                    "MONTHLY LONG-CALL PULLBACK": ("+2% on close (→+1% late)", "−5% on close")}

    # (take-profit fraction of credit, stop multiple of credit) per credit-spread book — used to
    # print the TARGET in ₹ and an HONEST stop. NB: with the c/w>=0.40 gate, 3x credit >= 1.2x width
    # and a vertical spread can never cost more than its width to close, so v2's 3x stop NEVER binds
    # (the real floor is the defined max loss). v1's 2x stop = 0.8x width DOES bind (user-caught 2026-07-29).
    _TG_EXIT = {"STOCK CREDIT v2 UNION": (0.50, 3.0),
                "STOCK CREDIT v0 (c/w 0.35-0.40)": (0.40, 99.0),
                "STOCK CREDIT v1": (0.40, 99.0),
                "SWING CREDIT · multi-day (NIFTY/FINNIFTY)": (0.0, 2.0)}

    def _tgt_stop(self, book):
        """(target, stop) for a book — tolerant of the SENSEX label variants passed to _tg()."""
        if book in self._TG_TGT_STOP:
            return self._TG_TGT_STOP[book]
        if book.startswith("SENSEX") or "SENSEX" in book:
            return self._TG_TGT_STOP["0DTE SENSEX"]
        if "NIFTY" in book and ("0DTE" in book or "INTRADAY" in book) and "BANKNIFTY" not in book:
            return self._TG_TGT_STOP["0DTE NIFTY"]
        return None
    # Books that HOLD to expiry (days→weeks) — the message must say so, or an index credit spread
    # entered days ago reads like a same-day 0DTE call (user-caught 2026-07-21). Same-day books
    # (0DTE NIFTY/SENSEX) are deliberately NOT in this set.
    _MULTIDAY_BOOKS = {"STOCK CREDIT v2 UNION", "STOCK CREDIT v1", "STOCK CREDIT v0 (c/w 0.35-0.40)",
                       "SWING CREDIT · multi-day (NIFTY/FINNIFTY)", "MONTHLY FUTURES PULLBACK",
                       "MONTHLY LONG-CALL PULLBACK"}

    # "Why this signal" — per-book backtest evidence line (trades analysed + win% + explicit
    # IS/OOS date ranges). Ends every signal message (user format 2026-07-30). Honest labels only.
    _TG_ANALYSIS = {
        "STOCK CREDIT v2 UNION":
            "• Donchian-union breakout fade · credit/width ≥ 0.40 · nearest expiry at least 10 days out\n"
            "• In-sample (1-Jan-2019 → 30-Sep-2024): 213 trades · <b>77.9%</b> win rate · +21.2% on margin · ₹2,436 net per trade · positive every year\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): 79 trades · <b>83.5%</b> win rate · +27.0% on margin · ₹3,267 net per trade · positive in both full years (2024 is a 3-month stub)\n"
            "• The backtest cannot model the live bid-ask gate, which rejects most candidates, so read this as a ceiling",
        "STOCK CREDIT v0 (c/w 0.35-0.40)":
            "• The tier just BELOW the c/w≥0.40 gate — same fade, same geometry, priced one band lower\n"
            "• The weakest evidence of the three stock books · forward paper-test at 1 lot\n"
            "• In-sample (1-Jan-2019 → 30-Sep-2024): 217 trades · <b>85.7%</b> win rate · +14.4% on margin · ₹1,731 net per trade · positive 5 of 6 years\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): 99 trades · <b>81.8%</b> win rate · only +7.2% on margin and positive just <b>1 of 2 full years</b>\n"
            "• It wins about four trades in five and still clears the least of the three books per trade",
        "STOCK CREDIT v1":
            "• Same fade, short 1-OTM · width 3 · book at 40% of credit · Donchian-10 · nearest expiry at least 10 days out\n"
            "• In-sample (1-Jan-2019 → 30-Sep-2024): 349 trades · <b>80.5%</b> win rate · +12.9% on margin · ₹1,109 net per trade · positive every year\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): 186 trades · <b>83.3%</b> win rate · +16.6% on margin · ₹1,842 net per trade · positive in both full years (2024 is a 3-month stub)\n"
            "• Fires about twice as often as v2 and rests on the larger measured sample",
        "0DTE NIFTY":
            "• 448 weekly expiries analysed since 2019\n"
            "• In-sample (1-Jan-2019 → 30-Sep-2024): <b>88%</b> win rate achieved\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): <b>90%</b> win rate achieved",
        "0DTE SENSEX":
            "• 89 expiries analysed\n"
            "• In-sample: CANNOT be captured — SENSEX weekly options only exist from Oct-2024\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): <b>88.8%</b> win rate achieved",
        "SWING CREDIT · multi-day (NIFTY/FINNIFTY)": "• forward paper-test — regime-dependent, unproven",
        "MONTHLY FUTURES PULLBACK":
            "• In-sample (2018 → 30-Sep-2024): <b>77.8%</b> win rate achieved\n"
            "• Out-of-sample (1-Oct-2024 → {TODAY}): <b>75.7%</b> win rate achieved",
        "MONTHLY LONG-CALL PULLBACK": "• forward paper-test — shelved as unreliable",
    }
    _TG_DISCLAIMER = ("⚠️ Tejas Jadhav is NOT a SEBI-registered research analyst/investment advisor. "
                      "Educational signals · invest at your own risk · consult a SEBI-registered advisor.")
    _TG_SIDE = {"BEAR_CALL": "BEAR CALL SPREAD", "BULL_PUT": "BULL PUT SPREAD", "BUY_FUT": "BUY FUTURES"}

    def _sym_history(self, sym, side="", book=""):
        """Per-name backtest history line for the signal message (user request, 24-Aug-2026):
        when the 15:36 scan names a stock, say how THAT stock has traded historically in both
        windows - trades, win rate, average profit and average loss per trade. Data is the
        harness-of-record row files folded into data/symbol_history.json (regenerate after any
        re-run). Missing name -> empty string, never a crash."""
        try:
            _shp = os.path.join(DATA_DIR, "symbol_history.json")
            _mt = os.path.getmtime(_shp)
            if getattr(self, "_symhist_mt", None) != _mt:
                self._symhist = json.load(open(_shp)); self._symhist_mt = _mt   # reload on rebuild

            import html as _html
            h = self._symhist.get(sym) or self._symhist.get(_html.unescape(str(sym)))
            sym = _html.escape(_html.unescape(str(sym)))   # M&M: look up raw, render escaped
            if not h:
                return ""
            def line(lbl, d):
                if not d:
                    return f"• {lbl}: no trades in this window"
                al = f"₹{d['avg_loss']:+,.0f}" if d.get("avg_loss") is not None else "no loss"
                aw = f"₹{d['avg_win']:+,.0f}" if d.get("avg_win") is not None else "no win"
                bc, bp = d.get("bc"), d.get("bp")
                sides = (f" ({bc} bear call{'s' if bc != 1 else ''} · "
                         f"{bp} bull put{'s' if bp != 1 else ''})"
                         if (bc is not None and bp is not None and (bc or bp)) else "")
                return (f"• {lbl}: <b>{d['n']}</b> trades{sides} · <b>{d['win']:.0f}%</b> win · "
                        f"avg profit {aw} · avg loss {al} per trade")
            # POOLED EXPECTANCY (user, 24-Aug-2026): weight each window's win rate by its trade
            # count (e.g. 18/29 x 72% + 11/29 x 73%), pool avg win/loss the same way, and state
            # the expected profit per trade = win% x avg win - loss% x avg loss.
            exp_line = ""
            try:
                i, o = h.get("is"), h.get("oos")
                parts = [d for d in (i, o) if d and d.get("n")]
                N = sum(d["n"] for d in parts)
                if N:
                    wr = sum(d["n"] * d["win"] for d in parts) / N / 100.0
                    wins = [(d["n"] * d["win"] / 100.0, d.get("avg_win") or 0) for d in parts]
                    loss = [(d["n"] * (1 - d["win"] / 100.0), abs(d.get("avg_loss") or 0)) for d in parts]
                    nw, nl = sum(w for w, _ in wins), sum(l for l, _ in loss)
                    aw = sum(w * v for w, v in wins) / nw if nw else 0
                    al = sum(l * v for l, v in loss) / nl if nl else 0
                    ev = wr * aw - (1 - wr) * al
                    # pooled line RETIRED (user, 24-Aug-2026): once the message quotes the firing
                    # strategy's own per-trade profit and the side split, a blend of both sides
                    # and all books adds no decision value.
                    exp_line = ""
            except Exception:
                pass
            sc_i, sc_o = h.get("scanned_is") or 0, h.get("scanned_oos") or 0
            scanned = (f"• Breakout signals scanned for {sym}: <b>{sc_i}</b> in-sample · "
                       f"<b>{sc_o}</b> out-of-sample — the gates admitted the trades below\n"
                       if (sc_i or sc_o) else "")
            # SIDE SPLIT (user, 24-Aug-2026): both sides' records, with THIS signal's side named.
            side_line = ""
            try:
                bc, bp = h.get("bear_call"), h.get("bull_put")
                def sd(lbl, d):
                    return (f"{lbl} <b>{d['n']}</b> tr · <b>{d['win']:.0f}%</b> win · "
                            f"₹{d['net']:+,.0f} actual overall profit"
                            if d else f"{lbl} no past trades")
                if bc or bp:
                    cur = ("BEAR CALL" if side == "BEAR_CALL" else
                           ("BULL PUT" if side == "BULL_PUT" else ""))
                    side_line = "\n• By side — " + sd("bear call:", bc) + "  |  " + sd("bull put:", bp)
                    if cur:
                        d = bc if side == "BEAR_CALL" else bp
                        if d and d.get("n"):
                            per = d["net"] / d["n"]
                            side_line += (f"\n• <b>This signal is a {cur} for which {sym} has given "
                                          f"{d['n']} {cur.lower()} trade{'s' if d['n'] != 1 else ''} · {d['win']:.0f}% win · "
                                          f"actual profit ₹{d['net']:+,.0f} till date = "
                                          f"₹{per:+,.0f} per lot per trade</b>")
                        else:
                            side_line += (f"\n• <b>This signal is a {cur}</b> — no past trades on "
                                          f"this side for this stock")
            except Exception:
                pass
            # THIS BOOK's own record (user, 24-Aug-2026): the pooled lines mix three exits, so
            # the signal also quotes the record of the book that fired it.
            bk_key = {"STOCK CREDIT v2 UNION": "book_v2", "STOCK CREDIT v1": "book_v1"}.get(book)
            if bk_key is None and "v0" in (book or ""): bk_key = "book_v0"
            if bk_key is None and "v2" in (book or ""): bk_key = "book_v2"
            if bk_key is None and "v1" in (book or ""): bk_key = "book_v1"
            d = h.get(bk_key) if bk_key else None
            book_line = ""
            if d and d.get("n"):
                _sd = "bc" if side == "BEAR_CALL" else ("bp" if side == "BULL_PUT" else None)
                ds = h.get(f"{bk_key}_{_sd}") if _sd else None
                tail = (f" — of which this side: <b>{ds['n']}</b> tr · <b>{ds['win']:.0f}%</b> · "
                        f"₹{ds['net']:+,.0f}" if ds and ds.get("n") else "")
                _pt = d["net"] / d["n"] if d.get("n") else 0
                book_line = (f"\n• As per the strategy {bk_key[5:]}: <b>{d['n']}</b> trade"
                             f"{'s' if d['n'] != 1 else ''} · <b>{d['win']:.0f}%</b> win · "
                             f"net ₹{d['net']:+,.0f} = <b>₹{_pt:+,.0f} actual profit per trade</b>"
                             f" (both windows pooled)" + tail)
                # BUCKET ROUTING NOTE (user-approved 24-Aug-2026, option 2): v1 and v2 are one
                # rich-credit bucket in two geometries, so when the OTHER geometry's record for
                # THIS name is materially better on a usable sample, say so - informational only,
                # the reader picks the strikes. v0 is a separate band and never suggested.
                if bk_key in ("book_v2", "book_v1"):
                    ok_ = "book_v1" if bk_key == "book_v2" else "book_v2"
                    od = h.get(ok_)
                    if (od and od.get("n", 0) >= 8 and d and
                            od["win"] >= d["win"] + 10 and od["net"] > d["net"]):
                        book_line += (f"\n• Note: this name's record is stronger under "
                                      f"<b>{ok_[5:]}</b> ({od['n']} tr · {od['win']:.0f}% · "
                                      f"₹{od['net']:+,.0f}) than {bk_key[5:]} "
                                      f"({d['n']} tr · {d['win']:.0f}% · ₹{d['net']:+,.0f})")
            return ("📜 <b>" + sym + " — this stock's own backtest record</b>\n"
                    + scanned
                    + line("In-sample 2019→Sep-24", h.get("is")) + "\n"
                    + line("Out-of-sample Oct-24→date", h.get("oos")) + book_line + exp_line + side_line)
        except Exception as e:
            logger.debug(f"_sym_history {sym}: {e}")
            return ""

    def _analysis(self, book, sym=""):
        a = self._TG_ANALYSIS.get(book)
        if a is None and ("SENSEX" in book or sym == "SENSEX"):
            a = self._TG_ANALYSIS["0DTE SENSEX"]
        # NB "NIFTY" is a substring of "BANKNIFTY" — must exclude it or BANKNIFTY (a REJECTED
        # book) would inherit NIFTY's 88/90% stats (bug caught in path test 2026-07-30).
        if a is None and ("0DTE" in book or "INTRADAY" in book) and "NIFTY" in book and "BANKNIFTY" not in book:
            a = self._TG_ANALYSIS["0DTE NIFTY"]
        if a:
            a = a.replace("{TODAY}", datetime.now(IST).strftime("%-d-%b-%Y"))
        return a

    def _tg(self, book, signals):
        """Fan out newly-opened signals to Telegram (format user-approved 2026-07-30):
        '🟢 EXECUTE NOW — MULTIDAY/INTRADAY SIGNAL' → trade + target/risk → separator →
        '📚 Why this signal — Tejas Jadhav, CFA …' with trades analysed + IS/OOS dates.
        Best-effort: never let a notify failure disturb the engine."""
        if not signals:
            return
        try:
            from engine.notifications import send_telegram
            from engine import config   # used by the intraday expiry/target lines below
            kind = ("MULTIDAY" if book in self._MULTIDAY_BOOKS
                    else ("INTRADAY" if ("0DTE" in book or "INTRADAY" in book) else "MULTIDAY"))
            items = signals if isinstance(signals, list) else []
            if not items:
                send_telegram(f"🟢 <b>EXECUTE NOW — {kind} SIGNAL</b>\n{book} · new signal(s) — "
                              f"details on the dashboard.")
                return
            # PER-SIGNAL ISOLATION (audit 17-Aug-2026). The whole loop used to sit inside one try,
            # so a single malformed signal killed every message after it and left one WARNING behind.
            # Each signal now fails on its own and the rest still go out.
            for s in items:
              try:
                if not isinstance(s, dict):
                    send_telegram(f"🟢 <b>EXECUTE NOW — {kind} SIGNAL</b>\n{book} · new signal — "
                                  f"details on the dashboard."); continue
                # html.escape dynamic fields — a symbol like "M&M" carries a raw '&' that breaks
                # Telegram HTML parse_mode and silently fails the send (bug fixed 2026-07-21).
                sym = html.escape(str(s.get("symbol") or s.get("index") or s.get("name") or ""))
                raw_side = str(s.get("side") or s.get("breakout_dir") or "")
                side = html.escape(self._TG_SIDE.get(raw_side, raw_side))
                verb = "CE" if "CALL" in raw_side else ("PE" if "PUT" in raw_side else "")
                g = lambda x: ("%g" % x) if isinstance(x, (int, float)) else None
                ss, ls = g(s.get("short_strike")), g(s.get("long_strike"))
                sp, lp = s.get("short_prem"), s.get("long_prem")
                credit, w, lot = s.get("credit"), s.get("width_pts"), s.get("lot")
                pretty = {"STOCK CREDIT v2 UNION": "Stock Credit v2 UNION",
                          "STOCK CREDIT v1": "Stock Credit v1",
                          "STOCK CREDIT v0 (c/w 0.35-0.40)": "Stock Credit v0",
                          "MONTHLY FUTURES PULLBACK": "Monthly Pullback",
                          "MONTHLY LONG-CALL PULLBACK": "Monthly Long-Call",
                          "SWING CREDIT · multi-day (NIFTY/FINNIFTY)": "Index Swing"}.get(book, book)
                head2 = (f"{sym} · {side}" if kind == "INTRADAY"
                         else f"{sym} · {side} ({pretty})")
                lines = [f"🟢 <b>EXECUTE NOW — {kind} SIGNAL</b>", head2]
                if ss and ls:
                    leg1 = f"SELL {ss} {verb}".rstrip() + (f" @ ₹{sp}" if sp is not None else "")
                    leg2 = f"BUY {ls} {verb}".rstrip() + (f" @ ₹{lp}" if lp is not None else "")
                    lines.append(f"{leg1}  /  {leg2}")
                    exp = self._fmt_d(s.get("expiry") or "")
                    if kind == "INTRADAY":
                        _fc = config.FNO_CLOSE   # 15:40 since 3-Aug-2026 — never a literal again
                        expbit = f"Expires TODAY at {int(_fc[:2])-12}:{_fc[3:]} PM"
                    else:
                        expbit = f"Expiry {exp}" if exp else ""
                    extra = " · ".join(x for x in (expbit,
                                                   (f"credit ₹{credit}" if credit is not None else ""),
                                                   (f"lot {lot}" if lot else "")) if x)
                    if extra: lines.append(extra)
                    have_nums = isinstance(credit, (int, float)) and isinstance(w, (int, float)) and lot
                    exit_ = self._TG_EXIT.get(book)
                    if kind == "INTRADAY":
                        _f = getattr(config, "ZERO_DTE_EARLY_CLOSE_FRAC", 0) or 0
                        lines.append(f"🎯 Books early at {_f:.0%} of max profit, else holds to settle · "
                                     "no stop — bought wing caps the loss" if _f else
                                     "🎯 Hold to settle · no stop — bought wing caps the loss")
                    elif exit_ and have_nums:
                        tp_frac, stop_mult = exit_
                        binds = stop_mult * credit < w   # a vertical can't cost > width to close
                        tgt = (f"🎯 Target: book {tp_frac*100:.0f}% of credit ≈ +₹{tp_frac*credit*lot:,.0f}/lot"
                               if tp_frac > 0 else "🎯 Target: hold to expiry — keep the full credit")
                        lines.append(tgt + ("" if binds else " (no stop — wing caps loss)"))
                        if binds:
                            lines.append(f"🛑 Stop: buy back if cost hits {stop_mult:g}× credit "
                                         f"≈ −₹{(stop_mult-1)*credit*lot:,.0f}/lot")
                    else:
                        tgt_stop = self._tgt_stop(book)
                        if tgt_stop:
                            lines.append(f"🎯 Target: {tgt_stop[0]} · 🛑 Stop: {tgt_stop[1]}")
                    if have_nums:
                        lines.append(f"Max profit/lot ₹{credit*lot:,.0f} · Max loss/lot ₹{(w-credit)*lot:,.0f}")
                elif s.get("order_label"):
                    lines.append(str(s["order_label"]))
                    tgt_stop = self._tgt_stop(book)
                    if tgt_stop:
                        lines.append(f"🎯 Target: {tgt_stop[0]} · 🛑 Stop: {tgt_stop[1]}")
                # PER-NAME EVIDENCE (user, 24-Aug-2026): when the named stock has its own
                # backtest record, THAT is the evidence a reader needs — the book-level
                # Donchian/IS/OOS bullets are dropped from the message and the header leads
                # straight into the stock. Books with no per-name record (the index books) keep
                # the original analysis block unchanged. Gated until the user approves the sample.
                sh = (self._sym_history(sym, side=str(s.get("side") or ""), book=book)
                      if getattr(config, "TG_SYMBOL_HISTORY_ENABLED", False) else "")
                if sh:
                    lines.append("——————————————")
                    lines.append("📚 <b>Why this signal</b> — Tejas Jadhav, CFA has performed extensive "
                                 "analysis of this strategy which gave below historical results —")
                    lines.append(sh)
                else:
                    ana = self._analysis(book, sym)
                    if ana:
                        lines.append("——————————————")
                        lines.append("📚 <b>Why this signal</b> — Tejas Jadhav, CFA has performed extensive "
                                     "analysis of this strategy which gave below historical results —")
                        lines.append(ana)
                lines.append(self._TG_DISCLAIMER)
                send_telegram("\n".join(lines))
              except Exception as e:
                logger.error("telegram notify (%s): signal %s FAILED, continuing with the rest: %s",
                             book, (s.get("symbol") if isinstance(s, dict) else "?"), e)
        except Exception as e:
            logger.warning(f"telegram notify ({book}): {e}")

    def _swing(self, now):
        """SWING CREDIT SPREADS (the 3rd strategy) — multi-day, overnight carry, decoupled from
        the intraday loop. Scans ONCE/day after the cutoff (a daily Donchian breakout needs ~the
        close) and marks-to-market / settles open positions every SWING_RESOLVE_INTERVAL. Runs
        even when the market is closed so overnight & weekend expiries get settled in the book."""
        try:
            from engine import config
            from engine import swing_credit
        except Exception as e:
            logger.warning(f"swing import: {e}")
            return
        # periodic resolve — runs even with SWING_CREDIT_ENABLED off so positions opened before
        # a disable still get marked-to-market and settled (the 07-24 disable orphaned an OPEN
        # NIFTY spread whose NOW/EXIT went stale in the UI). Cheap no-op when the book is empty.
        if (time.time() - self._last_swing_resolve) >= config.SWING_RESOLVE_INTERVAL:
            self._last_swing_resolve = time.time()
            try:
                n = swing_credit.resolve_swing_positions()
                if n:
                    logger.info(f"swing: resolved/closed {n} position(s)")
            except Exception as e:
                logger.warning(f"swing resolve: {e}")
        # once-daily scan after the cutoff, only on a trading day — the flag gates NEW entries only
        if not getattr(config, "SWING_CREDIT_ENABLED", False):
            return
        h, m = map(int, config.SWING_SCAN_AFTER.split(":"))
        after_cutoff = (now.hour * 60 + now.minute) >= (h * 60 + m)
        if (self.agent.is_market_open() and after_cutoff and self._swing_scan_day != now.date()):
            self._swing_scan_day = now.date()
            try:
                new = swing_credit.scan_swing_signals()
                if new:
                    logger.info(f"swing: opened {len(new)} new spread(s)")
                    self._tg("SWING CREDIT · multi-day (NIFTY/FINNIFTY)", new)
            except Exception as e:
                logger.warning(f"swing scan: {e}")

    def _monthly_fut(self, now):
        """MONTHLY FUTURES PULLBACK (the 5th strategy) — monthly-horizon, overnight carry.
        Once/day scan attempt after the cutoff (fires only near cycle start; internal guards)
        + periodic mark/close of open positions, same pattern as _swing."""
        try:
            from engine import config
            if not getattr(config, "MONTHLY_FUT_ENABLED", False):
                return
            from engine import monthly_fut
        except Exception as e:
            logger.warning(f"monthly_fut import: {e}")
            return
        if (time.time() - self._last_monthly_resolve) >= config.MONTHLY_FUT_RESOLVE_INTERVAL:
            self._last_monthly_resolve = time.time()
            try:
                n = monthly_fut.resolve_monthly_positions()
                if n:
                    logger.info(f"monthly_fut: closed {n} position(s)")
            except Exception as e:
                logger.warning(f"monthly_fut resolve: {e}")
        h, m = map(int, config.MONTHLY_FUT_SCAN_AFTER.split(":"))
        after_cutoff = (now.hour * 60 + now.minute) >= (h * 60 + m)
        if (self.agent.is_market_open() and after_cutoff and self._monthly_scan_day != now.date()):
            self._monthly_scan_day = now.date()
            try:
                new = monthly_fut.scan_monthly_signals()
                if new:
                    logger.info(f"monthly_fut: entered {len(new)} pullback long(s)")
                    self._tg("MONTHLY FUTURES PULLBACK", new)
            except Exception as e:
                logger.warning(f"monthly_fut scan: {e}")

    def _monthly_call(self, now):
        """MONTHLY LONG-CALL PULLBACK (the 6th strategy) — same signal as _monthly_fut, expressed
        as a bought ATM call. Once/day scan attempt after the cutoff (fires near cycle start) +
        periodic mark/close of open calls (trigger on underlying, P&L on premium)."""
        try:
            from engine import config
            if not getattr(config, "MONTHLY_CALL_ENABLED", False):
                return
            from engine import monthly_call
        except Exception as e:
            logger.warning(f"monthly_call import: {e}")
            return
        if (time.time() - self._last_monthly_call_resolve) >= config.MONTHLY_CALL_RESOLVE_INTERVAL:
            self._last_monthly_call_resolve = time.time()
            try:
                n = monthly_call.resolve_call_positions()
                if n:
                    logger.info(f"monthly_call: closed {n} call(s)")
            except Exception as e:
                logger.warning(f"monthly_call resolve: {e}")
        h, m = map(int, config.MONTHLY_FUT_SCAN_AFTER.split(":"))
        after_cutoff = (now.hour * 60 + now.minute) >= (h * 60 + m)
        if (self.agent.is_market_open() and after_cutoff and self._monthly_call_scan_day != now.date()):
            self._monthly_call_scan_day = now.date()
            try:
                new = monthly_call.scan_call_signals()
                if new:
                    logger.info(f"monthly_call: bought {len(new)} pullback call(s)")
                    self._tg("MONTHLY LONG-CALL PULLBACK", new)
            except Exception as e:
                logger.warning(f"monthly_call scan: {e}")

    @staticmethod
    def _stock_settlement_due() -> bool:
        """True if any OPEN stock-credit position has reached its expiry.

        Why this exists: the market-hours gate below must NOT apply to settlement. The expiry
        branch inside resolve_positions only fires once the session is over (`now >= 15:30`),
        while is_market_open() is 9:15-15:30 — so a naive "market hours only" gate would give
        settlement a one-minute window against a 15-minute timer and expired positions would sit
        OPEN forever. That is the same freeze that stranded the NIFTY bull-put in July (653d3c9).
        """
        today = datetime.now(IST).date().isoformat()
        for fn in ("stock_credit_v2_positions.json", "stock_credit_positions.json",
                   "stock_credit_v0_positions.json"):
            try:
                for p in json.load(open(os.path.join(DATA_DIR, fn))) or []:
                    if p.get("status") == "OPEN" and (p.get("expiry") or "9999-99-99") <= today:
                        return True
            except Exception:
                continue
        return False

    _MARKER_PATH = os.path.join(DATA_DIR, "day_markers.json")
    _MARKER_ATTRS = ("_stockcr_scan_day", "_watchlist_tg_day", "_zdte_scan_day",
                     "_watchlist_build_day", "_swing_scan_day", "_monthly_scan_day")

    def _load_day_markers(self):
        try:
            from datetime import date as _date
            d = json.load(open(self._MARKER_PATH))
            for k in self._MARKER_ATTRS:
                v = d.get(k)
                if v:
                    setattr(self, k, _date.fromisoformat(v))
        except Exception:
            pass

    def _save_day_markers(self):
        try:
            out = {}
            for k in self._MARKER_ATTRS:
                v = getattr(self, k, None)
                if v:
                    out[k] = v.isoformat()
            json.dump(out, open(self._MARKER_PATH, "w"))
        except Exception as e:
            logger.warning("day markers save: %s", e)

    def _scan_sentinel(self):
        """Deadline insurance for the 15:36 scan (25-Aug-2026). Runs in a daemon thread. If the
        main loop has not fired the day's stock scan by 15:36:20 - today it sat blocked in
        network retries until 15:48 and the scan silently never happened - this thread calls
        _stock_credit itself. The atomic marker swap inside makes double-running impossible."""
        while True:
            try:
                time.sleep(5)
                now = datetime.now(IST)
                if now.weekday() >= 5:
                    continue
                mins = now.hour * 60 + now.minute
                if not (15 * 60 + 36 <= mins <= 15 * 60 + 44):
                    continue
                if mins == 15 * 60 + 36 and now.second < 20:
                    continue                       # the main loop gets until 15:36:20
                if self._stockcr_scan_day == now.date():
                    continue
                logger.warning("SCAN SENTINEL firing at %s — the main loop has not scanned "
                               "(likely stalled); scanning from the sentinel thread",
                               now.strftime("%H:%M:%S"))
                self._stock_credit(now)
            except Exception as e:
                logger.warning("scan sentinel: %s", e)
                time.sleep(30)

    def _stock_credit(self, now):
        """STOCK CREDIT SPREADS (the 4th strategy) — high-frequency fade on the stock universe.
        Once/day scan after the cutoff + periodic mark-to-market, same pattern as _swing."""
        try:
            from engine import config
            if not getattr(config, "STOCK_CREDIT_ENABLED", False):
                return
            from engine import stock_credit
            from engine import stock_credit_v2
            try:
                from engine import stock_credit_v0
            except Exception:
                stock_credit_v0 = None
        except Exception as e:
            logger.warning(f"stock_credit import: {e}")
            return
        _mins = now.hour * 60 + now.minute
        # 15:17 — BUILD the UNION watchlist. Moved from 14:45 on 2026-08-04: F&O stocks now stop
        # trading continuously at 15:15 and settle in an auction by 15:35, so 15:17 is the first
        # moment the continuous session is complete. The build takes 11-19 s, so the old 14:45/15:05
        # split for slack is unnecessary — build and send in the same pass. (the slow ~100-stock sweep; on a throttled day it took
        # 17 min → the old combined 15:05 call landed at 15:22). Doing it at 14:45 gives ~20 min of
        # slack so it's always ready by 15:05. Near-close data (breakouts are close-based).
        if (self.agent.is_market_open() and _mins >= _watchlist_mins()
                and self._watchlist_build_day != now.date()):
            self._watchlist_build_day = now.date()
            try:
                w = stock_credit_v2.build_watchlist()
                logger.info(f"union watchlist built (15:17): {w.get('breakouts',0)} breakouts")
            except Exception as e:
                logger.warning(f"watchlist build 14:45: {e}")
        # 15:31 — REBUILD the watchlist and SEND the digest (user decision, 2026-08-06; 3-agent
        # adjudication 5-Aug). By 15:31 the CAS random close (15:28-15:30) has passed, so spot is
        # the auction value and the STRIKES ARE FINAL — the 15:17 build priced off the frozen 15:15
        # print and staged the wrong strikes on 4/14 names. The rebuild takes ~11-19 s, landing the
        # message ~15:31:30 with final strikes + live option prices, ~4.5 min before the 15:36 scan.
        # The 15:17 build above stays for the UI heads-up; this is the actionable message.
        def _digest_mins():
            h, m = map(int, getattr(config, "WATCHLIST_DIGEST_AT", "15:31").split(":"))
            return h * 60 + m
        if (self.agent.is_market_open() and _mins >= _digest_mins()
                and self._watchlist_tg_day != now.date()):
            self._watchlist_tg_day = now.date()
            self._save_day_markers()
            try:
                w2 = stock_credit_v2.build_watchlist()   # fresh, post-auction strikes
                nc = stock_credit_v2.notify_nearmiss(rebuild=False)
                logger.info(f"union watchlist rebuilt at {config.WATCHLIST_DIGEST_AT} "
                            f"({w2.get('breakouts', 0)} breakouts) · digest sent: {nc} candidate(s)")
            except Exception as e:
                logger.warning(f"watchlist digest {config.WATCHLIST_DIGEST_AT}: {e}")
        # MARK-TO-MARKET / TARGET CHECK — MARKET HOURS ONLY (user, 2026-08-03). It used to run
        # round the clock on the 15-min timer, so a target could be booked at e.g. 20:00 off
        # post-close quotes. Settlement is exempt: an expired position must still be closed out
        # after 15:30, so _stock_settlement_due() overrides the gate.
        if ((time.time() - self._last_stockcr_resolve) >= config.STOCK_CREDIT_RESOLVE_INTERVAL
                and (self.agent.is_market_open() or self._stock_settlement_due())):
            self._last_stockcr_resolve = time.time()
            try:
                n = stock_credit.resolve_positions()
                if n:
                    logger.info(f"stock_credit: resolved/closed {n} position(s)")
            except Exception as e:
                logger.warning(f"stock_credit resolve: {e}")
            try:
                n2 = stock_credit_v2.resolve_positions()
                if n2:
                    logger.info(f"stock_credit_v2: resolved/closed {n2} position(s)")
            except Exception as e:
                logger.warning(f"stock_credit_v2 resolve: {e}")
            if stock_credit_v0 is not None and getattr(config, "STOCK_CREDIT_V0_ENABLED", False):
                try:
                    n3 = stock_credit_v0.resolve_positions()
                    if n3:
                        logger.info(f"stock_credit_v0: resolved/closed {n3} position(s)")
                except Exception as e:
                    logger.warning(f"stock_credit_v0 resolve: {e}")
        h, m = map(int, config.STOCK_CREDIT_SCAN_AFTER.split(":"))
        mins_now = now.hour * 60 + now.minute
        after_cutoff = mins_now >= (h * 60 + m)
        # LATE-SCAN CATCH-UP (25-Aug-2026 — the audit's finding #7 fired live today). The engine is
        # single-threaded; on 25-Aug a network stall pushed the cycle from 15:32 straight to 15:48,
        # is_market_open() was False by then, and the day's ONLY stock scan silently never ran - no
        # signals, no no-signal notice, nothing in the record. The scan runs on official CLOSES, so
        # its ANSWER is still computable after the bell: until 16:30 a missed scan now runs anyway,
        # clearly labelled LATE (signals arriving after 15:40 cannot be placed, but the record and
        # the notice must exist either way).
        late_ok = (not self.agent.is_market_open()) and after_cutoff and mins_now <= (16 * 60 + 30)
        if ((self.agent.is_market_open() or late_ok) and after_cutoff
                and self._stockcr_scan_day != now.date()):
            # the marker swap is atomic: whichever of the main loop and the sentinel gets here
            # first claims the day; the loser sees the marker set and returns
            with self._scan_lock:
                if self._stockcr_scan_day == now.date():
                    return
                self._stockcr_scan_day = now.date()
                self._save_day_markers()
            if late_ok:
                logger.warning("stock scan running LATE at %s - the 15:36 window was missed "
                               "(cycle stalled); signals below are RECORD-ONLY, not placeable",
                               now.strftime("%H:%M"))
            _fired = 0        # counts signals across all three books, for the no-signal notice
            # v2 (the leader) scans FIRST so v1 can defer to it — one position per stock across
            # both books (no doubling-down on the same name). User request 2026-07-08.
            try:
                new2 = stock_credit_v2.scan_signals()
                if new2:
                    logger.info(f"stock_credit_v2: opened {len(new2)} new spread(s)")
                    _fired += len(new2)
                    self._tg("STOCK CREDIT v2 UNION", new2)
            except Exception as e:
                logger.warning(f"stock_credit_v2 scan: {e}")
            try:
                new = stock_credit.scan_signals()
                if new:
                    logger.info(f"stock_credit: opened {len(new)} new spread(s)")
                    _fired += len(new)
                    self._tg("STOCK CREDIT v1", new)
            except Exception as e:
                logger.warning(f"stock_credit scan: {e}")
            # v0 scans LAST of the three so it can see what v1 just opened. The books are
            # otherwise independent; the ONE tie-break is that if v0 and v1 would both trade the
            # same stock, v1 wins and v0 stands down, so only one signal goes out for that name
            # (user rule 2026-07-31). v0 vs v2 cannot clash — mutually exclusive c/w bands.
            if stock_credit_v0 is not None and getattr(config, "STOCK_CREDIT_V0_ENABLED", False):
                try:
                    new3 = stock_credit_v0.scan_signals()
                    if new3:
                        logger.info(f"stock_credit_v0: opened {len(new3)} new spread(s)")
                        _fired += len(new3)
                        self._tg("STOCK CREDIT v0 (c/w 0.35-0.40)", new3)
                except Exception as e:
                    logger.warning(f"stock_credit_v0 scan: {e}")
            if _fired == 0:
                self._tg_no_signal(now)


    def _tg_intraday_skip(self, now, reasons):
        """Say why the same-day index books did not trade (user request, 20-Aug-2026).

        The 15:36 message already covers the stock books. This is its counterpart for the 09:16
        window, and it exists for the same reason: on 20-Aug the SENSEX book skipped on a credit
        ratio of 0.038 against a 0.040 floor and nothing told him, so a designed skip and a dead
        engine looked identical from the outside.
        """
        try:
            from engine.notifications import send_telegram
            lines = [
                "\u26aa <b>NO INTRADAY TRADE TODAY \u2014 SCAN COMPLETE</b>",
                f"{now.strftime('%A, %d %b %Y')} \u00b7 scanned at {now.strftime('%H:%M')} on the open",
                "",
                "Thank you for waiting. The same-day books have run and none of them has a trade "
                "for you today.",
                "",
            ]
            for idx in sorted(reasons):
                lines.append(f"\u2022 <b>{idx}</b> \u2014 {reasons[idx]}")
            lines += [
                "",
                "<b>Standing down is the strategy working, not failing.</b> These books sell a "
                "same-day spread only when the market pays properly for carrying the risk to "
                "settlement. When the credit is thin the loss is still the full width, so a cheap "
                "trade is the one that gives the edge back.",
                "",
                "The next intraday scan runs on the following expiry, just after the open.",
                self._TG_DISCLAIMER,
            ]
            # send_telegram returns False on a missing/rotated token and every caller used to
            # discard it. This message exists so that silence is never ambiguous, so a silent
            # delivery failure would defeat the whole point. Say so in the log.
            if not send_telegram("\n".join(lines)):
                logger.warning("_tg_intraday_skip: Telegram delivery FAILED — the skip notice did "
                               "not reach him. Check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.")
        except Exception as e:
            logger.warning(f"_tg_intraday_skip: {e}")

    def _tg_no_signal(self, now):
        """Tell him the scan ran and found nothing (user request, 18-Aug-2026).

        Silence used to be ambiguous — a quiet 15:36 could mean no breakout qualified, or it could
        mean the engine never scanned. On 17-Aug a DNS outage made the engine call a live session an
        exchange holiday and the watchlist came back empty, and nothing said so. This message closes
        that gap: if it does not arrive, something is wrong.
        """
        try:
            from engine.notifications import send_telegram
            from engine import config
            n_wl = 0
            try:
                _raw = json.load(open(os.path.join(DATA_DIR, "union_watchlist.json")))
                n_wl = len(_raw if isinstance(_raw, list) else (_raw.get("rows") or []))
            except Exception:
                pass
            lines = [
                "⚪ <b>NO SIGNAL TODAY — SCAN COMPLETE</b>",
                f"{now.strftime('%A, %d %b %Y')} · scanned at {now.strftime('%H:%M')} on the official close",
                "",
                "Thank you for waiting. The scan has run and the system has no trade for you today.",
                "",
                f"• The full {len(config.UNIVERSE)}-stock universe was scanned on the closing-auction price",
                f"• {n_wl} name(s) reached the watchlist, and none cleared every gate" if n_wl
                else "• No stock closed outside its Donchian band, so nothing reached the watchlist",
                "• A trade needs all four: a breakout, credit ÷ width ≥ 0.40, premium ≥ ₹50, "
                "and a live two-sided market",
                "",
                "<b>Sitting out is the strategy working, not failing.</b> These books fade a breakout "
                "only when the market pays richly for it. On a quiet day that premium is not there, "
                "and taking a thin trade is how a good edge is given back.",
                "",
                "The next scan runs tomorrow at 15:36, after the closing auction.",
                self._TG_DISCLAIMER,
            ]
            if send_telegram("\n".join(lines)):
                logger.info("no-signal notice sent (watchlist %d, universe %d)", n_wl, len(config.UNIVERSE))
            else:
                logger.warning("no-signal notice: Telegram delivery FAILED — the 15:36 notice did "
                               "not reach him. Check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.")
        except Exception as e:
            logger.warning("no-signal notice failed: %s", e)

    def _zero_dte(self, now):
        """0DTE INTRADAY (5th strategy) — NIFTY expiry-day CE credit spread. One entry right
        after the open on weekly-expiry days; intraday MTM; booked at 15:30 settlement.
        Signals-only paper forward-test — see studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md."""
        try:
            from engine import config
            if not getattr(config, "ZERO_DTE_ENABLED", False):
                return
            from engine import zero_dte
        except Exception as e:
            logger.warning(f"zero_dte import: {e}")
            return
        if (time.time() - self._last_zdte_resolve) >= config.ZERO_DTE_RESOLVE_INTERVAL:
            self._last_zdte_resolve = time.time()
            try:
                n = zero_dte.resolve_positions()
                if n:
                    logger.info(f"zero_dte: settled {n} position(s)")
            except Exception as e:
                logger.warning(f"zero_dte resolve: {e}")
            try:
                zero_dte.write_status()   # pre-market "signal expected?" checker for the UI
            except Exception as e:
                logger.warning(f"zero_dte status: {e}")
        # SENSEX 0DTE book (engine/dte_multi.py) shares the cadence
        try:
            from engine import dte_multi
            hs, ms_ = map(int, config.ZERO_DTE_SETTLE_AFTER.split(":"))
            past_settle = (now.hour * 60 + now.minute) >= (hs * 60 + ms_)
            if (time.time() - getattr(self, "_dtem_resolve", 0)) >= config.ZERO_DTE_RESOLVE_INTERVAL:
                self._dtem_resolve = time.time()
                n = dte_multi.resolve_positions(past_settle)
                if n:
                    logger.info(f"dte_multi: settled {n} position(s)")
        except Exception as e:
            logger.warning(f"dte_multi resolve: {e}")
        h1, m1 = map(int, config.ZERO_DTE_SCAN_AFTER.split(":"))
        h2, m2 = map(int, config.ZERO_DTE_ENTRY_CUTOFF.split(":"))
        mins = now.hour * 60 + now.minute
        in_window = (h1 * 60 + m1) <= mins <= (h2 * 60 + m2)
        if (self.agent.is_market_open() and in_window and self._zdte_scan_day != now.date()):
            self._zdte_scan_day = now.date()
            self._save_day_markers()
            try:
                new = zero_dte.scan_signal()
                if new:
                    for p_ in new:   # may be 2: FLIP side + the hybrid add (2026-07-31)
                        logger.info(f"zero_dte: opened {p_['order_label']}")
                    self._tg("INTRADAY NIFTY", new)
            except Exception as e:
                logger.warning(f"zero_dte scan: {e}")
            try:
                from engine import dte_multi
                n = dte_multi.scan_signals()
                if n:
                    logger.info(f"dte_multi: opened {len(n)} spread(s)")
                    # each index gets its OWN clearly-labelled message (user: never combined)
                    self._tg("INTRADAY SENSEX", [p for p in n if p.get("symbol") == "SENSEX"])
            except Exception as e:
                logger.warning(f"dte_multi scan: {e}")
            # Tell him why the intraday books stood down (user request, 20-Aug-2026). Same reason
            # as the 15:36 no-signal message: silence cannot distinguish "the gate held" from "the
            # engine never ran". Only ELIGIBLE books appear — a book whose expiry is not today has
            # nothing to explain and is left out.
            try:
                reasons = {}
                reasons.update(getattr(zero_dte, "SCAN_TRACE", {}) or {})
                from engine import dte_multi as _dm
                reasons.update(getattr(_dm, "SCAN_TRACE", {}) or {})
                if reasons:
                    self._tg_intraday_skip(now, reasons)
            except Exception as e:
                logger.warning(f"intraday skip notice: {e}")

    def _manage_wakelock(self):
        """Hold a power assertion (`caffeinate -i`) WHILE THE MARKET IS OPEN, so an unattended
        laptop can't idle-sleep mid-session and suspend the engine (the system sleep timer is
        only ~1 min). Released after the close so normal sleep resumes — we don't keep the Mac
        awake 24/7. `-w <pid>` ties it to this process so a crash can't orphan it awake.

        NOTE: prevents IDLE sleep only. Closing the lid (clamshell) still sleeps; for fully
        unattended trading keep the lid open and on AC power.
        """
        open_now = self.agent.is_market_open()
        alive = self._caffeinate is not None and self._caffeinate.poll() is None
        try:
            if open_now and not alive:
                self._caffeinate = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
                logger.info("wakelock: caffeinate -i held (market open)")
            elif not open_now and alive:
                self._caffeinate.terminate()
                self._caffeinate = None
                logger.info("wakelock: released (market closed)")
        except Exception as e:
            logger.warning(f"wakelock manage failed: {e}")

    # Books watched for WIN/LOSS outcome Telegram messages (label -> positions file).
    _OUTCOME_BOOKS = [
        ("STOCK CREDIT v2 UNION", "stock_credit_v2_positions.json"),
        ("STOCK CREDIT v1", "stock_credit_positions.json"),
        ("STOCK CREDIT v0 (c/w 0.35-0.40)", "stock_credit_v0_positions.json"),
        ("SWING CREDIT · multi-day", "swing_positions.json"),
        ("INTRADAY NIFTY (same-day)", "zero_dte_positions.json"),
        ("INTRADAY SENSEX (same-day)", "sensex_dte_positions.json"),
        # MONTHLY FUTURES was MISSING here (found in the 2026-08-01 bug sweep). It is REGIME_OFF today
        # so nothing was lost, but the moment NIFTY clears its 200DMA it trades again and every WIN/LOSS
        # would have resolved SILENTLY — no Telegram result and absent from the portfolio summary. The
        # loop only fires on status WIN/LOSS, so this book's REGIME_OFF placeholder rows are ignored.
        ("MONTHLY FUTURES PULLBACK", "monthly_fut_positions.json"),
    ]

    @staticmethod
    def _ord_date(iso: str) -> str:
        """'2026-07-24' -> '24th July' (year appended only when it is not the current year).
        User wording, 2026-08-10: outcome messages name the day a person would say it, not ISO."""
        try:
            from datetime import date as _d
            d = _d.fromisoformat(iso)
            n = d.day
            suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
            out = f"{n}{suf} {d.strftime('%B')}"
            return out if d.year == _d.today().year else f"{out} {d.year}"
        except Exception:
            return iso or "?"

    def _outcomes(self):
        """Telegram every trade RESULT: when a paper position's status turns WIN/LOSS, send the
        P&L quoting the entry-date call. Read-only on the books; notified ids persisted in
        data/outcome_notified.json (seeded silently on first run so history doesn't flood).
        Throttled to ~60s; fully guarded — can never disturb trading."""
        if (time.time() - getattr(self, "_last_outcomes", 0)) < 60:
            return
        self._last_outcomes = time.time()
        try:
            from engine.notifications import send_telegram
            state_path = os.path.join(DATA_DIR, "outcome_notified.json")
            first_run = not os.path.exists(state_path)
            try:
                seen = set(json.load(open(state_path))) if not first_run else set()
            except Exception:
                seen = set(); first_run = True
            changed = False
            sent_any = False   # a NEW result actually went out this cycle (not first-run seeding)
            for label, fname in self._OUTCOME_BOOKS:
                path = os.path.join(DATA_DIR, fname)
                if not os.path.exists(path):
                    continue
                try:
                    book = json.load(open(path)) or []
                except Exception:
                    continue
                for p in book:
                    if p.get("status") not in ("WIN", "LOSS"):
                        continue
                    pid = p.get("id") or f"{fname}:{p.get('entry_date')}:{p.get('symbol')}"
                    if pid in seen:
                        continue
                    if first_run:
                        seen.add(pid); changed = True
                        continue          # seed silently — only NEW outcomes notify
                    # BUGFIX 2026-07-21: mark seen ONLY after a successful send (was marked before,
                    # so any send failure — a transient network error, or the "M&M" '&' breaking
                    # HTML parse_mode — permanently suppressed that result with no retry). And escape
                    # dynamic fields so the HTML path itself doesn't fail.
                    ok = False
                    try:
                        sym = html.escape(str(p.get("symbol") or p.get("index") or ""))
                        side = html.escape(str(p.get("side") or ""))
                        lbl = html.escape(str(label))
                        won = p.get("status") == "WIN"
                        qty = p.get("qty") or p.get("lot") or 0
                        pnl_pts = p.get("pnl_pts")
                        rs = f" ₹{pnl_pts*qty:+,.0f}" if isinstance(pnl_pts, (int, float)) and qty else ""
                        g = lambda x: ("%g" % x) if isinstance(x, (int, float)) else "?"
                        verb = "CE" if "CALL" in side else ("PE" if "PUT" in side else "")
                        # INTRADAY books settle the same session they fire, so their outcome line
                        # says "Today" (user, 2026-08-11). Guarded on the entry date actually being
                        # today: if a result goes out late — a retry the next morning, say — the
                        # word would be a lie, so it silently drops back to the plain wording.
                        _today_bit = ""
                        if fname in self._INTRADAY_BOOKS and \
                                p.get("entry_date") == datetime.now(IST).date().isoformat():
                            _today_bit = "<b>Today</b> "
                        _advtag = " · 📎 ADVISORY (weak side — not in the headline totals)" if p.get("advisory") else ""
                        ok = send_telegram(
                            f"📊 <b>RESULT — {lbl}</b>: {sym} {side} → {'✅ WIN' if won else '❌ LOSS'}{rs}{_advtag}\n"
                            f"This is the outcome of the Signal we gave for execution {_today_bit}on "
                            f"<b>{self._ord_date(p.get('entry_date'))}</b>: "
                            f"SELL {g(p.get('short_strike'))} {verb} / BUY {g(p.get('long_strike'))} {verb} "
                            f"(exp {p.get('expiry','?')})\n"
                            f"pts {pnl_pts:+.1f} × qty {qty} · closed {p.get('closed_date','?')}"
                            if isinstance(pnl_pts, (int, float)) else
                            f"📊 <b>RESULT — {lbl}</b>: {sym} {side} → {'✅ WIN' if won else '❌ LOSS'}\n"
                            f"This is the outcome of the Signal we gave for execution {_today_bit}on "
                            f"{self._ord_date(p.get('entry_date'))} · closed {p.get('closed_date','?')}")
                    except Exception as e:
                        logger.warning(f"outcome notify {label}: {e}")
                    if ok:
                        seen.add(pid); changed = True; sent_any = True
            if changed:
                self._write_json(state_path, sorted(seen))
            # Follow every RESULT with a running PORTFOLIO SUMMARY (once per cycle, not per
            # trade — several can resolve together and the summary would be identical).
            if sent_any:
                try:
                    txt = self._portfolio_summary_text()
                    if txt:
                        send_telegram(txt)
                except Exception as e:
                    logger.warning(f"portfolio summary notify: {e}")
        except Exception as e:
            logger.warning(f"outcomes: {e}")

    # Books whose expiry is same-day (0DTE) — everything else is a multi-day, month/week-end
    # spread. Drives the intraday-vs-month-end split in the portfolio summary.
    _INTRADAY_BOOKS = {"zero_dte_positions.json", "sensex_dte_positions.json"}
    # Short display tag per book for the open-positions breakdown.
    _BOOK_TAG = {
        "stock_credit_v2_positions.json": "v2",
        "stock_credit_positions.json": "v1",
        "stock_credit_v0_positions.json": "v0",
        "swing_positions.json": "SWING",
        "zero_dte_positions.json": "0DTE NIFTY",
        "sensex_dte_positions.json": "0DTE SENSEX",
        "monthly_fut_positions.json": "MONTHLY FUT",
    }

    @staticmethod
    def _fmt_d(s, with_year=False):
        try:
            return datetime.strptime(s, "%Y-%m-%d").strftime("%d-%b-%Y" if with_year else "%d-%b")
        except Exception:
            return s or "?"

    def _portfolio_summary_text(self):
        """Running live-trade record across all outcome books, SPLIT into intraday (0DTE,
        same-day expiry) and month-end (multi-day, held to weekly/monthly expiry). Win/loss/
        win% are CLOSED-only (an open position is neither yet); open trades carry a live MTM and
        their settlement date(s). First line stamps the exact date measurement began."""
        # `wv`/`lv` hold the individual rupee results so the message can report the AVERAGE
        # REALISED loss (user, 21-Aug-2026). Max loss is the wrong number to quote: a credit spread
        # only loses its full width if the underlying settles beyond the long strike, which is rare,
        # so max loss overstates the typical loss by two to three times on these books.
        buck = {"i": dict(w=0, l=0, pl=0.0, wv=[], lv=[]),
                "m": dict(w=0, l=0, pl=0.0, wv=[], lv=[])}
        adv = dict(n=0, pl=0.0)
        openn = 0; open_pl = 0.0; opens = []; start = None
        for _label, fname in self._OUTCOME_BOOKS:
            path = os.path.join(DATA_DIR, fname)
            if not os.path.exists(path):
                continue
            try:
                book = json.load(open(path)) or []
            except Exception:
                continue
            b = buck["i" if fname in self._INTRADAY_BOOKS else "m"]
            tag = self._BOOK_TAG.get(fname, fname)
            for p in book:
                ed = p.get("entry_date")
                if ed and (start is None or ed < start):
                    start = ed
                st = p.get("status")
                qty = p.get("qty") or p.get("lot") or 0
                pp = p.get("pnl_pts")
                rs = pp * qty if isinstance(pp, (int, float)) and qty else 0.0
                if p.get("advisory"):
                    # weak side of a side-qualified name: logged, shown separately, excluded
                    # from the headline record (user, 24-Aug-2026)
                    if st in ("WIN", "LOSS"):
                        adv["n"] += 1; adv["pl"] += rs
                    continue
                if st == "WIN":
                    b["w"] += 1; b["pl"] += rs; b["wv"].append(rs)
                elif st == "LOSS":
                    b["l"] += 1; b["pl"] += rs; b["lv"].append(rs)
                elif st == "OPEN":
                    openn += 1; open_pl += rs
                    opens.append({"exp": p.get("expiry"), "tag": tag,
                                  "sym": p.get("symbol") or p.get("index") or "?"})
                # ANY OTHER STATUS IS NEITHER OPEN NOR CLOSED — skip it. This used to be a bare
                # `else`, so monthly futures' REGIME_OFF marker rows (the book recording that it
                # STOOD ASIDE — null symbol, null expiry, no position) were counted as live trades
                # and shown as "?: 2 trades — ? (MONTHLY FUT)". User-reported 2026-08-03.
        ic, mc = buck["i"], buck["m"]
        closed = ic["w"] + ic["l"] + mc["w"] + mc["l"]
        if closed == 0:
            return ""
        wins = ic["w"] + mc["w"]; losses = ic["l"] + mc["l"]
        realized = ic["pl"] + mc["pl"]
        wr = wins / closed * 100

        def _row(c):
            """One section, written as a sentence. No ticks or crosses (user, 2026-08-04) — a
            column of ✅/❌ read as a scorecard of individual trades rather than a running total."""
            cc = c["w"] + c["l"]
            if cc == 0:
                return "   No closed trades yet."
            w = c["w"] / cc * 100
            aw = (sum(c["wv"]) / len(c["wv"])) if c["wv"] else None
            al = (sum(c["lv"]) / len(c["lv"])) if c["lv"] else None
            avg = ("   Average win <b>₹{:+,.0f}</b> · average loss <b>{}</b>".format(
                       aw if aw is not None else 0,
                       f"₹{al:+,.0f}" if al is not None else "no loss yet")
                   if (aw is not None or al is not None) else "")
            return (f"   Total trades = <b>{cc}</b> out of which our system achieved "
                    f"<b>{c['w']} Win{'s' if c['w'] != 1 else ''}</b> and "
                    f"<b>{c['l']} Loss{'es' if c['l'] != 1 else ''}</b>.\n"
                    f"   Win-rate <b>{w:.1f}%</b> · P/L <b>₹{c['pl']:+,.0f}</b>"
                    + ("\n" + avg if avg else ""))

        lines = [
            f"📈 <b>Saavi Institutional Trader has till date delivered for live trade from {self._fmt_d(start, with_year=True)}-</b>",
            "",
            "⚡ <b>INTRADAY</b> (same-day expiry)",
            _row(ic),
            "",
            "📅 <b>MONTH-END EXPIRY</b> (multi-day spreads)",
            _row(mc),
            "",
            (f"➕ <b>OVERALL</b> — Total trades = <b>{closed}</b> out of which our system achieved "
             f"<b>{wins} Win{'s' if wins != 1 else ''}</b> and "
             f"<b>{losses} Loss{'es' if losses != 1 else ''}</b>.\n"
             f"   Win-rate <b>{wr:.1f}%</b> · Realized <b>₹{realized:+,.0f}</b>"),
            "",
        ]
        if openn:
            if adv["n"]:
                lines.append(f"📎 Advisory (weak side of a side-qualified name, excluded from the "
                             f"headline): <b>{adv['n']}</b> closed · ₹{adv['pl']:+,.0f}")
            lines.append(f"⏳ Open: <b>{openn} trade{'s' if openn != 1 else ''}</b> · "
                         f"MTM <b>₹{open_pl:+,.0f}</b> — settle by date:")
            groups = {}
            for o in opens:
                groups.setdefault(o["exp"], []).append(o)
            for exp in sorted(groups, key=lambda e: (e is None, e)):
                items = groups[exp]
                n = len(items)
                names = ", ".join(f"{o['sym']} ({o['tag']})" for o in items)
                lines.append(f"   • {self._fmt_d(exp)}: <b>{n} trade{'s' if n != 1 else ''}</b> — {names}")
        else:
            if adv["n"]:
                lines.append(f"📎 Advisory (weak side of a side-qualified name, excluded from the "
                             f"headline): <b>{adv['n']}</b> closed · ₹{adv['pl']:+,.0f}")
            lines.append("⏳ Open: <b>0 trades</b>")
        return "\n".join(lines)

    def _morning_recheck(self, now):
        """09:30 — re-run every gate on the PREVIOUS session's stock-credit calls and say plainly
        whether to buy them today or not. Read-only: signal_recheck writes no book and no trade-log
        row, it only sends one Telegram (de-duped per day inside the module)."""
        try:
            from engine import config as _c
            if not getattr(_c, "SIGNAL_RECHECK_ENABLED", False) or now.weekday() >= 5:
                return
            # TRADING DAYS ONLY (user, 2026-08-05). A weekday check alone still fires on exchange
            # holidays; market_is_trading_today() is the same holiday-aware predicate the scan uses.
            from engine.data_utils import market_is_trading_today
            if not market_is_trading_today():
                # market_is_trading_today() is TIME-gated 09:15-15:40 as well as calendar-gated, so
                # it is False all evening on a perfectly normal trading day. Calling that "exchange
                # holiday" logged nonsense every 5 minutes after the close (found 5-Aug). Only claim
                # a holiday when the clock says we should be trading and the data says we are not.
                _mkt_hours = self.agent.is_market_open()
                logger.info("morning recheck: %s — no message",
                            "exchange holiday" if _mkt_hours else "outside market hours")
                return
            h, m = map(int, _c.SIGNAL_RECHECK_AT.split(":"))
            if (now.hour * 60 + now.minute) < h * 60 + m:
                return
            from engine import signal_recheck
            signal_recheck.run(send=True)
        except Exception as e:
            logger.warning(f"morning recheck: {e}")

    def _in_settle_grace(self) -> bool:
        """True for SETTLE_GRACE_MIN minutes after the F&O close, so the cycle that settles at
        SETTLE_AFTER gets its RESULT + PORTFOLIO Telegrams out at once instead of waiting for the
        next 300 s idle cycle. _outcomes() is throttled to 60 s and is_market_open() is inclusive
        only to 15:40:00, so without this the day's results landed ~15:45."""
        try:
            from engine.config import FNO_CLOSE, SETTLE_GRACE_MIN
            now = datetime.now(IST)
            if now.weekday() >= 5:
                return False
            h, m = map(int, FNO_CLOSE.split(":"))
            close_m = h * 60 + m
            mins = now.hour * 60 + now.minute
            return close_m <= mins <= close_m + SETTLE_GRACE_MIN
        except Exception:
            return False

    def cycle(self):
        now = datetime.now(IST)
        self._market(now)
        self._manage_wakelock()
        # FORWARD RECORD. On the MAIN CYCLE, not inside the 15:36 stock scan, because the 0DTE
        # books settle at 15:40 (SETTLE_AFTER) - four minutes AFTER that scan. Syncing there meant an
        # intraday loss would not reach the DB until the NEXT trading day (found 21-Aug-2026 when the
        # user asked whether actual intraday losses get recorded end of day). Idempotent and cheap,
        # so running it every tick costs nothing and catches every close path within seconds.
        try:
            from engine import forward_record as _fr
            _fr.sync()
        except Exception as e:
            logger.debug(f"forward_record sync: {e}")
        self._maybe_eod(now)
        self._fast_resolve()
        self._swing(now)
        self._stock_credit(now)
        self._monthly_fut(now)
        self._monthly_call(now)
        self._zero_dte(now)
        self._morning_recheck(now)
        try:
            from engine import session_observer
            session_observer.observe(now)   # READ-ONLY recorder; cannot affect a trade
        except Exception as e:
            logger.warning(f"session observer: {e}")
        self._outcomes()   # AFTER the book hooks: the cycle that settles at SETTLE_AFTER (15:40)
                           # notifies in the same pass. _in_settle_grace() keeps the fast tick alive
                           # past the close so the 60 s throttle cannot push results to ~15:45.
        from engine import config as _cfg
        if (getattr(_cfg, "SCAN_3FAMILY_ENABLED", True) and self.agent.is_market_open()
                and (time.time() - self._last_scan) >= SCAN_INTERVAL):
            self._last_scan = time.time()
            try:
                self._scan(now)
            except Exception as e:
                logger.error(f"scan cycle failed: {e}", exc_info=True)

    def run(self):
        logger.info(f"Engine runner started. DB stats: {store.stats()}")
        # Record any tunable that moved since the last start, before trading anything. Answers
        # "did we change something?" from the record instead of from git archaeology.
        try:
            from engine import config_ledger
            config_ledger.record("engine start")
        except Exception as e:
            logger.warning(f"config ledger: {e}")
        while True:
            try:
                self.cycle()
            except Exception as e:
                logger.error(f"cycle failed: {e}", exc_info=True)
            # tight loop during market hours; idle slowly when closed (still writes a
            # market snapshot every cycle and catches the 15:31-15:55 EOD window).
            time.sleep(TICK if (self.agent.is_market_open() or self._in_settle_grace()) else 300)


if __name__ == "__main__":
    if "--once" in sys.argv:        # one cycle (for testing), forces a scan
        r = EngineRunner()
        now = datetime.now(IST)
        r._market(now)
        if r.agent.is_market_open():
            r._scan(now)
        else:
            logger.info("market closed — wrote market snapshot only")
        print("DB stats:", store.stats())
    else:
        EngineRunner().run()
