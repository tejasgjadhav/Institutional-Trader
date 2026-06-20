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

from engine.config import IST
from engine.agent import Agent
from engine.trade_log import TradeLog
from engine.data_utils import (
    get_market_snapshot, get_last_5_trading_days
)

logger = logging.getLogger(__name__)

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


class ScanWorker(QThread):
    scan_complete = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def run(self):
        try:
            if not self.agent.is_market_open():
                self.scan_complete.emit([])
                return
            self.scan_complete.emit(self.agent.run_scan())
        except Exception as e:
            self.error_occurred.emit(str(e))


class IndexScanWorker(QThread):
    """Runs the ORB+VWAP index scan off the UI thread — REGARDLESS of market hours, so
    the PM index section still shows the day's signals after the 15:30 close / a restart."""
    done = Signal(list)

    def run(self):
        try:
            from engine.orb_vwap_live import scan_index_orbvwap
            self.done.emit(scan_index_orbvwap())
        except Exception:
            self.done.emit([])


class MarketDataWorker(QThread):
    """Fetch index data off the UI thread."""
    data_ready = Signal(dict)

    def run(self):
        try:
            # ONE batched LTP call for all three indices (was 3 separate calls → 429s)
            self.data_ready.emit(get_market_snapshot())
        except Exception as e:
            logger.warning(f"Market data worker failed: {e}")


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
        self.active_screen = 0
        self._mkt_running = False
        self._scanning = False
        self.sim_trades = self._load_sim_trades()

        self._check_recording_window()
        self._build_ui()
        self._refresh_market_data()
        self._resolve_outcomes()  # close any resolvable PENDING trades on startup
        self._refresh_log()      # show simulation immediately (or live paper trades)
        self._refresh_pm()        # show today's already-fired signals (seeded from log)
        self.trigger_scan()       # only scans if market is open
        self._refresh_index_signals()   # populate the ORB+VWAP index section now

        # timers
        self.scan_timer = QTimer(); self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(300_000)  # 5 min
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
        for tname in ("scan_timer", "clock_timer", "mkt_timer", "idx_timer"):
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
        if getattr(self, "_idx_running", False):
            return
        self._idx_running = True
        self.idx_worker = IndexScanWorker()
        self.idx_worker.done.connect(self._on_index_signals)
        self.idx_worker.finished.connect(lambda: setattr(self, "_idx_running", False))
        self.idx_worker.start()

    def _on_index_signals(self, rows):
        if rows:
            self.agent.orbvwap_signals = rows
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
        self.stack.addWidget(self._screen_alpha())      # 2
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
        tabs = [("PM DECISIONS", 0), ("WATCHLIST", 1), ("ALPHA", 2), ("TRADE LOG", 3),
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

    WL_COLS = ["TICKER", "ALPHA-Z", "DIR", "G1 ALPHA", "G2 ORB", "G3 ALIGN",
               "G4 CHASE", "PROGRESS"]

    def _screen_watchlist(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title(
            "WATCHLIST  -  passed Gate 1 (alpha), progressing through Gates 2-4 to PM DECISIONS"))
        self.wl_table = QTableWidget()
        self.wl_table.setColumnCount(len(self.WL_COLS))
        self.wl_table.setHorizontalHeaderLabels(self.WL_COLS)
        self.wl_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.wl_table.setAlternatingRowColors(True)
        self.wl_table.verticalHeader().setVisible(False)
        v.addWidget(self.wl_table)
        # legend
        from engine import config as C
        leg = QLabel("PASS = gate cleared, wait = pending    |    G1 alpha, G2 ORB breakout+volume, "
                     "G3 aligned with Nifty, G4 not over-extended (<="
                     f"{C.MAX_ENTRY_EXTENSION_PCT}%)    |    all 4 PASS = fires on PM DECISIONS")
        leg.setStyleSheet(f"color:{TEXT_DIM}; padding:6px 2px;"); leg.setWordWrap(True)
        v.addWidget(leg)
        return w

    def _screen_alpha(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("ALPHA  -  all 95 stocks scored, ranked by alpha-z"))
        self.alpha_table = QTableWidget()
        self.alpha_table.setColumnCount(7)
        self.alpha_table.setHorizontalHeaderLabels(["TICKER", "ALPHA-Z", "DIR", "BREADTH", "TREND", "FLOW", "EVENT"])
        self.alpha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alpha_table.setAlternatingRowColors(True)
        self.alpha_table.verticalHeader().setVisible(False)
        v.addWidget(self.alpha_table)
        return w

    LOG_COLS = ["TIME", "UNDERLYING", "OPT", "DIR", "ENTRY", "TARGET", "STOP", "OUTCOME", "P&L"]

    def _make_log_table(self) -> QTableWidget:
        t = QTableWidget(); t.setColumnCount(len(self.LOG_COLS))
        t.setHorizontalHeaderLabels(self.LOG_COLS)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setAlternatingRowColors(True); t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(36)
        return t

    def _screen_log(self) -> QWidget:
        """TRADE LOG — LIVE paper trades and SIMULATION kept separate, split by underlying."""
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("TRADE LOG  -  LIVE paper vs SIMULATION (kept separate)"))

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

        # STOCK first — most trades come from stocks
        v.addWidget(self._section_label("STOCK OPTIONS  (most trades)", GREEN))
        self.log_stock = self._make_log_table(); v.addWidget(self.log_stock, 2)
        v.addWidget(self._section_label("NIFTY OPTIONS  (index)", CYAN))
        self.log_nifty = self._make_log_table(); v.addWidget(self.log_nifty, 1)
        v.addWidget(self._section_label("BANKNIFTY OPTIONS  (index)", AMBER))
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
     "All P&amp;L is GROSS of costs. Option backtests use ~1 month of real premium history "
     "(the rest is direction); treat short-window rupee figures as directional. Full write-ups "
     "are the .md files in /studies on GitHub.")}

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

