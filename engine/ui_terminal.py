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
STOCKCR_SNAP = _os.path.join(DATA_DIR, "stock_credit.json")
STOCKCR_BOOK = _os.path.join(DATA_DIR, "stock_credit_positions.json")

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
        self._stockcr_rows = []
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
        tabs = [("PM DECISIONS", 0), ("WATCHLIST", 1), ("SWING TRADES", 2), ("TRADE LOG", 3),
                ("STUDIES", 4), ("README", 5)]
        for label, idx in tabs:
            b = QPushButton(label)
            b.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
            b.setMinimumHeight(44); b.setMinimumWidth(160)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.switch(i))
            self.tab_btns.append(b); h.addWidget(b)
        h.addStretch()

        # Autonomous — no scan button. A live indicator shows the auto-scan state.
        self.auto_lbl = QLabel("AUTO")
        self.auto_lbl.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.auto_lbl.setStyleSheet(f"color:{TEXT_DIM}; padding:0 14px;")
        h.addWidget(self.auto_lbl)
        return w

    def _highlight_tab(self, idx: int):
        for i, b in enumerate(self.tab_btns):
            if i == idx:
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
    PM_CREDIT_COLS = ["ACTION", "INSTRUMENT", "PREMIUM", "EXPIRY", "AMOUNT", "P&L / STATUS"]

    def _make_pm_table(self) -> QTableWidget:
        t = QTableWidget(); t.setColumnCount(len(self.PM_COLS))
        t.setHorizontalHeaderLabels(self.PM_COLS)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setAlternatingRowColors(True); t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)
        return t

    def _section_label(self, text, color) -> QLabel:
        l = QLabel(text); l.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{color}; padding:8px 4px 2px 4px;")
        return l

    def _screen_pm(self) -> QWidget:
        """PM DECISIONS — STOCK options on top (most signals), then NIFTY / BANKNIFTY."""
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("LATEST PM DECISIONS  -  BUY options, place manually in Upstox", AMBER))

        # STOCK options (single stocks; indices handled in the section below)
        v.addWidget(self._section_label("STOCK OPTIONS", GREEN))
        self.pm_stock = self._make_pm_table()
        self.pm_stock.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_stock, 2)   # shares space, scrolls internally

        # STOCK CREDIT SPREADS — the 4th strategy (high-frequency fade on single stocks).
        v.addWidget(self._section_label(
            "STOCK CREDIT SPREADS  (fade · credit/width≥0.40 · ~16/mo · SELL · forward-test)", GREEN))
        self.pm_stockcr = QTableWidget(); self.pm_stockcr.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_stockcr.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self.pm_stockcr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pm_stockcr.setAlternatingRowColors(True); self.pm_stockcr.verticalHeader().setVisible(False)
        self.pm_stockcr.verticalHeader().setDefaultSectionSize(32)
        self.pm_stockcr.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_stockcr, 1)

        # SWING CREDIT SPREADS — the 3rd strategy (multi-day · theta · SELL against the breakout).
        v.addWidget(self._section_label(
            "SWING CREDIT SPREADS  (index · multi-day · SELL spread, place manually · forward-test)", CYAN))
        self.pm_swing = QTableWidget(); self.pm_swing.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_swing.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self.pm_swing.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pm_swing.setAlternatingRowColors(True); self.pm_swing.verticalHeader().setVisible(False)
        self.pm_swing.verticalHeader().setDefaultSectionSize(34)
        self.pm_swing.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_swing, 1)

        # NIFTY & BANKNIFTY index options — handled by the ORB+VWAP strategy below
        v.addWidget(self._section_label("INDEX OPTIONS  (NIFTY / BANKNIFTY, paper forward-test)", PURPLE))
        self.pm_orbvwap = QTableWidget(); self.pm_orbvwap.setColumnCount(len(self.ORBVWAP_COLS))
        self.pm_orbvwap.setHorizontalHeaderLabels(self.ORBVWAP_COLS)
        self.pm_orbvwap.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pm_orbvwap.setAlternatingRowColors(True); self.pm_orbvwap.verticalHeader().setVisible(False)
        self.pm_orbvwap.verticalHeader().setDefaultSectionSize(34)
        self.pm_orbvwap.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_orbvwap, 1)

        self.pm_empty = QLabel("No trade-ready signals yet. Auto-scan runs every 5 min, 09:15-15:30 IST.")
        self.pm_empty.setStyleSheet(f"color:{TEXT_DIM}; padding:6px 4px;")
        self.pm_empty.setFont(QFont("Menlo", 12))
        v.addWidget(self.pm_empty)
        return w

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

    SWING_TAB_COLS = ["ENTERED", "NAME", "SELL  (strike/prem)", "BUY  (strike/prem)", "EXPIRY",
                      "CREDIT (total)", "NOW/EXIT", "P&L", "STATUS"]

    def _screen_swing(self) -> QWidget:
        """SWING TRADES — the credit-spread TRADE LOG, split into the two strategies. Each row shows
        exactly what to SELL and what to BUY (strike + premium), expiry, net credit and P&L."""
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("SWING TRADES  -  credit-spread trade log (what to SELL & BUY)", CYAN))
        v.addWidget(self._section_label("INDEX SWING  —  NIFTY / FINNIFTY  (~3/mo)", CYAN))
        self.sw_idx = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sw_idx, 1)
        v.addWidget(self._section_label("STOCK CREDIT SPREADS  (~16/mo)", GREEN))
        self.sw_stk = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sw_stk, 1)
        for t in (self.sw_idx, self.sw_stk):
            t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return w

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
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("TRADE LOG  -  stocks (3-Family) + ORB index  ·  LIVE vs SIMULATION"))

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
        v.addWidget(toggle)

        self.log_stats = QLabel("—")
        self.log_stats.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        self.log_stats.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(self.log_stats)

        # Three separate logs, one per strategy.
        # 1) STOCK OPTIONS — the 3-Family intraday buying system (most trades).
        # BUY strategies only here. The credit-spread (SELL) logs live in the SWING TRADES tab.
        v.addWidget(self._section_label("STOCK OPTIONS  —  3-Family (intraday buy)", GREEN))
        self.log_stock = self._make_log_table(); v.addWidget(self.log_stock, 2)
        v.addWidget(self._section_label("ORB+VWAP INDEX  —  NIFTY", PURPLE))
        self.log_nifty = self._make_log_table(); v.addWidget(self.log_nifty, 1)
        v.addWidget(self._section_label("ORB+VWAP INDEX  —  BANKNIFTY", AMBER))
        self.log_bnf = self._make_log_table(); v.addWidget(self.log_bnf, 1)
        for t in (self.log_stock, self.log_nifty, self.log_bnf):
            t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._style_log_toggle()
        return w

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
<p style="color:{CYAN};font-size:17px;font-weight:bold;">RESEARCH LOG  -  how each piece of the strategy was tested</p>
{dim("Every change below was backtested before going live (or deliberately NOT deployed). "
     "All P&amp;L is GROSS of costs unless noted. Full write-ups are the .md files in /studies on GitHub.")}

