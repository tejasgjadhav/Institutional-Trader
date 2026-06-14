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
    QHeaderView, QStackedWidget, QTextEdit, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QBrush

from engine.config import IST
from engine.agent import Agent
from engine.trade_log import TradeLog
from engine.data_utils import (
    get_nifty_close, get_banknifty_close, get_vix_close,
    check_api_health, get_last_5_trading_days
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


class MarketDataWorker(QThread):
    """Fetch index data off the UI thread."""
    data_ready = Signal(dict)

    def run(self):
        try:
            self.data_ready.emit({
                "nifty": get_nifty_close(),
                "banknifty": get_banknifty_close(),
                "vix": get_vix_close(),
            })
        except Exception as e:
            logger.warning(f"Market data worker failed: {e}")


class TerminalApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("INSTITUTIONAL TRADER · TERMINAL")
        self.setGeometry(40, 40, 1700, 1000)
        self.setStyleSheet(self._qss())

        self.agent = Agent()
        self.trade_log = TradeLog()
        self.last_scan_results = []
        self.active_screen = 0
        self._mkt_running = False

        self._check_recording_window()
        self._build_ui()
        self._refresh_market_data()
        self._check_apis()
        self.trigger_scan()

        # timers
        self.scan_timer = QTimer(); self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(300_000)  # 5 min
        self.clock_timer = QTimer(); self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(1000)
        # Market data: poll fast (2s) when open, slow (20s) when closed.
        self.mkt_timer = QTimer(); self.mkt_timer.timeout.connect(self._refresh_market_data)
        self.mkt_timer.start(2000)

    # ── recording window ──────────────────────────────────────────────────────
    def _check_recording_window(self):
        last5 = get_last_5_trading_days()
        self.recording_mode = datetime.now().date() in last5
        self.last5 = last5

    # ── stylesheet ────────────────────────────────────────────────────────────
    def _qss(self) -> str:
        return f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {TEXT};
    font-family: 'Menlo','Monaco','Courier New',monospace; }}
QLabel {{ color: {TEXT}; }}
QTableWidget {{ background-color: {PANEL}; alternate-background-color: {PANEL_LIGHT};
    border: 1px solid {BORDER}; gridline-color: {BORDER}; color: {TEXT};
    selection-background-color: {BORDER}; }}
QTableWidget::item {{ padding: 4px; border: none; }}
QHeaderView::section {{ background-color: {PANEL_LIGHT}; color: {GREEN};
    padding: 6px; border: none; border-bottom: 1px solid {BORDER};
    font-weight: bold; letter-spacing: 1px; }}
QTableCornerButton::section {{ background-color: {PANEL_LIGHT}; border: none; }}
QStatusBar {{ background-color: {PANEL}; color: {TEXT_DIM};
    border-top: 1px solid {BORDER}; }}
QTextEdit {{ background-color: {PANEL}; color: {TEXT};
    border: 1px solid {BORDER}; }}