{h("4 - Index ORB+VWAP: Trend-Ride Exit (the index fix)")}
{sub("Question: why was the index strategy losing every day?")}
{p("The old fixed +20% target capped winners while still taking full -20% stops - backwards "
   "for a trend setup. Replaced with: ride the winner, exit on VWAP reclaim after +12%, hard "
   "-20% stop; plus a clean-trend entry filter.")}
{res("Result (60-day): win 27% -&gt; 63%, -2.6%/trade -&gt; +0.8%/trade. Stops the bleed (still "
     "~breakeven net, a forward-test). NOW LIVE.")}
{dim("File: studies/INDEX_TREND_RIDE_EXIT.md")}

{h("5 - 365-Day Directional Validation (does the edge last a year?)")}
{sub("Question: does the signal predict direction over a full year, not just a lucky month?")}
{p("Option premiums only reach ~1 month back, but 5-min PRICE reaches ~365 days. Tested the "
   "directional edge on 1,117 signals over the year.")}
{res("Result: raw signal = coin flip (49%). ALIGNED (Gate 3) = 52% hit, +0.13%/trade, and it "
     "HOLDS across all 12 months (772 trades). The edge is real but THIN - options leverage it.")}
{dim("File: studies/UNDERLYING_VALIDATION_365D.md")}

{h("6 - Stock Option Exit Cap (+10% vs no cap)")}
{sub("Question: should we remove the +10% target and let stock winners ride?")}
{p("Tested +10% / +20% / +30% / no-cap on the same trades, -20% stop. NOT deployed.")}
{res("Result: removing the cap is INCONSISTENT - worst on 30-day (+0.5%), best on 60-day "
     "(+3.6%) = high variance, not a reliable edge. The +10% cap gives the best win rate "
     "(~60%) and lowest variance. KEPT at +10%.")}
{dim("File: studies/STOCK_OPTION_EXIT_CAP.md")}

{h("7 - Prophet Forward-Test (forecasting models)")}
{sub("Question: can a time-series forecaster (Prophet) predict the index or the P&amp;L?")}
{p("Forecast NIFTY/BANKNIFTY + the equity curve, then cross-validated the error.")}
{res("Result: 20-day directional hit-rate 43% (NIFTY) / 21% (BANKNIFTY) - WORSE than a coin "
     "flip; the forecast error is bigger than the move it predicts. Daily markets are near-"
     "random. NOT wired into the app - it would add noise, not signal.")}
{dim("File: studies/PROPHET_FORWARD_TEST.md")}

{h("8 - Data Availability Limits (what can be backtested)")}
{sub("Question: can we backtest 180 / 365 days on real option data?")}
{p("Probed Upstox depth. Daily price = 2+ yrs, 5-min price = ~1 yr, but option-premium "
   "candles = only ~3-4 weeks (expired contracts drop out of the instrument master).")}
{res("Result: a clean OPTION-P&amp;L backtest is capped at ~1 month. Longer validation needs the "
     "underlying-proxy (done), synthetic Black-Scholes premiums, or a paid options vendor.")}
{dim("File: studies/DATA_AVAILABILITY_LIMITS.md")}

{h("The honest bottom line")}
{p("After all of it: a <b>~52-61% directional, alignment-dependent, thin-but-real</b> edge. "
   "Gates 3 and 4 are the proven improvements; the index trend-ride stops a bleed; the cap "
   "and forecasting ideas were tested and correctly NOT deployed. Real profitability is "
   "unproven until the forward paper month logs real fills - which is what the live app does.")}
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
        rec = ("ON — today is one of the last 5 trading days, so signals are being recorded"
               if self.recording_mode else
               "OFF — today is outside the last-5-day window, so the system observes only")

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

<p style="color:{CYAN};font-size:17px;font-weight:bold;">INSTITUTIONAL TRADER — 3-Family Alpha · NSE Intraday Options</p>
{dim("A disciplined paper-trading framework. The 3-Family system scans 95 NSE stocks all day and "
     "only flags a trade when it clears four strict gates; NIFTY &amp; BANKNIFTY are handled by a "
     "separate parallel ORB+VWAP strategy. You place every order yourself in Upstox — the system "
     "never sends orders. It is a process for collecting honest evidence, not a proven money-maker.")}

{p(f"<b>Current mode:</b> SIMULATION (paper) · <b>OPTIONS-ONLY, BUY-ONLY</b>. <b>Recording:</b> {rec}.")}
{p(f"<b>Tuned config:</b> STOCKS — BUY OTM+1 · +{int(C.PREMIUM_TARGET_PCT)}% / −{int(C.PREMIUM_STOP_PCT)}% on premium · "
   f"cutoff 1 PM · {len(C.UNIVERSE)} stocks. &nbsp; INDEX — ORB+VWAP · BUY ATM · "
   f"+{int(C.ORB_VWAP_TARGET_PCT)}% / −{int(C.ORB_VWAP_STOP_PCT)}% · NIFTY &amp; BANKNIFTY.")}
{p(f"<b style='color:{AMBER}'>Status:</b> best backtest ~72% win (OTM+1, 1 PM) — but on only 18 trades, "
   f"so UNPROVEN. Larger 30-day samples read 50–65%; the 120-day underlying test showed no edge at 2:1. "
   f"Win rate is real-looking on small samples but not yet bankable — a 30+ session forward paper-test "
   f"with real costs is the only honest judge. (Full study: BACKTEST_RESULTS.md + the teaching PDF.)")}