{h("TESTS &amp; TRADES THAT FINALIZED THE LIVE STRATEGIES")}
{dim("~9,000 real-option spread-trades across 9 tests (+ thousands of config combinations). The two "
     "live credit strategies are what SURVIVED; the rejected rows define where the edge isn't.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>#</td><td>Test (real costs)</td><td>Trades</td><td>Result</td><td>Decision</td></tr>
<tr><td>1</td><td>Stock credit spread — generic</td><td>2,387</td><td>&minus;4.7%</td><td style="color:{RED};">rejected (slippage wall)</td></tr>
<tr><td>2</td><td>Index spread — FOLLOW breakout</td><td>73+111</td><td>&minus;26 to &minus;39%, 40% win</td><td style="color:{RED};">rejected &rarr; breakouts REVERT</td></tr>
<tr><td>3</td><td>Index FADE — grid (216 cfg)</td><td>114 days</td><td>fade family validates</td><td style="color:{AMBER};">switch to FADE</td></tr>
<tr><td>4</td><td>Index FADE — tenor refine (243 cfg)</td><td>115 days</td><td>mid-tenor&middot;1-OTM&middot;w3&middot;hold</td><td style="color:{AMBER};">final config</td></tr>
<tr><td>5</td><td>Index FADE — corrected</td><td>61</td><td>+12.3% net, both idx +</td><td style="color:{GREEN};">VALIDATED</td></tr>
<tr><td>6</td><td>Robustness — 5 defs &times; 5 indices</td><td>396</td><td>def-robust; BANKNIFTY &minus;6.7%</td><td style="color:{GREEN};">NIFTY+FINNIFTY (drop BNF)</td></tr>
<tr><td>7</td><td>ORB (intraday breakout)</td><td>413</td><td>NIFTY &minus;13.7%</td><td style="color:{RED};">boundary (needs real extension)</td></tr>
<tr><td>8</td><td>Stock FADE — 18 liquid</td><td>742</td><td>&minus;1.8% agg; c/w signal</td><td style="color:{AMBER};">add a gate</td></tr>
<tr><td>9</td><td>Stock FADE — full univ + gate</td><td>4,228&rarr;307</td><td>+16-25%, p5 +6.8%, 65% win</td><td style="color:{GREEN};">DEPLOYED (gated)</td></tr>
</table>
{dim("LIVE result: index swing (NIFTY+FINNIFTY, ~3/mo, rows 3-6) + stock high-frequency fade "
     "(credit/width&gt;=0.40 + prem&gt;=Rs50, ~16/mo, rows 8-9). Both paper FORWARD-TESTS.")}

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
   "live mid-cap fills) -&gt; runs as a FORWARD-TEST at 1 lot.")}
{dim("Files: studies/STOCK_OPTIONS_NO_EDGE.md (Parts 5-8) · engine/swing_credit.py · engine/stock_credit.py")}

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
   "The real, repeatable edge is the opposite — <b>SELLING a credit spread that FADES a breakout</b>: "
   "validated on the index (NIFTY+FINNIFTY swing, robust across 5 breakout definitions) and high-frequency "
   "on stocks (gated credit/width≥0.40). Both are deployed as paper FORWARD-TESTS — the backtests are "
   "real but optimistic, and live fills are the only honest judge.")}
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