QScrollBar:vertical {{ background: {PANEL}; width: 10px; }}
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
        self.stack.addWidget(self._screen_readme())     # 4
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

        sub = QLabel("3-FAMILY ALPHA · NSE INTRADAY")
        sub.setFont(QFont("Menlo", 9)); sub.setStyleSheet(f"color:{TEXT_DIM};")
        h.addWidget(sub); h.addSpacing(20); h.addStretch()

        mode = "● RECORDING" if self.recording_mode else "○ OBSERVATION"
        mode_color = GREEN if self.recording_mode else AMBER
        self.mode_label = QLabel(f"{mode}  ·  SIMULATION")
        self.mode_label.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        self.mode_label.setStyleSheet(f"color:{mode_color};")
        h.addWidget(self.mode_label)
        return w

    def _market_bar(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background-color:{BG}; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(w); h.setContentsMargins(16, 8, 16, 8); h.setSpacing(26)

        self.nifty_lbl = self._ticker_label("NIFTY 50", "—")
        self.bnf_lbl   = self._ticker_label("BANKNIFTY", "—")
        self.vix_lbl   = self._ticker_label("INDIA VIX", "—", AMBER)
        for lbl in (self.nifty_lbl, self.bnf_lbl, self.vix_lbl):
            h.addWidget(lbl)
        h.addStretch()

        self.api_lbl = QLabel("API ···")
        self.api_lbl.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        self.api_lbl.setStyleSheet(f"color:{TEXT_DIM};")
        h.addWidget(self.api_lbl)
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
        tabs = [("PM DECISIONS", 0), ("WATCHLIST", 1), ("ALPHA", 2), ("TRADE LOG", 3), ("README", 4)]
        for label, idx in tabs:
            b = QPushButton(label)
            b.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            b.setMinimumHeight(38); b.setMinimumWidth(150)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.switch(i))
            self.tab_btns.append(b); h.addWidget(b)
        h.addStretch()

        self.scan_btn = QPushButton("⟳ SCAN")
        self.scan_btn.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        self.scan_btn.setMinimumHeight(38); self.scan_btn.setMinimumWidth(110)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.trigger_scan)
        h.addWidget(self.scan_btn)
        self._style_scan_idle()
        return w

    def _style_scan_idle(self):
        self.scan_btn.setStyleSheet(
            f"QPushButton{{background-color:{PANEL_LIGHT};color:{GREEN};"
            f"border:1px solid {GREEN};border-radius:3px;}}"
            f"QPushButton:hover{{background-color:{GREEN};color:{BG};}}")

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
        l = QLabel(text); l.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{color}; padding:10px 4px; letter-spacing:1px;")
        return l

    def _screen_pm(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("▸ LATEST PM DECISIONS   —   trade-ready signals (place manually in Upstox)", AMBER))
        self.pm_table = QTableWidget()
        self.pm_table.setColumnCount(10)
        self.pm_table.setHorizontalHeaderLabels(
            ["TIME", "ORDER (BUY)", "STRIKE", "EXPIRY", "PREMIUM", "TARGET +10%", "STOP -20%", "LOT", "CAPITAL", "STATUS"])
        self.pm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pm_table.setAlternatingRowColors(True)
        self.pm_table.verticalHeader().setVisible(False)
        v.addWidget(self.pm_table)

        self.pm_empty = QLabel("No trade-ready signals. Market scan runs every 5 min · 09:15–15:30 IST.")
        self.pm_empty.setStyleSheet(f"color:{TEXT_DIM}; padding:8px 4px;")
        self.pm_empty.setFont(QFont("Menlo", 10))
        v.addWidget(self.pm_empty)
        return w

    def _screen_watchlist(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("▸ WATCHLIST   —   passed Gate 1 (alpha), awaiting ORB breakout"))
        self.wl_table = QTableWidget()
        self.wl_table.setColumnCount(6)
        self.wl_table.setHorizontalHeaderLabels(["TICKER", "ALPHA-Z", "DIR", "BREADTH", "TREND", "FLOW"])
        self.wl_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.wl_table.setAlternatingRowColors(True)
        self.wl_table.verticalHeader().setVisible(False)
        v.addWidget(self.wl_table)
        return w

    def _screen_alpha(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("▸ ALPHA   —   all 95 stocks scored by 3-family system"))
        self.alpha_table = QTableWidget()
        self.alpha_table.setColumnCount(7)
        self.alpha_table.setHorizontalHeaderLabels(["TICKER", "ALPHA-Z", "DIR", "BREADTH", "TREND", "FLOW", "EVENT"])
        self.alpha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alpha_table.setAlternatingRowColors(True)
        self.alpha_table.verticalHeader().setVisible(False)
        v.addWidget(self.alpha_table)
        return w

    def _screen_log(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("▸ TRADE LOG   —   paper trades + statistics"))
        self.log_stats = QLabel("—")
        self.log_stats.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.log_stats.setStyleSheet(f"color:{CYAN}; padding:6px 4px; background-color:{PANEL}; border:1px solid {BORDER};")
        v.addWidget(self.log_stats)
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(8)
        self.log_table.setHorizontalHeaderLabels(["TIME", "TICKER", "DIR", "ENTRY", "STOP", "TARGET", "OUTCOME", "P&L"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        v.addWidget(self.log_table)
        return w

    def _screen_readme(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(12, 4, 12, 12)
        v.addWidget(self._panel_title("▸ README   —   how this system trades, in plain language"))
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
{dim("A disciplined paper-trading framework. It scans NIFTY, BANKNIFTY and 95 NSE stocks all day, "
     "scores each one, and only flags a trade when it clears two strict gates. You place every "
     "order yourself in Upstox — the system never sends orders. It is a process for collecting "
     "honest evidence, not a proven money-maker.")}

{p(f"<b>Current mode:</b> SIMULATION (paper) · <b>OPTIONS-ONLY, BUY-ONLY</b>. <b>Recording:</b> {rec}.")}
{p(f"<b style='color:{AMBER}'>Status:</b> Best backtest = +{int(C.PREMIUM_TARGET_PCT)}%/−{int(C.PREMIUM_STOP_PCT)}% "
   f"premium exit → 77% win rate (recent 20 days, 13 trades — promising but UNPROVEN; "
   f"needs 30+ forward sessions to confirm after costs).")}

{h("1 · WHAT IT DOES (in one breath)")}
{p("Every 5 minutes during market hours it: (1) pulls fresh prices from Upstox, "
   "(2) gives each stock a single score called <b>alpha-z</b>, (3) checks if the score is strong "
   "and broad enough (Gate 1), (4) checks if the price is actually breaking out right now (Gate 2). "
   "If both gates pass, the stock appears on <b>PM DECISIONS</b> with exact entry, stop, target and quantity.")}

{h("2 · THE DAILY CLOCK (all times IST)")}
{p(f"<b>08:55</b> &nbsp; Mac wakes up automatically")}
{p(f"<b>09:00</b> &nbsp; App auto-launches")}
{p(f"<b>{C.MARKET_OPEN}</b> &nbsp; Market opens — scanning begins, ALPHA + WATCHLIST fill up")}
{p(f"<b>09:15–{C.TRADING_START}</b> &nbsp; First 30 min is the wildest part of the day — we only watch, no trades")}
{p(f"<b>{C.TRADING_START}</b> &nbsp; Trading window opens — confirmed signals become real PM DECISIONS")}
{p(f"<b>every 5 min</b> &nbsp; Re-scan NIFTY + BANKNIFTY + 95 stocks (parallel, batched, cached — a few sec); one new trade per scan")}
{p(f"<b>{C.NO_NEW_TRADES_AFTER}</b> &nbsp; No new trades after this (afternoon is thin)")}
{p(f"<b>{C.KILL_SWITCH_TIME}</b> &nbsp; Kill switch — every open position is force-closed")}
{p(f"<b>{C.MARKET_CLOSE}</b> &nbsp; Market closes — trade log shows the day's wins/losses")}
{p(f"<b>{C.BACKTEST_REFRESH_TIME}</b> &nbsp; Re-rank the tradeable universe on the latest {C.BACKTEST_LOOKBACK_DAYS}-day history")}

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
   "momentum + trend quality + opening-range microstructure")}
{p(f"<b style='color:{CYAN}'>FLOW</b> &nbsp;(weight {C.FAMILY_WEIGHTS['FLOW']['weight']}) — what are big players doing? "
   "options positioning (PCR / max-pain) + market regime (Nifty, VIX)")}
{p(f"<b style='color:{AMBER}'>EVENT</b> &nbsp;(weight {C.FAMILY_WEIGHTS['EVENT']['weight']}) — any news driving it? "
   "headlines + live NSE filings  (experimental — can't be backtested on free data)")}
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

{h("6 · THE TWO GATES")}
{sub("GATE 1 — Alpha Gate (strong enough + broad enough?)")}
{p(f"• |alpha-z| strictly greater than <b>{C.ALPHA_Z_THRESHOLD}</b>")}
{p(f"• at least <b>{C.MIN_FAMILIES_AGREE} of 3</b> families agree on direction")}
{p(f"• the stock is in the proven universe (top {C.TOP_N_TRADEABLE} by expectancy)")}
{dim("Passing Gate 1 puts the stock on the WATCHLIST, 'awaiting ORB breakout'.")}
{sub("GATE 2 — ORB Breakout + Volume (is the move happening NOW?)")}
{p("The latest 5-min candle must close beyond the opening-range (above the high for a LONG, "
   "below the low for a SHORT) with a volume surge. This is a second, independent method — "
   "two different techniques must agree before money is risked.")}
{p("When both gates pass, the stock moves to <b>PM DECISIONS</b>.")}

{h("7 · WHICH INSTRUMENT — BUY OPTIONS ONLY")}
{p("Every signal becomes a <b>bought option</b> (never sold): "
   "<b style='color:{0}'>LONG → buy ATM CALL</b>, <b style='color:{1}'>SHORT → buy ATM PUT</b>.".format(GREEN, RED))}
{p("The PM DECISIONS screen shows the exact order: strike, expiry, live premium, target/stop "
   "premium, lot size and capital — e.g. <b>BUY NIFTY 23600 CE 16-Jun @ Rs179</b> · tgt Rs197 · "
   "stop Rs143 · cap Rs11,654.")}
{dim(f"Strike = at-the-money from the live NSE chain · nearest expiry (Nifty weekly, BankNifty/stocks "
     f"monthly) · skip if ATM IV > {C.OPTION_IV_THRESHOLD} (premium too expensive). "
     f"Indices keep capital low: Nifty ~Rs12k/lot, BankNifty ~Rs28k/lot.")}

{h("8 · EXIT — ON THE OPTION PREMIUM (2:1 is NOT how options win)")}
{p(f"You exit on the option's own price, not the stock:")}
{p(f"• <b style='color:{GREEN}'>BOOK</b> at premium <b>+{C.PREMIUM_TARGET_PCT:.0f}%</b> &nbsp;(e.g. Rs100 → Rs{100*(1+C.PREMIUM_TARGET_PCT/100):.0f})")}
{p(f"• <b style='color:{RED}'>CUT</b> at premium <b>−{C.PREMIUM_STOP_PCT:.0f}%</b> &nbsp;(e.g. Rs100 → Rs{100*(1-C.PREMIUM_STOP_PCT/100):.0f})")}
{p(f"• <b>FORCE-CLOSE</b> at {C.KILL_SWITCH_TIME} regardless")}
{dim(f"Why small target + wide stop? Option premiums are volatile, so a quick +{C.PREMIUM_TARGET_PCT:.0f}% "
     f"is hit often (high win rate) while the wider −{C.PREMIUM_STOP_PCT:.0f}% stop avoids getting "
     f"shaken out by normal premium noise. In the recent backtest this gave ~77% win rate with "
     f"positive expectancy. The catch: it's only proven on 13 trades — forward sessions decide it.")}

{h("9 · RISK CONTROLS")}
{p(f"• Max <b>{C.MAX_TRADES_PER_DAY}</b> trades/day")}
{p(f"• <b>{C.CONSECUTIVE_LOSS_HALT}</b> stop-outs in a row → halt trading for the day")}
{p(f"• Every position force-closed at {C.KILL_SWITCH_TIME} — never hold overnight")}
{p(f"• Position size derived from the stop distance, not guesswork")}

{h("10 · PAPER TRADING & GO-LIVE RULE")}
{p("For the first month the system records every signal to its outcome (WIN at target, LOSS at stop, "
   "or FORCED at 3:10 PM). The TRADE LOG is your honest scorecard.")}
{p(f"<b style='color:{GREEN}'>Go-live bar:</b> win rate ≥ {C.PAPER_TRADING_MIN_WIN_RATE:.0%} "
   f"AND profit factor > {C.PAPER_TRADING_MIN_PF} across {C.PAPER_TRADING_MIN_SIGNALS}+ signals. "
   "Below that, the edge isn't proven — don't automate.")}
{dim("Honest note: factor hit-rates are barely above a coin-flip; after brokerage + taxes the edge is thin. "
     "Treat every signal as a hypothesis and judge it by the log over many sessions.")}

{h("11 · HOW IT RUNS (local machine)")}
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
        self.scan_btn.setText("SCANNING…"); self.scan_btn.setEnabled(False)
        self.worker = ScanWorker(self.agent)
        self.worker.scan_complete.connect(self._on_scan)
        self.worker.error_occurred.connect(lambda e: self.status.showMessage(f"Scan error: {e}"))
        self.worker.start()

    def _on_scan(self, signals: list):
        self.last_scan_results = signals
        self._refresh_pm(); self._refresh_watchlist(); self._refresh_alpha(); self._refresh_log()
        self.scan_btn.setText("⟳ SCAN"); self.scan_btn.setEnabled(True); self._style_scan_idle()

    # ── refreshers ────────────────────────────────────────────────────────────
    def _dir_color(self, d):
        return QColor(GREEN) if d == "LONG" else QColor(RED) if d == "SHORT" else QColor(TEXT_DIM)

    def _set_row(self, table, row, values, fg=None, bg=None):
        for col, val in enumerate(values):
            it = QTableWidgetItem(str(val))
            if fg: it.setForeground(QBrush(fg))
            if bg: it.setBackground(QBrush(bg))
            table.setItem(row, col, it)

    def _refresh_pm(self):
        ready = [s for s in self.last_scan_results if s.get("trade_ready")]
        self.pm_empty.setVisible(len(ready) == 0)
        self.pm_table.setRowCount(len(ready))
        from engine.options import build_live_option_order
        from engine.data_fetcher import get_cached_ltp
        for r, sig in enumerate(ready):
            spot = get_cached_ltp(sig["ticker"]) or sig.get("entry_price") or 0
            order = build_live_option_order(sig["ticker"], spot, sig.get("direction", "LONG"))
            if not order:
                vals = [datetime.now(IST).strftime("%H:%M:%S"),
                        f"{sig['ticker']} {sig.get('direction')}", "—", "—", "n/a",
                        "—", "—", "—", "—", "no option"]
                self._set_row(self.pm_table, r, vals, fg=QColor(TEXT_DIM))
                continue
            cap = f"Rs {order['capital']:,.0f}" if order.get("capital") else "—"
            vals = [datetime.now(IST).strftime("%H:%M:%S"),
                    f"BUY {order['symbol']} {order['instrument']}",
                    f"{int(order['strike'])}", order["expiry"],
                    f"Rs {order['premium']:.2f}", f"Rs {order['target_premium']:.2f}",
                    f"Rs {order['stop_premium']:.2f}", order.get("lot_size", "—"),
                    cap, "● BUY MANUAL"]
            self._set_row(self.pm_table, r, vals, fg=QColor(AMBER))

    def _refresh_watchlist(self):
        wl = [s for s in self.last_scan_results if s.get("passes_gate_1")]
        self.wl_table.setRowCount(len(wl))
        for r, sig in enumerate(wl):
            fam = sig.get("families_detail", {})
            vals = [sig.get("ticker"), f"{sig.get('alpha_z',0):.2f}", sig.get("direction"),
                    f"{sig.get('breadth',0)}/3",
                    f"{fam.get('TREND',{}).get('z_score',0):.2f}",
                    f"{fam.get('FLOW',{}).get('z_score',0):.2f}"]
            self._set_row(self.wl_table, r, vals, fg=self._dir_color(sig.get("direction")))

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

    def _refresh_log(self):
        st = self.trade_log.get_all_time_stats()
        self.log_stats.setText(
            f"  TRADES {st['num_trades']}   ·   W {st['num_wins']} / L {st['num_losses']}   ·   "
            f"WIN {st['win_rate']:.0%}   ·   PF {st['profit_factor']:.2f}   ·   "
            f"P&L Rs {st['total_pnl']:+.0f}   ·   EXP Rs {st['expectancy']:+.0f}/trade")
        trades = [t for t in self.trade_log.trades if t.get("outcome")][-25:]
        self.log_table.setRowCount(len(trades))
        for r, t in enumerate(trades):
            oc = t.get("outcome")
            fg = QColor(GREEN) if oc == "WIN" else QColor(RED) if oc == "LOSS" else QColor(CYAN)
            vals = [t.get("signal_time","")[:19], t.get("ticker"), t.get("direction"),
                    f"{t.get('entry',0):.2f}", f"{t.get('stop',0):.2f}", f"{t.get('target',0):.2f}",
                    oc, f"{t.get('realized_pnl_inr',0):+.0f}"]
            self._set_row(self.log_table, r, vals, fg=fg)

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
            interval = 2000 if self.agent.is_market_open() else 20000
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

    def _set_ticker(self, lbl, name, d: dict):
        """Render an index ticker with colored up/down vs previous close."""
        direction = d.get("direction", "FLAT")
        color = GREEN if direction == "UP" else (RED if direction == "DOWN" else TEXT_DIM)
        arrow = "▲" if direction == "UP" else ("▼" if direction == "DOWN" else "•")
        chg = d.get("change", 0.0)
        pct = d.get("pct", 0.0)
        lbl.setText(f"{name}  {d['price']:,.2f}   {arrow} {chg:+,.2f} ({pct:+.2f}%)")
        lbl.setStyleSheet(f"color:{color};")

    def _check_apis(self):
        h = check_api_health()
        keys = ["upstox_ltp", "upstox_intraday", "upstox_historical", "nifty", "banknifty", "vix"]
        active = sum(1 for k in keys if h.get(k)); total = len(keys)
        color = GREEN if active >= 4 else (AMBER if active >= 2 else RED)
        self.api_lbl.setText(f"API {active}/{total} ●")
        self.api_lbl.setStyleSheet(f"color:{color};")

    def _tick(self):
        now = datetime.now(IST)
        mkt = "OPEN" if self.agent.is_market_open() else "CLOSED"
        self.status.showMessage(
            f"  {now:%a %d %b %Y · %H:%M:%S} IST    ·    MARKET {mkt}    ·    "
            f"scanned {len(self.last_scan_results)}    ·    "
            f"ready {sum(1 for s in self.last_scan_results if s.get('trade_ready'))}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = TerminalApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
