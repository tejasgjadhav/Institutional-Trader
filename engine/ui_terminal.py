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
    QHeaderView, QStackedWidget, QTextEdit, QTextBrowser, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QBrush, QIcon, QPixmap

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
STOCKV0_SNAP  = _os.path.join(DATA_DIR, "stock_credit_v0.json")
STOCKV0_BOOK  = _os.path.join(DATA_DIR, "stock_credit_v0_positions.json")
# App logo — Saavi. Lives in data/ (gitignored) so the photo never leaves this machine;
# every use below falls back gracefully when the file is absent.
LOGO_PATH = _os.path.join(DATA_DIR, "saavi_logo.png")
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
        self.setWindowTitle("SAAVI INSTITUTIONAL TRADER · TERMINAL")
        if _os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))
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
        self._stockv0_rows = []
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

    def keyPressEvent(self, event):
        # Esc leaves full-screen (the launcher starts the app full-screen)
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

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

        if _os.path.exists(LOGO_PATH):
            logo = QLabel()
            logo.setPixmap(QPixmap(LOGO_PATH).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            h.addWidget(logo); h.addSpacing(8)

        title = QLabel("◤ SAAVI INSTITUTIONAL TRADER")
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
        self.sensex_lbl = self._ticker_label("SENSEX", "—")
        self.vix_lbl   = self._ticker_label("INDIA VIX", "—", AMBER)
        for lbl in (self.nifty_lbl, self.bnf_lbl, self.sensex_lbl, self.vix_lbl):
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
                ("SWING TRADE LOG", 2), ("INTRADAY TRADE LOG", 3), ("STUDIES", 4), ("README", 5)]
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
    # UNDERLYING added 2026-08-05: the price the signal was computed on -> the live price. GRASIM
    # fired a bear-call the day AFTER its breakout off a stale bar; this column makes that visible.
    PM_CREDIT_COLS = ["ACTION", "INSTRUMENT", "UNDERLYING", "LOT", "PREMIUM", "EXPIRY", "AMOUNT", "P&L / STATUS"]
    # BRK = the STRONGEST Donchian window that broke (D5/D10/D15/D20) — D10+ is a more durable
    # breakout than a bare D5 (see studies/DONCHIAN_D5_VS_D10.md).
    # SIGNAL→LIVE added 2026-08-05: the price the breakout was computed on, next to the live price.
    # A bear-call fired on GRASIM the day AFTER its breakout off a stale bar and nothing on screen
    # could reveal it. A large gap here is that failure, visible.
    # CREDIT added 2026-08-10 (user): the premium DIFFERENCE — what the short leg pays minus what
    # the hedge costs, in points. It is the numerator of C/W and what you actually collect.
    # MAX +/- RESTORED 2026-08-12 as ONE merged column (user): the pair is what gets read, and
    # one column fits where two did not. Original note kept below for the why.
    # MAX Rs+/Rs- were dropped because 14 columns could not fit, and with the horizontal scrollbar
    # off Qt SQUEEZES columns to the viewport — so the fixed widths were silently ignored and every
    # cell truncated. Both are derivable (credit x lot; (width-credit) x lot) and are shown in full
    # on the PM DECISIONS rows anyway. The columns the user actually reads keep real width.
    WATCH_COLS = ["STOCK", "SIDE", "BRK", "SIGNAL→LIVE", "SELL / BUY", "EXPIRY", "LOT", "C/W", "CREDIT", "PREM", "LIQ", "MAX ₹ +/−", "RESULT"]

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
        """Fixed widths for the 8 PM_CREDIT_COLS (ACTION/INSTRUMENT/UNDERLYING/LOT/PREMIUM/EXPIRY/
        AMOUNT/P&L·STATUS) summing ~1026px — same total as the watchlist. Stretch mode ballooned the
        table past the window and clipped the last column; fixed widths keep it single-screen."""
        h = t.horizontalHeader()
        for _c, _px in enumerate((96, 232, 168, 70, 110, 124, 138, 130)):
            h.setSectionResizeMode(_c, QHeaderView.ResizeMode.Fixed)
            h.resizeSection(_c, _px)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _screen_pm(self) -> QWidget:
        """PM DECISIONS — every strategy book, each section sized to its content inside a scroll area."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(6)
        v.addWidget(self._panel_title("LATEST PM DECISIONS  -  place manually in Upstox", AMBER))
        self.pm_timings = self._timings_label()
        v.addWidget(self.pm_timings)

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
        # Rebalanced 2026-08-10 (user screenshot): C/W truncated to "✗ …", LOT to "15…", BRK to
        # "D…", SIGNAL→LIVE cut on 4-digit prices. Space came out of STOCK/SELL-BUY/MAX columns —
        # the ones with headroom — so the row still fits one screen (sum 1288px < ~1400 window).
        # PROPORTIONAL, not fixed px (2026-08-12). Fixed widths were guesswork: the window is
        # 1700 logical px but the table's viewport is whatever is left after margins and the outer
        # scroll area, and with the horizontal scrollbar OFF Qt silently SQUEEZES columns to fit —
        # so every fixed-width attempt was overridden and truncated. Weights below are shares of
        # the ACTUAL viewport, recomputed on every resize, so columns can never be squeezed.
        # STOCK SIDE BRK SIG SELL/BUY EXP LOT C/W CRED PREM LIQ MAX RESULT
        self._watch_weights = (9, 9, 6, 7, 23, 7, 5, 7, 7, 4, 5, 18, 8)   # sums to 115
        _wh = self.pm_watch.horizontalHeader()
        for _c in range(len(self.WATCH_COLS)):
            _wh.setSectionResizeMode(_c, QHeaderView.ResizeMode.Fixed)
        self.pm_watch.resizeEvent = lambda e, _t=self.pm_watch: (
            self._size_watch_cols(), QTableWidget.resizeEvent(_t, e))[1]
        self.pm_watch.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # single view — never scroll sideways
        self.pm_watch.setAlternatingRowColors(True); self.pm_watch.verticalHeader().setVisible(False)
        self.pm_watch.verticalHeader().setDefaultSectionSize(28); self.pm_watch.setMaximumHeight(400)
        self.pm_watch.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._size_watch_cols()
        v.addWidget(self.pm_watch)

        # STOCK CREDIT v2 (TP-50 upgrade) — replaces the retired ORB+VWAP section (thin/inconsistent
        # on real 2019→date data). Runs PARALLEL to v1: short 2-OTM · width 4 · TP 50% · stop 3×.
        pmv2 = QLabel("★ STOCK CREDIT v2 UNION · sell 2-OTM / buy width-4 · TARGET book@50% credit · STOP 3× credit is INERT at c/w≥0.40 (held to expiry, floor = max loss) · WIN 84% over 2019–Sep 2024 / 87% over Oct 2024–now at this target/stop · ~7.6/mo (113-name universe) · SELL ★")
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

        # STOCK CREDIT v0 (c/w 0.35-0.40) — user-approved 2026-07-31. Rendered LAST and in cyan
        # rather than v2's gold, so the leader book stays visually distinct. Stats shown are the
        # honest IS/OOS pair — see studies/LOWCW_BAND_RESCUE.md §7.
        pmv0 = QLabel("STOCK CREDIT v0 · c/w 0.35–0.40 (the band below the v2 gate) · same geometry as v2 "
                      "(sell 2-OTM / buy width-4) · TARGET book@40% credit · NO STOP (wing caps loss) · "
                      "WIN 77% over 2019–Sep 2024 (positive 4 of those 6 yrs, +1.9% on margin) / "
                      "91% over Oct 2024–Jul 2026 (43 trades) · "
                      "one more CORE lot returned 82% more · 1 lot · max 3/day, 10 open · ~5.5 sig/mo · avg net ₹2,408/lot per trade · 1 lot · if v1 takes the SAME stock, v1 wins and v0 stands down (one signal only)")
        pmv0.setWordWrap(True)
        pmv0.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        pmv0.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:2px solid {CYAN}; border-radius:4px;")
        v.addWidget(pmv0)
        self.pm_stockv0 = QTableWidget(); self.pm_stockv0.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_stockv0.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_stockv0)
        self.pm_stockv0.setAlternatingRowColors(True); self.pm_stockv0.verticalHeader().setVisible(False)
        self.pm_stockv0.verticalHeader().setDefaultSectionSize(32)
        self.pm_stockv0.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pm_stockv0.setStyleSheet(f"QTableWidget {{ border: 2px solid {CYAN}; }}")
        v.addWidget(self.pm_stockv0, 1)

        # STOCK CREDIT SPREADS — the 4th strategy (high-frequency fade on single stocks).
        v.addWidget(self._section_label(
            "STOCK CREDIT SPREADS v1 · fade · sell 1-OTM / buy width-3 · TARGET book 40% of credit · NO STOP (wing caps loss) · WIN 85% over 2019–Sep 2024 / 86% over Oct 2024–now at this target · +ve every yr · TP-40/no-stop deployed 2026-07-30 (was TP-75/stop-2×: 64%/73%) · ~16/mo · SELL", GREEN))
        self.pm_stockcr = QTableWidget(); self.pm_stockcr.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_stockcr.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_stockcr)
        self.pm_stockcr.setAlternatingRowColors(True); self.pm_stockcr.verticalHeader().setVisible(False)
        self.pm_stockcr.verticalHeader().setDefaultSectionSize(32)
        self.pm_stockcr.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_stockcr, 1)

        # SWING CREDIT (index fade) — HIDDEN 2026-07-24 unless SWING_CREDIT_ENABLED (removed: failed
        # OOS, net −1.4%w). Widget still created (refresh code references pm_swing) but hidden.
        from engine import config as _swc
        _swing_on = getattr(_swc, "SWING_CREDIT_ENABLED", False)
        _swhdr = self._section_label("SWING CREDIT · NIFTY/FINNIFTY · fade · forward-test only · ~3/mo · SELL", CYAN)
        v.addWidget(_swhdr)
        self.pm_swing = QTableWidget(); self.pm_swing.setColumnCount(len(self.PM_CREDIT_COLS))
        self.pm_swing.setHorizontalHeaderLabels(self.PM_CREDIT_COLS)
        self._credit_cols(self.pm_swing)
        self.pm_swing.setAlternatingRowColors(True); self.pm_swing.verticalHeader().setVisible(False)
        self.pm_swing.verticalHeader().setDefaultSectionSize(34)
        self.pm_swing.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v.addWidget(self.pm_swing, 1)
        if not _swing_on:
            _swhdr.setVisible(False); self.pm_swing.setVisible(False)

        # MONTHLY FUTURES PULLBACK — the 5th strategy (monthly cycle · BUY front-month futures).
        # Signals-only paper test; needs ~Rs 15L to trade for real. Earnings-skip applied live.
        v.addWidget(self._section_label(
            "MONTHLY FUTURES PULLBACK · REV1-v2 · TARGET +2% (→+1% late) · STOP −5% on close · WIN 77.8% over 2018–Sep 2024 / 75.7% over Oct 2024–now at this target/stop · 5/cycle · BUY FUT (paper, ~₹15L)", AMBER))
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


        self.pm_empty = QLabel("Credit-spread signals appear ~15:36 (place by 15:40); expiry-day books live on the INTRADAY DECISIONS tab.")
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
    # stock-credit variant: same layout + an explicit BOOK column (v1 / v2) so the two
    # fade books are never confused when read side by side.
    SWING_TAB_BOOK_COLS = ["ENTERED", "BOOK", "LEG", "INSTRUMENT", "LOT", "ENTRY", "NOW/EXIT", "LEG P&L", "NET / STATUS"]

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
        self.sw_stk2 = self._make_log_table(self.SWING_TAB_BOOK_COLS)
        self.sw_stk2.setStyleSheet(f"QTableWidget {{ border: 2px solid {AMBER}; }}")
        v.addWidget(self.sw_stk2)
        v.addWidget(self._section_label("INDEX SWING — NIFTY/FINNIFTY · fade the breakout · hold to expiry (fwd-test only) · ~3/mo", CYAN))
        self.sw_idx_stats = self._stats_label(); v.addWidget(self.sw_idx_stats)
        self.sw_idx = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sw_idx)
        v.addWidget(self._section_label("STOCK CREDIT SPREADS v1 · fade the breakout · ~10/mo · SELL", GREEN))
        self.sw_stk_stats = self._stats_label(); v.addWidget(self.sw_stk_stats)
        self.sw_stk = self._make_log_table(self.SWING_TAB_BOOK_COLS); v.addWidget(self.sw_stk)
        v0hdr = QLabel("STOCK CREDIT v0 (c/w 0.35–0.40)   the band below the gate · book at 40% of credit · no stop · "
                       "77% IS (+ve 4/6 yrs) · 91% OOS (43 trades) · scans in parallel with v1/v2 — but on a same-stock clash v1 wins and v0 stands down")
        v0hdr.setWordWrap(True)
        v0hdr.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        v0hdr.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:2px solid {CYAN}; border-radius:4px;")
        v.addWidget(v0hdr)
        self.sw_v0_stats = self._stats_label()
        self.sw_v0_stats.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:2px solid {CYAN};")
        v.addWidget(self.sw_v0_stats)
        self.sw_v0 = self._make_log_table(self.SWING_TAB_BOOK_COLS)
        self.sw_v0.setStyleSheet(f"QTableWidget {{ border: 2px solid {CYAN}; }}")
        v.addWidget(self.sw_v0)
        v.addStretch(1)
        return self._scroll(inner)

    def _stats_label(self) -> QLabel:
        l = QLabel("—"); l.setFont(QFont("Menlo", 12, QFont.Weight.Bold)); l.setWordWrap(True)
        l.setStyleSheet(f"color:{CYAN}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        return l

    def _screen_zero_dte(self) -> QWidget:
        """INTRADAY DECISIONS — the 0DTE NIFTY expiry-day CE credit spread (5th strategy).
        One defined-risk trade per weekly expiry day, opened ~9:16, settled the same day 15:40."""
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(12, 4, 12, 8); v.setSpacing(4)
        v.addWidget(self._panel_title("INTRADAY DECISIONS  -  NIFTY expiry-day call credit spread", CYAN))
        self.zdte_timings = self._timings_label()
        v.addWidget(self.zdte_timings)
        # dynamic pre-market checker — engine refreshes data/zero_dte_status.json every ~2-5 min
        self.zdte_status = QLabel("checking today's status…")
        self.zdte_status.setWordWrap(True)
        self.zdte_status.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        self.zdte_status.setStyleSheet(f"color:{TEXT_DIM}; padding:10px; background-color:{PANEL}; border:2px solid {BORDER};")
        v.addWidget(self.zdte_status)
        hdr = QLabel("★ NIFTY EXPIRY-DAY CE SPREAD — WIN 88% over 2019–Sep 2024 / 90% over Oct 2024–now · +5.9%/MARGIN/TRADE · EVERY TUESDAY 9:16 · "
                     "MARGIN ≈ ₹14k/LOT (= MAX LOSS) · FLIP: sells PE in up-momentum weeks, CE otherwise · "
                     "HYBRID ADD (paper 07-31): the OPPOSITE side ~1% OTM is ALSO sold when it pays c/w ≥ 0.08 — "
                     "shared margin · IS 86.5%/+₹1.48L vs FLIP +₹1.04L · OOS 91.5%/+₹0.82L vs +₹0.64L · worst-case identical")
        hdr.setWordWrap(True)
        hdr.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:#000000; background-color:{CYAN}; padding:8px; border:2px solid {CYAN}; border-radius:4px;")
        v.addWidget(hdr)
        how = QLabel("RULES · trade ONLY when the strip above is GREEN (engine skips hot weeks)\n"
                     "  the strip tells you the SIDE: FLIP sells PE in up-momentum weeks (5-day ≥+1%), else CE\n"
                     "  9:16   SELL the chosen leg ~0.5% OTM · BUY the hedge 200 pts further out (same-day expiry)\n"
                     "  hybrid if the engine ALSO fires the opposite side (~1% OTM, c/w ≥ 0.08), place that spread too — margin is shared\n"
                     "  order  basket, wing (BUY) first, limit at mid · then NOTHING — no stop, no adjusting\n"
                     "  15:40  settles automatically (or earlier at 95% of max profit) · wins ~9 weeks in 10 · the rare loss can cost the full margin\n"
                     "FLIP edge: 87.1% win / +₹1.92L since 2019 vs 84.7% / +₹1.17L CE-only. Full research: STUDIES tab.")
        how.setWordWrap(True); how.setFont(QFont("Menlo", 11))
        how.setStyleSheet(f"color:{TEXT}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(how)
        self.zdte_stats = self._stats_label()
        v.addWidget(self.zdte_stats)
        self.zdte_table = self._make_log_table(self.SWING_TAB_COLS)
        self.zdte_table.setStyleSheet(f"QTableWidget {{ border: 2px solid {CYAN}; }}")
        v.addWidget(self.zdte_table, 1)
        v.addWidget(self._section_label("SENSEX EXPIRY-DAY — THURSDAYS · WIN 88.8% over Oct 2024–now · no earlier data (SENSEX option data starts Oct'24) · +7.6%/margin "
                                        "(89 expiries · 21-month history only · unfiltered)", AMBER))
        self.sdte_status = self._stats_label(); v.addWidget(self.sdte_status)
        self.sdte_stats = self._stats_label(); v.addWidget(self.sdte_stats)
        self.sdte_table = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.sdte_table, 1)
        v.addWidget(self._section_label("BANKNIFTY EXPIRY-DAY — MONTHLY (~1/mo) · WIN 79.5% over 2019–Sep 2024 (weeklies, +7.4%m) / 91% over Oct 2024–now (Oct'24–now, monthlies, +11%m)", PURPLE))
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
                rc = GREEN if rs > 0 else RED if rs < 0 else TEXT_DIM
                self.log_stats.setText(f"  INTRADAY expiry-day (all 3 books, live paper): {W} W / {L} L · "
                                       f"WIN {wr:.0f}% · booked <span style='color:{rc};'>Rs {rs:+,.0f}</span>")
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
        v.addWidget(self._panel_title("INTRADAY TRADE LOG  -  expiry-day books (2-leg format)"))

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
        v.addWidget(self._section_label("INTRADAY  —  NIFTY expiry-day FLIP spread (Tuesdays)", CYAN))
        self.log_zdte = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.log_zdte, 1)
        v.addWidget(self._section_label("INTRADAY  —  SENSEX expiry-day CE spread (Thursdays)", AMBER))
        self.log_sdte = self._make_log_table(self.SWING_TAB_COLS); v.addWidget(self.log_sdte, 1)
        v.addWidget(self._section_label("INTRADAY  —  BANKNIFTY expiry-day CE spread (monthly)", PURPLE))
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
        doc = QTextBrowser(); doc.setReadOnly(True); doc.setFont(QFont("Menlo", 11))
        doc.setOpenExternalLinks(True)   # make the studies/GitHub link actually clickable
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

<p style="color:{RED};font-size:17px;font-weight:bold;">⚠ THE STALE-BAR INCIDENT — FOUND 5-AUG · FIXED · VERIFIED 6-AUG. THE FORWARD RECORD RESTARTS 6-AUG-2026</p>
{p("For six weeks the scan <b>never read the current day's close</b>: the Upstox daily feed carries no same-day bar "
   "during the session, so every signal was computed on the <b>PREVIOUS session's close</b> against a one-day-shifted "
   "Donchian band. Reconstructing all 19 booked positions: <b>every one matches a T-1 breakout, zero require the same "
   "day</b>. GRASIM was the tell — it broke out Monday (+5.1%), and the bear call arrived Tuesday after it had already "
   "fallen 3.7%. The user's question — <i>why on earth a bear call?</i> — found what repeated code sweeps could not: "
   "the bug was in the DATA, not the code, and only shows up at the real read-time.")}
{res("<b>FIXED (5-Aug):</b> today's close now comes from the intraday series, where the auction print lands "
     "(todays_close) · a scan that cannot get TODAY's close refuses to fire · a DIRECTION AUDIT suppresses any signal "
     "contradicting the day's move (an invariant — verified on 1,182 real breakouts, zero legitimate conflicts) · and "
     "every signal's price is shown on screen next to the live price (SIGNAL→LIVE, AUC = auction close).")}
{res("<b>VERIFIED (6-Aug, first corrected session):</b> HAL bear call fired ON its up-day (+5.9%), signal price "
     "<b>4,920.00 = official bhavcopy close, EXACT</b> · 15:31 watchlist 19/20 exact vs bhavcopy · the stale guard "
     "fired in production (RELIANCE) and correctly refused to scan. The system now trades the same close-based signal "
     "the 2019-2026 backtests measured — for the first time.")}
{dim("Honest consequences: the pre-6-Aug live record (11W/4L) belongs to the DELAYED strategy and must not be compared "
     "to the 84-87% backtest figures. The forward record starts 6-Aug. Full record: studies/STALE_BAR_INCIDENT.md")}

<p style="color:{AMBER};font-size:17px;font-weight:bold;">⚠ NSE SESSION CHANGED — 3-AUG-2026 · ALL OUR TIMINGS MOVED</p>
{p("NSE moved the equity-<b>derivatives</b> close from <b>15:30 to 15:40</b> and introduced a <b>Closing Auction Session</b>. "
   "F&amp;O stocks now stop continuous trading at <b>15:15</b>, auction 15:15–15:35, and their official closing price is the "
   "<b>auction equilibrium price</b> — not the old 15:00–15:30 average. Every stock we trade is an F&amp;O stock, so this "
   "applies to all of them.")}
{res("<b>OUR NEW TIMINGS —</b> watchlist <b>15:17</b> · signals <b>15:36</b> · place by <b>15:40</b> · everything settles at "
     "<b>15:40</b> · intraday books also close early at <b>95% of max profit</b>.")}
{p("<b>Why it matters:</b> the old 15:10 scan read a price that no longer decides anything. Replaying 3-Aug across all 113 "
   "names: <b>32 breakouts on the 15:10 price vs 46 on the official close</b> — <b>+44%</b>, 15 names gained, 1 false signal "
   "(PNB) removed. The typical name drifts <b>0.68%</b> between 15:10 and the close, and 66 of 113 moved at least 0.5%. So "
   "moving the scan later <b>gains</b> signals; it does not cost them.")}
{p("<b>Is the 15:36–15:40 window tradeable?</b> Measured on 4-Aug across 18 watchlist names: <b>17 of 18</b> quote two-sided, "
   "<b>15 of 17</b> clear our liquidity gate, and c/w barely moves across the auction (GRASIM 0.35 → 0.38). But bid-ask "
   "roughly <b>doubles</b>, ~1% → 2–4%, so entry costs more than the model assumes.")}
{dim("Also fixed: the close had been hardcoded in SEVEN separate places, and the swing/stock books preferred the live price "
     "over the official close — so every expiry was settling on a pre-auction print. There is now one setting "
     "(SETTLE_AFTER = 15:40) and settlement takes the official close first. <b>Caveat:</b> the 95% early-close rule cannot "
     "be backtested — intraday option premium history does not exist — so it ships unmeasured and can be switched off. "
     "Full record: studies/NSE_SESSION_CHANGE_2026_08_03.md")}

<p style="color:{CYAN};font-size:18px;font-weight:bold;">HOW TO EXECUTE — step by step</p>
{dim("Everything below is a paper forward-test. The engine only SIGNALS; you place the order yourself in Upstox. Keep lots at 1.")}

<p style="color:{AMBER};font-size:15px;font-weight:bold;margin-top:14px;">THE STOCK BOOKS — v2, v1, v0 (one scan a day)</p>
{p("<b>1.</b> The engine scans ONCE at <b>15:36</b>, after the closing auction has struck the official close. Nothing fires before that. (It scanned at 15:10 until 4-Aug-2026 — NSE moved the close, see the notice at the top of this tab.)")}
{p("<b>2.</b> A stock that closed ABOVE its Donchian high or BELOW its Donchian low is a breakout. You <b>FADE</b> it — you sell against the move, not with it.")}
{p("<b>3.</b> Up-break → sell a <b>BEAR CALL</b> spread. Down-break → sell a <b>BULL PUT</b> spread. Nearest monthly expiry at least <b>10 days</b> out.")}
{p("<b>4.</b> Which strikes, per book:")}
{dim("&nbsp;&nbsp;&nbsp;• <b>v2</b> (leader) — SELL 2 strikes OTM, BUY 4 strikes further out. Only if credit ÷ width ≥ <b>0.40</b>.")}
{dim("&nbsp;&nbsp;&nbsp;• <b>v1</b> — SELL 1 strike OTM, BUY 3 strikes further out. Only if credit ÷ width ≥ <b>0.40</b>.")}
{dim("&nbsp;&nbsp;&nbsp;• <b>v0</b> — same strikes as v2, but takes the band v2 rejects: credit ÷ width between <b>0.35 and 0.40</b>.")}
{p("<b>5.</b> Short leg must be ≥ <b>₹50</b> premium, bid-ask ≤ 6%, OI ≥ 100. If it fails, skip it — thin options eat the edge.")}
{p("<b>6.</b> Place it <b>between 15:36 and 15:40</b> — derivatives now close at 15:40, so that is the whole window. The 15:17 watchlist names the likely candidates ~19 minutes ahead, so pre-stage from it and treat the 15:36 signal as confirmation. Spreads are roughly twice as wide in this window as at 14:45, so use limit orders.")}
{p("<b>7.</b> Exit — this is what sets the win rate, more than the entry does:")}
{dim("&nbsp;&nbsp;&nbsp;• <b>v2</b> — buy the spread back when it costs <b>50%</b> of the credit you collected. Stop at 3× credit (almost never reached).")}
{dim("&nbsp;&nbsp;&nbsp;• <b>v1 and v0</b> — buy it back at <b>40%</b> of the credit. <b>No stop</b> — the wing you bought already caps the loss.")}
{p("<b>8.</b> If nothing is bought back, it settles itself at expiry. Max loss is always (width − credit) × lot, known the moment you enter.")}
{p("<b>9.</b> If <b>v1 and v0 both signal the same stock, take v1 only</b> — the engine already suppresses v0's, so you will see one signal.")}

<p style="color:{AMBER};font-size:15px;font-weight:bold;margin-top:14px;">THE EXPIRY-DAY BOOKS — NIFTY (Tue) and SENSEX (Thu)</p>
{p("<b>1.</b> Only on that index's expiry day. The engine posts a pre-market status strip by 9:00 telling you whether it expects a signal.")}
{p("<b>2.</b> At <b>09:16</b>, off the opening price: SELL the call about <b>0.5% out of the money</b>, BUY the call <b>200 points</b> further out.")}
{p("<b>3.</b> NIFTY skips the week when 5-day realised volatility is ≥ 0.9% — losses cluster when the tape is already hot. The engine applies this for you.")}
{p("<b>4.</b> <b>Hold to the 15:40 settlement</b> — or until the spread has given back <b>95%</b> of its credit, whichever comes first. No stop — the bought wing is the stop. Margin ≈ ₹14k/lot and that is also the worst case.")}
{p("<b>5.</b> Entry time is the edge: the opening theta and IV crush is what you are paid for. Entering at 11:00 or later turns it negative.")}

<p style="color:{GREEN};font-size:15px;font-weight:bold;margin-top:14px;">THE FOUR RULES BEHIND ALL OF IT</p>
{p("<b>• Sell premium, do not buy it.</b> Every long-premium structure tested here lost money in both eras.")}
{p("<b>• Only sell when the premium is rich.</b> credit ÷ width ≥ 0.40 IS the edge — it is a proxy for elevated post-breakout IV. Strip it and the same trade loses.")}
{p("<b>• Fade the breakout, never follow it.</b> The follow version wins ~40% of the time.")}
{p("<b>• Book early.</b> Taking 40–50% of the credit beats holding to expiry on every book measured.")}

<p style="color:{CYAN};font-size:17px;font-weight:bold;margin-top:18px;">LIVE STRATEGIES — 1 lot</p>
{dim("Both windows named in full. The first is the years each strategy was built on; the second is later years it had never "
     "seen, which is the one that decides. <b>Rupees are NOT in this table</b> — they are all in the PROFIT AND LOSS table "
     "below, worked out from these signal counts, so there is only ONE money figure in this tab.")}
<table cellpadding="6" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Strategy</td><td>Win · 1-Jan-2019 → 30-Sep-2024</td><td>Win · 1-Oct-2024 → 1-Aug-2026</td><td>Signals/mo</td></tr>
<tr><td>★ Stock v2 UNION <span style="color:{TEXT_DIM};">(TP-50, stop 3×)</span></td><td>84% · positive every year</td><td>87% · positive every year</td><td>~7.6 modelled · <b>~3.5 real</b></td></tr>
<tr><td>Stock v1 <span style="color:{TEXT_DIM};">(TP-40, no stop)</span></td><td>85% · positive every year</td><td>86% · positive every year</td><td>~16 modelled · <b>~12 real</b></td></tr>
<tr><td>Stock v0 <span style="color:{TEXT_DIM};">(c/w 0.35–0.40, TP-40, no stop)</span></td><td>77% · positive 4 of the 6 years</td><td>91% · positive every year</td><td>~5.8</td></tr>
<tr><td>Intraday NIFTY <span style="color:{TEXT_DIM};">(Tuesday expiry)</span></td><td>88% · positive 7 of the 8 years</td><td>90% · positive every year</td><td>~4</td></tr>
<tr><td>Intraday SENSEX <span style="color:{TEXT_DIM};">(Thursday expiry)</span></td><td style="color:{TEXT_DIM};">no window exists — SENSEX <b>weekly options only began Oct 2024</b>, so this strategy has no 2019–2024 history to test on</td><td>88.8% · since Oct 2024 (~2 yrs)</td><td>~4</td></tr>
<tr style="color:{TEXT_DIM};"><td>Index swing fade</td><td>worked on these years</td><td style="color:{RED};">FAILED — −1.4% of width</td><td>~2.5</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td><b>TOTAL</b></td><td></td><td></td><td><b>~29/mo</b></td></tr>
</table>

<p style="color:{CYAN};font-size:17px;font-weight:bold;margin-top:18px;">PROFIT AND LOSS — the only money table</p>
{dim("<b>Per TRADE vs per MONTH — this is where the confusion was.</b> Expectancy is what one trade is worth; multiply by "
     "signals per month to get monthly. An older figure of ₹20,000/mo for v2 assumed <b>7.6 signals a month, which is wrong</b> "
     "— v2 really fires about 3.5. That mismatch, not the rupees, is what made the two numbers disagree. This table uses "
     "MEASURED signal rates throughout, and it is now the only place rupees appear. <b>Signals measured</b> is how many "
     "real trades each row's win rate and averages rest on — read it as the confidence in that row: v1 at 871 is the "
     "solid one, NIFTY at 73 and SENSEX at 89 are thin.")}
<table cellpadding="5" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;font-size:13px;">
<tr style="color:{CYAN};font-weight:bold;"><td>Book</td><td>Signals<br>measured</td><td>Signals<br>/month</td><td>Win rate</td><td>Avg WIN</td><td>Avg LOSS</td><td>Expectancy per trade = win% × avg win − loss% × avg loss</td><td>× signals<br>= ₹/month</td></tr>
<tr><td>★ Stock v2 UNION</td><td>346</td><td>~3.5</td><td>83.2%</td><td style="color:{GREEN};">+₹13,219</td><td style="color:{RED};">−₹11,645</td><td>83.2% × ₹13,219 − 16.8% × ₹11,645 = ₹10,998 − ₹1,956 = <b style="color:{GREEN};">+₹9,042</b></td><td><b>₹31,646</b></td></tr>
<tr><td>Stock v1</td><td>871</td><td>~12</td><td>85.1%</td><td style="color:{GREEN};">+₹5,557</td><td style="color:{RED};">−₹7,571</td><td>85.1% × ₹5,557 − 14.9% × ₹7,571 = ₹4,729 − ₹1,128 = <b style="color:{GREEN};">+₹3,601</b></td><td><b>₹43,211</b></td></tr>
<tr><td>Stock v0 (0.35–0.40)</td><td>293</td><td>~5.8</td><td>76.5%</td><td style="color:{GREEN};">+₹3,986</td><td style="color:{RED};">−₹11,505</td><td>76.5% × ₹3,986 − 23.5% × ₹11,505 = ₹3,049 − ₹2,704 = <b style="color:{AMBER};">+₹346</b></td><td>₹2,005</td></tr>
<tr><td>Intraday NIFTY</td><td>73</td><td>~4</td><td>93.2%</td><td style="color:{GREEN};">+₹1,202</td><td style="color:{RED};">−₹6,274</td><td>93.2% × ₹1,202 − 6.8% × ₹6,274 = ₹1,120 − ₹427 = <b style="color:{GREEN};">+₹694</b></td><td>₹2,775</td></tr>
<tr><td>Intraday SENSEX</td><td>89</td><td>~4</td><td>88.8%</td><td style="color:{GREEN};">+₹1,427</td><td style="color:{RED};">−₹4,549</td><td>88.8% × ₹1,427 − 11.2% × ₹4,549 = ₹1,267 − ₹509 = <b style="color:{GREEN};">+₹758</b></td><td>₹3,031</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td><b>TOTAL</b></td><td><b>1,672</b></td><td><b>~29/mo</b></td><td></td><td></td><td></td><td></td><td><b>₹82,667</b></td></tr>
<tr style="color:{AMBER};font-weight:bold;"><td><b>Plan on 80%</b></td><td></td><td></td><td></td><td></td><td></td><td></td><td><b>₹66,134</b></td></tr>
</table>
{dim("<b>Sanity-check it against the only real datapoint.</b> July 2026 came in at <b>24 closed trades and ₹44,789</b> "
     "realised — below the ₹82,667 here, because live fired fewer trades than the signal rates assume, not because the "
     "per-trade numbers were wrong (v1 realised ₹2,737 a trade live against ₹3,601 modelled). Treat ₹66,134 as a ceiling "
     "and one live month as the floor. <b>Rupees use current lot sizes</b>, so they are what a trade is worth TODAY — the "
     "older ₹54,224 model was built on smaller historic lots and understates it. "
     "<b>Read the win:loss shape too:</b> every book except v2 loses more on a loser than it makes on a winner, which is "
     "normal for selling credit spreads and is why the win rate has to stay high. <b>v0 is the fragile one</b> — 76.5% win "
     "with a 0.3:1 payoff leaves only ₹346 a trade on 2019–2024, against ₹2,808 on 2024–2026; that gap is its weak "
     "in-sample leg. <b>Correction 1-Aug-2026:</b> v2 previously showed 4.2:1 here — wrong, a lot-mix artifact and "
     "impossible for a defined-risk spread. On a consistent basis it is 1.1:1.")}

<p style="color:{CYAN};font-size:17px;font-weight:bold;margin-top:18px;">THE WORK BEHIND THOSE NUMBERS</p>
{dim("How much was screened to arrive at each live book, and what a winning and a losing trade actually pay, in rupees at 1 lot. "
     "Sources, so every figure is traceable: <b>v2</b> and <b>v0</b> from their backtests on real Upstox fills Oct 2024 – Jul 2026; "
     "<b>v1</b> from its 14 CLOSED live paper trades (real fills, small sample); <b>NIFTY</b> from the 73-trade FLIP sample and "
     "<b>SENSEX</b> from the 89-expiry study, both with per-trade rupee P&amp;L. v2's 4.2:1 is unusual for a defined-risk spread — "
     "its winners landed on much larger-lot names than its losers in the pre-cap study, so read it as lot-mix, not as a better payoff.")}
<table cellpadding="6" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Book</td><td>Raw signals screened</td><td>Trades analysed</td><td>Win rate</td><td>Avg WIN</td><td>Avg LOSS</td><td>Win : loss size</td></tr>
<tr><td>★ Stock v2 UNION</td><td>32,852</td><td>346</td><td>84% / 87%</td><td>+₹13,219</td><td>−₹11,645</td><td>1.1 : 1</td></tr>
<tr><td>Stock v1</td><td>25,978</td><td>871</td><td>85% / 86%</td><td>+₹5,557</td><td>−₹7,571</td><td>0.7 : 1</td></tr>
<tr><td>Stock v0 (0.35–0.40)</td><td>36,873</td><td>293</td><td>77% / 91%</td><td>+₹3,986</td><td>−₹11,505</td><td>0.3 : 1</td></tr>
<tr><td>Intraday NIFTY</td><td>448 expiry days</td><td>448</td><td>88% / 90%</td><td>+₹1,202</td><td>−₹6,274</td><td>0.2 : 1</td></tr>
<tr><td>Intraday SENSEX</td><td>89 expiry days</td><td>89</td><td>88.8%</td><td>+₹1,427</td><td>−₹4,549</td><td>0.3 : 1</td></tr>
<tr style="color:{TEXT_DIM};"><td>Classic strategies (all rejected)</td><td>227,000 trades · 7 families</td><td>0 kept</td><td>up to 83.6%</td><td colspan="3">every one negative after costs — Connors RSI-2, Larry Williams, Turtle, Supertrend, VWAP reversion, gap plays, NR7. The 83.6% is the illusion demo: a high win rate with negative expectancy.</td></tr>
<tr style="color:{GREEN};font-weight:bold;"><td><b>TOTAL RESEARCH</b></td><td><b>~287,000 signals/trades</b></td><td><b>~2,500 analysed</b></td><td colspan="4"><b>56 written studies · 106 runnable scripts · 2019 → 2026</b></td></tr>
</table>
{dim("Read the win:loss column, not just the win rate. <b>v0 is the honest outlier</b> — it wins 90% of the time but its average winner "
     "(₹4,342) is smaller than its average loser (₹12,145), so it only works while the win rate holds. v2 wins less often and still earns "
     "far more per trade, because its winners roughly match its losers (1.1:1) while it wins 83% of the time. A high win rate with a bad payoff ratio is the exact illusion the "
     "227,000-trade sweep was run to expose: a 0.15%-target bot prints 83.6% win and still loses money.")}

<p style="color:{CYAN};font-size:17px;font-weight:bold;">REJECTED / OFF</p>
<table cellpadding="6" cellspacing="0" style="color:{TEXT};border-collapse:collapse;margin:6px 0;">
<tr style="color:{CYAN};font-weight:bold;"><td>Strategy</td><td>Status</td><td>Why</td></tr>
<tr style="color:{TEXT_DIM};"><td>Intraday BANKNIFTY</td><td style="color:{RED};">REJECTED 07-19</td><td>edge ≈ 0 (t=+0.10, CI spans 0) · studies/BANKNIFTY_0DTE_REJECTION.md</td></tr>
<tr style="color:{TEXT_DIM};"><td>Index swing fade (NIFTY/FINNIFTY)</td><td style="color:{RED};">REMOVED 07-24</td><td>failed on 2024–2026 data (−1.4%w) · regime-dependent</td></tr>
<tr style="color:{TEXT_DIM};"><td>Monthly futures (REV1-v2)</td><td>REGIME-OFF</td><td>needs ~₹15L · waits for NIFTY &gt; 200-DMA</td></tr>
<tr style="color:{TEXT_DIM};"><td>Monthly long-call</td><td>SHELVED 07-13</td><td>gap/luck-dependent, unreliable</td></tr>
<tr style="color:{TEXT_DIM};"><td>3-Family + ORB+VWAP option-buying</td><td>OFF</td><td>direction is real but does not survive option-buying costs</td></tr>
</table>
<p style="color:{CYAN};font-size:17px;font-weight:bold;margin-top:18px;">WHY THESE WORK — the results that survived</p>
{res("<b>The exit sets the win rate, not the signal.</b> v1, on the IDENTICAL trade list: hold-to-expiry 54% · TP-75/stop-2× 64% (2019–24) / 73.6% (2024–26) · <b>TP-40/no-stop 85.0% (2019–24) / 86.0% (2024–26)</b>. Nothing about the entry changed. The 2× stop was realising losses that recover. File: V1_WINRATE_SWEEP.md")}
{res("<b>The credit/width gate is the whole edge.</b> 629 real trades bucketed: c/w ≥ 0.40 → 86% win, +34% of width. 0.30–0.35 → 78% win but only +1.1%. Win rate barely falls below the gate; the MONEY collapses ~10×, because the payoff turns lopsided. Never loosen it. File: CW_BUCKET_ANALYSIS.md")}
{res("<b>Universe expansion worked.</b> Screened all 180 NSE F&amp;O underlyings → 13 names added (universe 100 → 113): 5.78 → 7.56 signals/mo, win 84.1 → 85.5%, net +25.7 → +27.6% of width. Additive, no dilution. File: UNIVERSE_EXPANSION.md")}
{res("<b>0DTE NIFTY calm filter.</b> Skip the week when 5-day realised vol ≥ 0.9%: win 85.0 → 87.8%, avg +3.2 → +4.0% of margin, max drawdown −₹23.9k → −₹17.3k. File: studies/README.md")}
{res("<b>0DTE entry time.</b> Swept 10 entry times across 92 weeklies: 09:16 gives 90.4% win and +₹49.5k/lot. Waiting until 10:00 buys ~4pp of win rate but gives away 35–45% of the profit — the opening IV crush IS the trade.")}
{res("<b>v0, the 0.35–0.40 band.</b> Dead at v2's exits, positive at TP-40/no-stop: 77% win over 2019–2024 (+ve 4 of those 6 yrs) · 91% over 2024–2026 (+ve every yr, 43 trades) · ₹2,808 net per lot per trade. The weakest evidence of any live book — it is here to build a live record. File: LOWCW_BAND_RESCUE.md §7")}

<p style="color:{RED};font-size:17px;font-weight:bold;margin-top:18px;">TESTED AND REJECTED — do not re-mine these</p>
{dim("• <b>Buying options / long gamma / straddles</b> — lose in both eras, every variant (33–34% win).")}
{dim("• <b>Following the breakout</b> instead of fading it — ~40% win.")}
{dim("• <b>Trading below c/w 0.40</b> without changing the exit — win rate holds, money does not.")}
{dim("• <b>Re-cutting the 0.30–0.40 band to width 1</b> — 87.8% win and +18.1% on margin over 2019–2024, 6 of 6 years, survived every in-regime guard, then died on 2024–2026 data (74.3% / +1.4%, worse than doing nothing). File: LOWCW_BAND_RESCUE.md")}
{dim("• <b>Index fade (NIFTY/FINNIFTY) direction gates</b> — 6 positive years in 2019–2024, then reversed on 2024–2026 data.")}
{dim("• <b>BANKNIFTY 0DTE</b> — edge ≈ 0 (t = +0.10, confidence interval spans zero).")}
{dim("• <b>Event/news avoidance for 0DTE</b> — RBI, Budget, FOMC, VIX, gaps, earnings: all tested, all cost money. This book is PAID for visible fear.")}
{dim("• <b>Classic strategies</b> (Connors RSI-2, Larry Williams, Turtle, Supertrend, VWAP reversion, gap plays) — 227k trades: nothing beats the credit books after costs. A 0.15%-target bot prints 83.6% win with NEGATIVE expectancy — win rate alone proves nothing.")}

<p style="color:{CYAN};font-size:15px;font-weight:bold;margin-top:18px;">FULL STUDIES — every backtest, script and result</p>
{p('<a href="https://github.com/tejasgjadhav/Institutional-Trader/tree/main/studies" '
   'style="color:#4fc3f7;">github.com/tejasgjadhav/Institutional-Trader/tree/main/studies</a>')}
{dim("Each claim on this tab names its file. The folder holds the write-ups plus the runnable scripts in studies/ndte/ — "
     "every number here can be reproduced from raw NSE bhavcopy and Upstox data.")}

<p style="color:{TEXT_DIM};margin-top:14px;font-size:11px;">
Every study above is reproducible from /studies on GitHub. Backtests are real but optimistic — live fills are the only honest judge.
Paper forward-test only. For educational use. Not financial advice.
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
   "every 5 min in market hours, fires signals, resolves trades, books at the 15:40 derivatives close, and saves "
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
{p(f"<b>The daily credit-spread flow (v2 / v1 / v0 / swing):</b> "
   f"<b>{C.WATCHLIST_AFTER}</b> watchlist preview on this screen (names ~70% settled, strikes provisional — the "
   f"auction is still running) → <b>{getattr(C, 'WATCHLIST_DIGEST_AT', '15:31')}</b> Telegram digest with FINAL "
   f"strikes and live option prices (the auction close is struck by then — pre-stage from this) → "
   f"<b>{C.STOCK_CREDIT_SCAN_AFTER}</b> the scan fires on TODAY'S OFFICIAL CLOSE → place by <b>{C.FNO_CLOSE}</b> "
   f"(derivatives close) → settles {C.SETTLE_AFTER}.")}
{p(f"<b>Every signal shows the price it was computed on</b> (SIGNAL→LIVE on the watchlist, UNDERLYING on PM "
   "DECISIONS). 'AUC' means that price IS the closing-auction price — the official close, the exact field the "
   "2019–2026 backtests used. A red gap between signal and live price means the market has left the signal behind: "
   "ask before placing. This exists because for six weeks the scan silently read the PREVIOUS day's close "
   "(studies/STALE_BAR_INCIDENT.md); now a stale price refuses to fire and a wrong-direction signal is suppressed.")}
{p(f"<b>Intraday 0DTE:</b> entry 09:16 on expiry days, settles {C.SETTLE_AFTER} or earlier at 95% of max profit · "
   f"<b>Monthly futures pullback:</b> once per expiry cycle, ~{C.MONTHLY_FUT_SCAN_AFTER} on the first trading day "
   "after the monthly expiry, only when NIFTY &gt; its 200DMA. Signals are selective — many days few or none; "
   "that's the point, not a fault.")}

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
            if _os.path.exists(STOCKV0_SNAP):
                s3 = json.load(open(STOCKV0_SNAP))
                self._stockv0_rows = s3.get("rows", []) or []
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

    def _timings_label(self) -> QLabel:
        """A SIGNAL TIMINGS strip. Every time comes from engine.config, never a literal — the whole
        15:10->15:36 bug class this session was bare literals drifting out of sync with the engine."""
        lb = QLabel("—"); lb.setWordWrap(True); lb.setFont(QFont("Menlo", 11))
        lb.setStyleSheet(f"color:{TEXT_DIM}; padding:6px 8px; background-color:{PANEL}; "
                         f"border:1px solid {BORDER};")
        return lb

    def _update_timings(self):
        """Refresh both SIGNAL TIMINGS strips, highlighting the step the clock is in right now."""
        from engine import config as C
        now = datetime.now(IST); m = now.hour * 60 + now.minute
        def mins(hhmm):
            h, mm = map(int, hhmm.split(":")); return h * 60 + mm
        def strip(steps):
            # steps = [(start_min, end_min_or_None, "time", "what happens"), ...]
            out = []
            for st, en, tm, what in steps:
                live = st <= m and (en is None or m <= en)
                if live:
                    out.append(f'<span style="color:{CYAN};"><b>&#9654; {tm} {what}</b></span>')
                else:
                    out.append(f'<span style="color:{TEXT_DIM};">{tm} {what}</span>')
            return "&nbsp;&nbsp;<b>SIGNAL TIMINGS</b> &nbsp; " + \
                   f'<span style="color:{BORDER};"> &#8594; </span>'.join(out)

        wl, scan = C.WATCHLIST_AFTER, C.STOCK_CREDIT_SCAN_AFTER
        dg = getattr(C, "WATCHLIST_DIGEST_AT", "15:31")
        close, settle = C.FNO_CLOSE, C.SETTLE_AFTER
        if hasattr(self, "pm_timings"):
            self.pm_timings.setText(strip([
                (mins(C.MARKET_OPEN), mins(wl) - 1, C.MARKET_OPEN, "market opens"),
                (mins(wl), mins(dg) - 1, wl, "WATCHLIST (UI)"),
                (mins(dg), mins(scan) - 1, dg, "digest &#183; FINAL strikes + prices"),
                (mins(scan), mins(close), f"{scan}-{close}",
                 "SIGNALS fire &#183; v2 / v1 / v0 / swing &#183; PLACE the order"),
                (mins(settle), 24 * 60, settle, "settle &#183; WIN/LOSS + Telegram"),
            ]))
        if hasattr(self, "zdte_timings"):
            frac = getattr(C, "ZERO_DTE_EARLY_CLOSE_FRAC", 0) or 0
            early = f"close early at {frac:.0%} of max profit" if frac else "hold to expiry"
            self.zdte_timings.setText(strip([
                (0, mins("09:15"), "09:00", "pre-market status posted"),
                (mins("09:16"), mins("09:20"), "09:16", "ENTRY &#183; spread sold at the open"),
                (mins("09:20"), mins(settle) - 1, "all day", f"live tracking &#183; {early}"),
                (mins(settle), 24 * 60, settle, "settle &#183; WIN/LOSS + Telegram"),
            ]))

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
        elif m < 15 * 60 + 17:
            txt, col = ("● Market open. On expiry days the intraday spread posts right after the 09:16 open; "
                        "the CREDIT books — ★v2 + v1 + v0 + index swing — all scan at ~15:36, after the "
                        "closing auction.", GREEN)
        elif m < 15 * 60 + 36:
            txt, col = ("● UNION WATCHLIST is up (built 15:17) — these are the likely candidates. Closing "
                        "auction runs to 15:35; signals fire at 15:36. Pre-stage now, do not place yet.", AMBER)
        elif m <= 15 * 60 + 40:
            txt, col = ("● NOW: CREDIT SCAN IS IN — check ★ STOCK CREDIT v2 (gold) first, then v1 + v0 + INDEX "
                        "SWING. Derivatives close 15:40, so this is the whole placement window. Use limit "
                        "orders — spreads are ~2× wider here than mid-session.", CYAN)
        else:
            txt, col = "Market closed — today's signals are booked. Next session tomorrow ~09:15.", TEXT_DIM
        self.pm_now_hint.setText("  " + txt)
        self.pm_now_hint.setStyleSheet(f"color:{col}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")

    def _size_watch_cols(self):
        """Distribute the table's REAL viewport width across the columns by weight.

        Fixed pixel widths cannot work here: the horizontal scrollbar is off (single-screen rule),
        so Qt compresses any total wider than the viewport and the fixed values are ignored. Sizing
        from the measured viewport instead means the row always fits exactly and nothing truncates,
        whatever the window size."""
        try:
            w = self.pm_watch.viewport().width()
            if w < 200:
                return
            tot = sum(self._watch_weights)
            acc = 0
            for c, wt in enumerate(self._watch_weights[:-1]):
                px = int(w * wt / tot)
                self.pm_watch.setColumnWidth(c, px); acc += px
            self.pm_watch.setColumnWidth(len(self._watch_weights) - 1, max(40, w - acc))
        except Exception:
            pass

    def _refresh_union_watch(self):
        """Populate the always-on UNION WATCHLIST panel from data/union_watchlist.json (breakout
        stocks only, each with a per-gate tick-bar). Read-only; failures never disturb the UI."""
        import json as _json
        from engine import config as C   # times READ config — a hardcoded '3:05 PM' outlived two retimings here
        try:
            path = _os.path.join(DATA_DIR, "union_watchlist.json")
            if not _os.path.exists(path):
                self.pm_watch_hdr.setText(f"UNION WATCHLIST — no scan yet today (engine builds it at {C.WATCHLIST_AFTER}, once the auction has struck the close)")
                self.pm_watch.setRowCount(0); return
            d = _json.load(open(path)); rows = d.get("rows", []); ts = d.get("ts", "")
            # clear a stale (prior-day) watchlist — only ever show TODAY's scan
            if not ts.startswith(datetime.now(IST).date().isoformat()):
                self.pm_watch_hdr.setText(f"UNION WATCHLIST — no scan yet today (engine builds it at {C.WATCHLIST_AFTER}, once the auction has struck the close)")
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
                    # tick/cross only (user, 2026-08-12): the rupee value was never read and the
                    # width is better spent on BRK and MAX. The gate itself is what matters here.
                    premcell = "✓" if row.get("prem_ok") else "✗"
                    liqcell = "✓" if row.get("liq_ok") else f"✗ OI{oi}"
                result = "★ SIGNAL" if g == "PASS" else ("blocked" if evaluable else g.replace("_", " ").lower())
                # legs instead of a redundant breakout tick (every row IS a breakout)
                fmtk = lambda x: ("%g" % x) if isinstance(x, (int, float)) else None
                ss, ls = fmtk(row.get("short_strike")), fmtk(row.get("long_strike"))
                verb = "CE" if "CALL" in str(row.get("side", "")) else "PE"
                legs = f"SELL {ss} {verb} / BUY {ls} {verb}" if ss and ls else "—"
                sd = row.get("side", "")
                # "BEAR"/"BULL" alone never said CALL or PUT, and the SELL/BUY cell carried the
                # CE/PE only once at the end (user, 2026-08-11). Spell the structure out.
                side_s = ("BEAR CALL" if "CALL" in sd else
                          "BULL PUT" if "PUT" in sd else (sd or "—"))
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
                # SIGNAL price vs LIVE price. They should be close; a wide gap means the signal was
                # computed on a price the market has left behind — the GRASIM failure, made visible.
                _sig, _liv, _gap = row.get("signal_px"), row.get("live_px"), row.get("px_gap_pct")
                # "AUC" = the signal price IS the closing-auction price, i.e. the official EOD
                # close for an F&O stock and the exact field the backtests use. Anything else is a
                # provisional intraday print and the official close does not exist yet.
                # ONE value in the UI (user, 2026-08-12) — the latest price, plus AUC when it is
                # the auction close. The BACKEND still records signal_px, signal_src, live_px and
                # px_gap_pct unchanged; only this rendering collapses, and the cell is still tinted
                # amber/red by the gap so a stale signal is visible without the arrow.
                _tag = " AUC" if row.get("signal_auction") else ""
                _show = _liv if isinstance(_liv, (int, float)) else _sig
                sig_s = f"{_show:,.0f}{_tag}" if isinstance(_show, (int, float)) else "—"
                _cr = row.get("credit")
                crcell = f"₹{_cr:.1f}" if isinstance(_cr, (int, float)) else "—"
                mx = (f"+{_mp:,}/−{abs(_ml):,}" if isinstance(_mp, (int, float))
                      and isinstance(_ml, (int, float)) else "—")
                vals = [row.get("sym", "—"), side_s, f"D{row.get('dc','')}", sig_s,
                        legs, exp_s, lot_s, cwcell, crcell, premcell, liqcell, mx, result]
                self._set_row(self.pm_watch, i, vals)
                self._color_cell(self.pm_watch, i, 12, GREEN if g == "PASS" else (AMBER if evaluable else RED))
                if isinstance(_gap, (int, float)):
                    self._color_cell(self.pm_watch, i, 3,
                                     RED if abs(_gap) >= 1.0 else (AMBER if abs(_gap) >= 0.5 else TEXT_DIM))
                for c in (2, 3, 5, 6, 7, 8, 9, 10, 11, 12):   # centre everything except STOCK/SIDE/legs
                    it = self.pm_watch.item(i, c)
                    if it: it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            logger.warning(f"union watch refresh: {e}")

    def _refresh_pm(self):
        self._update_pm_now_hint()
        self._update_timings()
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
        if hasattr(self, "pm_stockv0"):
            self._fill_pm_credit(self.pm_stockv0, list(self._stockv0_rows or []), "stock")

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
                          "monthly expiry (NIFTY>200DMA), scan ~15:36", "—", "—", "—", "—", "—", "WATCHING"],
                          fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            if status in ("REGIME_OFF", "NO_CANDIDATES"):
                self._set_row(table, i, ["—", p.get("order_label", ""), "—", "—", "—",
                                          p.get("expiry", "—"), "—", status], fg=QColor(TEXT_DIM))
                continue
            pnl = p.get("pnl_pct")
            pnl_s = f"{pnl:+.2f}%" if pnl is not None else "—"
            stat_s = status if status == "OPEN" else f"{status} {pnl_s} ({p.get('reason','')})"
            entry = p.get("entry_px")
            cur = p.get("cur_px")
            prem = f"in {entry} now {cur}" if entry and cur else (f"{entry}" if entry else "—")
            vals = ["BUY FUT", p.get("order_label", p.get("symbol", "—")), "—", "1 lot",
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
                          "monthly expiry (NIFTY>200DMA), scan ~15:36", "—", "—", "—", "—", "—", "WATCHING"],
                          fg=QColor(TEXT_DIM))
            self._fit_table(table); return
        table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            status = p.get("status", "OPEN")
            if status in ("REGIME_OFF", "NO_CANDIDATES"):
                self._set_row(table, i, ["—", p.get("order_label", ""), "—", "—", "—",
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
        hint = ("no swing signal today — fires on a daily index breakout (fade), scan ~15:36"
                if kind == "index"
                else "no signal today — fires on a stock breakout w/ rich credit (≥0.40), scan ~15:36")
        if not rows:
            table.setRowCount(1)
            self._set_row(table, 0, ["—", hint, "—", "—", "—", "—", "—", "WATCHING"], fg=QColor(TEXT_DIM))
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
            # SIGNAL price -> LIVE price for the underlying. A wide gap means the breakout was read
            # off a price the market has since left behind (the GRASIM failure), so it is shown on
            # the trade itself rather than only in the log.
            _sig = p.get("signal_px"); _liv = None
            try:
                from engine.data_utils import todays_close as _tc
                # STOCKS ONLY. Index books (0DTE NIFTY/SENSEX, swing) carry the index under
                # "symbol" too, and "NIFTY.NS" has no NSE_EQ instrument key — the lookup failed and
                # spammed ~430 warnings/minute from the GUI thread (found 5-Aug). Checking
                # p["index"] was not enough; gate on membership of the stock UNIVERSE instead,
                # which is the only set of names that can resolve. Index rows fall back to the
                # entry spot below.
                from engine.config import UNIVERSE as _UNI
                _nm = p.get("symbol") or ""
                if _nm and f"{_nm}.NS" in _UNI:
                    _liv = _tc(_nm + ".NS")[0]
            except Exception:
                pass
            if isinstance(_sig, (int, float)) and isinstance(_liv, (int, float)) and _sig:
                _gp = (_liv - _sig) / _sig * 100
                und_s = f"{_sig:,.0f}→{_liv:,.0f} ({_gp:+.1f}%)"
            elif isinstance(_sig, (int, float)):
                und_s = f"sig {_sig:,.0f}"
            else:
                und_s = f"entry {p.get('entry_spot'):,.0f}" if p.get("entry_spot") else "—"
            rS, rB = 2 * i, 2 * i + 1
            # ACTION carries the option TYPE (CE/PE) so it's never truncated by a long stock name.
            # Row 1 — SELL the near leg (collect premium)
            self._set_row(table, rS,
                          [f"SELL {verb}", f"{name} {p.get('short_strike','—')}", und_s, lot_str, sp_s, exp,
                           f"credit Rs {credit*qty:,.0f}", status], fg=QColor(RED))
            # Row 2 — BUY the far leg (the hedge) — AMOUNT here = total MARGIN required (= max loss)
            self._set_row(table, rB,
                          [f"BUY {verb}", f"{name} {p.get('long_strike','—')}  (hedge)", "", lot_str, lp_s, exp,
                           f"margin Rs {cap:,.0f}", pnl], fg=QColor(GREEN))
            self._color_cell(table, rS, 7, self._status_color(status))     # STATUS on the SELL row
            if isinstance(_sig, (int, float)) and isinstance(_liv, (int, float)) and _sig:
                _g = abs((_liv - _sig) / _sig * 100)
                self._color_cell(table, rS, 2, QColor(RED) if _g >= 1.0 else
                                 QColor(AMBER) if _g >= 0.5 else QColor(TEXT_DIM))
            if pnl != "—":
                self._color_cell(table, rB, 7, QColor(GREEN) if pnl_pts > 0 else
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
            self._fill_swing_table(self.sw_stk2, STOCKCR2_BOOK, self.sw_stk2_stats, book_label="v2")
            if hasattr(self, "sw_v0"):
                self._fill_swing_table(self.sw_v0, STOCKV0_BOOK, self.sw_v0_stats, book_label="T2")
            self._fill_swing_table(self.sw_idx, SWING_BOOK, self.sw_idx_stats)
            self._fill_swing_table(self.sw_stk, STOCKCR_BOOK, self.sw_stk_stats, book_label="v1")
        except Exception as e:
            logger.warning(f"swing tab fill: {e}")

    def _fill_swing_table(self, table, book_path, stats_label=None, open_only=False, book_label=None):
        """One credit-spread trade log: each row spells out the SELL leg and BUY leg (strike +
        premium), expiry, net credit (total Rs), live/booked cost, P&L and status. Newest first.
        open_only=True → show ONLY still-open or entered-today rows (the INTRADAY 'live' view);
        settled history then lives in the TRADE LOG tab.
        book_label ('v1'/'v2') → the table has the extra BOOK column (SWING_TAB_BOOK_COLS)."""
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
            # each P&L figure carries ITS OWN sign colour — a green line with a red MTM inside it
            # was being read as "everything is profit" (user report 2026-07-30)
            def rs(x):
                c = GREEN if x > 0 else RED if x < 0 else TEXT_DIM
                return f"<span style='color:{c};'>Rs {x:+,.0f}</span>"
            stats_label.setText(
                f"  TRADES {n} · OPEN {len(opens)} · W {wins} L {losses} · WIN {wr:.0f}% "
                f"· margin Rs {margin_now:,.0f} · booked {rs(booked)} · MTM {rs(live)}")
            stats_label.setStyleSheet(
                f"color:{TEXT}; padding:8px; background-color:{PANEL}; border:1px solid {BORDER};")
        # open positions first, then newest closed
        book = sorted(book, key=lambda p: (p.get("status") != "OPEN", p.get("entry_date") or ""), reverse=False)
        book = sorted(book, key=lambda p: (p.get("status") == "OPEN", p.get("entry_date") or ""), reverse=True)
        rows = book[:40]
        if not rows:
            if stats_label is not None:
                stats_label.setText("  no trades yet — stats will populate after the first signal")
            table.setRowCount(1)
            empty = ["—", "—", "no trades yet — fires on a breakout with rich credit",
                     "—", "—", "—", "—", "WATCHING"]
            if book_label:
                empty.insert(1, book_label)
            self._set_row(table, 0, empty, fg=QColor(TEXT_DIM))
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
            sell_vals = [p.get("entry_date", "—"), f"① SELL {verb}", f"{name} {p.get('short_strike','—')}",
                         lot_str, price(sp), price(sc), money(sell_pnl), status]
            # Row 2 — BUY leg (the hedge) + the consolidated NET for the whole spread
            net_txt = f"NET {money(net_rs)}" + (f" ({net_pct:+.0f}%)" if net_pct is not None else "")
            buy_vals = [f"exp {p.get('expiry','—')}", f"② BUY {verb}", f"{name} {p.get('long_strike','—')}",
                        lot_str, price(lp), price(lc), money(buy_pnl), net_txt]
            off = 0
            if book_label:                       # BOOK column sits after ENTERED, on both leg rows
                sell_vals.insert(1, book_label); buy_vals.insert(1, book_label); off = 1
            self._set_row(table, rS, sell_vals, fg=QColor(RED))
            self._set_row(table, rB, buy_vals, fg=QColor(GREEN))
            # colors: status on SELL row, per-leg P&L + NET tinted by sign
            self._color_cell(table, rS, 7 + off, self._status_color(status))
            if sell_pnl is not None:
                self._color_cell(table, rS, 6 + off, QColor(GREEN) if sell_pnl > 0 else QColor(RED) if sell_pnl < 0 else QColor(TEXT_DIM))
            if buy_pnl is not None:
                self._color_cell(table, rB, 6 + off, QColor(GREEN) if buy_pnl > 0 else QColor(RED) if buy_pnl < 0 else QColor(TEXT_DIM))
            self._color_cell(table, rB, 7 + off, QColor(GREEN) if net_rs > 0 else QColor(RED) if net_rs < 0 else QColor(TEXT_DIM))
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
        if d.get("sensex"):   # older snapshot files lack it until the engine restarts
            self._set_ticker(self.sensex_lbl, "SENSEX", d["sensex"])
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
        lbl.setText(f"{name}  {d['price']:,.2f}  {arrow} {pct:+.2f}%")
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
            self.mode_label.setText(f"{mlbl}  -  engine runs 9:00-15:40 Mon-Fri (F&O close moved to 15:40 on 3-Aug-2026)")
            self.mode_label.setStyleSheet(f"color:{GREEN if is_open else AMBER};")
        self.status.showMessage(
            f"  {now:%a %d %b %Y · %H:%M:%S} IST   ·   MARKET {mkt}   ·   MODE {mode}   ·   "
            f"scanned {len(self.last_scan_results)}   ·   "
            f"ready {sum(1 for s in self.last_scan_results if s.get('trade_ready'))}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationDisplayName("SAAVI INSTITUTIONAL TRADER")
    if _os.path.exists(LOGO_PATH):
        app.setWindowIcon(QIcon(LOGO_PATH))   # macOS Dock icon
    win = TerminalApp()
    win.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