{h("1 · WHAT IT DOES (in one breath)")}
{p("Every 5 minutes during market hours it: (1) pulls fresh prices from Upstox, "
   "(2) gives each stock a single score called <b>alpha-z</b>, then runs four gates — strong &amp; "
   "broad enough (Gate 1), breaking out now (Gate 2), aligned with the Nifty (Gate 3), not already "
   "over-extended (Gate 4). If all four pass, the stock appears on <b>PM DECISIONS</b> with exact "
   "entry, stop, target and quantity.")}

{h("1b · PARALLEL STRATEGY — ORB+VWAP INDEX (forward-test)")}
{p("Running ALONGSIDE the stock system is a second, independent strategy on NIFTY &amp; BANKNIFTY "
   "<b>index options only</b>. Each scan it checks a 15-min Opening-Range Breakout confirmed by VWAP and "
   "the 30-min trend plus a clean-trend filter (entries before 11 AM, skipping 0-DTE expiry-day spikes), "
   "buys the <b>ATM</b> CALL/PUT, and rides it with a <b>trend-ride exit</b> (exit on VWAP reclaim after "
   "+12%, hard -20% stop, else square off at close). It shows in its own INDEX OPTIONS section on "
   "<b>PM DECISIONS</b> with a live status: WATCHING -&gt; RIDING -&gt; EXITED VWAP / STOPPED -20%.")}
{dim("VWAP needs volume and the spot index reports none on Upstox, so the VWAP line is drawn from the index "
     "FUTURES feed — but nothing except OPTIONS is ever traded. Honest note: Apr–Jun 2026 backtests show this "
     "is roughly breakeven (NIFTY −0.5%, BANKNIFTY +0.3%); it runs live to FORWARD-TEST it, not because it is "
     "proven. Full study: studies/WIN_RATE_RESEARCH_LOG.md.")}

{h("2 · THE DAILY CLOCK (all times IST)")}
{p(f"<b>08:55</b> &nbsp; Mac wakes up automatically")}
{p(f"<b>09:00</b> &nbsp; App auto-launches")}
{p(f"<b>{C.MARKET_OPEN}</b> &nbsp; Market opens — scanning begins, ALPHA + WATCHLIST fill up")}
{p(f"<b>09:15–{C.TRADING_START}</b> &nbsp; First 30 min is the wildest part of the day — we only watch, no trades")}
{p(f"<b>{C.TRADING_START}</b> &nbsp; Trading window opens — confirmed signals become real PM DECISIONS")}
{p(f"<b>every 5 min</b> &nbsp; Re-scan NIFTY + BANKNIFTY + 95 stocks (parallel, batched, cached — a few sec)")}
{dim("Signals are SPARSE — ~18 over a month, ~12 of 22 days have a signal (1 PM cutoff trades "
     "frequency for quality). Nothing fires before ~11:30 AM (scores need an hour of data); most "
     "cluster 12:30-1 PM. Blank days are normal for a selective strategy.")}
{p(f"<b>{C.NO_NEW_TRADES_AFTER}</b> &nbsp; No new trades after this (afternoon is thin)")}
{p(f"<b>{C.KILL_SWITCH_TIME}</b> &nbsp; Kill-switch guideline — don't hold into the volatile last 20 min")}
{p(f"<b>{C.MARKET_CLOSE}</b> &nbsp; Market closes — <b>every OPEN paper trade is force-booked WIN/LOSS at the close</b> "
   "(Mon–Fri, daily), unless its +target/−stop already hit. Then the trade log shows the day's result.")}
{p(f"<b>{C.BACKTEST_REFRESH_TIME}</b> &nbsp; Re-rank the tradeable universe on the latest {C.BACKTEST_LOOKBACK_DAYS}-day history")}

{h("2b · REFRESH CADENCE & LATENCY (how fresh each number is)")}
{p("<b>Full scan — every 5 minutes.</b> All three families recompute for 94 stocks + NIFTY/BANKNIFTY "
   "each cycle. One scan finishes in <b>~0.6–2.7 seconds</b> (16 workers + pooled keep-alive connections · "
   "~2.7s cold, ~0.6s warm cache), so a new signal surfaces within <b>≤5 min</b> of forming. "
   "Signal granularity = the 5-min candle.")}
{p(f"<b style='color:{GREEN}'>TREND</b> &nbsp;recomputed every 5 min · live 5-min candles (daily EMA cached per day)")}
{p(f"<b style='color:{CYAN}'>FLOW</b> &nbsp;recomputed every 5 min · option chain cached ~10 min, so OI/PCR is ≤10 min old")}
{p(f"<b style='color:{AMBER}'>EVENT</b> &nbsp;score read every 5 min · NSE scrape at startup then ~every 20 min, 9 AM–1 PM, so sentiment is ≤1 hour old")}
{p("<b>Market header</b> (NIFTY / BANKNIFTY / VIX) refreshes every <b>3 seconds</b> (live LTP, 5-min-candle fallback); the clock ticks every 1 second.")}
{dim("Summary — header: ~3s · signals/families: 5-min · options flow: ≤10 min · events: ≤1 hour. Scan compute itself: 2–6s.")}

