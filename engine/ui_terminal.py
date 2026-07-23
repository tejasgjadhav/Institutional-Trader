"""
Institutional Trader — Dark Terminal Dashboard (Bloomberg-style)

Black screen, green/amber accents. Screen 1 = Latest PM Decisions.
Sections: PM DECISIONS · WATCHLIST · ALPHA · TRADE LOG · INFO
Live Nifty / BankNifty / VIX from Upstox V3. Clear active-tab highlight.
"""
import sys
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QStatusBar,
    QHeaderView, QStackedWidget, QTextEdit, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QBrush

from engine.config import IST, DATA_DIR
from engine.agent import Agent
from engine.trade_log import TradeLog
from engine.data_utils import get_last_5_trading_days

logger = logging.getLogger(__name__)

# READ-ONLY VIEWER: the GUI never scans/executes/books. The headless engine
# (engine.engine_runner, run by launchd) does all that and writes these files;
# the GUI only reads + displays them.
import os as _os
LATEST_SCAN = _os.path.join(DATA_DIR, "latest_scan.json")
MARKET_SNAP = _os.path.join(DATA_DIR, "market_snapshot.json")
SWING_SNAP = _os.path.join(DATA_DIR, "swing.json")
SWING_BOOK = _os.path.join(DATA_DIR, "swing_positions.json")
MONTHLY_SNAP = _os.path.join(DATA_DIR, "monthly_fut.json")
MONTHLY_CALL_SNAP = _os.path.join(DATA_DIR, "monthly_call.json")
STOCKCR_SNAP = _os.path.join(DATA_DIR, "stock_credit.json")
STOCKCR2_SNAP = _os.path.join(DATA_DIR, "stock_credit_v2.json")
STOCKCR_BOOK = _os.path.join(DATA_DIR, "stock_credit_positions.json")
STOCKCR2_BOOK = _os.path.join(DATA_DIR, "stock_credit_v2_positions.json")
ZDTE_BOOK = _os.path.join(DATA_DIR, "zero_dte_positions.json")
ZDTE_STATUS = _os.path.join(DATA_DIR, "zero_dte_status.json")
SDTE_BOOK = _os.path.join(DATA_DIR, "sensex_dte_positions.json")
SDTE_STATUS = _os.path.join(DATA_DIR, "sensex_dte_status.json")
BDTE_BOOK = _os.path.join(DATA_DIR, "bnf_dte_positions.json")
BDTE_STATUS = _os.path.join(DATA_DIR, "bnf_dte_status.json")

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#000000"   # pure black screen
PANEL       = "#0a0e14"   # near-black panels
PANEL_LIGHT = "#11161f"   # alt rows
BORDER      = "#1c2433"
GREEN       = "#00e676"   # primary accent (bullish / active)
RED         = "#ff5252"   # bearish / loss
AMBER       = "#ffb300"   # warnings / VIX / PM highlight
CYAN        = "#29b6f6"   # info
TEXT        = "#d7dde5"   # body text
TEXT_DIM    = "#6b7785"   # secondary text
PURPLE      = "#b388ff"   # ORB+VWAP parallel strategy


# NOTE: this file is the READ-ONLY VIEWER. It deliberately has NO scan/fetch worker — the
# headless engine (engine_runner) does ALL scanning, signal-firing, resolving and data
# fetching, and writes to disk (latest_scan.json / market_snapshot.json / the DBs /
# trade_log.json). The viewer only READS those files and renders them. Do not add a worker
# that calls run_scan()/get_market_snapshot() here — that would break the decoupling.


class TerminalApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("INSTITUTIONAL TRADER · TERMINAL")
        self.setGeometry(40, 40, 1700, 1000)
        self.setMinimumSize(960, 620)   # keep nav + sections usable when resized down
        self.setStyleSheet(self._qss())

        self.agent = Agent()
        self.trade_log = TradeLog()
        self.last_scan_results = []
        self._swing_rows = []
        self._monthly_rows = []
        self._monthly_call_rows = []
        self._stockcr_rows = []
        self._stockcr2_rows = []
        self.active_screen = 0
        self._mkt_running = False
        self._scanning = False
        self.sim_trades = self._load_sim_trades()

        self._check_recording_window()
        self._build_ui()
        self._refresh_market_data()
        self._load_latest_scan()    # read-only: show whatever the engine last wrote
        self._refresh_log()      # show simulation immediately (or live paper trades)
        self._refresh_pm()        # show today's already-fired signals (seeded from log)
        self.trigger_scan()       # only scans if market is open
        self._refresh_index_signals()   # populate the ORB+VWAP index section now

        # timers
        self.scan_timer = QTimer(); self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(15_000)  # 15s — re-read the engine's latest scan from disk
        # Outcome timer: refresh PM DECISIONS + TRADE LOG fast (5s) so a WIN/LOSS the engine
        # just booked shows up near-immediately, decoupled from the heavier 15s full scan refresh.
        self.outcome_timer = QTimer(); self.outcome_timer.timeout.connect(self._refresh_outcomes)
        self.outcome_timer.start(5_000)
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(1000)
        # Market data: poll fast (2s) when open, slow (20s) when closed.
        self.mkt_timer = QTimer(); self.mkt_timer.timeout.connect(self._refresh_market_data)
        self.mkt_timer.start(3000)
        # ORB+VWAP index signals — refresh every 60s independent of the market-gated scan
        self.idx_timer = QTimer(); self.idx_timer.timeout.connect(self._refresh_index_signals)
        self.idx_timer.start(60_000)

    def closeEvent(self, event):
        """On quit: stop timers and wait for worker threads so we never destroy a
        still-running QThread (the 'Destroyed while thread is still running' warning)."""
        for tname in ("scan_timer", "outcome_timer", "clock_timer", "mkt_timer", "idx_timer"):
            t = getattr(self, tname, None)
            try:
                if t is not None: t.stop()
            except RuntimeError:
                pass
        for wname in ("worker", "idx_worker", "mkt_worker"):
            w = getattr(self, wname, None)
            try:
                if w is not None and w.isRunning():
                    w.quit(); w.wait(2000)
            except RuntimeError:
                pass
        super().closeEvent(event)

    def _refresh_index_signals(self):
        """READ-ONLY: index (ORB+VWAP) rows come from the engine's latest_scan.json,
        loaded by _load_latest_scan — just re-render them here (no live index scan)."""
        self._load_latest_scan()
        self._refresh_orbvwap()

    # ── recording window ──────────────────────────────────────────────────────
    def _check_recording_window(self):
        last5 = get_last_5_trading_days()
        self.recording_mode = datetime.now().date() in last5
        self.last5 = last5

    def _load_sim_trades(self) -> list:
        """Load the cached last-30-day option simulation (shown when market is closed)."""
        import json, os
        from engine.config import DATA_DIR
        path = os.path.join(DATA_DIR, "sim_option_trades.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # ── stylesheet ────────────────────────────────────────────────────────────
    def _qss(self) -> str:
        return f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {TEXT};
    font-family: 'Menlo','Monaco','Courier New',monospace; font-size: 15px; }}
QLabel {{ color: {TEXT}; }}
QTableWidget {{ background-color: {PANEL}; alternate-background-color: {PANEL_LIGHT};
    border: 1px solid {BORDER}; gridline-color: {BORDER}; color: {TEXT};
    selection-background-color: {BORDER}; font-size: 16px; }}
QTableWidget::item {{ padding: 9px 6px; border: none; }}
QHeaderView::section {{ background-color: {PANEL_LIGHT}; color: {GREEN};
    padding: 9px; border: none; border-bottom: 1px solid {BORDER};
    font-weight: bold; letter-spacing: 1px; font-size: 14px; }}
QTableCornerButton::section {{ background-color: {PANEL_LIGHT}; border: none; }}
QStatusBar {{ background-color: {PANEL}; color: {TEXT_DIM}; font-size: 14px; }}
QTextEdit {{ background-color: {PANEL}; color: {TEXT};
    border: 1px solid {BORDER}; font-size: 15px; }}