<p style="color:{CYAN};font-size:17px;font-weight:bold;">INSTITUTIONAL TRADER — NSE Options (paper · 4 parallel strategies)</p>
{dim("Grounded in the STUDIES tab. Mode: PAPER, signals-only — the headless engine fires signals and "
     "records them to the local DB + trade log daily; YOU place every order manually in Upstox. It never "
     "auto-trades. Each strategy has its own PM DECISIONS section and its own TRADE LOG.")}

{h("THE FOUR STRATEGIES AT A GLANCE")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>#</td><td>Strategy</td><td>Type</td><td>Backtest (real costs)</td><td>Status</td></tr>
<tr><td>1</td><td style="color:{GREEN};">Stock options · 3-Family</td><td>intraday BUY</td><td>~breakeven net (1yr −1.0%)</td><td>forward-test</td></tr>
<tr><td>2</td><td style="color:{GREEN};">Stock credit spreads</td><td>multi-day SELL (fade)</td><td>+16-25%, ~16/mo (optimistic)</td><td>forward-test</td></tr>
<tr><td>3</td><td style="color:{CYAN};">Swing credit spreads · NIFTY+FINNIFTY</td><td>multi-day SELL (fade)</td><td>+12-20%, ~3/mo (the validated edge)</td><td>forward-test</td></tr>
<tr><td>4</td><td style="color:{PURPLE};">ORB+VWAP index · NIFTY/BNF</td><td>intraday BUY</td><td>~breakeven net</td><td>forward-test</td></tr>
</table>
{p(f"<b style='color:{AMBER}'>Honest status (from the studies):</b> exhaustive testing — <b>~9,000 "
   f"real-option spread-trades across 9 tests</b> — showed <b>NO option-BUYING strategy clears real costs "
   f"out-of-sample</b> (you cross the bid-ask every leg and theta fights you). The real edge is the "
   f"opposite: <b>SELLING a credit spread that FADES a breakout</b> — validated on the index (#3) and "
   f"high-frequency on stocks (#2). All four run as <b>paper FORWARD-TESTS</b>; none is proven on live "
   f"fills yet. See the <b>STUDIES</b> tab for the full tests-&amp;-trades trail.")}

{h("THE TWO BIG IDEAS")}
{p("<b>Buying (#1, #4) — selectivity + capped risk.</b> Intraday direction is ~a coin flip, so don't "
   "predict: <b>filter hard</b> (cleanest setups only) and <b>cap risk</b> (buy options → worst case is the "
   "premium). Net of costs this is ~breakeven — kept as forward-tests, not money-makers.")}
{p("<b>Selling (#2, #3) — fade the breakout, harvest theta + IV crush.</b> A breakout spikes implied "
   "volatility and then mean-REVERTS. So <b>SELL</b> a defined-risk credit spread <i>against</i> the "
   "breakout: you collect the inflated premium, theta works <i>for</i> you, and you win if it reverts or "
   "just stalls. This is the only structure that beat real measured costs. <b>The credit/width gate is the "
   "edge</b> — a generic credit spread loses (−4.7%); only selling when richly paid relative to risk works.")}

{h("STEP 1 — Turn each stock into ONE number: alpha-z")}
{p("<b>Why one number?</b> Many weak signals are easier to gate as a single <b>conviction</b> score — "
   "<b>sign = direction</b> (+ long / − short), <b>size = conviction</b>. It is a weighted blend of 3 "
   "<b>families</b> (grouped so correlated signals can't fake breadth):")}
{p(f"<b style='color:{GREEN}'>TREND ({C.FAMILY_WEIGHTS['TREND']['weight']})</b> — three sub-factors, each "
   "z-scored vs its own history: <b>momentum</b> (60-min intraday return), <b>trend quality</b> (daily "
   "EMA-9 vs EMA-21 spread), <b>microstructure</b> (15-min opening-range break). <b>Why biggest:</b> "
   "trend/momentum is the only family that held an edge in testing.")}
{dim(f"&nbsp;&nbsp;Sub-factor weights (normalised within TREND by their sum "
     f"{sum(C.FAMILY_WEIGHTS['TREND']['factor_weights'].values()):.2f}): momentum "
     f"{C.FAMILY_WEIGHTS['TREND']['factor_weights']['momentum']} "
     f"(~{C.FAMILY_WEIGHTS['TREND']['factor_weights']['momentum']/sum(C.FAMILY_WEIGHTS['TREND']['factor_weights'].values()):.0%}), "
     f"trend-quality {C.FAMILY_WEIGHTS['TREND']['factor_weights']['trend_quality']} "
     f"(~{C.FAMILY_WEIGHTS['TREND']['factor_weights']['trend_quality']/sum(C.FAMILY_WEIGHTS['TREND']['factor_weights'].values()):.0%}), "
     f"microstructure {C.FAMILY_WEIGHTS['TREND']['factor_weights']['microstructure']} "
     f"(~{C.FAMILY_WEIGHTS['TREND']['factor_weights']['microstructure']/sum(C.FAMILY_WEIGHTS['TREND']['factor_weights'].values()):.0%}).")}
{dim("&nbsp;&nbsp;<b>How the weights were set — honest:</b> hit-rate-informed, NOT rigorously optimised. "
     "TREND got the biggest family weight because it was the only family with a real edge; momentum is the "
     "strongest sub-factor; <b>microstructure is deliberately tiny</b> because that ORB break is ALSO Gate 2 "
     "— keeping it small avoids double-counting the same signal in both the score and the gate. Fitting all "
     "weights to data (vs hand-set) is a known open improvement.")}
{p(f"<b style='color:{CYAN}'>FLOW ({C.FAMILY_WEIGHTS['FLOW']['weight']})</b> — live per-stock option flow "
   "(OI buildup + PCR trend). <b>Why:</b> an independent read of what option writers are positioning for.")}
{p(f"<b style='color:{AMBER}'>EVENT ({C.FAMILY_WEIGHTS['EVENT']['weight']})</b> — NSE news, keyword-scored. "
   "<b>Why tiny:</b> news is sparse and the scoring is crude — it nudges, it never decides.")}
{p(f"<b style='color:{CYAN}'>alpha-z = Σ(family z × weight) ÷ Σ(weights)</b> &nbsp;(weights read live from "
   f"config, sum = {sum(f['weight'] for f in C.FAMILY_WEIGHTS.values()):.2f}).")}
{dim(f"Example (bearish) — each family's <b>z-score × its weight</b>:")}
{dim(f"&nbsp;&nbsp;TREND&nbsp; z=−0.9 × weight {C.FAMILY_WEIGHTS['TREND']['weight']} = {-0.9*C.FAMILY_WEIGHTS['TREND']['weight']:+.2f}")}
{dim(f"&nbsp;&nbsp;FLOW&nbsp;&nbsp; z=−0.6 × weight {C.FAMILY_WEIGHTS['FLOW']['weight']} = {-0.6*C.FAMILY_WEIGHTS['FLOW']['weight']:+.2f}")}
{dim(f"&nbsp;&nbsp;EVENT z=&nbsp;0.0 × weight {C.FAMILY_WEIGHTS['EVENT']['weight']} = {0.0*C.FAMILY_WEIGHTS['EVENT']['weight']:+.2f}&nbsp;&nbsp;(EVENT is usually neutral, so it adds nothing)")}
{dim(f"&nbsp;&nbsp;alpha-z = sum ÷ (weights {sum(f['weight'] for f in C.FAMILY_WEIGHTS.values()):.2f}) = "
     f"<b>{(-0.9*C.FAMILY_WEIGHTS['TREND']['weight'] - 0.6*C.FAMILY_WEIGHTS['FLOW']['weight'] + 0.0*C.FAMILY_WEIGHTS['EVENT']['weight'])/sum(f['weight'] for f in C.FAMILY_WEIGHTS.values()):.2f}</b> → SHORT")}
{dim("Honest limitation: because EVENT rarely fires, in practice alpha-z is mostly TREND + FLOW — a "
     "momentum signal with a flow tilt, not three equal voices. (A 4th mean-reversion family was removed: "
     "it won only 47.6%.)")}

{h("STEP 2 — Six gates (each removes a known way to lose)")}
{sub("Gate 1 · Alpha — strong AND broad?")}
{p(f"Require |alpha-z| &gt; <b>{C.ALPHA_Z_THRESHOLD}</b> AND <b>≥{C.MIN_FAMILIES_AGREE} of 3</b> families "
   f"agree. <b>Why:</b> one noisy family shouldn't trigger a trade — demand both conviction and agreement. "
   f"Passing lands the stock on the <b>WATCHLIST</b>.")}
{sub("Gate 2 · ORB breakout + volume — is it happening NOW?")}
{p("The latest 5-min candle must break the opening range (with a volume surge), same direction as the "
   "score. <b>Why:</b> a score can be right but early — require the move to actually start before paying.")}
{sub("Gate 3 · Market alignment — don't fight the tape")}
{p("Only <b>LONG when Nifty is up</b>, <b>SHORT when Nifty is down</b>. <b>Why:</b> the biggest losers came "
   "from trades fighting the index. <i>Evidence: 60-day P&amp;L +Rs17k → +Rs31k (~2×) by cutting the trend-fighters.</i>")}
{sub("Gate 4 · Don't chase — already over-extended?")}
{p(f"Skip if the stock already moved &gt; <b>{C.MAX_ENTRY_EXTENSION_PCT}%</b> in the trade's direction from "
   f"the open. <b>Why:</b> buying an already-run stock is buying the top. <i>Evidence (365 days): "
   f"over-extended entries won ~45% vs ~55%; same profit on fewer trades.</i>")}
{sub("Gate 5 · Wide open — is there real morning momentum?")}
{p(f"Require the first-30-min opening range to be at least <b>{C.ORB_RANGE_WIDTH_MIN}%</b> of price wide. "
   f"<b>Why:</b> a wide opening range means the day has real energy → cleaner breakouts; a narrow, quiet "
   f"open is chop. <i>Evidence: validated on 365 days (506 trades) — directional win 51% → 54%; option win "
   f"30-day 61% → 66%, 60-day 66% → 70% at +10/−20.</i>")}
{sub("Gate 6 · Liquidity — can you actually fill and exit?")}
{p(f"Before firing, fetch the exact OTM+1 option's <b>live bid/ask + OI</b> and require a two-sided "
   f"market, spread <b>≤ {C.MAX_OPTION_SPREAD_PCT}%</b> of mid, and OI ≥ <b>{C.MIN_OPTION_OI}</b>. "
   f"<b>Why:</b> you buy at the ask and sell at the bid — with a +10% target a wide spread eats the edge, "
   f"and a stale LTP isn't a real price. Checked <b>only</b> for signals that already cleared Gates 1-5 "
   f"(~1-2/day), so the cost is ~1-2 quote calls a day — negligible. (`LIQUIDITY_FILTER`)")}
{p("All six pass → <b>PM DECISIONS</b>. The <b>WATCHLIST</b> tab shows each candidate's live gate "
   "progress (PASS / wait, e.g. <b>5/6 next: liquidity</b>), sorted closest-to-firing on top.")}

{h("STEP 3 — What you trade, and why")}
{p("Every signal is a <b>bought option</b> (never sold): <b style='color:{0}'>LONG → buy CALL</b>, "
   "<b style='color:{1}'>SHORT → buy PUT</b>. <b>Why buy-only:</b> loss is capped at the premium, and a "
   "small underlying move becomes a large % move on the option (leverage).".format(GREEN, RED))}
{p(f"<b style='color:{GREEN}'>STOCKS (the 3-Family system, {len(C.UNIVERSE)} names)</b> — buy <b>OTM+1</b>, "
   f"exit <b>+{int(C.PREMIUM_TARGET_PCT)}% / −{int(C.PREMIUM_STOP_PCT)}%</b> on the premium. <b>Why small "
   f"target / wide stop:</b> premiums are volatile, so a quick +{int(C.PREMIUM_TARGET_PCT)}% is hit often "
   f"(that is what makes win rate ~58–61%), while the wider −{int(C.PREMIUM_STOP_PCT)}% avoids being stopped "
   f"by noise. (Removing the cap was tested — worse, higher-variance — so it stays.)")}

{h("STEP 3b — THE INDEX STRATEGY (NIFTY &amp; BANKNIFTY) — full logic")}
{p("A <b>completely separate, parallel</b> strategy from the stock system. It does NOT use alpha-z, the 3 "
   "families, or the 5 gates. It is an intraday <b>Opening-Range Breakout + VWAP</b> momentum play on the "
   "two indices, in its own INDEX OPTIONS section on PM DECISIONS. (`engine/orb_vwap_live.py`)")}
{sub("Entry — a signal fires only when ALL of these line up")}
{p("<b>1. Opening range</b> = high/low of the first 15 min (first 3 × 5-min candles, 9:15–9:30).")}
{p("<b>2. Breakout</b> = the latest 5-min close is <b>&gt;0.07% beyond</b> the range — above the high → "
   "LONG, below the low → SHORT.")}
{p("<b>3. VWAP</b> = the close must also be on the breakout side of VWAP. VWAP needs volume and the spot "
   "index reports none on Upstox, so it is computed from the index <b>FUTURES</b> feed — but only OPTIONS "
   "are ever traded.")}
{p(f"<b>4. 30-min trend</b> = the close must be beyond where it was {C.ORB_VWAP_TREND_BARS} × 5-min = "
   f"<b>30 min ago</b>. <i>This is the index's OWN trend agreeing — NOT the stocks' cross-market "
   f"alignment gate (that does not apply here, since BankNifty almost always already moves with Nifty).</i>")}
{p("<b>5. Clean-trend filter</b> = VWAP must be sloping the trade's way (rising over the last 3 bars for a "
   "LONG) <b>and</b> price already <b>&gt;0.25% extended</b> from the open — cuts chop and false breaks.")}
{p(f"<b>Plus:</b> entries only <b>before {C.ORB_VWAP_ENTRY_CUTOFF}</b> (the move needs the morning), "
   f"<b>skip 0-DTE</b> expiry days (premium spikes), <b>one signal per index per day</b>.")}
{sub("What you buy &amp; the exit")}
{p(f"Buy the <b>ATM</b> CALL (LONG) / PUT (SHORT). <b>Exit = TREND-RIDE:</b> ride the winner; exit only "
   f"when the futures <b>reclaim VWAP</b> after the trade is already +{int(C.ORB_VWAP_ARM_PCT)}% in profit; "
   f"a <b>hard −{int(C.ORB_VWAP_STOP_PCT)}% premium stop</b> throughout; otherwise square off at the close. "
   f"Live status: WATCHING → ● RIDING → EXITED VWAP / STOPPED −{int(C.ORB_VWAP_STOP_PCT)}%.")}
{sub("Why these choices + what the backtest said")}
{p("<b>Why trend-ride (not a fixed target)?</b> An ORB break is a <i>trend</i> setup — the old fixed +20% "
   "target capped winners while still taking full −20% stops (backwards), and it <b>bled −2.6%/trade</b>. "
   "Riding the winner fixed it. We backtested it 30 &amp; 60 days (`studies/INDEX_TREND_RIDE_EXIT.md`):")}
{p("&nbsp;&nbsp;<b>30-day:</b> 65% win, +1.2%/trade &nbsp;·&nbsp; <b>60-day:</b> 63% win, +0.8%/trade "
   "&nbsp;(both GROSS) &nbsp;·&nbsp; the fix took win rate <b>27% → 63%</b>.")}
{dim("Capital per lot: Nifty ATM ~Rs8k, BankNifty ~Rs17k. <b>Honest:</b> those are GROSS — net of costs it "
     "is roughly <b>breakeven</b>, fragile out-of-sample, and runs as a <b>FORWARD-TEST</b>, not because it "
     "is proven. The big win was fixing the EXIT, not the trend filter (which was always there).")}

{h("THIRD STRATEGY — Swing Credit Spread (the one that beat real costs)")}
{p("A <b>third, separate</b> strategy — and the only structure that clears <b>real measured costs</b> out-of-"
   "sample. The other two BUY options (you pay the bid-ask and fight theta). This one <b>SELLS</b> a "
   "defined-risk credit spread, so theta works <i>for</i> you. It is multi-day (overnight carry), shown in "
   "its own <b>SWING CREDIT SPREADS</b> section on PM DECISIONS between the stock and index sections.")}
{p("<b>The signal:</b> a daily <b>Donchian-10 breakout</b> (a fresh 10-day high or low) on <b>NIFTY / "
   "FINNIFTY</b>. <b>The twist — FADE it:</b> index breakouts mean-REVERT, so we sell AGAINST the breakout "
   "(up-break → bear-call spread, down-break → bull-put spread). Selling <i>with</i> the breakout won only "
   "40%; fading wins ~65%.")}
{p("<b>Construct:</b> ~2-week expiry, short <b>1 strike OTM</b>, long <b>3 strikes</b> further (caps the "
   "loss), <b>held to expiry</b>; hard stop if the spread's cost-to-close hits <b>2× the credit</b>. You "
   "<b>receive</b> a credit up-front; best case both options expire worthless and you keep it.")}
{p(f"<b style='color:{CYAN}'>Why it's deployed:</b> +12–20% net/trade on margin (real costs), PF 1.4–1.95, "
   f"and <b>robust across 5 breakout definitions</b> (Donchian-10/15/20/30 + prior-week) — genuine "
   f"reversion, not a curve-fit. A 5-index test DROPPED BankNifty (tested −6.7%) and kept "
   f"<b>NIFTY + FINNIFTY</b>.")}
{dim("HONEST: HIGH variance (a loss ≈ the full margin), thin sample, ~2–3 signals/month. Runs as a "
     "FORWARD-TEST at 1 lot (`SWING_LOTS`) — NOT proven on live fills. Full record: STUDIES tab / "
     "studies/STOCK_OPTIONS_NO_EDGE.md Parts 5–8.")}

{h("FOURTH STRATEGY — Stock Credit Spread (the high-frequency sibling)")}
{p("The <b>frequency</b> version of #3 — the same FADE, on the full ~100-stock universe, so it fires "
   "<b>~16×/month</b> (vs the index's ~3). Its own <b>STOCK CREDIT SPREADS</b> section + trade log.")}
{p("<b>Signal:</b> a daily <b>Donchian-10 breakout</b> on any F&amp;O stock → FADE it (sell a credit "
   "spread). <b>The gate that makes it work:</b> only trade when <b>credit ≥ 40% of the strike width</b> "
   "AND short premium ≥ Rs50, AND it passes a <b>live liquidity check</b> (OI, bid-ask). A breakout spikes "
   "IV → rich premium; the gate sells that inflated premium and rides the reversion + IV crush.")}
{p("<b>Construct:</b> short 1-OTM, long 3 strikes wide, nearest monthly ≥10 DTE, hold to expiry, 2× stop. "
   "<b>Caps:</b> ≤5 new/day, ≤20 open at once (breakouts cluster — avoid a one-day pile-on).")}
{p(f"<b style='color:{GREEN}'>Backtest:</b> full universe, ~19mo, real premiums, credit/width≥0.40 + "
   f"prem≥Rs50 → <b>307 trades (~16/mo), 65% win, +16% (5% slip) / +25% (3%)</b>, holdout p5 +6.8%, "
   f"76/100 stocks net-positive, survives a 7%/leg slippage floor. A <i>generic</i> stock spread LOSES "
   f"−4.7% — the credit/width gate IS the edge.")}
{dim("HONEST: the ~+20%/month-on-margin backtest is OPTIMISTIC and WILL shrink live — the unmodelled risk "
     "is real mid-cap 4-leg fills + gap risk on ~16 concurrent shorts. Runs as a FORWARD-TEST at 1 lot "
     "(`STOCK_CREDIT_*`). DO NOT fill your margin. Full record: studies/STOCK_OPTIONS_NO_EDGE.md Part 8.")}

{h("STEP 4 — How it runs (engine vs viewer), and why split")}
{p("The <b>engine</b> (headless, launchd <b>…institutionaltrader.engine</b>, always on) does ALL the work — "
   "scan every 5 min, fire signals, resolve trades, 15:30 force-book — and saves everything to the local DB "
   "<b>daily</b> (engine.db = every scan + market snapshot; signals.db; trade_log.json). It wakes every 5 s "
   "in market hours; idles when closed.")}
{p("This <b>app is a read-only VIEWER</b> — it never scans / fires / resolves / writes; it only reads the "
   "engine's files and displays them (header: <b>READ-ONLY VIEWER — engine scan Nm ago</b>). <b>Why split:</b> "
   "a viewer crash can't stop trading, and execution timing is independent of the display.")}

{h("HONEST RESULTS & GO-LIVE BAR")}
{p(f"<b>Why the bar is high:</b> risking {int(C.PREMIUM_STOP_PCT)}% to make {int(C.PREMIUM_TARGET_PCT)}% means "
   f"breakeven needs ~<b>{C.PAPER_TRADING_BREAKEVEN_WIN_RATE:.0%}</b> wins. Capital-weighted winners keep it "
   f"net-positive gross, but costs + spread pull it back to ~breakeven. <b>Go-live bar:</b> win ≥ "
   f"<b>{C.PAPER_TRADING_MIN_WIN_RATE:.0%}</b> AND profit factor &gt; {C.PAPER_TRADING_MIN_PF} across "
   f"{C.PAPER_TRADING_MIN_SIGNALS}+ forward signals. Below that — don't automate.")}

{h("RISK CONTROLS")}
{p(f"No per-day trade cap (take every qualifying signal) · halt after <b>{C.CONSECUTIVE_LOSS_HALT}</b> "
   f"stop-outs in a row · force-close by {C.KILL_SWITCH_TIME} · never hold overnight · size from the stop distance.")}

{h("REFERENCE — timings & data")}
{p(f"<b>Daily clock (IST):</b> 08:55 Mac wakes · {C.MARKET_OPEN} open (scan begins) · {C.TRADING_START} "
   f"trading window · scan every 5 min · {C.NO_NEW_TRADES_AFTER} no new trades · {C.MARKET_CLOSE} force-book "
   f"open trades. Signals are selective — ~1–2/day (365-day study: ~1.7/day), many days none; the edge is "
   f"strongest 10:30–11:00.")}
{p("<b>Freshness:</b> market bar ~3–5 s · TREND/FLOW/EVENT recompute every 5 min (options flow ≤10 min, "
   "events ≤1 hour old) · a full ~102-instrument scan takes ~3–4 s (16 threads, batched LTP, cached daily history).")}
{p("<b>Data:</b> Upstox V3 (live LTP, 5-min candles, ~400-day daily history) on a read-only Analytics token; "
   "Yahoo is an emergency fallback only.")}

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
            if _os.path.exists(STOCKCR_SNAP):
                s = json.load(open(STOCKCR_SNAP))
                self._stockcr_rows = s.get("rows", []) or []
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
        """No-op. Tables scroll internally (ScrollBarAsNeeded) and share space via stretch
        factors, which is resize-safe. (Previously set minimum heights that overflowed the
        window on resize and pushed the nav off-screen.)"""
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

    def _refresh_pm(self):
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

    def _fill_pm_credit(self, table, rows, kind):
        """Render a PM credit-spread section as TWO ROWS per trade so it's unmistakable what to do:
        a SELL row (the leg you SELL — premium received, net credit) and a BUY row (the hedge you
        BUY — premium paid, max loss + live/booked P&L). Cols: ACTION·INSTRUMENT·PREMIUM·EXPIRY·AMOUNT·P&L/STATUS."""
        hint = ("no swing signal yet — fires on a daily index breakout (fade)" if kind == "index"
                else "no signal yet — fires on a stock breakout w/ rich credit (≥0.40)")
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", hint, "—", "—", "—", "WATCHING"], fg=QColor(TEXT_DIM))
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
            now = p.get("exit_cost") if status != "OPEN" else p.get("current_cost")
            if status == "OPEN" and now is None:
                pnl = "—"
            else:
                rs = pnl_pts * qty; pct = (rs / cap * 100) if cap else None
                pnl = f"Rs {rs:+,.0f}" + (f" ({pct:+.0f}%)" if pct is not None else "")
            rS, rB = 2 * i, 2 * i + 1
            # Row 1 — SELL the near leg (collect premium)
            self._set_row(table, rS,
                          ["SELL", f"{name} {p.get('short_strike','—')} {verb}", sp_s, exp,
                           f"credit Rs {credit*qty:,.0f}", status], fg=QColor(RED))
            # Row 2 — BUY the far leg (the hedge that caps the loss)
            self._set_row(table, rB,
                          ["BUY", f"{name} {p.get('long_strike','—')} {verb}  (hedge)", lp_s, exp,
                           f"max loss Rs {cap:,.0f}", pnl], fg=QColor(GREEN))
            self._color_cell(table, rS, 5, self._status_color(status))     # STATUS on the SELL row
            if pnl != "—":
                self._color_cell(table, rB, 5, QColor(GREEN) if pnl_pts > 0 else
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
            self._fill_swing_table(self.sw_idx, SWING_BOOK)
            self._fill_swing_table(self.sw_stk, STOCKCR_BOOK)
        except Exception as e:
            logger.warning(f"swing tab fill: {e}")

    def _fill_swing_table(self, table, book_path):
        """One credit-spread trade log: each row spells out the SELL leg and BUY leg (strike +
        premium), expiry, net credit (total Rs), live/booked cost, P&L and status. Newest first."""
        import json
        book = []
        try:
            if _os.path.exists(book_path):
                book = json.load(open(book_path)) or []
        except Exception as e:
            logger.warning(f"swing table load {book_path}: {e}")
        # open positions first, then newest closed
        book = sorted(book, key=lambda p: (p.get("status") != "OPEN", p.get("entry_date") or ""), reverse=False)
        book = sorted(book, key=lambda p: (p.get("status") == "OPEN", p.get("entry_date") or ""), reverse=True)
        rows = book[:60]
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", "no trades yet — fires on a breakout with rich credit",
                                     "—", "—", "—", "—", "—", "—", "WATCHING"], fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            status = p.get("status", "OPEN")
            name = p.get("symbol") or p.get("index") or "—"
            verb = "CE" if p.get("side") == "BEAR_CALL" else "PE"
            sp, lp = p.get("short_prem"), p.get("long_prem")
            sell = f"{p.get('short_strike','—')}{verb} @{sp:.1f}" if sp is not None else f"{p.get('short_strike','—')}{verb}"
            buy = f"{p.get('long_strike','—')}{verb} @{lp:.1f}" if lp is not None else f"{p.get('long_strike','—')}{verb}"
            qty = p.get("qty") or ((p.get("lot", 0) or 0) * int(p.get("num_lots", 1) or 1))
            credit = p.get("credit") or 0
            credit_cell = f"Rs {credit:.1f} (Rs {credit*qty:,.0f})"
            nowx = p.get("exit_cost") if status != "OPEN" else p.get("current_cost")
            pnl_pts = p.get("pnl_pts", 0.0) or 0.0; cap = p.get("capital") or 0
            if status == "OPEN" and nowx is None:
                pnl = "—"
            else:
                rs = pnl_pts * qty; pct = (rs / cap * 100) if cap else None
                pnl = f"Rs {rs:+,.0f}" + (f" ({pct:+.0f}%)" if pct is not None else "")
            fg = QColor(GREEN) if p.get("side") == "BULL_PUT" else QColor(RED)
            vals = [p.get("entry_date", "—"), name, sell, buy, p.get("expiry", "—"), credit_cell,
                    f"Rs {nowx:.1f}" if nowx is not None else "—", pnl, status]
            self._set_row(table, r, vals, fg=fg)
            self._color_cell(table, r, 8, self._status_color(status))
            if pnl != "—":
                self._color_cell(table, r, 7, QColor(GREEN) if pnl_pts > 0 else QColor(RED) if pnl_pts < 0 else QColor(TEXT_DIM))
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

    def _refresh_log(self):
        # credit-spread (SELL) logs now live in the SWING TRADES tab; this tab = BUY strategies only.
        self.trade_log._load()   # reload from disk — agent + resolver write to it
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
        openstr = f"  ·   OPEN {opn}" if (view == "live" and opn) else ""
        if view == "live":
            s = self.trade_log.pnl_summary(chosen)
            extra = (f"·   CAPITAL Rs {s['capital']:,.0f}   ·   P&L Rs {s['pnl']:+,.0f}   "
                     f"·   {'GAIN' if s['pnl'] >= 0 else 'LOSS'} {s['pct']:+.1f}%")
        else:
            extra = "·   reference only"
        self.log_stats.setText(
            f"  [{tag}]   TRADES {n}   ·   WINS {w}  LOSSES {l}{openstr}   ·   WIN {wr:.0f}%   {extra}")

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
        ts = getattr(self, "_latest_scan_ts", None)
        if ts:
            try:
                age = (now - datetime.fromisoformat(ts)).total_seconds()
                fresh = f"engine scan {int(age//60)}m ago" if age >= 60 else "engine scan just now"
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