{h("3 · DATA SOURCES & API SCHEDULE")}
{sub("Upstox V3 — the primary feed (low latency)")}
{p("• <b>Live LTP</b> (last traded price): checked continuously to watch stops & targets")}
{p("• <b>5-min candles</b>: the heartbeat of the scan — used for breakout + volume checks every 5 min")}
{p("• <b>Daily history</b>: ~400 days, used for trend/momentum maths and the 60-day backtest")}
{p("• <b>Indices</b>: Nifty 50, Bank Nifty, India VIX — fetched every 5 sec for the top bar & market regime")}
{dim("Instrument keys are ISIN-based (e.g. NSE_EQ|INE467B01029). The system auto-downloads "
     "Upstox's instrument master and caches it for 7 days, so symbols map to keys automatically.")}
{sub("Speed / latency")}
{dim("LTP is fetched BATCHED (all instruments in one call, ~0.2s vs ~6s) · daily history is cached "
     "per day · the scan runs on a 12-worker thread pool. A full 97-instrument scan finishes in a "
     "few seconds, so prices don't drift before a signal is read. (True tick streaming needs a paid "
     "trading token — not available on the read-only Analytics token.)")}
{sub("Yahoo Finance — emergency fallback only")}
{dim("Only used if the Upstox token is missing/expired. It is slower, so it is never the primary path.")}

{h("4 · THE 3 FAMILIES (how a stock is judged)")}
{p("Seven small checks are grouped into 3 independent <b>families</b>. Each family votes LONG, SHORT, or NEUTRAL. "
   "Grouping avoids fake breadth — momentum, trend and the volume-break all move together, so they count as one idea.")}
{p(f"<b style='color:{GREEN}'>TREND</b> &nbsp;(weight {C.FAMILY_WEIGHTS['TREND']['weight']}) — is it moving strongly? "
   "Three factors, each z-scored vs its own history: <b>momentum</b> (60-min intraday return), "
   "<b>trend quality</b> (daily EMA-9 vs EMA-21 spread), <b>microstructure</b> (15-min opening-range breakout, ±1). "
   f"Factor weights — momentum {C.FAMILY_WEIGHTS['TREND']['factor_weights']['momentum']}, "
   f"trend {C.FAMILY_WEIGHTS['TREND']['factor_weights']['trend_quality']}, "
   f"micro {C.FAMILY_WEIGHTS['TREND']['factor_weights']['microstructure']}.")}
{p(f"<b style='color:{CYAN}'>FLOW</b> &nbsp;(weight {C.FAMILY_WEIGHTS['FLOW']['weight']}) — what are option writers doing? "
   "<b>LIVE per-stock options flow</b> from the chain (cached ~10 min): <b>OI-buildup imbalance</b> "
   "(are writers adding puts or calls?) + <b>PCR trend</b> (put/call OI ratio rising or falling). "
   "Writers add puts for support = bullish (+); add calls for resistance = bearish (−). "
   "Symmetric &amp; per-stock — equally positive or negative, no market-wide constant.")}
{p(f"<b style='color:{AMBER}'>EVENT</b> &nbsp;(weight {C.FAMILY_WEIGHTS['EVENT']['weight']}) — any news driving it? "
   "<b>LIVE</b>: NSE corporate announcements scraped at startup then ~every 20 min, 9 AM–1 PM, "
   "keyword-scored (orders/results/bonus = +1, fraud/penalty/downgrade = −1, routine = 0). "
   "Down-weighted on purpose — keyword scoring is crude, so it informs but never decides.")}
{dim("A 4th family (mean-reversion) was removed — it won only 47.6% in backtests. A family that doesn't win has no place here.")}

{h("5 · THE ALPHA-Z CALCULATION")}
{p("Each family produces a <b>z-score</b>: how unusual the reading is. "
   "0 = average · +1 = clearly bullish · −1 = clearly bearish · ±2 = extreme.")}
{p("We blend them into one number, the <b>alpha-z</b>, as a weighted average:")}
{p(f"<b style='color:{CYAN}'>alpha-z = Σ(family z × family weight) ÷ Σ(weights)</b>")}
{sub("Worked example — a stock reading bearish")}
{dim("TREND z = −0.9 (weight 0.65) · FLOW z = −0.6 (weight 0.17) · EVENT z = +0.2 (weight 0.18)")}
{dim("top = (−0.9×0.65) + (−0.6×0.17) + (0.2×0.18) = −0.585 − 0.102 + 0.036 = −0.651")}
{dim("bottom = 0.65 + 0.17 + 0.18 = 1.00  →  alpha-z = −0.65")}
{p("Reading it: negative = bearish; size 0.65 is above the 0.55 bar; 2 of 3 families agree SHORT → "
   "it PASSES Gate 1. Sign = direction, size = conviction.")}