QScrollBar:vertical {{ background: {PANEL}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; }}
"""

    # ── build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget(); v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

        v.addWidget(self._header())
        v.addWidget(self._market_bar())
        v.addWidget(self._tab_bar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._screen_pm())        # 0
        self.stack.addWidget(self._screen_watchlist())  # 1
        self.stack.addWidget(self._screen_swing())      # 2
        self.stack.addWidget(self._screen_log())        # 3
        self.stack.addWidget(self._screen_studies())    # 4
        self.stack.addWidget(self._screen_readme())     # 5
        self.stack.addWidget(self._screen_zero_dte())   # 6
        v.addWidget(self.stack, 1)

        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.setCentralWidget(root)
        self._highlight_tab(0)

    def _header(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background-color:{PANEL}; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(w); h.setContentsMargins(16, 10, 16, 10)

        title = QLabel("◤ INSTITUTIONAL TRADER")
        title.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{GREEN}; letter-spacing:2px;")
        h.addWidget(title)

        sub = QLabel("NSE INTRADAY OPTIONS  -  PAPER")
        sub.setFont(QFont("Menlo", 9)); sub.setStyleSheet(f"color:{TEXT_DIM};")
        h.addWidget(sub); h.addSpacing(20); h.addStretch()

        mode = "RECORDING" if self.recording_mode else "OBSERVATION"
        mode_color = GREEN if self.recording_mode else AMBER
        self.mode_label = QLabel(f"{mode}  -  SIMULATION")
        self.mode_label.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        self.mode_label.setStyleSheet(f"color:{mode_color};")
        h.addWidget(self.mode_label)
        return w

    def _market_bar(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background-color:{BG}; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(w); h.setContentsMargins(16, 8, 16, 8); h.setSpacing(16)

        self.nifty_lbl = self._ticker_label("NIFTY 50", "—")
        self.bnf_lbl   = self._ticker_label("BANKNIFTY", "—")
        self.vix_lbl   = self._ticker_label("INDIA VIX", "—", AMBER)
        for lbl in (self.nifty_lbl, self.bnf_lbl, self.vix_lbl):
            h.addWidget(lbl)
        h.addStretch()
        # live clock (top-right) — ticks every second
        self.clock_lbl = QLabel("—")
        self.clock_lbl.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        self.clock_lbl.setStyleSheet(f"color:{CYAN};")
        h.addWidget(self.clock_lbl)
        return w

    def _ticker_label(self, name, value, color=None) -> QLabel:
        lbl = QLabel(f"{name}  {value}")
        lbl.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color:{color or TEXT};")
        lbl.setProperty("ticker_name", name)
        return lbl

    def _tab_bar(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background-color:{PANEL}; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(w); h.setContentsMargins(8, 0, 8, 0); h.setSpacing(2)

        self.tab_btns = []
        tabs = [("PM DECISIONS", 0), ("INTRADAY DECISIONS", 6),
                ("SWING TRADE LOG", 2), ("TRADE LOG", 3), ("STUDIES", 4), ("README", 5)]
        for label, idx in tabs:
            b = QPushButton(label)
            b.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
            b.setMinimumHeight(44); b.setMinimumWidth(160)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.switch(i))
            b.setProperty("stack_idx", idx)   # button order ≠ stack order (INTRADAY sits 2nd)
            self.tab_btns.append(b); h.addWidget(b)
        h.addStretch()

        # Autonomous — no scan button. A live indicator shows the auto-scan state.
        self.auto_lbl = QLabel("AUTO")
        self.auto_lbl.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.auto_lbl.setStyleSheet(f"color:{TEXT_DIM}; padding:0 14px;")
        h.addWidget(self.auto_lbl)
        return w

    def _highlight_tab(self, idx: int):
        for b in self.tab_btns:
            if b.property("stack_idx") == idx:
                b.setStyleSheet(
                    f"background-color:{BG};color:{GREEN};border:none;"
                    f"border-top:2px solid {GREEN};border-bottom:2px solid {GREEN};")
            else:
                b.setStyleSheet(
                    f"QPushButton{{background-color:{PANEL};color:{TEXT_DIM};border:none;}}"
                    f"QPushButton:hover{{color:{TEXT};}}")

    # ── screens ───────────────────────────────────────────────────────────────
    def _panel_title(self, text, color=GREEN) -> QLabel:
        l = QLabel(text); l.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{color}; padding:10px 4px; letter-spacing:1px;")
        return l

    PM_COLS = ["TIME", "STOCK", "TYPE", "STRIKE", "EXPIRY", "ENTRY PREM", "CURRENT",
               "TARGET +10%", "STOP -20%", "LOT", "CAPITAL", "STATUS"]
    ORBVWAP_COLS = ["TIME", "INDEX", "TYPE", "STRIKE", "EXPIRY", "ENTRY",
                    "EXIT RULE", "STOP -20%", "CURRENT", "LOT", "STATUS"]
    # Credit spreads on PM DECISIONS are shown TWO ROWS per trade (a SELL row + a BUY row).
    PM_CREDIT_COLS = ["ACTION", "INSTRUMENT", "LOT", "PREMIUM", "EXPIRY", "AMOUNT", "P&L / STATUS"]
    # BRK = the STRONGEST Donchian window that broke (D5/D10/D15/D20) — D10+ is a more durable
    # breakout than a bare D5 (see studies/DONCHIAN_D5_VS_D10.md).
    WATCH_COLS = ["STOCK", "SIDE", "BRK", "SELL / BUY", "EXPIRY", "LOT", "C/W", "PREM", "LIQ", "MAX ₹+", "MAX ₹−", "RESULT"]

    def _make_pm_table(self) -> QTableWidget:
        t = QTableWidget(); t.setColumnCount(len(self.PM_COLS))
        t.setHorizontalHeaderLabels(self.PM_COLS)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setAlternatingRowColors(True); t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)
        return t

    def _section_label(self, text, color) -> QLabel:
        l = QLabel(text); l.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        l.setWordWrap(True)   # never let a long header run off the panel
        l.setStyleSheet(f"color:{color}; padding:8px 4px 2px 4px;")
        return l

    def _credit_cols(self, t):
        """Fixed widths for the 7 PM_CREDIT_COLS (ACTION/INSTRUMENT/LOT/PREMIUM/EXPIRY/AMOUNT/
        P&L·STATUS) summing ~1026px — same total as the watchlist. Stretch mode ballooned the
        table past the window and clipped the last column; fixed widths keep it single-screen."""
        h = t.horizontalHeader()
        for _c, _px in enumerate((100, 300, 88, 128, 120, 150, 140)):
            h.setSectionResizeMode(_c, QHeaderView.ResizeMode.Fixed)
            h.resizeSection(_c, _px)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _screen_pm(self) -> QWidget:
        """PM DECISIONS — every strategy book, each section sized to its content inside a scroll area."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(6)
        v.addWidget(self._panel_title("LATEST PM DECISIONS  -  place manually in Upstox", AMBER))

        # Dynamic "where to look NOW" banner (updated each refresh from the IST clock).
        self.pm_now_hint = QLabel("—"); self.pm_now_hint.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.pm_now_hint.setWordWrap(True)
        self.pm_now_hint.setStyleSheet(f"color:{AMBER}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(self.pm_now_hint)

        # UNION WATCHLIST — always-on engine heartbeat. Today's breakout stocks stepping through the
        # gates with a tick-bar; proves the engine ran even on a 0-signal day. Reads union_watchlist.json.
        self.pm_watch_hdr = QLabel("UNION WATCHLIST — waiting for first scan…")
        self.pm_watch_hdr.setFont(QFont("Menlo", 12, QFont.Weight.Bold)); self.pm_watch_hdr.setWordWrap(True)
        self.pm_watch_hdr.setStyleSheet(f"color:{CYAN}; padding:6px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(self.pm_watch_hdr)
        self.pm_watch = QTableWidget(); self.pm_watch.setColumnCount(len(self.WATCH_COLS))
        self.pm_watch.setHorizontalHeaderLabels(self.WATCH_COLS)
        # Single-screen guarantee: FIXED px for the compact columns, Stretch for the text ones —
        # stretch columns absorb exactly the remaining viewport width, so the table can never be
        # wider than the screen (ResizeToContents inflated the minimum width and caused panning).
        _wh = self.pm_watch.horizontalHeader()
        # ALL columns FIXED (no Stretch): the outer scroll widget is wider than the window
        # (the credit tables below force it), so a Stretch column balloons and pushes the last
        # columns off-screen. Fixed widths summing ~1030px keep the whole row on one screen.
        for _c, _px in ((0, 120), (1, 72), (2, 52), (3, 300), (4, 92), (5, 60),
                        (6, 80), (7, 96), (8, 84), (9, 116), (10, 116), (11, 104)):
            # STOCK,SIDE,BRK,SELL/BUY,EXPIRY,LOT,C/W,PREM,LIQ,MAX+,MAX-,RESULT (sum ~1276px, fits ~1400 window)
            _wh.setSectionResizeMode(_c, QHeaderView.ResizeMode.Fixed)      # STOCK,DIR,SIDE,BRK,legs,C/W,PREM,LIQ,RESULT
            _wh.resizeSection(_c, _px)
        self.pm_watch.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # single view — never scroll sideways
        self.pm_watch.setAlternatingRowColors(True); self.pm_watch.verticalHeader().setVisible(False)
        self.pm_watch.verticalHeader().setDefaultSectionSize(28); self.pm_watch.setMaximumHeight(260)
        self.pm_watch.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_watch)

        # STOCK CREDIT v2 (TP-50 upgrade) — replaces the retired ORB+VWAP section (thin/inconsistent
        # on real 2019→date data). Runs PARALLEL to v1: short 2-OTM · width 4 · TP 50% · stop 3×.
        pmv2 = QLabel("★ STOCK CREDIT v2 UNION · sell the breakout spread, book at half credit · 87% win OOS · ~5–6/mo · SELL ★")
        pmv2.setWordWrap(True)
        pmv2.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        pmv2.setStyleSheet(f"color:#000000; background-color:{AMBER}; padding:8px; border:2px solid {AMBER}; border-radius:4px;")
        v.addWidget(pmv2)
        self.pm_stockcr2 = QTableWidget(); self.pm_stockcr2.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_stockcr2.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_stockcr2)
        self.pm_stockcr2.setAlternatingRowColors(True); self.pm_stockcr2.verticalHeader().setVisible(False)
        self.pm_stockcr2.verticalHeader().setDefaultSectionSize(32)
        self.pm_stockcr2.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pm_stockcr2.setStyleSheet(f"QTableWidget {{ border: 2px solid {AMBER}; }}")
        v.addWidget(self.pm_stockcr2, 1)

        # STOCK CREDIT SPREADS — the 4th strategy (high-frequency fade on single stocks).
        v.addWidget(self._section_label(
            "STOCK CREDIT SPREADS v1 · fade · 73% win OOS (TP-75) · ~16/mo · SELL", GREEN))
        self.pm_stockcr = QTableWidget(); self.pm_stockcr.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_stockcr.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_stockcr)
        self.pm_stockcr.setAlternatingRowColors(True); self.pm_stockcr.verticalHeader().setVisible(False)
        self.pm_stockcr.verticalHeader().setDefaultSectionSize(32)
        self.pm_stockcr.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_stockcr, 1)

        # SWING CREDIT SPREADS — the 3rd strategy (multi-day · theta · SELL against the breakout).
        v.addWidget(self._section_label(
            "SWING CREDIT · NIFTY/FINNIFTY · fade · forward-test only · ~3/mo · SELL", CYAN))
        self.pm_swing = QTableWidget(); self.pm_swing.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_swing.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_swing)
        self.pm_swing.setAlternatingRowColors(True); self.pm_swing.verticalHeader().setVisible(False)
        self.pm_swing.verticalHeader().setDefaultSectionSize(34)
        self.pm_swing.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_swing, 1)

        # MONTHLY FUTURES PULLBACK — the 5th strategy (monthly cycle · BUY front-month futures).
        # Signals-only paper test; needs ~Rs 15L to trade for real. Earnings-skip applied live.
        v.addWidget(self._section_label(
            "MONTHLY FUTURES PULLBACK · REV1-v2 · 76% win OOS · 5/cycle · BUY FUT (paper, ~₹15L)", AMBER))
        self.pm_monthly = QTableWidget(); self.pm_monthly.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_monthly.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_monthly)
        self.pm_monthly.setAlternatingRowColors(True); self.pm_monthly.verticalHeader().setVisible(False)
        self.pm_monthly.verticalHeader().setDefaultSectionSize(32)
        self.pm_monthly.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_monthly, 1)

        # MONTHLY LONG-CALL PULLBACK — the 6th strategy. SHELVED 2026-07-13 (unreliable — see
        # STUDIES). Section only rendered while MONTHLY_CALL_ENABLED; hidden when shelved.
        from engine import config as _cfg
        if getattr(_cfg, "MONTHLY_CALL_ENABLED", False):
            v.addWidget(self._section_label(
                "MONTHLY LONG-CALL PULLBACK · SHELVED (high variance) · 5/cycle · BUY CALL", AMBER))
            self.pm_monthly_call = QTableWidget(); self.pm_monthly_call.setColumnCount(len(self.PM_CREDIT_COLS))
            self.pm_monthly_call.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
            self._credit_cols(self.pm_monthly_call)
            self.pm_monthly_call.setAlternatingRowColors(True); self.pm_monthly_call.verticalHeader().setVisible(False)
            self.pm_monthly_call.verticalHeader().setDefaultSectionSize(32)
            self.pm_monthly_call.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            v.addWidget(self.pm_monthly_call, 1)

        # 3-Family stock-options section retired from view 2026-07-07 (engine still scans)
        self.pm_stock = self._make_pm_table()
        self.pm_stock.setVisible(False)


        self.pm_empty = QLabel("Credit-spread signals appear ~15:10; 0DTE books live on the INTRADAY DECISIONS tab.")
        self.pm_empty.setStyleSheet(f"color:{TEXT_DIM}; padding:6px 4px;")
        self.pm_empty.setFont(QFont("Menlo", 12))
        v.addWidget(self.pm_empty)
        v.addStretch(1)
        return self._scroll(inner)

    # Active gates only (G4 chase + G5 wide were retired 2026-06; min-premium folded into LIQ).
    WL_COLS = ["TICKER", "ALPHA-Z", "DIR", "G1 ALPHA", "G2 ORB", "G3 ALIGN",
               "PREM+LIQ", "PROGRESS"]

    def _screen_watchlist(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title(
            "WATCHLIST  -  passed Gate 1 (alpha), progressing through Gates 2-6 to PM DECISIONS"
            "      ( ★ = priority stock: persistent-winner tilt, ~75% hist / 110 trades )"))
        self.wl_table = QTableWidget()
        self.wl_table.setColumnCount(len(self.WL_COLS))
        self.wl_table.setHorizontalHeaderLabels(self.WL_COLS)
        _wlhdr = self.wl_table.horizontalHeader()
        _wlhdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # TICKER column sizes to its content so the "★ NAME.NS" of priority stocks isn't
        # clipped to "★ …"; the gate columns still stretch to fill the rest.
        _wlhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.wl_table.setAlternatingRowColors(True)
        self.wl_table.verticalHeader().setVisible(False)
        v.addWidget(self.wl_table)
        # legend
        from engine import config as C
        leg = QLabel("PASS = gate cleared, wait = pending    |    G1 alpha, G2 ORB breakout+volume, "
                     "G3 aligned with Nifty, PREM+LIQ = OTM+1 option premium >= "
                     f"Rs{C.MIN_OPTION_PREMIUM:.0f} AND liquid (spread <={C.MAX_OPTION_SPREAD_PCT}%, "
                     f"OI >={C.MIN_OPTION_OI}; checked only after G1-G3)    |    all 4 PASS = fires "
                     "on PM DECISIONS.   (G4 don't-chase & G5 wide-open retired 2026-06 — didn't "
                     "hold on the real-option backtest.)")
        leg.setStyleSheet(f"color:{TEXT_DIM}; padding:6px 2px;"); leg.setWordWrap(True)
        v.addWidget(leg)
        return w

    # Trade log: each spread = TWO leg rows (one below the other), per-leg P&L, then the NET.
    SWING_TAB_COLS = ["ENTERED", "LEG", "INSTRUMENT", "LOT", "ENTRY", "NOW/EXIT", "LEG P&L", "NET / STATUS"]

    def _screen_swing(self) -> QWidget:
        """SWING TRADES — the credit-spread TRADE LOG, split into the two strategies. Each row shows
        exactly what to SELL and what to BUY (strike + premium), expiry, net credit and P&L."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("SWING TRADE LOG  -  credit spreads (what to SELL & BUY)", CYAN))
        # ★ STOCK CREDIT v2 — the TP-50 upgrade. Kept FIRST + gold-highlighted: the leader book,
        # watch it closest. Backtest stats live on PM DECISIONS / STUDIES; this log shows LIVE only.
        v2hdr = QLabel("★ STOCK CREDIT v2 UNION ★   sell the breakout spread · book at half credit · stop 3×")
        v2hdr.setWordWrap(True)
        v2hdr.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        v2hdr.setStyleSheet(f"color:#000000; background-color:{AMBER}; padding:8px; border:2px solid {AMBER}; border-radius:4px;")
        v.addWidget(v2hdr)
        self.sw_stk2_stats = self._stats_label()
        self.sw_stk2_stats.setStyleSheet(f"color:{AMBER}; padding:8px; background-color:{PANEL}; border:2px solid {AMBER};")
        v.addWidget(self.sw_stk2_stats)
        self.sw_stk2 = self._make_log_table(self.SWING_TAB_COLS)
        self.sw_stk2.setStyleSheet(f"QTableWidget {{ border: 2px solid {AMBER}; }}")
        v.addWidget(self.sw_stk2)
        v.addWidget(self._section_label("INDEX SWING — NIFTY/FINNIFTY · fade the breakout · hold to expiry (fwd-test only) · ~3/mo", CYAN))
        self.sw_idx_stats = self._stats_label(); v.addWidget(self.sw_idx_stats)
        self.sw_idx = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sw_idx)
        v.addWidget(self._section_label("STOCK CREDIT SPREADS v1 · fade the breakout · ~10/mo · SELL", GREEN))
        self.sw_stk_stats = self._stats_label(); v.addWidget(self.sw_stk_stats)
        self.sw_stk = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sw_stk)
        v.addStretch(1)
        return self._scroll(inner)

    def _stats_label(self) -> QLabel:
        l = QLabel("—"); l.setFont(QFont("Menlo", 12, QFont.Weight.Bold)); l.setWordWrap(True)
        l.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        return l

    def _screen_zero_dte(self) -> QWidget:
        """INTRADAY DECISIONS — the 0DTE NIFTY expiry-day CE credit spread (5th strategy).
        One defined-risk trade per weekly expiry day, opened ~9:16, settled the same day 15:30."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("INTRADAY DECISIONS  -  0DTE NIFTY expiry-day call credit spread", CYAN))
        # dynamic pre-market checker — engine refreshes data/zero_dte_status.json every ~2-5 min
        self.zdte_status = QLabel("checking today's status…")
        self.zdte_status.setWordWrap(True)
        self.zdte_status.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        self.zdte_status.setStyleSheet(f"color:{TEXT_DIM}; padding:10px; background-color:{PANEL}; border:2px solid {BORDER};")
        v.addWidget(self.zdte_status)
        hdr = QLabel("★ 0DTE NIFTY CE SPREAD — 90% WIN OOS · +5.9%/MARGIN/TRADE · EVERY TUESDAY 9:16 · "
                     "MARGIN ≈ ₹14k/LOT (= MAX LOSS) · FLIP: sells PE in up-momentum weeks, CE otherwise")
        hdr.setWordWrap(True)
        hdr.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:#000000; background-color:{CYAN}; padding:8px; border:2px solid {CYAN}; border-radius:4px;")
        v.addWidget(hdr)
        how = QLabel("RULES · trade ONLY when the strip above is GREEN (engine skips hot weeks)\n"
                     "  the strip tells you the SIDE: FLIP sells PE in up-momentum weeks (5-day ≥+1%), else CE\n"
                     "  9:16   SELL the chosen leg ~0.5% OTM · BUY the hedge 200 pts further out (same-day expiry)\n"
                     "  order  basket, wing (BUY) first, limit at mid · then NOTHING — no stop, no adjusting\n"
                     "  15:30  settles automatically · wins ~9 weeks in 10 · the rare loss can cost the full margin\n"
                     "FLIP edge: 87.1% win / +₹1.92L since 2019 vs 84.7% / +₹1.17L CE-only. Full research: STUDIES tab.")
        how.setWordWrap(True); how.setFont(QFont("Menlo", 11))
        how.setStyleSheet(f"color:{TEXT}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(how)
        self.zdte_stats = self._stats_label()
        v.addWidget(self.zdte_stats)
        self.zdte_table = self._make_log_table(self.SWING_TAB_COLS)
        self.zdte_table.setStyleSheet(f"QTableWidget {{ border: 2px solid {CYAN}; }}")
        v.addWidget(self.zdte_table, 1)
        v.addWidget(self._section_label("SENSEX 0DTE — THURSDAYS · 88.8% win · +7.6%/margin "
                                        "(89 expiries · 21-month history only · unfiltered)", AMBER))
        self.sdte_status = self._stats_label(); v.addWidget(self.sdte_status)
        self.sdte_stats = self._stats_label(); v.addWidget(self.sdte_stats)
        self.sdte_table = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sdte_table, 1)
        v.addWidget(self._section_label("BANKNIFTY 0DTE — MONTHLY EXPIRY (~1/mo) · 79.5%/+7.4%m "
                                        "2019-24 weeklies + 91%/+11%m recent monthlies", PURPLE))
        self.bdte_status = self._stats_label(); v.addWidget(self.bdte_status)
        self.bdte_stats = self._stats_label(); v.addWidget(self.bdte_stats)
        self.bdte_table = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.bdte_table, 1)
        v.addStretch(0)
        return self._scroll(inner)

    def _fill_dte_status(self, label, path, name):
        import json
        try:
            st = json.load(open(path)) if _os.path.exists(path) else {}
        except Exception:
            st = {}
        v = st.get("verdict")
        if v == "EXPECTED":
            done = " · ENTERED ✓" if st.get("entered_today") else ""
            label.setText(f"  ✓ {name} SIGNAL EXPECTED TODAY 9:16 · EXPIRY {st.get('date')} · preview SELL ~{st.get('preview_short')} CE / "
                          f"BUY ~{st.get('preview_wing')} CE (final = live 9:16 price){done}")
            label.setStyleSheet(f"color:#000000; background-color:{GREEN}; padding:8px;")
        elif v == "NO-ENTRY":
            label.setText(f"  {name}: not an expiry day · NEXT EXPIRY {st.get('next_expiry','?')}")
            label.setStyleSheet(f"color:{TEXT_DIM}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        else:
            label.setText(f"  {name}: status pending (engine writes every ~2 min)")
            label.setStyleSheet(f"color:{TEXT_DIM}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")

    def _refresh_zero_dte_tab(self):
        if not hasattr(self, "zdte_table"):
            return
        try:
            self._fill_swing_table(self.zdte_table, ZDTE_BOOK, self.zdte_stats, open_only=True)
            if hasattr(self, "log_stats"):
                import json as _j
                W = L = 0; rs = 0.0
                for bp in (ZDTE_BOOK, SDTE_BOOK, BDTE_BOOK):
                    try:
                        for p in (_j.load(open(bp)) if _os.path.exists(bp) else []):
                            if p.get("status") == "WIN": W += 1
                            elif p.get("status") == "LOSS": L += 1
                            if p.get("status") in ("WIN", "LOSS"):
                                q = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
                                rs += (p.get("pnl_pts", 0.0) or 0.0) * q
                    except Exception:
                        pass
                wr = W / (W + L) * 100 if (W + L) else 0
                self.log_stats.setText(f"  INTRADAY 0DTE (all 3 books, live paper): {W} W / {L} L · "
                                       f"WIN {wr:.0f}% · booked Rs {rs:+,.0f}")
                self.log_stats.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; "
                                             f"border:2px solid {CYAN}; font-weight:bold;")
            if hasattr(self, "log_zdte"):
                self._fill_swing_table(self.log_zdte, ZDTE_BOOK)   # full history in TRADE LOG tab
            if hasattr(self, "log_sdte"):
                self._fill_swing_table(self.log_sdte, SDTE_BOOK)
                self._fill_swing_table(self.log_bdte, BDTE_BOOK)
            if hasattr(self, "sdte_table"):
                self._fill_swing_table(self.sdte_table, SDTE_BOOK, self.sdte_stats, open_only=True)
                self._fill_swing_table(self.bdte_table, BDTE_BOOK, self.bdte_stats, open_only=True)
                self._fill_dte_status(self.sdte_status, SDTE_STATUS, "SENSEX")
                self._fill_dte_status(self.bdte_status, BDTE_STATUS, "BANKNIFTY")
        except Exception as e:
            logger.warning(f"zero_dte tab fill: {e}")
        try:
            import json
            st = json.load(open(ZDTE_STATUS)) if _os.path.exists(ZDTE_STATUS) else {}
            v = st.get("verdict")
            rv = st.get("rv5")
            rvtxt = f"rv5 {rv:.2f}% vs limit {st.get('rv5_max')}%" if rv is not None else "rv5 n/a (fails open)"
            asof = (st.get("ts") or "")[11:16]
            if v == "EXPECTED":
                done = "  ·  ENTERED ✓ (see book below)" if st.get("entered_today") else ""
                self.zdte_status.setText(
                    f"  ✓ SIGNAL EXPECTED TODAY at 9:16  ·  NIFTY weekly EXPIRY {st.get('date')}  ·  {rvtxt} (calm){done}\n"
                    f"  preview off last spot {st.get('spot')}: SELL ~{st.get('preview_short')} CE / BUY ~{st.get('preview_wing')} CE — "
                    f"FINAL strikes come from the LIVE 9:15-9:16 price, not the previous close  (as of {asof})")
                self.zdte_status.setStyleSheet(f"color:#000000; background-color:{GREEN}; padding:10px; border:2px solid {GREEN};")
            elif v == "SKIP":
                self.zdte_status.setText(
                    f"  ✗ NO TRADE THIS WEEK — calm-regime filter says SKIP  ·  {rvtxt} (hot tape)  (as of {asof})")
                self.zdte_status.setStyleSheet(f"color:#000000; background-color:{AMBER}; padding:10px; border:2px solid {AMBER};")
            elif v == "NO-ENTRY":
                self.zdte_status.setText(
                    f"  — not an expiry day  ·  next NIFTY weekly expiry: {st.get('next_expiry','?')}  ·  {rvtxt}  (as of {asof})")
                self.zdte_status.setStyleSheet(f"color:{TEXT_DIM}; padding:10px; background-color:{PANEL}; border:2px solid {BORDER};")
        except Exception as e:
            logger.warning(f"zero_dte status fill: {e}")

    LOG_COLS = ["TIME", "UNDERLYING", "OPT", "DIR", "ENTRY", "TARGET", "STOP", "OUTCOME", "P&L"]
    SWING_LOG_COLS = ["ENTERED", "INDEX", "SPREAD (sell/buy)", "CREDIT", "NOW/EXIT", "OUTCOME", "P&L"]
    STOCKCR_LOG_COLS = ["ENTERED", "STOCK", "SPREAD (sell/buy)", "C/W", "CREDIT", "NOW/EXIT", "OUTCOME", "P&L"]

    def _make_log_table(self, cols=None) -> QTableWidget:
        cols = cols or self.LOG_COLS
        t = QTableWidget(); t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setAlternatingRowColors(True); t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(36)
        return t

    def _screen_log(self) -> QWidget:
        """TRADE LOG — the BUY strategies (3-Family stocks + ORB index). Credit spreads (SELL) are
        in the SWING TRADES tab. LIVE paper vs SIMULATION kept separate."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(6)
        v.addWidget(self._panel_title("TRADE LOG  -  intraday 0DTE books (2-leg format)"))

        # LIVE / SIMULATION toggle
        self.log_view = "live"
        toggle = QWidget(); th = QHBoxLayout(toggle); th.setContentsMargins(0, 0, 0, 0); th.setSpacing(6)
        self.log_live_btn = QPushButton("LIVE PAPER TRADES")
        self.log_sim_btn = QPushButton("SIMULATION (30-day historical)")
        for b in (self.log_live_btn, self.log_sim_btn):
            b.setFont(QFont("Menlo", 11, QFont.Weight.Bold)); b.setMinimumHeight(34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_live_btn.clicked.connect(lambda: self._set_log_view("live"))
        self.log_sim_btn.clicked.connect(lambda: self._set_log_view("sim"))
        th.addWidget(self.log_live_btn); th.addWidget(self.log_sim_btn); th.addStretch()
        toggle.setVisible(False)  # 3-Family retired from view 2026-07-07 (user: better books elsewhere)

        self.log_stats = QLabel("—")
        self.log_stats.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.log_stats.setWordWrap(True)   # wrap to a 2nd line instead of overflowing (no horizontal drag)
        self.log_stats.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(self.log_stats)

        # Three separate logs, one per strategy.
        # 1) STOCK OPTIONS — the 3-Family intraday buying system (most trades).
        # BUY strategies only here. The credit-spread (SELL) logs live in the SWING TRADES tab.
        self.log_stock = self._make_log_table(); self.log_stock.setVisible(False)  # hidden (3-Family)
        self.log_nifty = self._make_log_table(); self.log_nifty.setVisible(False)  # hidden (ORB retired)
        # INTRADAY 0DTE credit spreads (SELL) — same 2-leg format as SWING TRADES
        v.addWidget(self._section_label("INTRADAY 0DTE  —  NIFTY expiry-day FLIP spread (Tuesdays)", CYAN))
        self.log_zdte = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.log_zdte, 1)
        v.addWidget(self._section_label("INTRADAY 0DTE  —  SENSEX expiry-day CE spread (Thursdays)", AMBER))
        self.log_sdte = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.log_sdte, 1)
        v.addWidget(self._section_label("INTRADAY 0DTE  —  BANKNIFTY expiry-day CE spread (monthly)", PURPLE))
        self.log_bdte = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.log_bdte, 1)
        v.addWidget(self._section_label("ORB+VWAP INDEX  —  BANKNIFTY", AMBER))
        self.log_bnf = self._make_log_table(); v.addWidget(self.log_bnf, 1)
        v.addStretch(1)
        self._style_log_toggle()
        return self._scroll(inner)

    def _style_log_toggle(self):
        for b, key in ((self.log_live_btn, "live"), (self.log_sim_btn, "sim")):
            if self.log_view == key:
                b.setStyleSheet(f"background-color:{GREEN}; color:{BG}; border:none; padding:4px 14px;")
            else:
                b.setStyleSheet(f"background-color:{PANEL_LIGHT}; color:{TEXT_DIM}; "
                                f"border:1px solid {BORDER}; padding:4px 14px;")

    def _set_log_view(self, view: str):
        self.log_view = view
        self._style_log_toggle()
        self._refresh_log()

    def _screen_studies(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("STUDIES  -  the research behind the strategy, in order"))
        doc = QTextEdit(); doc.setReadOnly(True); doc.setFont(QFont("Menlo", 11))
        doc.setHtml(self._studies_html())
        v.addWidget(doc)
        return w

    def _strategy_summary_table(self) -> str:
        """Canonical strategy table — LIVE books first, then rejected/paper. Win rate is split
        IS / OOS / per-CALENDAR-YEAR so a book that only works in one regime is visible at a glance.
        Per-year strings are MEASURED from per-trade data (v2: /tmp/d5_10_15_20_*.json; 0DTE:
        studies/ndte/ndte1{3,4}_trades*.json) — never estimated. v1 has no per-trade file, so its
        per-year cell says so rather than inventing one."""
        live = [
            # name, B/S, IS, OOS, per-yr, worst yr, capital/lot, net/trade RoC, avgW/avgL, hold, sig/mo, Rs/mo, colour
            ("★ Stock fade v2 UNION (TP-50)", "SELL", "84.3%", "87%",
             "19:96 20:88 21:85 22:90 23:79 24:81 25:85 26:89", "79%",
             "~₹10,500", "<b>+52.3%</b> (~₹4,069)", "+101.7% / −101.8%", "<b>12.1d</b> avg<br/>med 9 · p90 27",
             "5–6", "₹20–23k · ₹10–12k", AMBER),
            ("Stock credit v1 · fade (TP-75)", "SELL", "54%", "73%",
             "<span style='color:#888;'>no per-trade file</span>", "—",
             "~₹9,000", "+17.9%w OOS", "—", "days–weeks",
             "~16", "₹9k · ₹4–5k", GREEN),
            ("0DTE SENSEX CE spread", "SELL", "—", "89.0%",
             "24:75 25:90 26:93", "75%",
             "₹11,519", "<b>+6.62%</b> (+₹762)", "+₹1,418 / −₹4,549", "SAME DAY",
             "~4.1", "₹3,153 · ₹1.6k", AMBER),
            ("0DTE NIFTY FLIP spread", "SELL", "86.5%", "93.2%",
             "19:85 20:85 21:76 22:87 23:94 24:91 25:94 26:94", "76%",
             "₹13,577", "<b>+4.11%</b> (+₹558)", "+₹1,168 / −₹4,038", "SAME DAY",
             "~3.2", "₹1,771 · ₹0.9k", CYAN),
        ]
        dead = [
            ("0DTE BANKNIFTY (monthly)", "78.6% (not 91%)",
             "19:67 20:67 21:83 22:64 23:92 24:89 25:90 26:83", "64%",
             "+0.55%m · t=+0.10 · CI spans 0", "84 · 2019→Jun26",
             "✗ REJECTED · edge ≈ 0", "DISABLED 07-19"),
            ("Monthly futures (REV1-v2)", "75.1% IS · 75.7% OOS", "—", "—",
             "+1.0%/tr · ~3.9%/mo on margin", "281+70 · 2018→26",
             "✓ validated OOS", "PAPER · REGIME-OFF (needs ₹15L)"),
            ("Index fade · NIFTY/FINNIFTY", "54%", "—", "—",
             "−1.4% of width", "181 · 2019→Sep24",
             "✗ regime-dep · failed OOS", "forward-test only"),
            ("3-Family stocks (BUY)", "50.6% (direction)", "—", "—",
             "dir +0.107%/tr · −1.0% net as options", "19,454 · 2019→26",
             "~ direction edge, not net", "paper · hidden 07/26"),
        ]
        lt = "".join(
            f"<tr><td style='color:{c};font-weight:bold;'>{nm}</td><td>{bs}</td>"
            f"<td>{is_}</td><td style='color:{GREEN};font-weight:bold;'>{oos}</td>"
            f"<td style='font-size:10px;'>{yr}</td><td style='color:{AMBER};'>{wy}</td>"
            f"<td>{cap}</td><td style='color:{GREEN};'>{roc}</td><td style='font-size:10px;'>{wl}</td>"
            f"<td style='color:{CYAN};'>{hold}</td><td>{fq}</td><td>{pnl}</td></tr>"
            for nm, bs, is_, oos, yr, wy, cap, roc, wl, hold, fq, pnl, c in live)
        dt = "".join(
            f"<tr style='color:{TEXT_DIM};'><td><s>{nm}</s></td><td>{wr}</td>"
            f"<td colspan='2' style='font-size:10px;'>{yr}</td><td>{wy}</td><td>{ret}</td><td>{tw}</td>"
            f"<td style='color:{RED};'>{vd}</td><td>{st}</td></tr>"
            for nm, wr, yr, wy, ret, tw, vd, st in dead)
        return (
            f"<table cellpadding='5' cellspacing='0' style='color:{TEXT};border-collapse:collapse;margin:6px 0;'>"
            f"<tr style='color:{CYAN};font-weight:bold;'><td>LIVE book</td><td>B/S</td><td>Win IS</td>"
            f"<td>Win OOS</td><td>Win by calendar year</td><td>Worst yr</td>"
            f"<td>Capital /lot<br/>(= max loss)</td><td>NET return on capital<br/>per trade (after losses)</td>"
            f"<td>avg WIN / avg LOSS</td><td>Holding</td>"
            f"<td>Sig/mo</td><td>₹/mo @1 lot (model · plan)</td></tr>{lt}"
            f"<tr style='color:{GREEN};font-weight:bold;'><td colspan='11'>TOTAL — 4 live books</td>"
            f"<td>≈ ₹36,924 · ₹29,540</td></tr></table>"
            f"<p style='color:{TEXT_DIM};font-size:11px;'><b>All figures are PER LOT.</b> Capital = the margin "
            f"actually blocked = (width − credit) × lot = the <b>maximum possible loss</b>, which for a "
            f"defined-risk spread is the true capital at risk. The NET return column is already net of the loss "
            f"rate — it is the mean across ALL trades including losers, so the loss leg is subtracted, not added "
            f"afterwards. <b>Note the asymmetry:</b> a loss costs 3–7× what a win pays (NIFTY −₹4,038 vs "
            f"+₹1,168). That is precisely why ~88% win rate is required, and why BANKNIFTY at 78.6% could not "
            f"carry itself.</p>"
            f"<p style='color:{TEXT_DIM};font-size:11px;'><b>HOLDING — measured, not assumed.</b> v2 over 369 "
            f"bhav-era trades: avg <b>12.1 calendar days</b>, median 9, p90 27, max 38 — and <b>3 of 4 exits are "
            f"the early TP-50</b> (279 trades, 75.6%, median just 6 days), not a wait to expiry (18.2%, median "
            f"24d); stops are rare (6.2%) but slow (median 20d). 0DTE holding is certain: 09:16→15:30, ~6h, "
            f"<b>zero overnight gap risk</b>.<br/><b>Per DAY of capital — this reverses the ranking:</b> v2 "
            f"+52.3%/12.1d = <b>+4.3%/day</b> · NIFTY 0DTE <b>+4.7%/day</b> · SENSEX <b>+7.6%/day</b>. Per day "
            f"committed, the 0DTE books MATCH OR BEAT the leader. v2 wins on ₹/month only because its capital is "
            f"continuously deployed (~5.5 signals/mo × 12.1d ≈ 2.2 concurrent positions) while 0DTE capital sits "
            f"<b>idle ~90% of the month</b>. So do not read +52% as '10× better than 4.7%' — that is a holding-"
            f"period illusion.<br/><b>Reality check on v2:</b> those figures imply ≈97%/month on deployed capital "
            f"(~₹22.4k profit on ~₹23.1k average tied up). That is NOT credible live, and independently "
            f"corroborates the standing warning that the v2 backtest is OPTIMISTIC — <b>keep lots at 1</b>.</p>"
            f"<p style='color:{TEXT_DIM};font-size:11px;'><b>v2 RoC excludes 24 trades printing c/W&gt;0.90</b> "
            f"(stale illiquid prints that collapse margin toward zero); it is capital-weighted, not a mean of "
            f"ratios, which would otherwise read an impossible +302%.</p>"
            f"<p style='color:{AMBER};font-weight:bold;margin:10px 0 2px 0;'>Rejected · paper · regime-off — where the edge is NOT</p>"
            f"<table cellpadding='5' cellspacing='0' style='color:{TEXT};border-collapse:collapse;margin:2px 0;'>"
            f"<tr style='color:{CYAN};font-weight:bold;'><td>Book</td><td>Win</td><td colspan='2'>Win by calendar year</td>"
            f"<td>Worst yr</td><td>Return</td><td>Trades · window</td><td>Verdict</td><td>Status</td></tr>{dt}</table>"
            f"<p style='color:{TEXT_DIM};font-size:11px;'><b>How to read this:</b> the per-year column is the "
            f"honesty check — a book that only works in one regime shows it here. v2 UNION has held 79-96% every "
            f"year for 8 years; NIFTY 0DTE dipped to 76% in 2021 and has run 91-94% since; SENSEX has only 3 years "
            f"so treat it as promising, not proven. BANKNIFTY was rejected precisely because its per-year line "
            f"swings 64-92% with no trend — noise, not edge. All per-year figures are MEASURED from per-trade "
            f"data; v1 has no per-trade file so it shows IS/OOS only rather than an invented series. SELL returns "
            f"are NET of entry+exit costs on real premiums; BUY are underlying-direction only. All books remain "
            f"paper forward-tests — none proven on live fills. Detail: studies/STRATEGY_SUMMARY.md.</p>")


    def _studies_html(self) -> str:
        def h(t):
            return f'<p style="color:{GREEN};font-size:15px;font-weight:bold;margin-top:20px;">{t}</p>'
        def sub(t):
            return f'<p style="color:{AMBER};font-weight:bold;margin-top:8px;">{t}</p>'
        def p(t):
            return f'<p style="color:{TEXT};margin:4px 0;">{t}</p>'
        def dim(t):
            return f'<p style="color:{TEXT_DIM};margin:3px 0;">{t}</p>'
        def res(t):  # result / verdict line
            return f'<p style="color:{CYAN};margin:4px 0;">{t}</p>'

        return f"""