{h("6 · THE GATES")}
{sub("GATE 1 — Alpha Gate (strong enough + broad enough?)")}
{p(f"• |alpha-z| strictly greater than <b>{C.ALPHA_Z_THRESHOLD}</b>")}
{p(f"• at least <b>{C.MIN_FAMILIES_AGREE} of 3</b> families agree on direction")}
{p(f"• the stock is in the proven universe (top {C.TOP_N_TRADEABLE} by expectancy)")}
{dim("Passing Gate 1 puts the stock on the WATCHLIST, 'awaiting ORB breakout'.")}
{sub("GATE 2 — ORB Breakout + Volume (is the move happening NOW?)")}
{p("The latest 5-min candle must close beyond the opening-range (above the high for a LONG, "
   "below the low for a SHORT) with a volume surge. A second, independent confirmation.")}
{sub("GATE 3 — Market Alignment (don't fight the tape)")}
{p("The trade must agree with the Nifty's intraday direction — <b>only LONG when Nifty is up, "
   "only SHORT when Nifty is down</b>. Blocks 'short into a rising market' losers. "
   "<i>30-day backtest: win 58%→60%, P&L +1.0%→+1.6%.</i>")}
{sub("GATE 4 — Don't Chase (is the stock already over-extended?)")}
{p(f"Skip the signal if the stock has already moved more than <b>{C.MAX_ENTRY_EXTENSION_PCT}%</b> "
   f"in the trade's direction from the day's open — buying an already-run stock is buying the top. "
   f"<i>365-day validation: over-extended entries won ~45% vs ~55% in the sweet spot. Option 60-day: "
   f"same profit on 26% fewer trades, return-on-capital +1.7% to +2.8%.</i>")}
{p("When all four gates pass, the stock moves to <b>PM DECISIONS</b>.")}
{sub("Watching the gates fill — the WATCHLIST tab")}
{p("Every stock that clears Gate 1 appears on <b>WATCHLIST</b> with a live per-gate readout: "
   "<b>G1 / G2 / G3 / G4</b> each show <b>PASS</b> or <b>wait</b>, plus a progress column "
   "(e.g. <b>3/4  next: align</b>) and <b>4/4 READY -&gt; PM</b> when it fires. The list is sorted "
   "closest-to-firing on top, so you can see exactly which gate each candidate is waiting on.")}

{h("7 · WHICH INSTRUMENT — BUY OPTIONS ONLY (two strategies)")}
{p("Every signal — in either strategy — becomes a <b>bought option</b> (never sold): "
   "<b style='color:{0}'>LONG → buy CALL</b>, <b style='color:{1}'>SHORT → buy PUT</b>.".format(GREEN, RED))}
{sub("STOCK OPTIONS — 3-Family system (95 stocks)")}
{p(f"Strike = <b>OTM+1</b> (offset {C.OPTION_STRIKE_OFFSET}): one strike OUT-of-the-money — CALL one "
   f"above spot, PUT one below. Exit <b>+{int(C.PREMIUM_TARGET_PCT)}% / −{int(C.PREMIUM_STOP_PCT)}%</b> "
   f"on premium. Shown in the green STOCK OPTIONS section on PM DECISIONS, "
   f"e.g. <b>BUY RELIANCE 1300 CE @ Rs…</b>.")}
{sub("INDEX OPTIONS — ORB+VWAP strategy (NIFTY &amp; BANKNIFTY)")}
{p(f"Strike = <b>ATM</b>. A 15-min Opening-Range Breakout that holds VWAP and aligns with the 30-min "
   f"trend (before 11 AM, skipping expiry-day) buys the ATM CALL/PUT. Added a <b>clean-trend "
   f"filter</b>: only enter when VWAP is sloped the trade's way and price is already &gt;0.25% "
   f"extended from the open.")}
{p(f"<b>Exit — TREND-RIDE</b> (not a fixed target): let the winner run; exit only when the futures "
   f"<b>reclaim VWAP</b> after the trade is +{int(C.ORB_VWAP_ARM_PCT)}% in profit; "
   f"<b>hard −{int(C.ORB_VWAP_STOP_PCT)}% stop</b> throughout; else square off at the close. This "
   f"replaced the old fixed +20% target, which 60-day testing showed was the cause of the daily "
   f"losses (27% win, −2.6%/trade → 63% win, +0.8%/trade). Shown in the purple ORB+VWAP section, "
   f"colour-coded CALL green / PUT red.")}
{dim(f"Nearest expiry (Nifty weekly, BankNifty/stocks monthly) · skip if IV > {C.OPTION_IV_THRESHOLD}. "
     f"Indices keep capital low: Nifty ~Rs12k/lot, BankNifty ~Rs28k/lot.")}

{h("8 · EXIT — ON THE OPTION PREMIUM (2:1 is NOT how options win)")}
{p(f"You exit on the option's own price, not the underlying:")}
{p(f"• <b style='color:{GREEN}'>STOCKS</b> &nbsp; BOOK <b>+{int(C.PREMIUM_TARGET_PCT)}%</b> / CUT "
   f"<b>−{int(C.PREMIUM_STOP_PCT)}%</b> on premium (e.g. Rs100 → Rs{100*(1+C.PREMIUM_TARGET_PCT/100):.0f} / "
   f"Rs{100*(1-C.PREMIUM_STOP_PCT/100):.0f})")}
{p(f"• <b style='color:{PURPLE}'>INDEX (ORB+VWAP)</b> &nbsp; BOOK <b>+{int(C.ORB_VWAP_TARGET_PCT)}%</b> / CUT "
   f"<b>−{int(C.ORB_VWAP_STOP_PCT)}%</b> on premium (symmetric)")}
{p(f"• <b>FORCE-CLOSE</b> at {C.KILL_SWITCH_TIME} regardless")}
{dim(f"Why small target + wide stop? Option premiums are volatile, so a quick +{C.PREMIUM_TARGET_PCT:.0f}% "
     f"is hit often (high win rate) while the wider −{C.PREMIUM_STOP_PCT:.0f}% stop avoids getting "
     f"shaken out by normal premium noise. In the recent backtest this gave ~77% win rate with "
     f"positive expectancy. The catch: it's only proven on 13 trades — forward sessions decide it.")}

{h("9 · RISK CONTROLS")}
{p("• <b>No per-day trade cap</b> — every qualifying signal is taken")}
{p(f"• <b>{C.CONSECUTIVE_LOSS_HALT}</b> stop-outs in a row → halt trading for the day")}
{p(f"• Every position force-closed at {C.KILL_SWITCH_TIME} — never hold overnight")}
{p(f"• Position size derived from the stop distance, not guesswork")}

{h("10 · PAPER TRADING & GO-LIVE RULE")}
{p("For the first month the system records every signal to its outcome (WIN at target, LOSS at stop, "
   "or FORCED at 3:10 PM). The TRADE LOG is your honest scorecard.")}
{p(f"<b>Why the bar is high:</b> with a +{int(C.PREMIUM_TARGET_PCT)}% target and −{int(C.PREMIUM_STOP_PCT)}% "
   f"stop you risk {int(C.PREMIUM_STOP_PCT)}% to make {int(C.PREMIUM_TARGET_PCT)}%, so the BREAKEVEN win rate is "
   f"{int(C.PREMIUM_STOP_PCT)}/({int(C.PREMIUM_TARGET_PCT)}+{int(C.PREMIUM_STOP_PCT)}) = "
   f"<b>~{C.PAPER_TRADING_BREAKEVEN_WIN_RATE:.0%}</b>. Below that you LOSE money.")}
{p(f"<b style='color:{GREEN}'>Go-live bar:</b> win rate ≥ <b>{C.PAPER_TRADING_MIN_WIN_RATE:.0%}</b> "
   f"(a margin above breakeven) AND profit factor > {C.PAPER_TRADING_MIN_PF} across "
   f"{C.PAPER_TRADING_MIN_SIGNALS}+ signals. Below that, the edge isn't proven — don't automate.")}
{dim("Honest note: backtests show ~72% on tiny samples but no proven edge. After brokerage + taxes the "
     "edge is thin. Treat every signal as a hypothesis and judge it by the live log over many sessions.")}

{h("11 · SPEED — how fast is a scan?")}
{p("The strategy logic is essentially instant; the only real cost is fetching data over the network.")}
{p("<b>Per stock:</b> score 3 families + alpha-z + all 4 gates + instrument choice = <b>~1.6 ms</b> (CPU). "
   "Fetching that stock's 5-min candles = <b>~440 ms</b> (network) — 99% of the time.")}
{p(f"<b>Full scan of NIFTY + BANKNIFTY + {len(C.UNIVERSE)} stocks:</b> ~3–4 seconds. We get there with "
   "12 parallel threads, a daily-history cache (fetched once per day), and batched live prices (all in one "
   "call). Sequential it would take ~43 seconds.")}
{dim("A 3–4 second scan inside a 5-minute window means a signal is seen almost the instant a candle closes — "
     "prices barely drift before the order appears. (First scan of the day ~6–7s for one-time cache warmup.)")}

{h("12 · HOW IT RUNS (local machine)")}
{p("Everything runs <b>locally</b> on this Mac — not from the cloud:")}
{p(f"• <b>08:55 weekdays</b> — Mac wakes itself (pmset schedule)")}
{p(f"• <b>09:00 weekdays</b> — app auto-launches (launchd: com.sayali.institutionaltrader)")}
{p(f"• Files live at <b>~/files/institutional-trader</b> · run by the local Python venv")}
{dim("GitHub (github.com/tejasgjadhav/Institutional-Trader) is the BACKUP / version history only — "
     "the app does NOT pull from it at runtime. To update what runs, edit the local files (changes "
     "are pushed to GitHub for safekeeping). Token lives in local .env (never committed).")}

<p style="color:{TEXT_DIM};margin-top:16px;font-size:10px;">
Last 5 trading days (recording window): {', '.join(str(d) for d in self.last5)} &nbsp;·&nbsp;
Universe: {len(C.UNIVERSE)} stocks &nbsp;·&nbsp; For educational use only. Not financial advice.
</p>