<div style="color:{TEXT};">
<p style="color:{AMBER};font-size:18px;font-weight:bold;">⚠ RECOMMENDATION (2026-07-19) — NO strategy change. The gap is VALIDATION, not strategy.</p>
{p("<b>Asked: any change in strategy? Evidence says no.</b> Every modification tested this session was "
   "rejected on data — event/news/earnings/shock filters, gap filters, VIX filters, a longer Donchian "
   "window, extending rv5 to SENSEX/BNF. The two things deployed (election blackout, min credit/width) "
   "are RISK exclusions, not edges. The mechanism: this is a short-vol book, it is PAID for visible "
   "fear, so filters that dodge visible stress remove exactly the trades where the market overpays.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>#</td><td>Action</td><td>Why</td><td>Status</td></tr>
<tr><td><b>①</b></td><td><b>AUDIT the two STOCK books</b> (v2 + v1)</td>
    <td><b>DONE 07-19 — BOTH PASS DECISIVELY.</b> v2 t=<b>+13.78</b>, CI [+60.6,+80.7], positive <b>8/8</b>
        calendar years, drop the 10 best trades and <b>83% of profit survives</b>. v1 t=<b>+7.09</b>,
        CI [+19.8,+34.9], <b>3/3</b> years, 69% survives. Worst trade costs 8 and 12 trades of profit
        respectively — versus BANKNIFTY's <b>102 MONTHS</b>. The ₹32,000 is NOT fabricated.</td>
    <td style="color:{GREEN};">✓ PASSED</td></tr>
<tr><td><b>①b</b></td><td>…but the MAGNITUDE is still optimistic</td>
    <td>The audit proves an edge EXISTS and is robust. It does NOT prove its SIZE survives live fills.
        v2 implies ≈97%/month on deployed capital, and 24 of 569 trades printed c/W&gt;0.95 (stale marks
        where a spread appears to pay 99.5% of its width). <b>Keep the books, distrust the number.</b></td>
    <td style="color:{AMBER};">standing caveat</td></tr>
<tr><td><b>②</b></td><td>Reconsider the <b>80% plan-on haircut</b></td>
    <td>A 20% haircut on numbers that may themselves be 2–3× high is not conservative.
        <b>~50% (≈₹18.5k) is more defensible</b> until ① lands.</td>
    <td style="color:{TEXT_DIM};">flagged only — needs your sign-off</td></tr>
<tr style="color:{AMBER};"><td><b>⚠</b></td><td><b>Election blackout is INERT — no news engine</b></td><td>It is a HAND-MAINTAINED date list; nothing fetches election/policy dates at runtime. (events.py scrapes NSE <i>corporate</i> news for STOCK scoring only; event_calendar.json is research data the engine never reads.) <b>All 4 entries are in the past → it cannot fire.</b> Engine now WARNs every scan while no future dates exist. Next Lok Sabha due 2029, ECI has not published dates, so nothing to add yet — but it must be filled in when announced.</td><td style="color:{AMBER};">mechanism live · list empty</td></tr>
<tr><td><b>③</b></td><td>Do NOT resize / add books / add filters</td>
    <td>Nothing in the evidence supports it. Keep lots at 1.</td>
    <td style="color:{GREEN};">holding</td></tr>
</table>
{res("<b>★ SHOULD NIFTY 0DTE BE REMOVED? NO — it is the SECOND-STRONGEST book in the portfolio.</b> "
     "Asked because ₹1,771/mo is the smallest live contribution. But that is a SIZE question, not a "
     "VALIDITY question, and on evidence NIFTY is second only to v2: <b>273 trades over 8 calendar years, "
     "positive in 7</b> (only 2019, −₹3,522), <b>t = +4.43</b>, 95% CI [+2.62, +6.77] <b>excludes zero</b>, "
     "bootstrap p(mean≤0) = <b>0.0002</b>, and dropping its 5 best trades still leaves <b>87% of the "
     "profit</b> (+₹132,369 of +₹152,267). Compare BANKNIFTY, which WAS removed: t=+0.10, CI spans zero, "
     "p=0.33, drop 3 best → −₹8. Those are OPPOSITE situations that merely sit near each other in a ₹/month "
     "column. On return per DAY of capital NIFTY runs +4.7%/day — ahead of v2's +4.3%/day. Removing the "
     "book with the second-strongest evidence because it has the smallest headline rupee number would be "
     "exactly backwards. <b>KEEP IT.</b> File: studies/STOCK_BOOKS_AUDIT.md")}
{res("<b>WHY ① MATTERED — every stale number checked this session came in OPTIMISTIC.</b> BANKNIFTY: "
     "claimed 91% win / ₹1,500 per month → measured <b>78.6% / ₹141</b>, roughly <b>10× overstated</b>. "
     "NIFTY 0DTE: ₹2,500 → ₹1,771 (−29%). SENSEX: ₹3,200 → ₹3,153 (accurate). Two of three overstated, "
     "one by an order of magnitude — and the two books carrying 87% of the total have not been checked "
     "at all. Independent corroboration: v2's own measured figures imply <b>≈97% per month on deployed "
     "capital</b> (~₹22.4k profit on ~₹23.1k tied up). That is not a credible live return. It does NOT "
     "mean v2 has no edge — it means the MAGNITUDE is inflated, which is exactly what the standing "
     "'backtest is OPTIMISTIC, keep lots at 1' warning has always said. Full write-up: studies/NEXT_ACTIONS.md")}

<p style="color:{CYAN};font-size:18px;font-weight:bold;">THE LIVE STRATEGIES — SUMMARY</p>
{dim("Win rate is split IS / OOS / by CALENDAR YEAR. The per-year column is the honesty check: a book that "
     "only worked in one regime cannot hide behind a blended average.")}
{self._strategy_summary_table()}

<p style="color:{CYAN};font-size:17px;font-weight:bold;">IN PLAIN ENGLISH — what these strategies actually do</p>
{p("<b>Every book here SELLS insurance instead of buying lottery tickets.</b> That one sentence covers all of them. "
   "An option buyer pays a small premium hoping for a big move. We are on the other side: we take the premium, and "
   "we keep it as long as the big move does NOT happen. Most of the time, it does not happen.")}
{p("<b>The 0DTE index books (NIFTY / SENSEX / BANKNIFTY) — a one-day bet that the market won&#39;t sprint.</b> "
   "On the morning an index option expires, we look at where the index opened — say NIFTY at 25,000. We then sell "
   "someone the right to buy NIFTY at 25,125 (0.5% higher) before the day ends. They pay us for that right. "
   "We are betting NIFTY will NOT climb 0.5% today. If it doesn&#39;t, the right expires worthless and we keep the "
   "whole payment. That happens roughly <b>9 times out of 10</b>.")}
{p("<b>The safety net (this is the important part).</b> If NIFTY did rocket upward, selling that right alone could "
   "cost us an unlimited amount. So at the same time we BUY the right to buy at 25,325 (further out). That second "
   "option is our insurance: no matter how violently the market moves, our maximum loss is capped and known before "
   "we enter. That pair — sell one, buy one further away — is what &#39;credit spread&#39; means. We collect the "
   "difference, and the gap between the two strikes is the worst case.")}
{p("<b>So the trade-off is: win small, often — lose bigger, rarely.</b> We might collect ₹9,500 when we win and "
   "lose ₹10,500 when we don&#39;t. That is why the win rate has to stay high to make money. At ~89% wins it works; "
   "at ~76% it would break even; below that it bleeds. Everything else in this tab is us checking, honestly, "
   "whether the win rate is real and whether it holds up in bad years.")}
{p("<b>The stock fade books do the same thing over days instead of hours.</b> When a stock jumps to a new high, "
   "crowds rush to buy its call options and those options get expensive on hope. Breakouts usually stall. So we sell "
   "that expensive hope with the same capped-risk structure, and buy it back cheaper a few days later.")}
{res("THE ONE COUNTER-INTUITIVE LESSON (proved across 448 trades, 2019→2026): <b>scary days are GOOD days for us.</b> "
     "It feels obvious that we should stand aside on RBI policy day, on a war headline, on a big results day. We "
     "tested all of it — and every single &#39;avoid the scary day&#39; rule LOST money. The reason: when everyone is "
     "frightened, insurance gets expensive, and we are the ones SELLING insurance. Fear is what we are paid for. "
     "The 7 expiry days that landed on a real geopolitical shock won 7 out of 7. What actually hurts us is not "
     "drama — it is being paid too little, which is why the only filter we added refuses trades where the premium "
     "is too thin to be worth the risk.")}

<p style="color:{CYAN};font-size:17px;font-weight:bold;">CONSOLIDATED MONTHLY P&amp;L — model, all live books (1 lot vs 2 lots)</p>
{dim("MODEL figures on REAL premiums, NET of charged slippage + brokerage, win/loss rate already baked in. "
     "Plan on ~80% of net (a 20% haircut for live fill quality — fair for these real-premium books, vs a "
     "blanket half). All correlated short-premium — a crash month hits several at once. studies/CONSOLIDATED_PNL.md")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};"><td><b>Book</b></td><td><b>Win</b></td><td><b>~₹/mo · 1 lot</b></td><td><b>~₹/mo · 2 lots</b></td><td><b>basis</b></td></tr>
<tr><td>★ Stock fade v2 UNION (leader)</td><td>87%</td><td>~₹20,000</td><td>~₹40,000</td><td style="color:{TEXT_DIM};">prior study · not re-measured</td></tr>
<tr><td>Stock fade v1 (control)</td><td>73%</td><td>~₹12,000*</td><td>~₹24,000</td><td style="color:{TEXT_DIM};">prior study · not re-measured</td></tr>
<tr><td>0DTE NIFTY</td><td>88.3%</td><td>~₹1,771</td><td>~₹3,542</td><td style="color:{GREEN};">MEASURED 273 tr · 86 mo</td></tr>
<tr><td>0DTE SENSEX</td><td>89.0%</td><td>~₹3,153</td><td>~₹6,306</td><td style="color:{GREEN};">MEASURED 91 tr · 22 mo</td></tr>
<tr style="color:{TEXT_DIM};"><td><s>0DTE BANKNIFTY (monthly)</s> <span style="color:{RED};font-weight:bold;">REJECTED 07-19</span></td><td><s>78.6%</s></td><td><s>~₹141</s></td><td><s>~₹282</s></td><td>edge ≈ 0 · see rejection note</td></tr>
<tr style="color:{GREEN};"><td><b>CONSOLIDATED (full history, ex-BANKNIFTY)</b></td><td><b>—</b></td><td><b>≈ ₹36,924</b></td><td><b>≈ ₹73,848</b></td><td></td></tr>
<tr style="color:{AMBER};"><td><b>Plan-on (80% of net)</b></td><td><b>—</b></td><td><b>≈ ₹29,540</b></td><td><b>≈ ₹59,080</b></td><td></td></tr>
</table>
{dim("<b>CORRECTED 2026-07-19</b> — the three 0DTE rows are now MEASURED from the 448-expiry dataset "
     "(1 lot, net of costs, ₹/mo = total ÷ distinct calendar months), replacing older estimates. What changed: "
     "NIFTY ₹2,500→₹1,771 · SENSEX ₹3,200→₹3,153 (confirmed) · <b>BANKNIFTY 91%/₹1,500 → 78.6%/₹141</b>. "
     "The BANKNIFTY claim was the badly stale one. On the RECENT era only (Oct&#39;24→date) the 0DTE books read "
     "NIFTY 93.2%/₹2,290 · SENSEX 89.0%/₹3,153 · BANKNIFTY 88.9%/₹696 (consolidated ≈₹38,139) — that recent "
     "slice is what the old numbers were built on. Full history is the honest planning number.")}
{res("<b>★ BANKNIFTY 0DTE — REJECTED &amp; DISABLED 2026-07-19</b> (DTE_MULTI_BANKNIFTY_ENABLED=False; open "
     "positions still settle, only new entries stop). NOT because it loses — the MEDIAN trade is +14.1% of "
     "margin — but because its edge is <b>indistinguishable from zero</b> and the tail swamps it: avg +0.55%m, "
     "<b>t = +0.10</b>, 95% CI [−9.98%, +11.09%], bootstrap p(mean≤0) = 0.33. <b>The entire profit is 3 trades</b> "
     "— drop the 3 best and 7.5 years comes to <b>−₹8</b>. It made +₹141/month while its worst single day cost "
     "−₹14,298 = <b>~102 months of profit in one session</b>. The &#39;91% / ₹1,500-a-month&#39; number it was "
     "carried on was never supported (measured: 78.6% / ₹141). Two rescues were tested and BOTH failed: the "
     "monthly-pinning hypothesis (monthly 76.1% vs weekly 80.4% within the same era) and &#39;the recent era "
     "proves it&#39; (n=18, and EVERY book rose in Era B). An adversarial audit found no bug that flips the sign; "
     "the one gap it did find (no liquidity floor on the long wing) would FLATTER the book, so rejecting is the "
     "conservative side of that error. NOT claiming it is proven unprofitable — the CI spans zero, so the verdict "
     "is UNPROVEN. At ~12 trades/yr it can never accumulate evidence fast enough to prove itself, which is itself "
     "the argument. Reversal bar: ≥30 new monthly expiries with a 95% CI excluding zero. "
     "File: studies/BANKNIFTY_0DTE_REJECTION.md")}
{dim("<b>BANKNIFTY — &#39;but monthly expiry should win more, surely?&#39; TESTED 2026-07-19, answer NO.</b> "
     "Real mechanism to expect it (monthly = huge OI = strike PINNING holds the index still, which is what an OTM "
     "seller wants), so it was worth testing. Tested WITHIN Era A — same years, same pipeline, only expiry type "
     "differing: <b>MONTHLY n=67 → 76.1% win / −1.55%m</b> vs <b>WEEKLY n=214 → 80.4% win / +8.51%m</b>. Monthly was "
     "WORSE, beat weekly in only 2 of 6 years, and isn&#39;t even collecting richer premium (median c/W 0.190 vs "
     "0.170). 2-proportion z = −0.75 = NOT significant, so honestly: monthly confers NO win-rate advantage; the gap "
     "is noise that if anything points the wrong way. So Era B&#39;s 88.9% is REGIME + tiny sample (n=18 = 16W/2L, "
     "CI ≈65-99%), not the expiry change — EVERY book jumped in Era B (NIFTY 86.5%→93.2%). Its era gap is still "
     "CONFOUNDED by the weekly→monthly break, so read all this as &#39;the 91%/₹1,500 claim is unsupported&#39;, "
     "NOT as &#39;the book is proven bad&#39;. File: studies/ndte/ndte19_bnf_monthly.py. "
     "*v1 ₹ remains an estimate (per-lot ₹ not separately published). Stock-book rows are carried from prior "
     "studies and were NOT re-measured this session. Capital ~₹2–2.5L (1 lot) / ~₹4–5L (2 lots). Monthly Futures "
     "excluded (needs ₹15L, regime-off). NOT live — in the current drought a realistic this-month is near ₹0; "
     "2 lots doubles P&amp;L AND drawdown.")}

<p style="color:{CYAN};font-size:16px;font-weight:bold;">→ WHAT THE BOOK EARNS PER MONTH TODAY (post-rejection · 1 lot)</p>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Live book</td><td>Status</td><td>Win</td><td>₹/mo · 1 lot</td><td>Evidence</td></tr>
<tr><td>★ Stock fade v2 UNION</td><td style="color:{GREEN};">LIVE</td><td>87%</td><td>~₹20,000</td><td style="color:{TEXT_DIM};">prior study · not re-measured</td></tr>
<tr><td>Stock fade v1 (control)</td><td style="color:{GREEN};">LIVE</td><td>73%</td><td>~₹12,000</td><td style="color:{TEXT_DIM};">prior study · not re-measured</td></tr>
<tr><td>0DTE SENSEX</td><td style="color:{GREEN};">LIVE</td><td>89.0%</td><td>~₹3,153</td><td style="color:{GREEN};">MEASURED · 91 trades</td></tr>
<tr><td>0DTE NIFTY</td><td style="color:{GREEN};">LIVE</td><td>88.3%</td><td>~₹1,771</td><td style="color:{GREEN};">MEASURED · 273 trades</td></tr>
<tr style="color:{TEXT_DIM};"><td><s>0DTE BANKNIFTY</s></td><td style="color:{RED};font-weight:bold;">REJECTED 07-19</td><td>78.6%</td><td>₹0 <s>(was ₹141)</s></td><td>edge ≈ 0 · t = +0.10</td></tr>
<tr style="color:{TEXT_DIM};"><td>Index swing fade (NIFTY/FINNIFTY)</td><td>paper</td><td>54%</td><td>~₹0</td><td>regime-dep · failed OOS</td></tr>
<tr style="color:{TEXT_DIM};"><td>Monthly futures (REV1-v2)</td><td>REGIME-OFF</td><td>75.7%</td><td>₹0 now</td><td>needs ~₹15L · NIFTY &lt; 200DMA</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td><b>TOTAL · 1 lot</b></td><td></td><td><b>—</b></td><td><b>≈ ₹36,924</b></td><td>was ₹39,000 pre-correction</td></tr>
<tr style="color:{AMBER};font-weight:bold;"><td><b>PLAN ON · 80% of net</b></td><td></td><td><b>—</b></td><td><b>≈ ₹29,540</b></td><td>live-fill haircut</td></tr>
<tr style="color:{AMBER};"><td>TOTAL · 2 lots</td><td></td><td>—</td><td>≈ ₹73,848</td><td>plan-on ≈ ₹59,080</td></tr>
</table>
{dim("<b>Read this honestly:</b> ₹36,924 is a MODEL on real premiums with costs charged and the loss leg already "
     "subtracted — not a forecast. <b>₹32,000 of it (87%) is the two STOCK books, which were NOT re-measured this "
     "session</b> and still rest on their prior studies; only the ₹4,924 of 0DTE is measured here. In the current "
     "signal drought a realistic this-month is near ₹0. Every book is correlated short-premium — a crash month "
     "hits them together, so treat the total as ONE position, not five independent ones.")}

<p style="color:{CYAN};font-size:16px;font-weight:bold;">How each ₹/mo is built — expectancy = win% × avg win − loss% × avg loss (the loss leg IS subtracted)</p>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};"><td><b>Book</b></td><td><b>Win</b></td><td><b>Avg win</b></td><td><b>Avg loss</b></td><td><b>Net / trade (win×W − loss×L)</b></td><td><b>×/mo</b></td><td><b>≈ ₹/mo</b></td></tr>
<tr><td>v2 UNION</td><td>86%</td><td>+₹6,048</td><td>−₹7,922</td><td>.86×6,048 − .14×7,922 = <b>+₹4,069</b></td><td>~5</td><td>~₹20,000</td></tr>
<tr><td>Stock v1</td><td>73%</td><td>+41.0% width</td><td>−51.5% width</td><td>.73×41 − .27×51.5 = <b>≈+16%w</b> (OOS +17.9%w)</td><td>~16</td><td>~₹12,000*</td></tr>
<tr><td>0DTE NIFTY</td><td><b>88.3%</b></td><td>—</td><td>—</td><td><b>+4.69% of margin</b> MEASURED, 273 tr / 86 mo</td><td>~3.2</td><td>~₹1,771</td></tr>
<tr><td>0DTE SENSEX</td><td><b>89.0%</b></td><td>—</td><td>—</td><td><b>+7.62% of margin</b> MEASURED, 91 tr / 22 mo</td><td>~4.1</td><td>~₹3,153</td></tr>
<tr style="color:{TEXT_DIM};"><td><s>0DTE BANKNIFTY</s></td><td><s>91%</s> → 78.6%</td><td>—</td><td>−₹14,298 worst</td><td>+0.55%m · <b>t=+0.10, CI spans 0</b> · profit was 3 trades</td><td>~1</td><td style="color:{RED};">REJECTED</td></tr>
</table>
{dim("Every 'net/trade' already subtracts the loss leg — that is the answer to 'did you count losses'. Units "
     "differ: v2/BNF in ₹, v1 in % of width, 0DTE in % of margin. *v1 &amp; BANKNIFTY ₹/mo stay ESTIMATES "
     "(their avg-win is not separately published, so ₹ is % × freq × typical margin, not a clean expectancy). "
     "Sources: STOCK_FADE_TP50_UPGRADE.md, STOCK_V1_OOS.md, INTRADAY_85PCT_0DTE_CE_SPREAD.md.")}

<p style="color:{CYAN};font-size:17px;font-weight:bold;">RESEARCH LOG  -  how each piece of the strategy was tested</p>
{dim("Every change below was backtested before going live (or deliberately NOT deployed). "
     "All P&amp;L is GROSS of costs unless noted. Full write-ups are the .md files in /studies on GitHub.")}
{h("0DTE EVENT AVOIDANCE — SERIES CLOSED (2026-07-19)  ·  Opus tested · Fable decided")}
{sub("Q: should we stand aside when we already KNOW something is happening today? "
     "A: NO — every statistical filter tested costs money. Two STRUCTURAL exclusions are now live; "
     "they are risk limits, not edges. Baseline 448 expiries 2019→Jul&#39;26: 86.6% win · +4.51%m · +₹2.33L.")}

<p style="color:{GREEN};font-weight:bold;margin:8px 0 2px 0;">★ NOW LIVE — two structural exclusions (config-flagged · set []/0 to revert)</p>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:4px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Rule</td><td>Scope</td><td>Skips when</td><td>Measured cost</td><td>Why (structural, not statistical)</td></tr>
<tr><td style="color:{GREEN};">Election blackout</td><td>all 3 books</td><td>counting day / exit-poll session</td>
    <td><b>₹0</b> — never fired in 448</td><td>scheduled INSIDE-window BINARY; short premium is the wrong trade vs a bimodal outcome</td></tr>
<tr><td style="color:{GREEN};">Min credit/width ≥ 0.04</td><td>SENSEX + BANKNIFTY<br/><span style="color:{TEXT_DIM};">NIFTY untouched</span></td><td>c/W &lt; 0.04 at entry</td>
    <td>removes 60 dead trades</td><td>near-zero credit vs a full settlement tail = negative EV by ARITHMETIC, not regime</td></tr>
</table>
{dim("2024-06-04 (NIFTY −5.9%) was dodged by CALENDAR LUCK, not design — the blackout buys that for zero premium. "
     "0.04 is the structural boundary of the negative-EV bucket and deliberately NOT the sweep&#39;s argmax: the "
     "better-scoring 0.06-0.12 cutoffs were EXPLICITLY REJECTED as in-sample optima on small skip-counts. "
     "NIFTY already carries the principle via ZERO_DTE_MIN_CREDIT_PCT.")}

<p style="color:{AMBER};font-weight:bold;margin:10px 0 2px 0;">Everything tested — and why each failed</p>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:4px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Candidate</td><td>Δ vs trade-all</td><td>What the skipped days actually did</td><td>Verdict</td></tr>
<tr><td>Calendar events (RBI/Budget/FOMC)</td><td style="color:{RED};">−₹33.1k</td><td>event subset BEAT baseline: 85.3% win, +5.14%m</td><td style="color:{RED};">✗ both eras</td></tr>
<tr><td>Overnight GAP (any threshold)</td><td style="color:{RED};">fails</td><td>sign INVERTS by era: down-gaps −12.5%m in A, <b>+19.7%m in B</b></td><td style="color:{RED};">✗ regime artifact</td></tr>
<tr><td>India VIX level ≥15 / ≥18 / ≥20</td><td style="color:{RED};">−₹123.7k / −₹74.5k / −₹37.2k</td><td>high-VIX days were fine</td><td style="color:{RED};">✗ both eras</td></tr>
<tr><td>India VIX spike ≥ +10%</td><td style="color:{RED};">−₹17.2k</td><td>flagged days were <b>92.9% win, +13.3%m</b> — the BEST days</td><td style="color:{RED};">✗ backwards</td></tr>
<tr><td>India VIX level ≥ 25</td><td>+₹10.6k (Era A)</td><td>Era B has n=1 — a description of COVID</td><td style="color:{AMBER};">~ untestable · revisit if Era B n≥10</td></tr>
<tr><td>Heavyweight earnings (NIFTY/SENSEX)</td><td style="color:{RED};">−₹14.1k / −₹7.0k</td><td>intraday-result days: 89.5% win, +13.6%m</td><td style="color:{RED};">✗ weight arithmetic</td></tr>
<tr><td>Bank results (BANKNIFTY)</td><td>—</td><td><b>ZERO of 84 expiries</b> hit an intraday bank result</td><td style="color:{TEXT_DIM};">no observations</td></tr>
<tr><td>Geopolitical shocks</td><td style="color:{RED};">would skip winners</td><td>7 shock expiries went <b>7/7, +21.4%m</b></td><td style="color:{RED};">✗ + list is hindsight</td></tr>
<tr><td>Realized vol (rv5) on SENSEX/BNF</td><td style="color:{RED};">fails</td><td>helps Era A +₹47.6k, costs Era B −₹18.0k</td><td style="color:{RED};">✗ regime artifact</td></tr>
</table>
{dim("Half-sizing instead of skipping never rescued any rule; removing the single worst day never changed a sign. "
     "Only 51 of 367 heavyweight result releases land inside the 09:16-15:30 window at all — HDFCBANK/ICICIBANK "
     "report on SATURDAYS. Elections never coincided with an expiry in 7.5 years.")}

<p style="color:{AMBER};font-weight:bold;margin:10px 0 2px 0;">The one positive finding — cheap premium is uncompensated tail risk (win rate is an INVERSE mirage)</p>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:4px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>credit/width at entry</td><td>n</td><td>Win %</td><td>Avg % of margin</td><td>Total ₹</td></tr>
<tr><td>0.00 – 0.04  <span style="color:{RED};">(now skipped)</span></td><td>60</td><td style="color:{GREEN};"><b>91.7%</b></td><td style="color:{RED};"><b>−0.49%</b></td><td style="color:{RED};">−₹1,878</td></tr>
<tr><td>0.04 – 0.08</td><td>103</td><td>87.4%</td><td style="color:{RED};">−0.30%</td><td>+₹5,689</td></tr>
<tr><td>0.08 – 0.12</td><td>104</td><td>89.4%</td><td>+6.02%</td><td>+₹82,258</td></tr>
<tr><td>0.12 – 0.18</td><td>88</td><td>84.1%</td><td>+5.95%</td><td>+₹57,823</td></tr>
<tr><td>0.18 +</td><td>93</td><td style="color:{AMBER};"><b>81.7%</b></td><td style="color:{GREEN};"><b>+10.03%</b></td><td style="color:{GREEN};">+₹89,555</td></tr>
</table>
{dim("The CHEAPEST bucket has the HIGHEST win rate and still LOSES money; the richest has the LOWEST win rate and "
     "makes the most. Same shape as the stock book&#39;s validated c/w≥0.40 gate — and it was PREDICTED in advance by "
     "the closing finding below, so it is a confirmed hypothesis, not a data-dredge.")}

{res("CLOSING FINDING — this book is PAID FOR VISIBLE FEAR. A fixed-%-OTM spread sold on a scary morning collects "
     "inflated premium against a strike that hasn&#39;t moved, so observable risk is COMPENSATION, not danger. Every "
     "filter keying on ex-ante-visible stress removes exactly the trades where the market OVERPAYS. The only real "
     "threats are (a) INTRADAY surprises — which occurred ZERO times in 448 expiries and cannot be filtered ex ante, "
     "and (b) true crisis regimes (VIX≥25) — too rare to test. The mirror image is the only thing that survived: "
     "cheap premium is uncompensated tail risk. Cross-checks: NIFTY 88.3%/+4.69%m ≡ documented 87.8%/+4.0%m; SENSEX "
     "89.0%/+7.62%m ≡ documented 88.8%/+7.6%m. Files: ZERO_DTE_EVENT_DAYS.md · ZERO_DTE_PREOPEN_SIGNALS.md · "
     "ZERO_DTE_EARNINGS_SHOCKS.md")}
{dim("CAVEATS: BANKNIFTY rows are structurally confounded (weekly→monthly expiry break, SEBI rationalisation) and "
     "carry less weight. SENSEX is a SINGLE-ERA book (BSE weeklies launched 2023) so it can never pass an era split "
     "— it may only ever receive structural rules, never swept ones. Era A = bhavcopy 2019→Jul&#39;24 (incl. COVID), "
     "Era B = Upstox Oct&#39;24→date; gap Jul-Sep&#39;24 where NSE retired the legacy bhavcopy format.")}

{res("CREDIT/WIDTH BUCKETS (2026-07-15): net is a GRADIENT below the 0.40 gate — win rate barely drops "
     "(87→82→76%) but the money collapses. ≥0.40 = +31.7%w (deployed core, 87% win) · 0.35-0.40 = +9.2%w "
     "(REAL but ⅓ the edge, 82% win, +ve all 3 yrs, brutal −65% avg loss) · 0.30-0.35 = +1.1%w (breakeven "
     "— skip). 629 trades Oct24-Jul26 real premiums. Win rate is a MIRAGE below 0.40 (breakeven WR ≈76%). "
     "SINGLE REGIME — NOT validated 2019-24; 0.35-0.40 is promising, not proven → if used, a SEPARATE "
     "1-lot secondary tier, never merged into the core book. File: studies/CW_BUCKET_ANALYSIS.md")}

{h("CONSOLIDATED PORTFOLIO — organised by WIN-RATE TIER (user request 2026-07-10)")}
{sub("TIER A — the ≥80%-win books (the priority group, all defined-risk, all fit ~₹2L). "
     "TIER B — the monthly-futures pair, kept SEPARATE: lower win rate, different capital base, "
     "the long-delta diversifier / higher-return-on-capital experiment.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>TIER A · ≥80% WIN</td><td>Win (IS / OOS)</td><td>Signals/mo</td><td>1 lot MODEL</td><td>1 lot PLAN-ON</td></tr>
<tr><td>★ Stock fade v2 UNION (swing)</td><td>85% / <b>88%</b></td><td>5–6</td><td>₹20–23k</td><td>₹10–12k</td></tr>
<tr><td>NIFTY 0DTE (FLIP)</td><td><b>88.3%</b> measured</td><td>~3.2</td><td>₹1,771</td><td>₹0.9k</td></tr>
<tr><td>SENSEX 0DTE (CE)</td><td><b>89.0%</b> measured</td><td>~4.1</td><td>₹3,153</td><td>₹1.6k</td></tr>
<tr style="color:{TEXT_DIM};"><td><s>BANKNIFTY monthly 0DTE</s> <span style="color:{RED};">REJECTED 07-19</span></td><td><s>91.3%</s> → 78.6%</td><td>~1</td><td><s>₹820</s> → ₹141</td><td>₹0</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td>TIER A TOTAL (~₹2–2.5L capital)</td><td><b>≈88% blended</b></td><td>~13</td><td>~₹25k</td><td>~₹12.5k</td></tr>
<tr><td colspan="5" style="color:{BORDER};">———————————————————————————————————</td></tr>
<tr style="color:{AMBER};font-weight:bold;"><td>TIER B · monthly futures pair (SEPARATE)</td><td>Win</td><td>Freq</td><td>Return on capital</td><td>Capital</td></tr>
<tr><td style="color:{AMBER};">1 · Monthly futures pullback (REV1-v2, FUT)</td><td>75.7% OOS</td><td>5/cycle</td><td>~3.9%/mo · worst −20%</td><td>~₹15L margin</td></tr>
<tr><td style="color:{AMBER};">2 · Same signal as monthly CALL (early-exit)</td><td>67% OOS</td><td>5/cycle</td><td>~6–7%/mo · worst −51%</td><td>~₹2L premium</td></tr>
</table>
{dim("Stock credit v1 (73% OOS) sits between the tiers — kept as the ~16/mo live-fill control book, "
     "not counted in Tier A. Tier B stays PAPER; it is the long-delta diversifier and the "
     "return-on-capital experiment, deliberately apart from the ≥80%-win group per the user's ask. "
     "10%/mo AT ≥75% win was shown empirically unreachable — see studies/monthly_fut.")}
{h("★ WORKED EXAMPLE — STOCK FADE v2 UNION, one trade start to finish (the LEADER)")}
{sub("The idea in one line: after a stock breaks out, its call options get expensive on hope — "
     "breakouts usually stall — so we SELL that hope with a capped-loss spread and buy it back "
     "cheaper days later.")}
{p("<b>3:10 PM — the signal.</b> HAVELLS closes at <b>₹1,520</b>, breaking above its 10-day high "
   "(₹1,505). Crowd buys calls → IV spikes → premiums get rich. The gate checks we're being paid "
   "enough to fade it. The two rows PM DECISIONS would show:")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Row</td><td>Order (1 lot = 500)</td><td>Why this strike</td><td>Premium</td></tr>
<tr><td style="color:{GREEN};">SELL</td><td>SELL HAVELLS 1540 CE</td><td>2 strikes OTM — breathing room</td><td>receive ₹55/sh</td></tr>
<tr><td style="color:{RED};">BUY</td><td>BUY HAVELLS 1580 CE</td><td>4 strikes further — the safety net</td><td>pay ₹36/sh</td></tr>
</table>
{p("<b>Credit banked now:</b> (55−36) = ₹19/sh × 500 = <b>₹9,500</b>. <b>Gate:</b> credit/width "
   "19/40 = 0.475 ≥ 0.40 ✓ · short prem ₹55 ≥ ₹50 ✓. <b>Margin blocked = absolute worst case:</b> "
   "(40−19)×500 = <b>₹10,500</b> — the bought 1580 CE caps every outcome, no gap can exceed it.")}
{p("<b>Then, checked once a day:</b> ~86% of the time HAVELLS stalls/dips, the spread deflates, and "
   "when closing costs ≤ ₹9.5 (HALF the credit) the engine books the WIN — <b>+₹4,750-ish in a few "
   "days</b>, no waiting for expiry. ~14% of the time the stock keeps charging: exit at the 3×-credit "
   "stop, avg loss −₹7,922, hard-capped at the ₹10,500 already blocked. Expectancy ≈ (86%×₹6,048) − "
   "(14%×₹7,922) = <b>+₹4,069/trade</b>, 5–6 trades/mo.")}
{res("TESTING BEHIND IT: 96-config grid (Donchian × strike × width × TP × stop) on REAL NSE bhavcopy "
     "premiums 2019→Sep'24 with entry+exit slippage — winner not a lone cell (27/96 configs pass; the "
     "whole TP-50 neighbourhood works). IS: 273 trades, 85.35% win, only 4 negative months in 60, worst "
     "loss-streak 4. Then re-run on data the search NEVER saw (Upstox expired options Oct'24→Jul'26): "
     "87.88% win, +31.9% of width. UNION upgrade (DC 5+10+15+20 windows) OOS-validated separately: 173 "
     "trades, 87% win, +29.5%w. Win ≥79% EVERY calendar year 2019→2026. Files: "
     "studies/STOCK_FADE_TP50_UPGRADE.md, UNION_DONCHIAN_FREQUENCY.md")}
{res("UNION vs D10 — DECISION (2026-07-13): KEEP UNION. UNION already IS 'both' (= D10+D5+D15+D20, a "
     "superset of D10), so +34% more signals at the SAME win rate/expectancy — no 'run both' mode. But "
     "the scanner is NOT the bottleneck: Jul 1-13 D10 alone threw 105 breakouts, only 1 cleared; the "
     "credit/width>=0.40 gate is the wall (thin-IV regime), not the Donchian window. Do NOT loosen the "
     "gate (strip it -> +26%w becomes -1.1%). Frequency comes from the v1 book (~10-16/mo), not a looser "
     "v2. File: studies/STOCK_FADE_V2_UNION_VS_D10.md")}
{res("DONCHIAN 5/10/15/20 — FULL-HISTORY VALIDATION (2026-07-19): is a longer window more DURABLE "
     "than D5? Ran each window STANDALONE (not the union) over 2019→date, two eras stitched — NSE "
     "bhavcopy 2019→Sep'24 (569/415/343/296 trades) + Upstox premiums Oct'24→date. NO. "
     "D5(=UNION) 85.4% win / +29.1%w / 6.3/mo · D10 86.3% / +29.0%w / 4.6/mo · D15 85.4% / +27.2%w / "
     "3.8/mo · D20 83.4% / +26.2%w / 3.3/mo. Win rate PEAKS at D10 then FALLS (D20 worst); "
     "net-per-trade DECLINES monotonically past D10. Total edge/mo (freq×net) = D5 1.83 > D10 1.33 > "
     "D15 1.03 > D20 0.86 width-units — D5's frequency wins, longer windows sacrifice throughput for a "
     "win bump only D10 even delivers (+0.9pp, no net gain). All four +ve EVERY year 2019-26 — the "
     "c/w≥0.40 GATE is the durable edge, not the window. Cross-checks: bhav D10 273/85.3% ≡ documented "
     "273/85.35%; Oct'24 D5 200/87.5% ≡ known 203/87.2%. REPORT-ONLY, engine unchanged. "
     "File: studies/DONCHIAN_5_10_15_20.md")}

{h("WHY DOES v1 SHOW 54% NEXT TO v2 UNION's 85%+? — it is NOT the number of calls")}
{p("<b>Same signal, same gate, different EXIT GEOMETRY — and the 54% is the OLD hold-to-expiry test.</b> "
   "The 54%/+5.3%w figure (718 bhavcopy trades 2019→Sep'24) predates v1's deployed TP-75 book-early "
   "exit. Re-tested 2026-07-10 with the DEPLOYED config (TP at 75% of the credit, stop 2×) on the same "
   "Upstox OOS window v2 used (Oct'24→Jul'26): <b>346 trades · 73.4% win · +17.9% of width · positive "
   "every year incl. the 2026 correction</b> (2024 +29.7 / 2025 +17.0 / 2026 +15.0). Booking the win "
   "early is what lifts the rate — the same mechanism as v2's TP-50, just less aggressive.")}
{p("<b>Apples-to-apples on the identical window/script:</b> v2 UNION 87–88% win · +29.5–31.9%w · ~8/mo "
   "vs v1 73.4% · +17.9%w · ~16/mo. v2 stays the LEADER on both win rate and expectancy (deeper 2-OTM "
   "strikes, wider wings, faster profit-taking, 3× stop room). <b>Why keep v1:</b> (1) longest-validated "
   "baseline (718 + 346 real-premium trades); (2) ~2× the signals → live-fill evidence twice as fast; "
   "(3) the control in the live A/B — if v2's edge shrinks on real fills, v1 shows whether the fault is "
   "geometry or market. Files: studies/STOCK_V1_OOS.md")}

{h("★ FLIP UPGRADE — NIFTY Tuesday book (DEPLOYED 2026-07-07)")}
{p("Each expiry morning the book reads NIFTY's 5-day return: <b>≥ +1% → SELL the PE spread</b> "
   "(ride the up-momentum), <b>otherwise SELL the CE spread</b>. Same wing, same margin, same "
   "filters — only the SIDE flips. Fixes the failure where a grinding rally runs over call-selling.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Year</td><td>CE-always win / ₹</td><td>FLIP win / ₹</td></tr>
<tr><td>2019</td><td>87.0% / +2,888</td><td>84.8% / <span style="color:{RED}">−3,859</span></td></tr>
<tr><td>2020</td><td>79.2% / +1,843</td><td>83.0% / +22,758</td></tr>
<tr><td>2021</td><td>84.6% / +16,863</td><td>76.9% / +11,406</td></tr>
<tr><td>2022</td><td>86.5% / +45,476</td><td>86.5% / +38,736</td></tr>
<tr><td>2023</td><td>86.5% / +16,392</td><td>94.2% / +27,819</td></tr>
<tr><td>2024</td><td>82.1% / +14,588</td><td>89.7% / +33,610</td></tr>
<tr><td>2025</td><td>86.8% / +3,897</td><td>94.3% / +42,921</td></tr>
<tr><td>2026 H1</td><td>84.0% / +14,821</td><td>88.0% / +18,620</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td>ALL (372)</td><td>84.7% / +1,16,768</td><td>87.1% / +1,92,010</td></tr>
</table>
{res("Net edge +₹75,242 (+64%) over CE-always, win rate 84.7%→87.1%. Only 2019 lost (−₹3.9k, one "
     "bad week) — negligible vs 2020 +₹22.8k / 2025 +₹42.9k. Real premiums 2019→2026, W=200 both "
     "sides, costs charged. SENSEX/BANKNIFTY stay plain-CE (validated-only). File: studies/FLIP_SIDE_CREDIT_FADE.md")}

{h("★ SENSEX 0DTE — THURSDAY expiry-day CE spread (LIVE 2026-07-09)")}
{p("Identical structure to NIFTY (sell CE 0.5% OTM at open, wing ~0.83% of spot ≈600 pts, hold "
   "to same-day 15:30 settlement), on BSE's SENSEX weekly expiry — a SECOND payday each week. "
   "Runs plain CE: the NIFTY flip was tested on SENSEX and is WORSE here (88.6% CE vs 86.4% flip, "
   "and the flip adds losing weeks), so SENSEX keeps CE.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>SENSEX CE, real premiums Oct'24→Jun'26</td><td>n</td><td>Win</td><td>Avg %margin</td><td>Total 1 lot</td></tr>
<tr><td>All expiries</td><td>89</td><td><b>88.8%</b></td><td>+7.57%</td><td>+₹67,248</td></tr>
<tr><td>2025 · 2026 H1</td><td>51 · 26</td><td>90.2% · 92.3%</td><td>+6.6% · +15.8%</td><td>+₹34.1k · +₹37.3k</td></tr>
</table>
{res("Loss profile (88 both-side expiries): 78 W / 10 L · avg win +₹1,423 · avg loss −₹4,549 · "
     "worst −₹8,963. Margin ≈ ₹11-12k/lot. Caveats: 21-month single-era history only (BSE weeklies "
     "are young — no 2019-24 depth); Oct-Dec'24 was the expiry-transition era (weak). REPORT + LIVE "
     "paper from Thu 2026-07-09. Files: INTRADAY_85PCT_0DTE_CE_SPREAD.md, FLIP_SIDE_CREDIT_FADE.md")}

{h("★ BANKNIFTY 0DTE — MONTHLY expiry-day CE spread (LIVE · ~1/mo)")}
{p("Same structure on BANKNIFTY's MONTHLY expiry (its weeklies were abolished by SEBI Nov'24, so "
   "only the monthly is tradeable). Fatter returns, lower win rate — BANKNIFTY is wilder.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>BANKNIFTY CE, real premiums</td><td>n</td><td>Win</td><td>Avg %margin</td><td>Total 1 lot</td></tr>
<tr><td>Weeklies 2019→Sep'24 (structure validation)</td><td>273</td><td>79.5%</td><td>+7.42%</td><td>+₹89,616</td></tr>
<tr><td><b>Monthlies Oct'24→Jun'26 (deployed cadence)</b></td><td>23</td><td><b>91.3%</b></td><td>+10.95%</td><td>+₹17,214</td></tr>
</table>
{res("Weeklies positive 2019-2023 (incl. 2020 crash +11.8%m); 2024-stub negative (−₹13k). Worst "
     "trade −₹10.7k (wk) / −₹14.3k (monthly). Margin ≈ ₹11-14k/lot. Deploy MONTHLY-only. Caveat: "
     "monthly sample small (23). File: studies/INTRADAY_85PCT_0DTE_CE_SPREAD.md (BANKNIFTY section)")}

{res("Capital: ~₹2–2.5L at 1 lot each · ~₹4–5L at 2 lots (swing books + recycling intraday margins). "
     "PLAN-ON = ~half of model until live fills prove out (this repo's standing rule).")}
{dim("Honesty: monthly figures are AVERAGES — a combined bad month at 2 lots can be −₹40–60k; the three "
     "0DTE books' LIVE history starts 2026-07-07; the five OPTIONS books are correlated short-premium in a "
     "crash — size on the worst month, not the average (the monthly-futures book is long-delta and regime-"
     "gated, the one diversifier — but it is paper-only). Frequency extension verdicts: SENSEX Thu 88.8%/+7.6%m "
     "(89 exp, 21-mo history only); BANKNIFTY 2019→24 weeklies 79.5%/+7.4%m +₹89.6k, positive 2019–23, "
     "2024 −₹13k, weeklies abolished → MONTHLY-only deploy (91%/+11%m, 23 tr); near-DAILY selling "
     "REJECTED (−₹3.4k/333 non-expiry day-trades — the edge is expiry-day theta only).")}

{h("★ MONTHLY FUTURES PULLBACK — REV1-v2 (the 6th book · PAPER 2026-07-10 · needs ~₹15L)")}
{sub("Question (user goal): monthly trades in FUTURES only, ≥75% win rate, ≥10%/month net?")}
{p("Tested on REAL NSE bhavcopy futures 2018→Jul'26 (FUTSTK 100-stock universe + FUTIDX): a 90-config "
   "grid across 8 families (momentum L/S, pullback, index trend/dip, Donchian-fade shorts, hedged, "
   "low-vol) × TP/SL exits, strict IS (2018→Sep'24) / OOS (Oct'24→Jul'26) split, selection on IS only. "
   "<b>The rule:</b> at each expiry-cycle start with NIFTY&gt;200DMA, take the 8 worst 1-month losers "
   "still above their OWN 200DMA, keep the 5 highest-vol, BUY the front-month future; exit on close "
   "crossing TP +2% (decaying to +1% after day 12) or SL −5%; else expiry settle.")}
{res("REV1-v2: 75.1% win IS (281 tr) · 75.7% OOS (70 tr) · ~3.9%/mo on margin capital · worst month "
     "−20% · 8/11 OOS months positive. The momentum runner-up FAILED OOS (bull artifact) — pullback is "
     "the survivor. VERDICT on the 10%/mo ask: INFEASIBLE — needs +2.2%/trade net, best honest edge is "
     "+0.85%; every config printing near 10%/mo in-sample collapsed OOS. Calendar spreads ≈0 net since "
     "2021; capital recycling DILUTES the edge (mid-month candidates are weak).")}
{p("<b>Loser anatomy:</b> across 8 entry factors (pullback depth, vol, trend distance, gap-proneness, "
   "52w-high distance, beta, OI, regime) winners and losers are IDENTICAL at entry — losses are not "
   "predictable, they are the price of the 75% wins. Half of OOS losses were 1-day news shocks → the "
   "live-only <b>EARNINGS-SKIP</b> rule drops candidates with results before expiry (NSE event calendar, "
   "fails open). Counter-intuitive: the most gap-prone names are the BEST bucket (80.7% win) — do NOT "
   "filter them out.")}
{dim("Paper-only: 5 × ₹10L notional needs ₹11L margin + buffer ≈ ₹15L capital. Regime-gated: stands "
     "aside when NIFTY &lt; 200DMA (in cash Mar→Jul 2026). Files: studies/monthly_fut/MONTHLY_FUTURES.md "
     "(+ bt.py, grid_results.json, trade lists — full reproducible trail).")}

{h("✗ MONTHLY LONG-CALL PULLBACK — SHELVED 2026-07-13 (unreliable, gap/luck-dependent)")}
{sub("Same signal as the futures book, but BUY an ATM CALL. Built + deployed 2026-07-13, then "
     "SHELVED the SAME DAY after the trade-by-trade ledger exposed it. Kept dormant "
     "(MONTHLY_CALL_ENABLED=False); documented here so nobody re-deploys it thinking it works.")}
{res("WHY SHELVED — the 12-month ledger (1 lot each, real premiums): +₹63,815 net, 65% win LOOKS "
     "fine, but ONE trade — POLYCAB +₹47,353 — was ¾ of it. Ex-POLYCAB the whole year is +₹16.5k "
     "across 40 trades ≈ noise. And POLYCAB's win was a real +8.2% ONE-DAY GAP (28-Jan→03-Feb), "
     "NOT a +2% edge: the '+2% take-profit' does not cap wins — it rides gap-throughs to that "
     "day's close. So the profit depends on rarely catching a big favourable gap (luck), while "
     "cycle P&L swings −₹58k (Mar) to +₹71k (Feb). A luck/gap-dependent profile — NOT a durable edge.")}
{p("<b>Also failed in the build (so nobody re-mines it):</b> holding calls to expiry LOSES on theta "
   "(28–39% win); 8 picks DILUTED the edge OOS (+6-7%→+0.3%/mo); 'loss-minimizing' gates "
   "(momentum + −3% stop) looked great IS (6.4%/mo) but LOST money OOS (−2.7%/mo) — curve-fit; "
   "win-rate levers (lower TP, deeper ITM) can't beat the ~70% ceiling (win rate = the signal's "
   "hit rate). Even the surviving simple 5-pick is risk-adjusted WORSE than the future (1.5%/mo "
   "vs 3.9% at −20% worst-month) — its higher headline return is leverage, not edge.")}
{dim("Verdict: buying calls tops out ~67-70% win and leans on lucky gaps; SELLING defined-risk "
     "credit spreads wins ~86% without needing a gap. The spreads are the reliable core; this book "
     "stays shelved. Files: studies/monthly_fut/MAX_TRADES_OPTIONS.md + opt_*.py + "
     "call_ledger_6mo/12mo.csv (full IS+OOS + trade ledgers).")}

{h("★ 0DTE INTRADAY (the 5th strategy) — NIFTY Tue · SENSEX Thu · BANKNIFTY monthly · LIVE FLIP on NIFTY")}
{sub("Question (user goal): an INTRADAY strategy — closed the same day — with ≥85% win rate, "
     "positive net returns and >2% per trade on capital, retail-tradeable?")}
{p("First, what does NOT work (so nobody re-mines it): on 7.5 years of real 5-min data (100 F&O "
   "stocks), NO directional intraday strategy on the underlying reaches even 82% win with net>0 — "
   "234 variants tested (flushes, RSI/z confluence, gap fades, VWAP targets, trailing stops). A "
   "90%+ win rate IS manufacturable (tiny target / wide stop: 92% win, 7,688 trades) but earns "
   "≈0.00% gross — geometry, not edge. Files: INTRADAY_90PCT_WINRATE.md.")}
{p("What DOES work — selling expiry-day premium with defined risk, and (LIVE 2026-07-07) FLIPPING "
   "the side by momentum: <b>each NIFTY weekly expiry morning, if the 5-day return ≥ +1% SELL the "
   "PE spread (0.5% OTM below), else SELL the CE spread (0.5% OTM above); wing 200 pts, hold to "
   "same-day settlement, no stop.</b> One trade a week, 2 legs, margin ≈ max loss ≈ ₹14k/lot. "
   "The base CE-only numbers below; the FLIP upgrade table is in the section above.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>REAL premiums, costs charged</td><td>n</td><td>Win</td><td>Avg net (% of margin)</td></tr>
<tr><td>In-sample — NSE bhavcopy 2019→Sep'24 (config chosen here)</td><td>282</td><td>84.4%</td><td>+3.17%</td></tr>
<tr style="color:{GREEN};"><td><b>Out-of-sample — Upstox Oct'24→Jun'26 (search never saw it)</b></td><td><b>91</b></td><td><b>86.8%</b></td><td><b>+3.28%</b></td></tr>
<tr><td>Combined 2019→2026 — positive EVERY calendar year</td><td>373</td><td>85.0%</td><td>+3.20%</td></tr>
</table>
{res("Per-year (win / avg %margin): 2019 87/+1.4 · 2020 79/+0.8 · 2021 87/+3.1 · 2022 87/+8.5 · "
     "2023 85/+2.3 · 2024 85/+5.1 · 2025 87/+0.4 · 2026 85/+5.7. Higher-win variant (short 0.75% "
     "OTM): 90.1% win OOS but +1.7%/trade — the win-vs-return dial.")}
{res("The honest shape: avg win +9.8%m · avg loss −34.1%m · worst −102%m (one full-width day — "
     "capped, that IS the max loss) · max losing streak 3 · 28/87 months negative · median month "
     "+₹2.1k, worst −₹14.8k (1 lot). ~4.3 trades/mo · avg ₹348/trade · ≈₹1.5k/mo per lot (MODEL).")}
{dim("Why the side matters: CE-selling is the right DEFAULT (expiry-day rallies are usually "
     "capped by pinning + IV crush), but in an up-MOMENTUM week the danger is above — so the FLIP "
     "sells PE instead (validated: FLIP 87.1% vs CE-only 84.7% since 2019; PE-ALWAYS loses, so the "
     "edge is the CONDITIONAL switch, not the put side itself). Risks: short-gamma tail (a violent "
     "move through the short costs the full width), fills at the opening print unproven live — hence "
     "PAPER forward-test, 1 lot. Files: INTRADAY_85PCT_0DTE_CE_SPREAD.md + FLIP_SIDE_CREDIT_FADE.md.")}

{h("★★★ THE LEADER — STOCK CREDIT v2 (TP-50)  ·  win ≥79% EVERY year 2019→2026")}
{sub("Question: can the validated stock fade win >65% in every regime with good profit — and hold OOS?")}
{p("Same signal + gate as v1 (Donchian-10 breakout → fade; credit/width ≥ 0.40 + prem ≥ Rs50), new "
   "geometry + exits: <b>short 2-OTM · width 4 · TAKE-PROFIT at 50% of the credit · stop 3×</b>. "
   "Found via a 96-config grid on real bhavcopy premiums (entry AND exit slippage charged) — 27 "
   "configs hit the goal, the whole TP-50/stop-3× neighborhood passes (structural, not a fit cell). "
   "Mechanism: book the win early (IV-crush harvest), give losers 3× room to mean-revert.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>IN-SAMPLE (bhavcopy, exit costs)</td><td>2019</td><td>2020</td><td>2021</td><td>2022</td><td>2023</td><td>2024 Jan-Sep</td><td>ALL</td></tr>
<tr><td style="color:{GREEN};">Win %</td><td>100</td><td>90</td><td>86</td><td>88</td><td>79</td><td>82</td><td><b>85.35</b></td></tr>
<tr><td style="color:{GREEN};">Net % of width</td><td>+61.0</td><td>+25.4</td><td>+9.3</td><td>+30.5</td><td>+18.4</td><td>+22.3</td><td><b>+24.5</b></td></tr>
<tr><td style="color:{TEXT_DIM};">Trades</td><td>18</td><td>31</td><td>51</td><td>51</td><td>62</td><td>60</td><td>273</td></tr>
</table>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>OUT-OF-SAMPLE (Upstox, search never saw it — NO overlap: 2024 splits at Oct 1)</td><td>2024 Oct-Dec</td><td>2025</td><td>2026 Jan-Jul</td><td>ALL OOS</td></tr>
<tr><td style="color:{GREEN};">Win %</td><td>87</td><td>86</td><td>91</td><td><b>87.88</b></td></tr>
<tr><td style="color:{GREEN};">Net % of width</td><td>+19.5</td><td>+34.9</td><td>+31.3</td><td><b>+31.9</b></td></tr>
<tr><td style="color:{TEXT_DIM};">Trades</td><td>15</td><td>74</td><td>43</td><td>132</td></tr>
</table>
{res("EXACT distribution (not averages): in-sample 233 WINS / 40 LOSSES; win median +32.0 / max +92 "
     "of width, loss median −51.1 / worst −71.9 (capped by the hedge). Longest losing streak 4. "
     "OOS: 116 W / 16 L.")}
{res("P&amp;L with the ₹40k EXPOSURE CAP (width×lot — live in the engine; win rate unchanged 85.7%): "
     "<b>MODEL ₹16-17k/mo at 1 lot · PRACTICAL ~₹8-10k · 2 lots ≈ ₹32-34k / ₹16-20k.</b> "
     "Worst month −₹26.4k, worst single loss −₹21.6k, best month +₹58.3k, 5/54 months negative. "
     "LIVE column = the forward test.")}
{sub("PROFIT EQUATION (simple):")}
{p("<b>Profit/trade = (Win% × AvgWin) − (Loss% × AvgLoss) = (86% × ₹6,048) − (14% × ₹7,922) = ₹4,069</b> "
   "&nbsp;→&nbsp; Monthly = 4.3 trades × ₹4,069 ≈ <b>₹17.5k</b>")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>MODEL (capped book)</td><td>1 lot</td><td>2 lots</td><td>5 lots</td><td>How it's calculated</td></tr>
<tr><td>Margin/trade <b>(= MAX LOSS — all the broker blocks)</b></td><td>₹10k</td><td>₹20k</td><td>₹50k</td><td>(width − credit) × lot ≈ 0.575 × avg notional ₹17.4k</td></tr>
<tr style="color:{AMBER};"><td><b>Investment (book capital)</b></td><td><b>₹1L</b></td><td><b>₹2L</b></td><td><b>₹5L</b></td><td>≈ 6 concurrent × margin + buffer</td></tr>
<tr><td>Avg win / trade</td><td>+₹6,048</td><td>+₹12.1k</td><td>+₹30.2k</td><td>mean of the 200 capped wins</td></tr>
<tr><td>Avg loss / trade</td><td>−₹7,922</td><td>−₹15.8k</td><td>−₹39.6k</td><td>mean of the 33 capped losses (each ≤ max loss)</td></tr>
<tr><td>Profit / trade</td><td>₹4,069</td><td>₹8,138</td><td>₹20,345</td><td>(86% × 6,048) − (14% × 7,922)</td></tr>
<tr style="color:{GREEN};"><td><b>Profit / month</b></td><td><b>₹17.5k</b></td><td><b>₹35.0k</b></td><td><b>₹87.5k</b></td><td>4.3 trades/mo × profit/trade</td></tr>
<tr style="color:{GREEN};"><td><b>% gain / month</b></td><td><b>~17.5%</b></td><td><b>~17.5%</b></td><td><b>~17.5%</b></td><td>₹17,500 ÷ ₹1,00,000</td></tr>
<tr style="color:{GREEN};"><td><b>Run since Jan 2019 → Jul 2026</b></td><td><b>₹14.3L</b></td><td><b>₹28.6L</b></td><td><b>₹71.4L</b></td><td>exact ₹9.48L (233 tr) + ₹4.8L (≈118 OOS tr × ₹4,069)</td></tr>
</table>
{dim("Fixed lots, NO compounding, MODEL numbers (today's lot sizes). Practical planning ≈ half until "
     "live fills prove the model — the forward test's LIVE column is the referee.")}
{dim("Worst-month forensic (pre-cap Feb-2021 '−₹2.28L'): ONE stock — BAJAJFINSV — lost the same spread "
     "3× (re-entry into a relentless trend), AND the rupee figure was inflated by an era artifact: "
     "today's lot (300) applied to 2021 pre-split prices (true 2021 loss ~₹35k/hit at lot 125). "
     "Percent figures are exact; pre-cap rupee extremes were overstated — the cap blocks that whole "
     "class of trade (₹120k notional skipped).")}
{dim("Trade-off: ~4-6 signals/mo (vs v1's ~10) — deeper geometry clears the credit gate less often. "
     "DEPLOYED 2026-07-04 as a PARALLEL book (1 lot) — gold sections on PM DECISIONS + SWING TRADES. "
     "Live fills are the only unproven link. File: studies/STOCK_FADE_TP50_UPGRADE.md")}

{sub("BEGINNER EXAMPLE — one trade, start to finish (HAVELLS):")}
{p("3:10 PM: HAVELLS closes ₹1,520, breaking its 10-day high. Crowd buys calls -> calls get "
   "EXPENSIVE (IV spike). Breakouts usually stall — so v2 SELLS that expensive hope, with a safety net:")}
{p("&nbsp;&nbsp;<b>SELL 1 lot 1540 CE @ ₹55</b> (2 strikes up = breathing room) &nbsp;·&nbsp; "
   "<b>BUY 1 lot 1580 CE @ ₹36</b> (4 strikes up = the cap). "
   "Credit = 19 × 500 = <b>₹9,500 received now</b>. Gate: 19/40 = 0.475 ≥ 0.40 ✓, prem 55 ≥ 50 ✓, "
   "notional ₹20k ≤ ₹40k ✓. <b>Margin blocked = worst case = (40−19)×500 = ₹10,500</b> — not a rupee more.")}
{p("86% of the time: stock stalls, spread deflates, engine books the WIN at half the credit "
   "(<b>+₹4,750-ish within days</b>). 14%: stock keeps charging — stop fires, avg loss −₹7,922, "
   "NEVER beyond the blocked ₹10,500. You are the insurance company: keep the premium 6 times "
   "out of 7, every payout capped in advance.")}

{h("★★★ RECENT WINDOW vs REAL — why the optimistic numbers dropped")}
{sub("The verdicts above are the real out-of-sample truth; the recent forward-test window flattered every strategy:")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Strategy</td><td>Recent window (optimistic)</td><td>Real multi-year / OOS</td></tr>
<tr><td style="color:{GREEN};">Stock fade credit spread</td><td>+16–25% (Oct24→date)</td><td>+5.3% width, 5/6 yrs (bhavcopy) — <b>held</b></td></tr>
<tr><td style="color:{PURPLE};">Index fade credit spread</td><td>+12% (Oct24→date)</td><td>−1.4%, sign FLIPPED OOS — <b>failed</b></td></tr>
<tr><td>3-Family stocks (intraday)</td><td>+1.5% on 180d</td><td>dir +0.107%/tr, +ve ALL 8 yrs · net −1.0%</td></tr>
<tr><td>ORB+VWAP index (intraday)</td><td>+0.9% / 18 mo (train+test)</td><td>dir +0.04%/tr, −ve ~2/8 yrs</td></tr>
</table>
{dim("BUY strategies now tested on REAL Kite 5-min back to 2019 (studies/BUY_STRATEGIES_2019_REALTEST.md) — "
     "the intraday data Upstox couldn't reach. Only the UNDERLYING direction is measurable (intraday option "
     "premiums don't exist historically). 3-FAMILY FULL-GATE (real code: alpha-z + volume-surge ORB + "
     "alignment): 19,454 signals, 50.6% hit, +0.107%/trade, POSITIVE EVERY YEAR 2019→2026 — the gates are "
     "real (a no-gate proxy is a 48% coin flip), a fairer verdict than 'overfit'. But +0.107% is underlying; "
     "options leverage it ~10x yet theta/IV/spread/-15% stops/costs eat it -> the real-option year was −1.0% "
     "net. ORB+VWAP: 2,303 signals, thin (+0.04%/tr) and negative in ~2/8 yrs per index. Neither survives "
     "option-buying costs NET; both stay paper forward-tests — but 3-Family's DIRECTION edge is durable.")}
{dim("Two caveats I won't hide: (1) 'Validated' = on real HISTORICAL premiums, not live fills — it's "
     "+5.3% of width (~+9%/trade on margin), 54% win, and 2023 was −4.5%; modest, high-variance, still a "
     "forward-test. Lots stay at 1. (2) The stock fade's multi-year number is CLEAN bhavcopy, but its "
     "recent-window +16–25% is the older OPTIMISTIC (uncleaned) backtest — the identical clean OOS test "
     "that broke the index fade has NOT yet been run on stocks. So 'held on both windows' is clean + "
     "optimistic, not clean + clean. See studies/STOCK_OPTIONS_NO_EDGE.md Parts 10–11.")}

{h("TESTS &amp; TRADES THAT FINALIZED THE LIVE STRATEGIES")}
{dim("~9,000 real-option spread-trades across 9 tests (+ thousands of config combinations). The two "
     "live credit strategies are what SURVIVED; the rejected rows define where the edge isn't.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>#</td><td>Test (real costs)</td><td>Trades</td><td>Result</td><td>Decision</td></tr>
<tr><td>1</td><td>Stock credit spread — generic</td><td>2,387</td><td>&minus;4.7%</td><td style="color:{RED};">rejected (slippage wall)</td></tr>
<tr><td>2</td><td>Index spread — FOLLOW breakout</td><td>73+111</td><td>&minus;26 to &minus;39%, 40% win</td><td style="color:{RED};">rejected &rarr; breakouts REVERT</td></tr>
<tr><td>3</td><td>Index FADE — grid (216 cfg)</td><td>114 days</td><td>fade family validates</td><td style="color:{AMBER};">switch to FADE</td></tr>
<tr><td>4</td><td>Index FADE — tenor refine (243 cfg)</td><td>115 days</td><td>mid-tenor&middot;1-OTM&middot;w3&middot;hold</td><td style="color:{AMBER};">final config</td></tr>
<tr><td>5</td><td>Index FADE — corrected</td><td>61</td><td>+12.3% net (Oct24→date only)</td><td style="color:{AMBER};">validated on RECENT window*</td></tr>
<tr><td>6</td><td>Robustness — 5 defs &times; 5 indices</td><td>396</td><td>def-robust; BANKNIFTY &minus;6.7%</td><td style="color:{GREEN};">NIFTY+FINNIFTY (drop BNF)</td></tr>
<tr><td>7</td><td>ORB (intraday breakout)</td><td>413</td><td>NIFTY &minus;13.7%</td><td style="color:{RED};">boundary (needs real extension)</td></tr>
<tr><td>8</td><td>Stock FADE — 18 liquid</td><td>742</td><td>&minus;1.8% agg; c/w signal</td><td style="color:{AMBER};">add a gate</td></tr>
<tr><td>9</td><td>Stock FADE — full univ + gate</td><td>4,228&rarr;307</td><td>+16-25%, p5 +6.8%, 65% win (recent*)</td><td style="color:{GREEN};">DEPLOYED (gated)</td></tr>
<tr style="color:{TEXT_DIM};"><td colspan="5"><i>— then the REAL pre-2024 test on NSE bhavcopy premiums (2019→Sep 2024) settled it —</i></td></tr>
<tr><td>10</td><td>Index FADE — real bhavcopy</td><td>181</td><td>&minus;1.4%, +ve only 2019 &amp; 2024</td><td style="color:{RED};">DOWNGRADED (regime-dep)</td></tr>
<tr><td>11</td><td>Index FADE — dir+flush gate</td><td>32&rarr;27</td><td>+15.1% in-sample, &minus;2.8% OOS</td><td style="color:{RED};">salvage FAILED OOS &rarr; reverted</td></tr>
<tr><td>12</td><td>Stock FADE — real bhavcopy (gated)</td><td>718</td><td>+5.3% width, 54% win, 5/6 yrs</td><td style="color:{GREEN};">✓ VALIDATED on real data</td></tr>
<tr><td>13</td><td>MIDCPNIFTY FADE — real bhavcopy</td><td>~15</td><td>~20% win, &minus;25 to &minus;28% (illiquid)</td><td style="color:{RED};">✗ reject (opts only from mid-2022)</td></tr>
<tr><td>14</td><td>BUY strategies — real Kite 5-min 2019→date</td><td>21.8k</td><td>3-Fam dir +.107%/tr +ve every yr; ORB +.04% thin</td><td style="color:{AMBER};">dir real, not net (option costs)</td></tr>
<tr><td>15</td><td>Stock fade v2 — TP-50 grid + OOS</td><td>273+132</td><td>85%/+24.5% in-sample · 88%/+31.9% OOS · ≥79% win 8/8 yrs</td><td style="color:{GREEN};">✓ VALIDATED+OOS — awaiting deploy</td></tr>
</table>
{dim("LIVE result: the STOCK high-frequency fade (credit/width&gt;=0.40 + prem&gt;=Rs50, ~16/mo, rows 8-9,12) "
     "is the one edge VALIDATED on real multi-year premiums. The index swing (NIFTY+FINNIFTY, rows 3-6) was "
     "DOWNGRADED — net-negative on real 2019→Sep24 data and a gate salvage failed OOS (rows 10-11); it runs "
     "ungated as a small forward-test only. Both remain paper FORWARD-TESTS. *rows 5/9 are recent-window "
     "optimistic figures; rows 10-14 are the real out-of-sample verdicts. MIDCPNIFTY (row 13) rejected — "
     "illiquid, options only from mid-2022. The BUY strategies (row 14) now tested on real Kite 5-min back "
     "to 2019: 3-Family full-gate direction edge is +ve every year but net −1% as option-buying; ORB+VWAP "
     "thin/inconsistent. See studies/BUY_STRATEGIES_2019_REALTEST.md.")}

{h("★★ THE ONE EDGE THAT WORKED — SWING CREDIT SPREAD (fade the breakout)")}
{sub("Question: after every option-BUYING idea failed real costs, does anything clear them?")}
{p("Exhaustively, no buying strategy (intraday, spreads, multi-day) survives real costs + a "
   "holdout — you cross the bid-ask every leg and theta works against you. The fix is to SELL "
   "premium. A defined-risk credit spread sold AGAINST a daily index breakout (index breakouts "
   "mean-REVERT, so we FADE them), mid-tenor, held to expiry, is the first structure to clear "
   "<b>measured</b> costs out-of-sample.")}
{res("Result (real costs, ~20mo): +12-20% net/trade on margin, PF 1.4-1.95. ROBUST across 5 "
     "breakout definitions (Donchian-10/15/20/30 + prior-week) AND validated per-index: NIFTY "
     "(PF 1.95) + FINNIFTY (PF 1.44) deployed; BANKNIFTY DROPPED (tested -6.7% on 40 trades — "
     "its earlier +13% was small-sample luck). HIGH variance (a loss ~= full margin); ~2-3 "
     "signals/month. Runs LIVE as a forward-test in its own PM section — NOT yet proven on live fills.")}
{p("<b>High-frequency sibling (stocks):</b> the same fade on the full ~100-stock universe, GATED to "
   "credit/width &gt;= 0.40 + premium &gt;= Rs50 + a live liquidity check, fires <b>~16x/month</b>: "
   "65% win, +16-25% net/trade, holdout p5 +6.8%, 76/100 stocks. A breakout spikes IV -&gt; you sell "
   "the rich premium and ride the reversion + IV crush. (A <i>generic</i> stock spread loses -4.7% — "
   "the credit/width gate IS the edge.) Backtest is OPTIMISTIC (~20%/mo on margin won't fully survive "
   "live mid-cap fills) -&gt; runs as a FORWARD-TEST at 1 lot. SUPERSEDED AS LEADER by "
   "STOCK CREDIT v2 (TP-50) — see THE LEADER section above; v1 keeps running in parallel.")}
{dim("Files: studies/STOCK_OPTIONS_NO_EDGE.md (Parts 5-9) · engine/swing_credit.py · engine/stock_credit.py")}

{h("★★★ OUT-OF-TIME REGIME TEST — REAL NSE bhavcopy premiums (2019→Sep-2024)")}
{sub("Question: is the fade edge durable, or was Oct'24–Jun'26 a lucky regime? — now on REAL premiums")}
{p("NSE F&amp;O <b>bhavcopy</b> carries the actual daily CLOSE + OI of every option contract (incl. "
   "expired) back to 2019 — the data no broker API exposes. Downloaded every trading day 2019→Sep-2024 "
   "for NIFTY/FINNIFTY + the full ~100-stock universe, then ran the DEPLOYED geometry on real premiums, "
   "cleaned: OI liquidity filter, expiry settled via the UNDERLYING intrinsic, 2x stop on the real "
   "premium path, P&amp;L as net % of width (lot-independent). This REPLACES the earlier calibrated "
   "proxy — it is the real answer.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Config (deployed geometry)</td><td>Trades</td><td>Win%</td><td>Net % of width</td></tr>
<tr><td style="color:{PURPLE};">Index fade — NIFTY (no gate)</td><td>181</td><td>54%</td><td style="color:{RED};">-1.4%</td></tr>
<tr><td style="color:{TEXT};">Stock fade — UNGATED</td><td>6844</td><td>56%</td><td style="color:{RED};">-1.1%</td></tr>
<tr><td style="color:{GREEN};">Stock fade — GATED (cw&gt;=0.40, prem&gt;=Rs50)</td><td>718</td><td>54%</td><td style="color:{GREEN};">+5.3%</td></tr>
</table>
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Gated stock fade, net % of width</td><td>2019</td><td>2020</td><td>2021</td><td>2022</td><td>2023</td><td>2024</td></tr>
<tr><td style="color:{GREEN};">Net %</td><td>+22.7</td><td>+0.4</td><td>+3.0</td><td>+13.4</td><td style="color:{RED};">-4.5</td><td>+1.1</td></tr>
</table>
{res("Finding — the credit/width gate IS the edge, and it survives out-of-time. Strip it and the stock "
     "fade LOSES (-1.1%, like a generic spread and like the index). Keep it and the same universe returns "
     "+5.3% of width (~+9%/trade on margin), positive in 5 of 6 years on REAL premiums — the ONE durable, "
     "regime-robust edge. The INDEX fade is net-NEGATIVE out-of-time (-1.4%), positive only in 2019 &amp; "
     "2024 (favorable regimes) — the Oct'24–Jun'26 '+12%' landed on a good regime, NOT a real edge.")}
{dim("Reality check: the real edge is ~1/3-1/2 of the optimistic recent-window backtest (+16-25% -> +5.3% "
     "of width; 65% -> 54% win). DOWNGRADE the index swing to regime-dependent; treat the GATED STOCK "
     "credit spread as the primary fade. Keep lots at 1. File: studies/STOCK_OPTIONS_NO_EDGE.md (Part 10).")}

{h("★ REAL-OPTION OPTIMIZATION + 1-YEAR REALITY CHECK (2026-06)")}
{sub("Question: what is the edge on REAL option P&amp;L, not the underlying proxy?")}
{p("Upstox Plus unlocked historical premiums for EXPIRED contracts, so the strategy was "
   "re-backtested on actual option P&amp;L. A min-premium config (option &gt;= Rs30 + alignment, "
   "-15 stop) LOOKED great on a 180-day window: 64% win, +1.5%. But re-run on a FULL YEAR "
   "(232 trades) it came in <b>55% win, -1.0% profit</b> — overfit to a recent ~6-month regime. "
   "A train/test split INSIDE a short window is not true out-of-sample.")}
{res("Honest verdict: STOCKS have NO proven durable edge — the min-premium gate is kept only "
     "because richer options have ~3x tighter spreads (a cost filter), not for profit. The "
     "INDEX trend-ride (-15 stop) DID hold: +0.9% over 18 months (453 trades), positive on both "
     "train and test — the one real, thin edge. Stocks stay a paper forward-test.")}
{dim("File: studies/REAL_OPTION_OPTIMIZATION.md (CORRECTION at top)")}

{h("1 - Win-Rate Research Log (the baseline)")}
{sub("Question: how high can the win rate realistically go?")}
{p("Swept risk-reward, timeframes, ORB benchmarks and factor studies across many configs.")}
{res("Result: a hard ~52-57% out-of-sample win-rate wall. No single tweak breaks it; the "
     "edge has to come from FILTERING bad trades, not a magic indicator.")}
{dim("File: studies/WIN_RATE_RESEARCH_LOG.md")}

{h("2 - Gate 3: Market Alignment (the Final Strategy)")}
{sub("Question: does NOT fighting the Nifty's intraday direction help?")}
{p("Only LONG when Nifty is up, only SHORT when Nifty is down. Backtested 30 + 60 days.")}
{res("Result (60-day): win ~59%, P&amp;L +Rs17,299 -&gt; +Rs30,911 (~2x), fewer trades. The gain "
     "is risk, not hit-rate: it cuts the trend-fighting trades that lose BIG. NOW LIVE.")}
{dim("File: studies/FINAL_STRATEGY_TESTING_60DAY.md")}

{h("3 - Gate 4: Don't Chase (entry-extension filter)")}
{sub("Question: do signals that fire after the stock already ran lose edge?")}
{p("Found via 365-day analysis: entries already &gt;2.9% extended from the open won ~45% vs "
   "~55% in the sweet spot. Skip the chasers. Tuned 2.6 vs 2.9 (2.9 won every metric).")}
{res("Result (60-day): win 59% -&gt; 61%, P&amp;L +Rs32,519 -&gt; +Rs36,792, return-on-capital "
     "+1.7% -&gt; +2.8% on 26% fewer trades. A risk-efficiency gain. NOW LIVE.")}
{dim("File: studies/GATE4_DONT_CHASE.md")}

{h("4 - Gate 5: Wide Open (opening-range width filter)")}
{sub("Question: can a 5th gate raise the win rate at the same +10/-20 risk-reward?")}
{p("A disciplined loop: collect 90 days of trades with features + premium paths, search "
   "candidates by out-of-sample expectancy, then VALIDATE on 365 days. 'Wide opening range "
   "(&gt;=0.8% of price)' = real morning momentum; narrow opens are chop. (Time-of-day looked "
   "great on the small sample but flipped on 365 days -> rejected as noise.)")}
{res("Result (365-day, 506 trades, validated): directional win 51% -&gt; 54%; option win 30-day "
     "61% -&gt; 66%, 60-day 66% -&gt; 70% at the SAME +10/-20. DEPLOYED as Gate 5.")}
{dim("File: studies/GATE5_WIDE_OPEN.md")}

{h("5 - Index ORB+VWAP: Trend-Ride Exit (the index fix)")}
{sub("Question: why was the index strategy losing every day?")}
{p("The old fixed +20% target capped winners while still taking full -20% stops - backwards "
   "for a trend setup. Replaced with: ride the winner, exit on VWAP reclaim after +12%, hard "
   "-20% stop; plus a clean-trend entry filter.")}
{res("Result (60-day): win 27% -&gt; 63%, -2.6%/trade -&gt; +0.8%/trade. Stops the bleed (still "
     "~breakeven net, a forward-test). NOW LIVE.")}
{dim("File: studies/INDEX_TREND_RIDE_EXIT.md")}

{h("6 - 365-Day Directional Validation (does the edge last a year?)")}
{sub("Question: does the signal predict direction over a full year, not just a lucky month?")}
{p("Option premiums only reach ~1 month back, but 5-min PRICE reaches ~365 days. Tested the "
   "directional edge on 1,117 signals over the year.")}
{res("Result: raw signal = coin flip (49%). ALIGNED (Gate 3) = 52% hit, +0.13%/trade, and it "
     "HOLDS across all 12 months (772 trades). The edge is real but THIN - options leverage it.")}
{dim("File: studies/UNDERLYING_VALIDATION_365D.md")}

{h("7 - Stock Option Exit Cap (+10% vs no cap)")}
{sub("Question: should we remove the +10% target and let stock winners ride?")}
{p("Tested +10% / +20% / +30% / no-cap on the same trades, -20% stop. NOT deployed.")}
{res("Result: removing the cap is INCONSISTENT - worst on 30-day (+0.5%), best on 60-day "
     "(+3.6%) = high variance, not a reliable edge. The +10% cap gives the best win rate "
     "(~60%) and lowest variance. KEPT at +10%.")}
{dim("File: studies/STOCK_OPTION_EXIT_CAP.md")}

{h("8 - Prophet Forward-Test (forecasting models)")}
{sub("Question: can a time-series forecaster (Prophet) predict the index or the P&amp;L?")}
{p("Forecast NIFTY/BANKNIFTY + the equity curve, then cross-validated the error.")}
{res("Result: 20-day directional hit-rate 43% (NIFTY) / 21% (BANKNIFTY) - WORSE than a coin "
     "flip; the forecast error is bigger than the move it predicts. Daily markets are near-"
     "random. NOT wired into the app - it would add noise, not signal.")}
{dim("File: studies/PROPHET_FORWARD_TEST.md")}

{h("9 - Data Availability Limits (what can be backtested)")}
{sub("Question: can we backtest 180 / 365 days on real option data?")}
{p("Probed Upstox depth. Daily price = 2+ yrs, 5-min price = ~1 yr, but option-premium "
   "candles = only ~3-4 weeks (expired contracts drop out of the instrument master).")}
{res("Result: a clean OPTION-P&amp;L backtest is capped at ~1 month. Longer validation needs the "
     "underlying-proxy (done), synthetic Black-Scholes premiums, or a paid options vendor.")}
{dim("File: studies/DATA_AVAILABILITY_LIMITS.md")}

{h("The honest bottom line")}
{p("After ~9,000 real-option spread-trades: <b>option BUYING has no net edge</b> out-of-sample (the "
   "3-Family gates and the index trend-ride are ~breakeven net — kept as forward-tests, not money-makers). "
   "The real, repeatable edge is the opposite — <b>SELLING a credit spread that FADES a breakout</b> — but "
   "real pre-2024 premiums (NSE bhavcopy 2019→Sep 2024) narrowed that to ONE strategy: the <b>gated STOCK "
   "fade</b> (credit/width≥0.40), which held +5.3% of width / 54% win across 5 of 6 years. The INDEX swing "
   "did NOT hold — it was net-negative (−1.4%) on real multi-year data and a gate salvage failed "
   "out-of-sample, so it's downgraded to a regime-dependent forward-test. Nothing here is proven on live "
   "fills — the backtests are real but optimistic, and live fills are the only honest judge.")}
<p style="color:{TEXT_DIM};margin-top:14px;font-size:10px;">
All studies reproducible from /studies on GitHub. Gross of costs. For educational use only. Not financial advice.
</p>
</div>
"""

    def _screen_readme(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("README  -  how this system trades, in plain language"))
        doc = QTextEdit(); doc.setReadOnly(True); doc.setFont(QFont("Menlo", 11))
        doc.setHtml(self._readme_html())
        v.addWidget(doc)
        return w

    def _readme_html(self) -> str:
        from engine import config as C

        def h(t):   # section header
            return f'<p style="color:{GREEN};font-size:15px;font-weight:bold;margin-top:18px;">{t}</p>'
        def sub(t):
            return f'<p style="color:{AMBER};font-weight:bold;margin-top:10px;">{t}</p>'
        def p(t):
            return f'<p style="color:{TEXT};margin:4px 0;">{t}</p>'
        def dim(t):
            return f'<p style="color:{TEXT_DIM};margin:3px 0;">{t}</p>'

        return f"""
<div style="color:{TEXT};">

<p style="color:{CYAN};font-size:17px;font-weight:bold;">SYSTEM SETUP &amp; APPLICATION MANUAL</p>
{dim("How this system is installed, how it runs, and how to use every tab. For WHAT the strategies are "
     "and how they were validated, see the STUDIES tab. Mode: PAPER, signals-only — the headless engine "
     "fires signals and records them daily; YOU place every order manually in Upstox. It never auto-trades.")}
{p("<b>TELEGRAM ALERTS — LIVE (2026-07-13):</b> every book's new signal is pushed to the Telegram channel the "
   "moment the engine opens the position — all 8 sources wired (3-Family, Stock Credit v1 + v2 UNION, "
   "Swing, Monthly Futures, Monthly Long-Call, 0DTE NIFTY, SENSEX/BANKNIFTY 0DTE). One post per signal, "
   "no repeats; place the order manually in Upstox as usual. A quiet channel = nothing cleared the gates "
   "that day. Config in .env (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID; a channel id fans out to all joiners).")}

{h("1 — WHAT IT IS (in one breath)")}
{p(f"A paper-trading engine for NSE options + futures running <b>6 parallel strategy books</b> on "
   f"~{len(C.UNIVERSE)} stocks + NIFTY/BANKNIFTY/FINNIFTY/SENSEX. It scans, scores, and surfaces "
   "BUY/SELL signals on a dashboard; you place the orders. The books: <b>stock fade v2 UNION</b> (the "
   "leader) + stock fade v1 (SELL credit spreads), THREE <b>0DTE expiry-day spreads</b> (NIFTY Tue flip · "
   "SENSEX Thu · BANKNIFTY monthly), the index-fade forward-test, the <b>monthly FUTURES pullback</b> "
   "(REV1-v2, BUY front-month futures — paper, needs ~₹15L), and the intraday 3-Family scanner "
   "(hidden; data heartbeat). Full strategy detail + backtests: <b>STUDIES tab</b>.")}

{h("2 — SETUP (Mac and Windows)")}
{p("<b>macOS:</b> <b>1.</b> git clone the repo &amp; cd in. <b>2.</b> Run <b>./setup.sh</b> — makes the venv, "
   "installs deps, writes the .env template, and installs the two launchd jobs (engine + viewer, auto-start). "
   "<b>3.</b> Edit <b>.env</b> and add your free Upstox <b>Analytics</b> token (read-only feed, no trading "
   "token). <b>4.</b> Kickstart the engine; the viewer auto-launches 09:00 on weekdays.")}
{p("<b>Windows:</b> <b>1.</b> Install Python 3.9+ (tick 'Add to PATH'). <b>2.</b> git clone &amp; cd in. "
   "<b>3.</b> Run <b>setup.bat</b> — venv + deps + .env template. <b>4.</b> Edit <b>.env</b>, add your token. "
   "<b>5.</b> Start <b>run_engine.bat</b> (keep it minimised) and <b>run_viewer.bat</b> (the dashboard). "
   "Windows has no launchd, so you start those two yourself; drop a shortcut to run_engine.bat in "
   "shell:startup to auto-start at login.")}
{dim("SECURITY: .env holds your token — it is gitignored and must NEVER be committed. Needs Python 3.9+ and "
     "internet during market hours. Built/run daily on macOS; the Python engine + PySide6 dashboard are "
     "cross-platform (the two Mac-only bits — auto-start and keep-awake — simply no-op on Windows).")}

{h("3 — HOW IT RUNS (engine vs viewer — two processes)")}
{p(f"<b style='color:{GREEN}'>ENGINE</b> (headless, launchd job, always on): does ALL the work — scans "
   "every 5 min in market hours, fires signals, resolves trades, books at the 15:30 close, and saves "
   "everything to local files (engine.db, signals.db, trade_log.json, the credit-spread books). Wakes "
   "every 5 s while the market is open; idles when closed. Runs whether or not this window is open.")}
{p(f"<b style='color:{PURPLE}'>VIEWER</b> (this app, read-only): never scans/fires/writes — it only reads "
   "what the engine wrote and displays it (header shows 'READ-ONLY VIEWER — engine scan Nm ago'). Re-reads "
   "disk every ~5–15 s. <b>Why split:</b> a viewer crash can never stop trading, and timing is independent "
   "of the display. <b>For unattended running:</b> keep the laptop on, lid open, on AC power.")}

{h("4 — THE APP, TAB BY TAB")}
{sub("PM DECISIONS — today's actions")}
{p("The board of what to place TODAY. A live banner at the top says which window is active right now. One "
   "section per strategy, each labelled with its signal window. <b>Credit spreads show as two rows</b> — a "
   "SELL row (the leg you sell + premium received) and a BUY row (the hedge + premium paid) — with LOT and "
   "total MARGIN. The option type (CE/PE) is in the ACTION column so it's never hidden by a long name. "
   "Shows only <b>today's</b> credit-spread signals; ongoing ones live in SWING TRADES. The <b>MONTHLY "
   "FUTURES PULLBACK</b> section is the exception: its 5 BUY-FUT positions stay visible all month "
   "(the trade IS the month) with live P&amp;L, TP/SL levels and day count.")}
{sub("WATCHLIST — the funnel (stocks)")}
{p("Every stock that cleared Gate 1 (alpha), progressing through the remaining gates toward PM DECISIONS. "
   "Sorted closest-to-firing on top (e.g. '3/4 next: ORB'). This is where you watch a 3-Family setup build.")}
{sub("SWING TRADES — the credit-spread trade log")}
{p("The two SELL strategies (index swing + stock), split. Each spread is <b>two leg rows</b> with per-leg "
   "entry / current / P&amp;L, then the consolidated <b>NET</b>. A stats bar shows trades, win rate, margin "
   "deployed and booked/open P&amp;L. The 'NOW' value keeps running live even after a WIN/LOSS is booked.")}
{sub("TRADE LOG — the intraday BUY strategies")}
{p("3-Family stocks + ORB NIFTY/BANKNIFTY, LIVE vs SIMULATION. Because intraday capital recycles daily, "
   "returns are shown on the <b>average capital deployed per day</b>, with an <b>IRR</b> annualized over "
   "CALENDAR days (idle weekends count) — the honest yardstick, gated until ~30 days of track record.")}
{sub("STUDIES — the strategies &amp; the research")}
{p("The strategy summary table (win/loss, avg P&amp;L per trade, return per month) + the full tests-and-"
   "trades trail: ~9,000 real-option spread-trades across 9 tests, showing what worked and what was "
   "rejected. This is the 'why' behind every live strategy.")}

{h("5 — SIGNAL TIMING (IST, trading days only)")}
{p(f"<b>Stock options (3-Family):</b> {C.MARKET_OPEN}–{C.MARKET_CLOSE}, most active 10:30–11:00 · "
   f"<b>ORB+VWAP index:</b> before {C.ORB_VWAP_ENTRY_CUTOFF} · "
   f"<b>Stock &amp; Swing credit spreads:</b> once/day, ~{C.STOCK_CREDIT_SCAN_AFTER} (a daily breakout needs "
   f"the near-close) · <b>Monthly futures pullback:</b> once per expiry cycle, ~{C.MONTHLY_FUT_SCAN_AFTER} "
   "on the first trading day after the monthly expiry — only when NIFTY &gt; its 200DMA (stands aside "
   "otherwise, and says so). Signals are selective — many days few or none; that's the point, not a fault.")}

{h("6 — HOW TO PLACE AN ORDER")}
{p("<b>BUY strategies:</b> the PM row gives the exact BUY — e.g. 'BUY RELIANCE 1400 CE @ Rs X'. Place it in "
   "Upstox; exit at the shown target/stop. <b>Credit spreads (SELL):</b> place <b>both legs together</b> — "
   "the SELL row first (you receive the credit), the BUY row as the hedge (caps the loss). Read the strikes, "
   "type and premiums straight off the two rows. Hold to expiry unless the stop (2× credit) triggers. "
   "<b>Monthly futures (BUY FUT):</b> buy 1 lot of the front-month future named in the row; exit "
   "market-on-close the day the close crosses the TP or SL shown in the AMOUNT column, else hold to "
   "expiry. PAPER-ONLY at current capital — the book needs ~₹15L to trade for real.")}

{h("7 — RISK CONTROLS")}
{p(f"Halt after <b>{C.CONSECUTIVE_LOSS_HALT}</b> stop-outs in a row · intraday trades force-closed by "
   f"{C.KILL_SWITCH_TIME} (never held overnight) · credit spreads are defined-risk (max loss = margin) and "
   "carry overnight to expiry. <b>Sizing:</b> KEEP LOTS AT 1 while forward-testing; never fill your whole "
   "margin — ~16 correlated stock spreads can move against you together on a bad day.")}

{h("8 — HEALTH CHECKS &amp; DATA")}
{p("<b>Engine alive?</b> the viewer header shows the last scan age; if it stops advancing during market "
   "hours, the engine isn't scanning. <b>Data:</b> Upstox V3 on a read-only Analytics token (live LTP, "
   "5-min &amp; daily candles, index/option chains); real expired-option history ~Oct 2024–Jun 2026 for "
   "backtests. All data saved locally, daily. Yahoo is an emergency fallback only.")}

<p style="color:{TEXT_DIM};margin-top:16px;font-size:10px;">
Universe: {len(C.UNIVERSE)} stocks &nbsp;·&nbsp; weights TREND {C.FAMILY_WEIGHTS['TREND']['weight']} / FLOW {C.FAMILY_WEIGHTS['FLOW']['weight']} / EVENT {C.FAMILY_WEIGHTS['EVENT']['weight']} &nbsp;·&nbsp; For educational use only. Not financial advice.
</p>

</div>
"""

    # ── interactions ──────────────────────────────────────────────────────────
    def switch(self, idx: int):
        self.active_screen = idx
        self.stack.setCurrentIndex(idx)
        self._highlight_tab(idx)

    def trigger_scan(self):
        """READ-ONLY: load the latest scan the headless engine wrote to disk and refresh
        the display. The GUI never scans, executes, or books — engine_runner does all that."""
        self._load_latest_scan()
        self._refresh_pm(); self._refresh_watchlist(); self._refresh_swing_tab(); self._refresh_log()
        self._refresh_zero_dte_tab()

    def _load_latest_scan(self):
        """Read the engine's latest scan snapshot (results + ORB+VWAP rows) from disk."""
        import json
        try:
            if _os.path.exists(LATEST_SCAN):
                d = json.load(open(LATEST_SCAN))
                self.last_scan_results = d.get("results", []) or []
                self.agent.orbvwap_signals = d.get("orbvwap", []) or []
                self._latest_scan_ts = d.get("ts")
        except Exception as e:
            logger.warning(f"load latest_scan failed: {e}")
        # swing credit spreads — its own snapshot (engine writes data/swing.json on resolve/scan)
        try:
            if _os.path.exists(SWING_SNAP):
                s = json.load(open(SWING_SNAP))
                self._swing_rows = s.get("rows", []) or []
        except Exception as e:
            logger.warning(f"load swing.json failed: {e}")
        try:
            if _os.path.exists(MONTHLY_SNAP):
                s = json.load(open(MONTHLY_SNAP))
                self._monthly_rows = s.get("rows", []) or []
            if _os.path.exists(MONTHLY_CALL_SNAP):
                sc = json.load(open(MONTHLY_CALL_SNAP))
                self._monthly_call_rows = sc.get("rows", []) or []
        except Exception as e:
            logger.warning(f"load monthly_fut.json failed: {e}")
        try:
            if _os.path.exists(STOCKCR_SNAP):
                s = json.load(open(STOCKCR_SNAP))
                self._stockcr_rows = s.get("rows", []) or []
            if _os.path.exists(STOCKCR2_SNAP):
                s2 = json.load(open(STOCKCR2_SNAP))
                self._stockcr2_rows = s2.get("rows", []) or []
        except Exception as e:
            logger.warning(f"load stock_credit.json failed: {e}")

    # ── refreshers ────────────────────────────────────────────────────────────
    @staticmethod
    def _underlying_kind(ticker: str) -> str:
        if ticker == "NIFTY": return "NIFTY"
        if ticker == "BANKNIFTY": return "BANKNIFTY"
        return "STOCK"

    def _dir_color(self, d):
        return QColor(GREEN) if d == "LONG" else QColor(RED) if d == "SHORT" else QColor(TEXT_DIM)

    def _set_row(self, table, row, values, fg=None, bg=None):
        for col, val in enumerate(values):
            it = QTableWidgetItem(str(val))
            if fg: it.setForeground(QBrush(fg))
            if bg: it.setBackground(QBrush(bg))
            table.setItem(row, col, it)

    def _color_cell(self, table, row, col, color):
        it = table.item(row, col)
        if it:
            it.setForeground(QBrush(color))

    # ── PM DECISIONS persists the DAY'S fired signals (not just the current scan) ──
    def _ensure_fired_today(self):
        """READ-ONLY: reset at day rollover, then RE-SEED from the engine's trade log on
        EVERY refresh so PM DECISIONS picks up signals the headless engine writes mid-day.
        (_seed_fired_from_log is idempotent — it skips tickers already shown.)"""
        today = datetime.now(IST).date()
        if getattr(self, "_fired_day", None) != today:
            self._fired_day = today
            self._fired_today = []
            try:    # refresh the daily CSV snapshot of signals.db (once per day)
                from engine import signal_db
                signal_db.export_csv()
            except Exception:
                pass
        self._seed_fired_from_log(today)   # re-read the trade log each refresh (read-only viewer)

    def _seed_fired_from_log(self, today):
        try:
            import os, json
            from engine.config import TRADE_LOG_PATH
            if not os.path.exists(TRADE_LOG_PATH):
                return
            with open(TRADE_LOG_PATH) as f:
                data = json.load(f)
            trades = data.get("trades", []) if isinstance(data, dict) else data
            for t in trades:
                st = str(t.get("signal_time", ""))
                tk = t.get("ticker")
                if not tk or not st.startswith(today.isoformat()):
                    continue
                if any(x["ticker"] == tk for x in self._fired_today):
                    continue
                self._fired_today.append({
                    "time": st[11:19] if len(st) >= 19 else st, "ticker": tk,
                    "direction": t.get("direction"),
                    "instrument": t.get("instrument") or ("CALL" if t.get("direction") == "LONG" else "PUT"),
                    "kind": self._underlying_kind(tk), "order": None,
                    "alpha_z": t.get("alpha_z"), "breadth": t.get("breadth"), "vol_ratio": None,
                })
        except Exception as e:
            logger.warning(f"Seed fired-from-log failed: {e}")

    def _record_fired(self, sig):
        """Capture a freshly-fired signal so it stays on PM DECISIONS all day."""
        self._ensure_fired_today()
        tk = sig.get("ticker")
        if not tk or any(x["ticker"] == tk for x in self._fired_today):
            return
        order = None
        try:
            from engine.options import build_live_option_order
            from engine.data_fetcher import get_cached_ltp
            spot = get_cached_ltp(tk) or sig.get("entry_price") or 0
            order = build_live_option_order(tk, spot, sig.get("direction", "LONG"))
        except Exception:
            pass
        self._fired_today.append({
            "time": datetime.now(IST).strftime("%H:%M:%S"), "ticker": tk,
            "direction": sig.get("direction"),
            "instrument": "CALL" if sig.get("direction") == "LONG" else "PUT",
            "kind": self._underlying_kind(tk), "order": order,
            "alpha_z": sig.get("alpha_z"), "breadth": sig.get("breadth"),
            "vol_ratio": sig.get("vol_ratio"),
        })

    @staticmethod
    def _fit_table(table):
        """Size the table to show ALL its rows (no cramped internal scroll). Safe because the
        PM / TRADE LOG / SWING screens are each wrapped in a QScrollArea (see _scroll), so the
        whole page scrolls smoothly and the nav bar stays fixed above."""
        rh = table.verticalHeader().defaultSectionSize() or 32
        n = max(table.rowCount(), 1)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(34 + n * rh + 6)   # header + rows + padding

    def _scroll(self, inner: QWidget) -> QScrollArea:
        """Wrap a screen's content in a vertical scroll area so long/stacked sections stay
        readable and navigation is smooth (the tab bar lives outside the stack, so it's unaffected)."""
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(inner)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return sa

    def _refresh_outcomes(self):
        """Fast (5s) refresh of the outcome-sensitive views only — PM DECISIONS + TRADE LOG —
        so a freshly booked WIN/LOSS appears within seconds. Fully guarded: a read error here
        must never crash the read-only viewer."""
        try:
            self._refresh_pm()
        except Exception as e:
            logger.warning(f"outcome refresh (pm): {e}")
        try:
            self._refresh_log()
        except Exception as e:
            logger.warning(f"outcome refresh (log): {e}")

    def _update_pm_now_hint(self):
        """Dynamic 'where to look NOW' banner on PM DECISIONS, driven by the IST clock."""
        if not hasattr(self, "pm_now_hint"):
            return
        now = datetime.now(IST); m = now.hour * 60 + now.minute; wd = now.weekday()
        holiday = getattr(self, "_holiday", False)
        if wd >= 5:
            txt, col = "Weekend — market closed. No signals today; next session Monday ~09:15.", TEXT_DIM
        elif holiday:
            txt, col = "Market holiday — no signals today. Next trading day ~09:15.", TEXT_DIM
        elif m < 9 * 60 + 15:
            txt, col = "Pre-open — scanning starts 09:15; intraday signals from ~09:30.", AMBER
        elif m < 15 * 60 + 10:
            txt, col = ("● Market open. On expiry days the 0DTE spread posts right after the 09:16 open; "
                        "the CREDIT books — ★v2 + v1 + index swing — all scan at ~15:10.", GREEN)
        elif m <= 15 * 60 + 35:
            txt, col = ("● NOW: ~15:10 CREDIT SCAN — check ★ STOCK CREDIT v2 (gold) first, then v1 + INDEX SWING. "
                        "New spreads appear here to place before the close.", CYAN)
        else:
            txt, col = "Market closed — today's signals are booked. Next session tomorrow ~09:15.", TEXT_DIM
        self.pm_now_hint.setText("  " + txt)
        self.pm_now_hint.setStyleSheet(f"color:{col}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")

    def _refresh_union_watch(self):
        """Populate the always-on UNION WATCHLIST panel from data/union_watchlist.json (breakout
        stocks only, each with a per-gate tick-bar). Read-only; failures never disturb the UI."""
        import json as _json
        try:
            path = _os.path.join(DATA_DIR, "union_watchlist.json")
            if not _os.path.exists(path):
                self.pm_watch_hdr.setText("UNION WATCHLIST — no scan yet today (engine builds it at 3:05 PM, near the close)")
                self.pm_watch.setRowCount(0); return
            d = _json.load(open(path)); rows = d.get("rows", []); ts = d.get("ts", "")
            # clear a stale (prior-day) watchlist — only ever show TODAY's scan
            if not ts.startswith(datetime.now(IST).date().isoformat()):
                self.pm_watch_hdr.setText("UNION WATCHLIST — no scan yet today (engine builds it at 3:05 PM, near the close)")
                self.pm_watch.setRowCount(0); return
            hhmm = ts[11:16] if len(ts) >= 16 else "—"
            self.pm_watch_hdr.setText(f"UNION WATCHLIST · today's breakout stocks only — last scan {hhmm} · "
                                      f"{d.get('breakouts',0)} breakouts · {d.get('passed',0)} passed")
            self.pm_watch.setRowCount(len(rows))
            for i, row in enumerate(rows):
                g = row.get("gate", ""); evaluable = g not in ("NO_STRIKE", "NO_QUOTE")
                cw = row.get("cw"); prem = row.get("prem"); oi = row.get("oi")
                cwcell = premcell = liqcell = "—"
                if evaluable:
                    # show the ACTUAL number in every gate cell (with ✓/✗), not a bare tick
                    cwcell = f"{'✓' if row.get('cw_ok') else '✗'} {cw}"
                    premcell = f"{'✓' if row.get('prem_ok') else '✗'} ₹{prem}"
                    liqcell = "✓" if row.get("liq_ok") else f"✗ OI{oi}"
                result = "★ SIGNAL" if g == "PASS" else ("blocked" if evaluable else g.replace("_", " ").lower())
                # legs instead of a redundant breakout tick (every row IS a breakout)
                fmtk = lambda x: ("%g" % x) if isinstance(x, (int, float)) else None
                ss, ls = fmtk(row.get("short_strike")), fmtk(row.get("long_strike"))
                verb = "CE" if "CALL" in str(row.get("side", "")) else "PE"
                legs = f"SELL {ss} / BUY {ls} {verb}" if ss and ls else "—"
                sd = row.get("side", "")
                side_s = "BEAR" if "CALL" in sd else ("BULL" if "PUT" in sd else (sd or "—"))
                _e = str(row.get("expiry", "") or "")     # 2026-07-28 -> "28-Jul" (fits the column)
                _MON = ("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
                try:
                    exp_s = f"{_e[8:10]}-{_MON[int(_e[5:7]) - 1]}" if len(_e) >= 10 else (_e or "—")
                except Exception:
                    exp_s = _e or "—"
                _lot = row.get("lot"); _mp = row.get("max_profit"); _ml = row.get("max_loss")
                lot_s = str(_lot) if _lot else "—"
                mp_s = f"₹{_mp:,}" if isinstance(_mp, (int, float)) else "—"
                ml_s = f"₹{_ml:,}" if isinstance(_ml, (int, float)) else "—"
                vals = [row.get("sym", "—"), side_s, f"D{row.get('dc','')}",
                        legs, exp_s, lot_s, cwcell, premcell, liqcell, mp_s, ml_s, result]
                self._set_row(self.pm_watch, i, vals)
                self._color_cell(self.pm_watch, i, 11, GREEN if g == "PASS" else (AMBER if evaluable else RED))
                for c in (2, 4, 5, 6, 7, 8, 9, 10, 11):    # centre everything except STOCK/SIDE/legs
                    it = self.pm_watch.item(i, c)
                    if it: it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            logger.warning(f"union watch refresh: {e}")

    def _refresh_pm(self):
        self._update_pm_now_hint()
        self._refresh_union_watch()
        self._ensure_fired_today()
        from engine.options import build_live_option_order
        from engine.data_fetcher import get_cached_ltp, fetch_upstox_ltp
        fired = sorted([f for f in self._fired_today if f["kind"] == "STOCK"],
                       key=lambda f: f["time"], reverse=True)   # newest on top
        outcomes = self._today_trade_outcomes()
        self.pm_empty.setVisible(len(fired) == 0)
        self.pm_stock.setRowCount(len(fired))
        for r, f in enumerate(fired):
            order = f.get("order")
            if order is None:  # seeded-from-log row — try to build the option order now
                try:
                    spot = get_cached_ltp(f["ticker"]) or 0
                    order = build_live_option_order(f["ticker"], spot, f.get("direction", "LONG"))
                    f["order"] = order
                except Exception:
                    order = None
            sym = f["ticker"].replace(".NS", "")
            # (read-only viewer — the engine writes signals.db, the GUI only displays)
            oc_rec = outcomes.get((sym, "3-Family"))
            status = self._pm_status(self._oc_status(oc_rec))   # OPEN / WIN / LOSS, synced to trade log
            kind = (order["instrument"] if order else f.get("instrument", ""))
            fg = QColor(GREEN) if kind == "CALL" else (QColor(RED) if kind == "PUT" else QColor(AMBER))
            if not order:
                vals = [f["time"], sym, kind, "—", "—", "—", "—", "—", "—", "—", "—", status]
                self._set_row(self.pm_stock, r, vals, fg=fg)
                self._color_cell(self.pm_stock, r, 11, self._status_color(status)); continue
            # live current premium of the exact option — fetch ONLY while OPEN. A booked
            # (WIN/LOSS) trade needs no live quote, so skipping it keeps the fast 5s outcome
            # refresh off the network for closed rows (no GUI-thread stall, no wasted API calls).
            curp = "—"
            if status == "OPEN":
                try:
                    lt = fetch_upstox_ltp(order["option_key"])
                    if lt.get("success") and lt.get("price"):
                        curp = f"Rs {lt['price']:.2f}"
                except Exception:
                    pass
            elif oc_rec and oc_rec.get("exit"):
                curp = f"Rs {oc_rec['exit']:.2f}"   # booked exit price (closed) — not a stale live quote
            cap = f"Rs {order['capital']:,.0f}" if order.get("capital") else "—"
            vals = [f["time"], sym, kind, f"{order['strike']:.2f}", order["expiry"],
                    f"Rs {order['premium']:.2f}", curp,
                    f"Rs {order['target_premium']:.2f}", f"Rs {order['stop_premium']:.2f}",
                    order.get("lot_size", "—"), cap, status]
            self._set_row(self.pm_stock, r, vals, fg=fg)
            self._color_cell(self.pm_stock, r, 11, self._status_color(status))

        self._fit_table(self.pm_stock)
        self._refresh_swing()
        self._refresh_stock_credit()
        self._refresh_monthly()
        self._refresh_monthly_call()
        self._refresh_orbvwap()

    @staticmethod
    def _db_record_stock(f, order, sym):
        try:
            from engine import signal_db
            o = order or {}
            signal_db.record_signal(
                time=f.get("time"), strategy="3-Family", symbol=sym,
                direction=f.get("direction"), opt_type=f.get("instrument"),
                strike=o.get("strike"), expiry=o.get("expiry"),
                entry_premium=o.get("premium"), target_premium=o.get("target_premium"),
                stop_premium=o.get("stop_premium"), lot=o.get("lot_size"),
                capital=o.get("capital"), alpha_z=f.get("alpha_z"),
                breadth=f.get("breadth"), vol_ratio=f.get("vol_ratio"), status="OPEN")
        except Exception:
            pass

    def _today_trade_outcomes(self):
        """Map today's booked trades -> outcome, so PM DECISIONS shows the SAME status as the
        authoritative trade log: OPEN while live, WIN/LOSS once closed. Read-only (the viewer
        never writes). Keyed by (symbol-without-.NS, strategy)."""
        out = {}
        try:
            import json as _json
            p = _os.path.join(DATA_DIR, "trade_log.json")
            if not _os.path.exists(p):
                return out
            d = _json.load(open(p))
            today = datetime.now(IST).date().isoformat()
            for t in d.get("trades", []):
                if (t.get("signal_time") or "").startswith(today):
                    key = ((t.get("ticker") or "").replace(".NS", ""), t.get("strategy"))
                    out[key] = {"outcome": t.get("outcome"),         # 'WIN'/'LOSS'/None(open)
                                "exit": t.get("exit_premium"),       # the price it was BOOKED at
                                "option_key": t.get("option_key")}   # for a LIVE quote while open
        except Exception as e:
            logger.warning(f"trade outcomes read failed: {e}")
        return out

    @staticmethod
    def _oc_status(rec):
        return rec.get("outcome") if isinstance(rec, dict) else rec

    @staticmethod
    def _pm_status(outcome):
        """PM DECISIONS status label, synced to the trade log: WIN / LOSS when booked, else OPEN."""
        if outcome == "WIN":
            return "WIN"
        if outcome == "LOSS":
            return "LOSS"
        return "OPEN"

    def _status_color(self, status):
        if status == "WIN":
            return QColor(GREEN)
        if status == "LOSS":
            return QColor(RED)
        return QColor(AMBER)   # OPEN

    def _today_index_signals(self):
        """Today's ORB+VWAP signals from signals.db — PERSISTENT (survives engine restart
        and the 11:00 entry cutoff), so a fired NIFTY/BANKNIFTY signal stays on PM all day."""
        out = {}
        try:
            import sqlite3
            db = _os.path.join(DATA_DIR, "signals.db")
            if not _os.path.exists(db):
                return out
            con = sqlite3.connect(db)
            today = datetime.now(IST).date().isoformat()
            cols = ["time", "symbol", "direction", "opt_type", "strike", "expiry",
                    "entry_premium", "stop_premium", "lot", "status"]
            for row in con.execute(
                    f"SELECT {','.join(cols)} FROM pm_signals WHERE date=? AND strategy='ORB+VWAP'",
                    (today,)):
                d = dict(zip(cols, row))
                out[d["symbol"]] = d            # latest row per index (UNIQUE constraint)
            con.close()
        except Exception as e:
            logger.warning(f"index signals read failed: {e}")
        return out

    def _refresh_orbvwap(self):
        if not hasattr(self, "pm_orbvwap"):
            return   # RETIRED: PM slot now shows STOCK CREDIT v2
        """Index ORB+VWAP rows on PM DECISIONS. A FIRED signal persists for the whole day
        (from signals.db); an index with no signal yet shows the live WATCHING placeholder."""
        live = {s.get("index"): s for s in (getattr(self.agent, "orbvwap_signals", []) or [])}
        fired = self._today_index_signals()
        outcomes = self._today_trade_outcomes()
        indices = ["NIFTY", "BANKNIFTY"]
        self.pm_orbvwap.setRowCount(len(indices))
        for r, idx in enumerate(indices):
            rec = fired.get(idx)
            status = None
            if rec and rec.get("entry_premium"):     # a real fired signal today — persist it
                kind = rec.get("opt_type") or "—"
                strike = f"{rec['strike']:.2f}" if isinstance(rec.get("strike"), (int, float)) else "—"
                entry = f"Rs {rec['entry_premium']:.2f}"
                stop = f"Rs {rec['stop_premium']:.2f}" if rec.get("stop_premium") else "—"
                oc_rec = outcomes.get((idx, "ORB+VWAP"))
                status = self._pm_status(self._oc_status(oc_rec))   # OPEN / WIN / LOSS, synced to trade log
                # CURRENT premium:
                #  - booked (WIN/LOSS): the EXIT it was booked at (the engine 'current' goes
                #    stale post-11:00 cutoff and can read below intrinsic — the impossible 370).
                #  - OPEN: a LIVE option quote fetched here every refresh (~5s), so it's dynamic
                #    like the stock rows — not the engine's frozen 5-min/post-cutoff value.
                lr = live.get(idx) or {}
                cur = "—"
                if status in ("WIN", "LOSS") and oc_rec and oc_rec.get("exit"):
                    cur = f"Rs {oc_rec['exit']:.2f}"
                elif status == "OPEN" and oc_rec and oc_rec.get("option_key"):
                    try:
                        from engine.data_fetcher import fetch_upstox_ltp
                        lt = fetch_upstox_ltp(oc_rec["option_key"])
                        if lt.get("success") and lt.get("price"):
                            cur = f"Rs {lt['price']:.2f}"
                    except Exception:
                        pass
                    if cur == "—" and lr.get("current"):   # fallback to engine's value
                        cur = f"Rs {lr['current']:.2f}"
                elif lr.get("current"):
                    cur = f"Rs {lr['current']:.2f}"
                vals = [rec.get("time", "—"), idx, kind, strike, rec.get("expiry", "—"),
                        entry, "VWAP-break · -20%", stop, cur, rec.get("lot", "—"),
                        status]
                fg = QColor(GREEN) if kind == "CALL" else QColor(RED)
            else:                                     # no signal yet — live placeholder
                lr = live.get(idx, {})
                vals = [datetime.now(IST).strftime("%H:%M"), idx, "—", "—", "—", "—", "—",
                        "—", "—", "—", lr.get("status", "WATCHING")]
                fg = QColor(TEXT_DIM)
            self._set_row(self.pm_orbvwap, r, vals, fg=fg)
            if status:
                self._color_cell(self.pm_orbvwap, r, 10, self._status_color(status))
        self._fit_table(self.pm_orbvwap)

    def _refresh_swing(self):
        """SWING CREDIT SPREADS on PM DECISIONS — two rows per trade (SELL leg + BUY leg)."""
        if hasattr(self, "pm_swing"):
            self._fill_pm_credit(self.pm_swing, list(self._swing_rows or []), "index")

    def _refresh_stock_credit(self):
        """STOCK CREDIT SPREADS on PM DECISIONS — two rows per trade (SELL leg + BUY leg)."""
        if hasattr(self, "pm_stockcr"):
            self._fill_pm_credit(self.pm_stockcr, list(self._stockcr_rows or []), "stock")
        if hasattr(self, "pm_stockcr2"):
            self._fill_pm_credit(self.pm_stockcr2, list(self._stockcr2_rows or []), "stock")

    def _refresh_monthly(self):
        """MONTHLY FUTURES PULLBACK on PM DECISIONS — one row per position (single-leg futures).
        Unlike the credit sections, OPEN positions stay visible all month (the trade IS the
        month), plus recent closes and the standing-aside marker."""
        if not hasattr(self, "pm_monthly"):
            return
        table = self.pm_monthly
        rows = list(self._monthly_rows or [])
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", "no cycle yet — enters the first trading day after "
                          "monthly expiry (NIFTY>200DMA), scan ~15:10", "—", "—", "—", "—", "WATCHING"],
                          fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            if status in ("REGIME_OFF", "NO_CANDIDATES"):
                self._set_row(table, i, ["—", p.get("order_label", ""), "—", "—",
                                          p.get("expiry", "—"), "—", status], fg=QColor(TEXT_DIM))
                continue
            pnl = p.get("pnl_pct")
            pnl_s = f"{pnl:+.2f}%" if pnl is not None else "—"
            stat_s = status if status == "OPEN" else f"{status} {pnl_s} ({p.get('reason','')})"
            entry = p.get("entry_px")
            cur = p.get("cur_px")
            prem = f"in {entry} now {cur}" if entry and cur else (f"{entry}" if entry else "—")
            vals = ["BUY FUT", p.get("order_label", p.get("symbol", "—")), "1 lot",
                    prem, p.get("expiry", "—"),
                    f"TP {p.get('tp_px','—')} / SL {p.get('sl_px','—')}",
                    stat_s if status != "OPEN" else f"OPEN {pnl_s} · d{p.get('sessions',0)}"]
            fg = QColor(GREEN) if status == "WIN" else QColor(RED) if status == "LOSS" else None
            self._set_row(table, i, vals, fg=fg)
        self._fit_table(table)

    def _refresh_monthly_call(self):
        """MONTHLY LONG-CALL PULLBACK on PM DECISIONS — one row per bought call. Same layout as
        the futures book; shows the CALL to BUY, entry/now premium, and P&L on the premium."""
        if not hasattr(self, "pm_monthly_call"):
            return
        table = self.pm_monthly_call
        rows = list(self._monthly_call_rows or [])
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", "no cycle yet — enters the first trading day after "
                          "monthly expiry (NIFTY>200DMA), scan ~15:10", "—", "—", "—", "—", "WATCHING"],
                          fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            if status in ("REGIME_OFF", "NO_CANDIDATES"):
                self._set_row(table, i, ["—", p.get("order_label", ""), "—", "—",
                                          p.get("expiry", "—"), "—", status], fg=QColor(TEXT_DIM))
                continue
            pnl = p.get("pnl_pct")
            pnl_s = f"{pnl:+.1f}%" if pnl is not None else "—"
            ep, cp = p.get("entry_prem"), p.get("cur_prem")
            prem = f"in ₹{ep} now ₹{cp}" if ep and cp else (f"₹{ep}" if ep else "—")
            vals = ["BUY CALL", p.get("order_label", p.get("symbol", "—")),
                    f"{p.get('strike','')} CE", prem, p.get("opt_expiry", p.get("expiry", "—")),
                    f"spot TP {p.get('tp_px','—')} / SL {p.get('sl_px','—')}",
                    f"{status} {pnl_s} ({p.get('reason','')})" if status != "OPEN"
                    else f"OPEN {pnl_s} · d{p.get('sessions',0)}"]
            fg = QColor(GREEN) if status == "WIN" else QColor(RED) if status == "LOSS" else None
            self._set_row(table, i, vals, fg=fg)
        self._fit_table(table)

    def _fill_pm_credit(self, table, rows, kind):
        """Render a PM credit-spread section as TWO ROWS per trade so it's unmistakable what to do:
        a SELL row (the leg you SELL — premium received, net credit) and a BUY row (the hedge you
        BUY — premium paid, max loss + live/booked P&L). Cols: ACTION·INSTRUMENT·PREMIUM·EXPIRY·AMOUNT·P&L/STATUS."""
        # PM DECISIONS shows only TODAY's signals (what to place now). Older/ongoing positions
        # live in the SWING TRADES trade log.
        today = datetime.now(IST).date().isoformat()
        rows = [p for p in rows if p.get("entry_date") == today]
        hint = ("no swing signal today — fires on a daily index breakout (fade), scan ~15:10"
                if kind == "index"
                else "no signal today — fires on a stock breakout w/ rich credit (≥0.40), scan ~15:10")
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", hint, "—", "—", "—", "—", "WATCHING"], fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows) * 2)
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            name = p.get("index") or p.get("symbol") or "—"
            verb = "CE" if p.get("side") == "BEAR_CALL" else "PE"
            sp, lp = p.get("short_prem"), p.get("long_prem")
            sp_s = f"Rs {sp:.1f}" if sp is not None else "—"
            lp_s = f"Rs {lp:.1f}" if lp is not None else "—"
            exp = p.get("expiry", "—")
            qty = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
            credit = p.get("credit") or 0
            cap = p.get("capital") or 0
            pnl_pts = p.get("pnl_pts", 0.0) or 0.0
            now = p.get("current_cost")   # LIVE cost-to-close — keeps running even after WIN/LOSS
            if now is None:
                pnl = "—"
            else:
                rs = pnl_pts * qty; pct = (rs / cap * 100) if cap else None
                pnl = f"Rs {rs:+,.0f}" + (f" ({pct:+.0f}%)" if pct is not None else "")
            lot = p.get("lot", 0) or 0
            num_lots = int(p.get("num_lots", 1) or 1)
            lot_str = f"{lot}" + (f"×{num_lots}" if num_lots > 1 else "")
            rS, rB = 2 * i, 2 * i + 1
            # ACTION carries the option TYPE (CE/PE) so it's never truncated by a long stock name.
            # Row 1 — SELL the near leg (collect premium)
            self._set_row(table, rS,
                          [f"SELL {verb}", f"{name} {p.get('short_strike','—')}", lot_str, sp_s, exp,
                           f"credit Rs {credit*qty:,.0f}", status], fg=QColor(RED))
            # Row 2 — BUY the far leg (the hedge) — AMOUNT here = total MARGIN required (= max loss)
            self._set_row(table, rB,
                          [f"BUY {verb}", f"{name} {p.get('long_strike','—')}  (hedge)", lot_str, lp_s, exp,
                           f"margin Rs {cap:,.0f}", pnl], fg=QColor(GREEN))
            self._color_cell(table, rS, 6, self._status_color(status))     # STATUS on the SELL row
            if pnl != "—":
                self._color_cell(table, rB, 6, QColor(GREEN) if pnl_pts > 0 else
                                 QColor(RED) if pnl_pts < 0 else QColor(TEXT_DIM))   # P&L on the BUY row
        self._fit_table(table)

    def _refresh_watchlist(self):
        wl = [s for s in self.last_scan_results if s.get("passes_gate_1")]

        def gates(s):
            # ACTIVE gates only (matches deployed config): G1 alpha, G2 ORB, G3 align,
            # then PREM+LIQ (option >= min premium AND liquid; checked only after G1-G3).
            return [True, bool(s.get("gate_2")), bool(s.get("aligned")),
                    bool(s.get("liquid") and s.get("liquidity_checked"))]

        # closest-to-firing on top: most gates passed first, then alpha-z
        wl.sort(key=lambda s: (sum(gates(s)), abs(s.get("alpha_z", 0))), reverse=True)
        self.wl_table.setRowCount(len(wl))
        for r, sig in enumerate(wl):
            g = gates(sig)
            npass = sum(g)
            mark = lambda ok: "PASS" if ok else "wait"
            if npass == 4:
                prog = "4/4  READY -> PM"
            else:
                nxt = ["alpha", "ORB", "align", "prem+liq"][g.index(False)]
                prog = f"{npass}/4  next: {nxt}"
            tk = ("★ " if sig.get("priority") else "") + str(sig.get("ticker"))
            vals = [tk, f"{sig.get('alpha_z',0):.2f}", sig.get("direction"),
                    mark(g[0]), mark(g[1]), mark(g[2]), mark(g[3]), prog]
            self._set_row(self.wl_table, r, vals, fg=self._dir_color(sig.get("direction")))
            # color each gate cell: green when passed, dim when waiting; READY row glows green
            for col, ok in zip((3, 4, 5, 6), g):
                it = self.wl_table.item(r, col)
                if it: it.setForeground(QColor(GREEN) if ok else QColor(TEXT_DIM))
            pit = self.wl_table.item(r, 7)
            if pit: pit.setForeground(QColor(GREEN) if npass == 4 else QColor(AMBER))

    def _refresh_swing_tab(self):
        """Fill the two split credit-spread trade-log tables (index swing + stock)."""
        if not hasattr(self, "sw_idx"):
            return
        try:
            self._fill_swing_table(self.sw_stk2, STOCKCR2_BOOK, self.sw_stk2_stats)
            self._fill_swing_table(self.sw_idx, SWING_BOOK, self.sw_idx_stats)
            self._fill_swing_table(self.sw_stk, STOCKCR_BOOK, self.sw_stk_stats)
        except Exception as e:
            logger.warning(f"swing tab fill: {e}")

    def _fill_swing_table(self, table, book_path, stats_label=None, open_only=False):
        """One credit-spread trade log: each row spells out the SELL leg and BUY leg (strike +
        premium), expiry, net credit (total Rs), live/booked cost, P&L and status. Newest first.
        open_only=True → show ONLY still-open or entered-today rows (the INTRADAY 'live' view);
        settled history then lives in the TRADE LOG tab."""
        import json
        from datetime import date as _date
        book = []
        try:
            if _os.path.exists(book_path):
                book = json.load(open(book_path)) or []
        except Exception as e:
            logger.warning(f"swing table load {book_path}: {e}")
        if open_only:
            today = _date.today().isoformat()
            book = [p for p in book if p.get("status") == "OPEN" or p.get("entry_date") == today]
        # ── summary stats (capital deployed, win rate, P&L) ──
        if stats_label is not None:
            def _qty(p): return p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
            def _pnl(p): return (p.get("pnl_pts", 0.0) or 0.0) * _qty(p)
            n = len(book); opens = [p for p in book if p.get("status") == "OPEN"]
            wins = sum(1 for p in book if p.get("status") == "WIN")
            losses = sum(1 for p in book if p.get("status") == "LOSS")
            closed = wins + losses
            wr = (wins / closed * 100) if closed else 0
            margin_now = sum((p.get("capital") or 0) for p in opens)        # capital deployed in open trades
            booked = sum(_pnl(p) for p in book if p.get("status") in ("WIN", "LOSS"))
            live = sum(_pnl(p) for p in opens)
            pc = GREEN if booked >= 0 else RED
            stats_label.setText(
                f"  TRADES {n} · OPEN {len(opens)} · W {wins} L {losses} · WIN {wr:.0f}% "
                f"· margin Rs {margin_now:,.0f} · booked Rs {booked:+,.0f} · MTM Rs {live:+,.0f}")
            stats_label.setStyleSheet(
                f"color:{pc}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        # open positions first, then newest closed
        book = sorted(book, key=lambda p: (p.get("status") != "OPEN", p.get("entry_date") or ""), reverse=False)
        book = sorted(book, key=lambda p: (p.get("status") == "OPEN", p.get("entry_date") or ""), reverse=True)
        rows = book[:40]
        if not rows:
            if stats_label is not None:
                stats_label.setText("  no trades yet — stats will populate after the first signal")
            table.setRowCount(1)
            self._set_row(table, 0, ["—", "—", "no trades yet — fires on a breakout with rich credit",
                                     "—", "—", "—", "—", "WATCHING"], fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows) * 2)          # two leg rows per trade
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            name = p.get("symbol") or p.get("index") or "—"
            verb = "CE" if p.get("side") == "BEAR_CALL" else "PE"
            lot = p.get("lot", 0) or 0; num_lots = int(p.get("num_lots", 1) or 1)
            lot_str = f"{lot}" + (f"×{num_lots}" if num_lots > 1 else "")
            qty = p.get("qty") or (lot * num_lots)
            sp, lp = p.get("short_prem"), p.get("long_prem")            # entry premiums
            sc, lc = p.get("short_cur"), p.get("long_cur")              # current/exit leg values
            # per-leg P&L (rupees): SELL leg profits when it FALLS; BUY leg tracks its own move
            sell_pnl = (sp - sc) * qty if (sp is not None and sc is not None) else None
            buy_pnl = (lc - lp) * qty if (lp is not None and lc is not None) else None
            net_pts = p.get("pnl_pts", 0.0) or 0.0; cap = p.get("capital") or 0
            net_rs = net_pts * qty
            net_pct = (net_rs / cap * 100) if cap else None
            def money(x): return f"Rs {x:+,.0f}" if x is not None else "—"
            def price(x): return f"Rs {x:.1f}" if x is not None else "—"
            rS, rB = 2 * i, 2 * i + 1
            # LEG carries the option TYPE (CE/PE) so it's never truncated by a long stock name.
            # Row 1 — SELL leg (the short you sold)
            self._set_row(table, rS,
                          [p.get("entry_date", "—"), f"① SELL {verb}", f"{name} {p.get('short_strike','—')}",
                           lot_str, price(sp), price(sc), money(sell_pnl), status], fg=QColor(RED))
            # Row 2 — BUY leg (the hedge) + the consolidated NET for the whole spread
            net_txt = f"NET {money(net_rs)}" + (f" ({net_pct:+.0f}%)" if net_pct is not None else "")
            self._set_row(table, rB,
                          [f"exp {p.get('expiry','—')}", f"② BUY {verb}", f"{name} {p.get('long_strike','—')}",
                           lot_str, price(lp), price(lc), money(buy_pnl), net_txt], fg=QColor(GREEN))
            # colors: status on SELL row, per-leg P&L + NET tinted by sign
            self._color_cell(table, rS, 7, self._status_color(status))
            if sell_pnl is not None:
                self._color_cell(table, rS, 6, QColor(GREEN) if sell_pnl > 0 else QColor(RED) if sell_pnl < 0 else QColor(TEXT_DIM))
            if buy_pnl is not None:
                self._color_cell(table, rB, 6, QColor(GREEN) if buy_pnl > 0 else QColor(RED) if buy_pnl < 0 else QColor(TEXT_DIM))
            self._color_cell(table, rB, 7, QColor(GREEN) if net_rs > 0 else QColor(RED) if net_rs < 0 else QColor(TEXT_DIM))
        self._fit_table(table)

    def _norm_trade(self, t: dict) -> dict:
        """Normalise a live paper-trade OR a simulation trade to a display row."""
        if "under" in t:  # simulation trade (from option backtest)
            ep = t.get("entry_prem") or 0
            return {"time": f"{t.get('day','')} {t.get('entry_time','')}",
                    "under": t["under"], "opt": t.get("opt_type", ""),
                    "dir": t.get("direction", ""), "entry": ep,
                    "target": round(ep*1.10, 2), "stop": round(ep*0.80, 2),
                    "outcome": t.get("outcome", ""), "pnl": t.get("pnl_pct") or 0, "unit": "%"}
        # Show the OPTION premium (what you actually pay), not the underlying price.
        # `or 0` guards against None (e.g. ORB+VWAP trend-ride logs target=None).
        entry = t.get("entry_premium") or t.get("entry") or 0
        tgt = t.get("target_premium") or t.get("target") or 0
        stp = t.get("stop_premium") or t.get("stop") or 0
        return {"time": (t.get("signal_time") or "")[:19], "under": t.get("ticker", ""),
                "opt": t.get("instrument", ""), "dir": t.get("direction", ""),
                "entry": entry, "target": tgt, "stop": stp,
                "outcome": t.get("outcome") or "OPEN", "pnl": t.get("realized_pnl_inr") or 0, "unit": ""}

    def _refresh_swing_log(self):
        """SWING CREDIT SPREAD log — read-only from the engine's book (data/swing_positions.json).
        Independent of the LIVE/SIM toggle: it's always a live forward-test. Newest first."""
        if not hasattr(self, "log_swing"):
            return
        import json
        book = []
        try:
            if _os.path.exists(SWING_BOOK):
                book = json.load(open(SWING_BOOK)) or []
        except Exception as e:
            logger.warning(f"load swing book failed: {e}")
        # newest first: open positions, then by entry date desc
        book = sorted(book, key=lambda p: (p.get("status") != "OPEN", p.get("entry_date") or ""),
                      reverse=False)
        book = sorted(book, key=lambda p: p.get("entry_date") or "", reverse=True)
        rows = book[:40]
        self.log_swing.setRowCount(len(rows))
        for r, p in enumerate(rows):
            status = p.get("status", "OPEN")
            verb = "CE" if p.get("side") == "BEAR_CALL" else "PE"
            spread = f"{p.get('short_strike','—')}/{p.get('long_strike','—')} {verb}"
            credit = p.get("credit")
            nowx = p.get("exit_cost") if status != "OPEN" else p.get("current_cost")
            qty = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
            pnl_pts = p.get("pnl_pts", 0.0) or 0.0
            cap = p.get("capital") or 0
            if status == "OPEN" and nowx is None:
                pnl = "—"
            else:
                rs = pnl_pts * qty
                pct = (rs / cap * 100) if cap else None
                pnl = f"Rs {rs:+,.0f}" + (f"  ({pct:+.0f}%)" if pct is not None else "")
            fg = (QColor(GREEN) if status == "WIN" else QColor(RED) if status == "LOSS"
                  else QColor(AMBER))
            vals = [p.get("entry_date", "—"), p.get("index", "—"), spread,
                    f"Rs {credit:.1f}" if credit is not None else "—",
                    f"Rs {nowx:.1f}" if nowx is not None else "—", status, pnl]
            self._set_row(self.log_swing, r, vals, fg=fg)
            self._color_cell(self.log_swing, r, 5, self._status_color(status))
        self._fit_table(self.log_swing)

    def _refresh_stock_credit_log(self):
        """STOCK CREDIT SPREAD log — read-only from data/stock_credit_positions.json. Newest first."""
        if not hasattr(self, "log_stockcr"):
            return
        import json
        book = []
        try:
            if _os.path.exists(STOCKCR_BOOK):
                book = json.load(open(STOCKCR_BOOK)) or []
        except Exception as e:
            logger.warning(f"load stock_credit book failed: {e}")
        book = sorted(book, key=lambda p: p.get("entry_date") or "", reverse=True)[:60]
        self.log_stockcr.setRowCount(len(book))
        for r, p in enumerate(book):
            status = p.get("status", "OPEN")
            verb = "CE" if p.get("side") == "BEAR_CALL" else "PE"
            spread = f"{p.get('short_strike','—')}/{p.get('long_strike','—')} {verb}"
            credit = p.get("credit")
            nowx = p.get("exit_cost") if status != "OPEN" else p.get("current_cost")
            qty = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
            pnl_pts = p.get("pnl_pts", 0.0) or 0.0; cap = p.get("capital") or 0
            if status == "OPEN" and nowx is None:
                pnl = "—"
            else:
                rs = pnl_pts * qty; pct = (rs / cap * 100) if cap else None
                pnl = f"Rs {rs:+,.0f}" + (f"  ({pct:+.0f}%)" if pct is not None else "")
            fg = (QColor(GREEN) if status == "WIN" else QColor(RED) if status == "LOSS" else QColor(AMBER))
            vals = [p.get("entry_date", "—"), p.get("symbol", "—"), spread,
                    f"{p.get('credit_width','—')}",
                    f"Rs {credit:.1f}" if credit is not None else "—",
                    f"Rs {nowx:.1f}" if nowx is not None else "—", status, pnl]
            self._set_row(self.log_stockcr, r, vals, fg=fg)
            self._color_cell(self.log_stockcr, r, 6, self._status_color(status))
        self._fit_table(self.log_stockcr)

    @staticmethod
    def _intraday_capital_metrics(trades):
        """Intraday strategies redeploy the SAME capital every trading day, so return is measured on
        the AVERAGE CAPITAL DEPLOYED PER (trading) DAY — not the sum of every trade's capital. But the
        IRR (annualized return) counts ALL CALENDAR DAYS, including non-trading days on which the
        capital sits idle earning nothing — that's the honest yardstick. Returns:
          avg_daily_cap — mean of each trading day's deployed capital (premium × lot)
          period_ret    — cumulative % return on that capital over the logged span
          daily_ret     — average % return PER CALENDAR DAY (P&L spread over calendar days, incl idle)
          irr_str       — IRR annualized over CALENDAR time = (1+period_ret)^(365/cal_days) − 1."""
        from collections import defaultdict
        from datetime import date
        closed = [t for t in trades if t.get("outcome") in ("WIN", "LOSS")]
        if not closed:
            return None

        def cap(t):
            ep = t.get("entry_premium") if t.get("entry_premium") is not None else (t.get("entry") or 0)
            lot = t.get("lot") if t.get("lot") is not None else t.get("qty")
            return float(ep or 0) * float(lot or 0)

        def day(t):
            return (t.get("signal_time") or t.get("outcome_time") or "")[:10]

        dc, dp = defaultdict(float), defaultdict(float)
        for t in closed:
            dc[day(t)] += cap(t)
            dp[day(t)] += float(t.get("realized_pnl_inr") or 0)
        ndays = len(dc)                                   # distinct TRADING days
        total_cap, total_pnl = sum(dc.values()), sum(dp.values())
        if ndays == 0 or total_cap <= 0:
            return None
        avg_daily_cap = total_cap / ndays
        # calendar span first→last trade, INCLUDING weekends/holidays (capital idle on those days)
        ds = sorted(dc.keys())
        try:
            cal_days = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days + 1
        except Exception:
            cal_days = ndays
        cal_days = max(cal_days, ndays)
        pr = total_pnl / avg_daily_cap                    # cumulative return on the committed capital
        period_ret = pr * 100
        daily_ret = period_ret / cal_days                 # avg % per CALENDAR day (idle days count)
        # IRR annualized over CALENDAR time — only meaningful with a real track record.
        if cal_days < 30:
            irr_str = f"n/a (need ~30+ cal-days, have {cal_days})"
        elif pr <= -1:
            irr_str = "−100%/yr"
        else:
            irr = (1 + pr) ** (365.0 / cal_days) - 1
            irr_str = (f"{irr*100:+,.0f}%/yr" if abs(irr) < 100 else f"{irr:+,.1f}×/yr")
        return {"ndays": ndays, "cal_days": cal_days, "avg_daily_cap": avg_daily_cap,
                "daily_ret": daily_ret, "period_ret": period_ret, "irr_str": irr_str}

    def _refresh_log(self):
        # 2026-07-09: 3-Family/ORB retired from this tab — their tables are hidden and the stats
        # line is now owned by _refresh_zero_dte_tab (fresh 0DTE W/L across all 3 books, in blue).
        return
        self.trade_log._load()   # (unreachable legacy below, kept for reference)
        live = [t for t in self.trade_log.trades if t.get("signal_time")]  # OPEN + closed
        sim = getattr(self, "sim_trades", [])
        # LIVE and SIMULATION are kept STRICTLY separate — never mixed.
        view = getattr(self, "log_view", "live")
        chosen = live if view == "live" else sim
        # keep the toggle labels showing each set's count
        if hasattr(self, "log_live_btn"):
            try:
                self.log_live_btn.setText(f"LIVE PAPER TRADES ({len(live)})")
                self.log_sim_btn.setText(f"SIMULATION 30-day ({len(sim)})")
            except RuntimeError:
                pass

        if not chosen:
            empty_msg = ("No live paper trades yet — they appear here once the system fires real "
                         "signals during market hours." if view == "live"
                         else "No simulation data cached yet.")
            self.log_stats.setText(f"  [{'LIVE PAPER' if view=='live' else 'SIMULATION (30-day historical)'}]   {empty_msg}")
            for table in (self.log_nifty, self.log_bnf, self.log_stock):
                table.setRowCount(0); self._fit_table(table)
            return

        allt = [self._norm_trade(t) for t in chosen]
        n = len(allt); w = sum(1 for t in allt if t["outcome"] == "WIN")
        l = sum(1 for t in allt if t["outcome"] == "LOSS")
        opn = sum(1 for t in allt if t["outcome"] == "OPEN")
        closed = w + l
        wr = (w / closed * 100) if closed else 0
        tag = "LIVE PAPER" if view == "live" else "SIMULATION (30-day historical · reference only)"
        openstr = f" · OPEN {opn}" if (view == "live" and opn) else ""
        if view == "live":
            s = self.trade_log.pnl_summary(chosen)
            im = self._intraday_capital_metrics(chosen)
            if im and im["avg_daily_cap"] > 0:
                # intraday: the SAME capital cycles daily, so return % and IRR are on the
                # AVERAGE CAPITAL DEPLOYED PER DAY (not the summed-across-all-trades capital).
                extra = (f" · P&L Rs {s['pnl']:+,.0f} · avg cap/day Rs {im['avg_daily_cap']:,.0f} "
                         f"({im['ndays']}d traded / {im['cal_days']} cal) · ret {im['period_ret']:+.0f}% "
                         f"· {im['daily_ret']:+.2f}%/cal-day · IRR {im['irr_str']}")
            else:
                extra = f" · P&L Rs {s['pnl']:+,.0f} · {s['pct']:+.1f}%"
        else:
            extra = " · reference only"
        self.log_stats.setText(
            f"  [{tag}] TRADES {n} · W {w} L {l}{openstr} · WIN {wr:.0f}%{extra}")

        buckets = {"NIFTY": [], "BANKNIFTY": [], "STOCK": []}
        for t in allt:
            buckets[self._underlying_kind(t["under"])].append(t)
        for kind, table in (("NIFTY", self.log_nifty), ("BANKNIFTY", self.log_bnf), ("STOCK", self.log_stock)):
            rows = buckets[kind][-40:]
            table.setRowCount(len(rows))
            for r, t in enumerate(rows):
                oc = t["outcome"]
                fg = (QColor(GREEN) if oc == "WIN" else QColor(RED) if oc == "LOSS"
                      else QColor(AMBER) if oc == "OPEN" else QColor(CYAN))
                if oc == "OPEN":
                    pnl = "—"
                else:
                    pv = t.get("pnl") or 0
                    pnl = f"{pv:+.1f}%" if t["unit"] == "%" else f"Rs {pv:+.0f}"
                num = lambda v: f"{v:.2f}" if v else "—"   # "—" for missing (e.g. trend-ride target)
                vals = [t["time"], t["under"].replace(".NS",""), t["opt"], t["dir"],
                        num(t['entry']), num(t['target']), num(t['stop']), oc, pnl]
                self._set_row(table, r, vals, fg=fg)
            self._fit_table(table)

    # ── market data + clock ───────────────────────────────────────────────────
    def _refresh_market_data(self):
        """READ-ONLY: render the market bar from the snapshot the engine wrote to disk
        (no live fetch here — the headless engine owns all data fetching)."""
        import json
        try:
            if _os.path.exists(MARKET_SNAP):
                d = json.load(open(MARKET_SNAP))
                self._market_ts = d.get("ts")   # engine heartbeat — written every cycle
                if d.get("nifty") and d.get("banknifty") and d.get("vix"):
                    self._on_market_data(d)
        except Exception as e:
            logger.warning(f"load market_snapshot failed: {e}")

    def _mkt_done(self):
        self._mkt_running = False

    def _on_market_data(self, d: dict):
        self._holiday = bool(d.get("holiday"))   # weekday+hours but no live data = NSE holiday
        self._set_ticker(self.nifty_lbl, "NIFTY 50", d["nifty"])
        self._set_ticker(self.bnf_lbl, "BANKNIFTY", d["banknifty"])
        # VIX: arrow + colored by direction (down-vol = green calm, up-vol = red fear)
        x = d["vix"]
        xdir = x.get("direction", "FLAT")
        arrow = "▲" if xdir == "UP" else ("▼" if xdir == "DOWN" else "•")
        self.vix_lbl.setText(f"INDIA VIX  {x['price']:.2f}  {arrow} {x.get('pct',0):+.2f}%")
        # For VIX, falling is risk-on(green); keep amber as neutral base for readability
        self.vix_lbl.setStyleSheet(f"color:{AMBER};")

    @staticmethod
    def _src_tag(source: str) -> str:
        sl = (source or "").lower()
        if "5m" in sl:     return " ·5m"
        if "yahoo" in sl:  return " ·15m"
        if "live" in sl:   return ""
        if "traded" in sl: return " ·close"   # after hours: today's last traded price
        return " ·prev"   # live unavailable → showing previous session

    def _set_ticker(self, lbl, name, d: dict):
        """Render an index ticker with colored up/down vs the previous session close."""
        direction = d.get("direction", "FLAT")
        color = GREEN if direction == "UP" else (RED if direction == "DOWN" else TEXT_DIM)
        arrow = "▲" if direction == "UP" else ("▼" if direction == "DOWN" else "•")
        chg = d.get("change", 0.0)
        pct = d.get("pct", 0.0)
        # % FIRST (right after price) so it's never the part that clips on a narrow window.
        # Source (live / close / delayed) is in the hover tooltip, not inline — keeps the bar clean.
        lbl.setText(f"{name}  {d['price']:,.2f}  {arrow} {pct:+.2f}%  ({chg:+,.2f})")
        lbl.setStyleSheet(f"color:{color};")
        lbl.setToolTip(f"{name}: {d['price']:,.2f}  {chg:+,.2f} ({pct:+.2f}%)  source: {d.get('source','')}")

    def _tick(self):
        now = datetime.now(IST)
        # EOD booking is done by the headless engine, not the GUI (read-only viewer).
        # HOLIDAY: weekday + market hours by the clock, but no live data flowing (engine-detected).
        holiday = getattr(self, "_holiday", False) and self.agent.is_market_open()
        is_open = self.agent.is_market_open() and not holiday
        mkt = "HOLIDAY" if holiday else ("OPEN" if is_open else "CLOSED")
        # live clock in the index bar (top-right), green when market is open
        if hasattr(self, "clock_lbl"):
            self.clock_lbl.setText(f"{now:%a %d %b  %H:%M:%S} IST   {mkt}")
            self.clock_lbl.setStyleSheet(f"color:{GREEN if is_open else AMBER};")
        mode = "LIVE" if is_open else "SIMULATION"
        # Keep the AUTO badge in sync when idle (scanning sets it to LIVE·scanning)
        # freshness of the engine's last scan (read-only viewer)
        fresh = "no engine data yet"
        # Liveness = the market-snapshot ts (written EVERY engine cycle). latest_scan.json is
        # written only by the DISABLED 3-Family scan, so it goes stale even while the engine is
        # healthy — never use it as the alive indicator.
        ts = getattr(self, "_market_ts", None) or getattr(self, "_latest_scan_ts", None)
        if ts:
            try:
                age = (now - datetime.fromisoformat(ts)).total_seconds()
                fresh = f"engine active {int(age//60)}m ago" if age >= 60 else "engine active just now"
            except Exception:
                pass
        if hasattr(self, "auto_lbl"):
            self.auto_lbl.setText(f"READ-ONLY VIEWER  -  {fresh}")
            self.auto_lbl.setStyleSheet(f"color:{CYAN if is_open else AMBER}; padding:0 14px;")
        if hasattr(self, "mode_label"):
            mlbl = "MARKET HOLIDAY (no trading today)" if holiday else ("MARKET OPEN" if is_open else "MARKET CLOSED")
            self.mode_label.setText(f"{mlbl}  -  engine runs 9:00-15:30 Mon-Fri")
            self.mode_label.setStyleSheet(f"color:{GREEN if is_open else AMBER};")
        self.status.showMessage(
            f"  {now:%a %d %b %Y · %H:%M:%S} IST   ·   MARKET {mkt}   ·   MODE {mode}   ·   "
            f"scanned {len(self.last_scan_results)}   ·   "
            f"ready {sum(1 for s in self.last_scan_results if s.get('trade_ready'))}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = TerminalApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