</div>
"""

    # ── interactions ──────────────────────────────────────────────────────────
    def switch(self, idx: int):
        self.active_screen = idx
        self.stack.setCurrentIndex(idx)
        self._highlight_tab(idx)

    def trigger_scan(self):
        # Autonomous: only scans live during market hours; otherwise stays in
        # SIMULATION (last-30-day historical option data already loaded).
        if not self.agent.is_market_open():
            return
        if getattr(self, "_scanning", False):
            return
        self._scanning = True
        if hasattr(self, "auto_lbl"):
            self.auto_lbl.setText("LIVE - scanning..."); self.auto_lbl.setStyleSheet(f"color:{GREEN}; padding:0 14px;")
        self.worker = ScanWorker(self.agent)
        self.worker.scan_complete.connect(self._on_scan)
        self.worker.error_occurred.connect(lambda e: self.status.showMessage(f"Scan error: {e}"))
        self.worker.start()

    def _on_scan(self, signals: list):
        self._scanning = False
        self.last_scan_results = signals  # ALL scored stocks (ALPHA shows everything)

        # Log + notify any NEW trade-ready signal (not already logged today).
        ready = [s for s in signals if s.get("trade_ready") and self.agent.is_trading_window()]
        new_ready = [s for s in ready if s.get("ticker") not in getattr(self, "_notified_today", set())]
        if new_ready:
            if not hasattr(self, "_notified_today"):
                self._notified_today = set()
            for s in new_ready:
                self._notified_today.add(s["ticker"])
                self._record_fired(s)   # persist on PM DECISIONS for the whole day
            try:
                self.agent.execute_signals(new_ready)  # writes trade log + fires notifications
            except Exception as e:
                logger.warning(f"execute_signals failed: {e}")

        self._resolve_outcomes()   # close PENDING paper trades (WIN/LOSS) on the premium
        self._refresh_pm(); self._refresh_watchlist(); self._refresh_alpha(); self._refresh_log()
        if hasattr(self, "auto_lbl"):
            self.auto_lbl.setText("LIVE"); self.auto_lbl.setStyleSheet(f"color:{GREEN}; padding:0 14px;")

    def _resolve_outcomes(self):
        """Mark PENDING paper trades WIN/LOSS by replaying the option premium."""
        try:
            from engine.paper_resolver import resolve_pending
            n = resolve_pending(self.agent.trade_log)
            if n:
                logger.info(f"Resolved {n} paper-trade outcome(s)")
        except Exception as e:
            logger.warning(f"resolve outcomes failed: {e}")

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

    # ── PM DECISIONS persists the DAY'S fired signals (not just the current scan) ──
    def _ensure_fired_today(self):
        """Reset the day's fired-signal list at rollover; seed from the trade log so a
        mid-day app restart doesn't lose signals that already fired today."""
        today = datetime.now(IST).date()
        if getattr(self, "_fired_day", None) != today:
            self._fired_day = today
            self._fired_today = []
            self._seed_fired_from_log(today)
            try:    # refresh the daily CSV snapshot of signals.db
                from engine import signal_db
                signal_db.export_csv()
            except Exception:
                pass

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

    def _refresh_pm(self):
        self._ensure_fired_today()
        from engine.options import build_live_option_order
        from engine.data_fetcher import get_cached_ltp, fetch_upstox_ltp
        fired = sorted([f for f in self._fired_today if f["kind"] == "STOCK"],
                       key=lambda f: f["time"], reverse=True)   # newest on top
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
            self._db_record_stock(f, order, sym)   # persist to signals.db
            kind = (order["instrument"] if order else f.get("instrument", ""))
            fg = QColor(GREEN) if kind == "CALL" else (QColor(RED) if kind == "PUT" else QColor(AMBER))
            if not order:
                vals = [f["time"], sym, kind, "—", "—", "—", "—", "—", "—", "—", "—", "FIRED"]
                self._set_row(self.pm_stock, r, vals, fg=fg); continue
            # live current premium of the exact option
            curp = "—"
            try:
                lt = fetch_upstox_ltp(order["option_key"])
                if lt.get("success") and lt.get("price"):
                    curp = f"Rs {lt['price']:.2f}"
            except Exception:
                pass
            cap = f"Rs {order['capital']:,.0f}" if order.get("capital") else "—"
            vals = [f["time"], sym, kind, f"{order['strike']:.2f}", order["expiry"],
                    f"Rs {order['premium']:.2f}", curp,
                    f"Rs {order['target_premium']:.2f}", f"Rs {order['stop_premium']:.2f}",
                    order.get("lot_size", "—"), cap, "FIRED"]
            self._set_row(self.pm_stock, r, vals, fg=fg)

        self._fit_table(self.pm_stock)
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
                breadth=f.get("breadth"), vol_ratio=f.get("vol_ratio"), status="FIRED")
        except Exception:
            pass

    def _refresh_orbvwap(self):
        """Render the parallel ORB+VWAP index strategy rows on PM DECISIONS."""
        rows = getattr(self.agent, "orbvwap_signals", []) or []
        self.pm_orbvwap.setRowCount(len(rows))
        for r, s in enumerate(rows):
            status = s.get("status", "—")
            if s.get("entry"):  # an active/closed signal
                try:
                    from engine import signal_db
                    signal_db.record_signal(
                        time=s.get("time"), strategy="ORB+VWAP", symbol=s.get("index"),
                        direction=s.get("direction"), opt_type=s.get("kind"),
                        strike=s.get("strike"), expiry=s.get("expiry"),
                        entry_premium=s.get("entry"), target_premium=s.get("target"),
                        stop_premium=s.get("stop"), lot=s.get("lot"),
                        capital=s.get("capital"), status=s.get("status"))
                except Exception:
                    pass
                cur = f"Rs {s['current']:.2f}" if s.get("current") else "—"
                kind = s.get("kind", "—")
                strike = f"{s['strike']:.2f}" if isinstance(s.get("strike"), (int, float)) else s.get("strike", "—")
                exit_cell = s.get("exit_rule") or (f"Rs {s['target']:.2f}"
                                                   if s.get("target") else "VWAP-break")
                vals = [s.get("time", "—"), s.get("index", "—"), kind,
                        strike, s.get("expiry", "—"),
                        f"Rs {s['entry']:.2f}", exit_cell,
                        f"Rs {s['stop']:.2f}", cur, s.get("lot", "—"), status]
                # CALL = green, PUT = red — so the option type is obvious at a glance
                fg = QColor(GREEN) if kind == "CALL" else QColor(RED)
            else:  # watching / skip / no-data placeholder
                vals = [datetime.now(IST).strftime("%H:%M"), s.get("index", "—"),
                        "—", "—", "—", "—", "—", "—", "—", "—", status]
                fg = QColor(TEXT_DIM)
            self._set_row(self.pm_orbvwap, r, vals, fg=fg)
        self._fit_table(self.pm_orbvwap)

    def _refresh_watchlist(self):
        wl = [s for s in self.last_scan_results if s.get("passes_gate_1")]

        def gates(s):
            # G1 is true for everyone on the watchlist; G2/G3/G4 are the progress.
            return [True, bool(s.get("gate_2")), bool(s.get("aligned")),
                    bool(s.get("not_extended"))]

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
                nxt = ["alpha", "ORB", "align", "not-extended"][g.index(False)]
                prog = f"{npass}/4  next: {nxt}"
            vals = [sig.get("ticker"), f"{sig.get('alpha_z',0):.2f}", sig.get("direction"),
                    mark(g[0]), mark(g[1]), mark(g[2]), mark(g[3]), prog]
            self._set_row(self.wl_table, r, vals, fg=self._dir_color(sig.get("direction")))
            # color each gate cell: green when passed, dim when waiting; READY row glows green
            for col, ok in zip((3, 4, 5, 6), g):
                it = self.wl_table.item(r, col)
                if it: it.setForeground(QColor(GREEN) if ok else QColor(TEXT_DIM))
            pit = self.wl_table.item(r, 7)
            if pit: pit.setForeground(QColor(GREEN) if npass == 4 else QColor(AMBER))

    def _refresh_alpha(self):
        rows = self.last_scan_results
        self.alpha_table.setRowCount(len(rows))
        for r, sig in enumerate(rows):
            fam = sig.get("families_detail", {})
            vals = [sig.get("ticker"), f"{sig.get('alpha_z',0):.2f}", sig.get("direction"),
                    f"{sig.get('breadth',0)}/3",
                    f"{fam.get('TREND',{}).get('z_score',0):.2f}",
                    f"{fam.get('FLOW',{}).get('z_score',0):.2f}",
                    f"{fam.get('EVENT',{}).get('z_score',0):.2f}"]
            self._set_row(self.alpha_table, r, vals, fg=self._dir_color(sig.get("direction")))

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

    def _refresh_log(self):
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
        # Skip if a previous fetch is still in flight (avoids overlap/crash).
        if self._mkt_running:
            return
        self._mkt_running = True
        self.mkt_worker = MarketDataWorker()
        self.mkt_worker.data_ready.connect(self._on_market_data)
        self.mkt_worker.finished.connect(self._mkt_done)
        self.mkt_worker.start()
        # Adapt cadence to market state (timer may not exist on the very first call)
        timer = getattr(self, "mkt_timer", None)
        if timer is not None:
            interval = 3000 if self.agent.is_market_open() else 20000
            if timer.interval() != interval:
                timer.setInterval(interval)

    def _mkt_done(self):
        self._mkt_running = False

    def _on_market_data(self, d: dict):
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

    def _maybe_eod_book(self, now):
        """Force-close every OPEN paper trade at end of day, Mon–Fri, exactly once a day.
        Runs from the 1-sec clock (not the scan loop) so it ALWAYS fires. Books just after
        the 15:30 close using the full session's premium — unless target/stop already hit."""
        if now.weekday() >= 5:                       # Sat / Sun
            return
        m = now.hour * 60 + now.minute
        if not (15 * 60 + 31 <= m <= 15 * 60 + 55):  # 15:31–15:55 window
            return
        if getattr(self, "_eod_booked", None) == now.date():
            return
        self._eod_booked = now.date()
        logger.info("EOD daily booking — force-closing open paper trades at the 15:30 close")
        try:
            self._resolve_outcomes()                 # resolver force-closes (past kill switch)
            self._refresh_log(); self._refresh_pm()
        except Exception as e:
            logger.warning(f"EOD booking failed: {e}")

    def _tick(self):
        now = datetime.now(IST)
        self._maybe_eod_book(now)                     # daily 15:30 force-close (Mon–Fri)
        is_open = self.agent.is_market_open()
        mkt = "OPEN" if is_open else "CLOSED"
        # live clock in the index bar (top-right), green when market is open
        if hasattr(self, "clock_lbl"):
            self.clock_lbl.setText(f"{now:%a %d %b  %H:%M:%S} IST   {'OPEN' if is_open else 'CLOSED'}")
            self.clock_lbl.setStyleSheet(f"color:{GREEN if is_open else AMBER};")
        mode = "LIVE" if is_open else "SIMULATION"
        # Keep the AUTO badge in sync when idle (scanning sets it to LIVE·scanning)
        if hasattr(self, "auto_lbl") and not getattr(self, "_scanning", False):
            if is_open:
                self.auto_lbl.setText("LIVE - AUTO 5-min"); self.auto_lbl.setStyleSheet(f"color:{GREEN}; padding:0 14px;")
            else:
                self.auto_lbl.setText("SIMULATION"); self.auto_lbl.setStyleSheet(f"color:{AMBER}; padding:0 14px;")
        if hasattr(self, "mode_label"):
            self.mode_label.setText(f"{'LIVE' if is_open else 'SIMULATION'}  -  9:00-15:30 Mon-Fri auto-live")
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
