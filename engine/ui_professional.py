"""
Institutional Trader — Professional Clean Dashboard
Clean design, clear tab selection, live market data
Simulation: 30-day history, records last 5 trading days
"""
import sys
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QStatusBar,
    QHeaderView, QStackedWidget, QTextEdit, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QBrush, QIcon

from engine.config import IST
from engine.agent import Agent
from engine.trade_log import TradeLog
from engine.data_utils import (
    get_nifty_close, get_banknifty_close, get_vix_close, check_api_health, get_last_5_trading_days
)

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Background scan thread"""
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
            signals = self.agent.run_scan()
            self.scan_complete.emit(signals)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ProfessionalTradingApp(QMainWindow):
    """Clean professional trading dashboard"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Institutional Trader — Paper Trading Dashboard")
        self.setGeometry(50, 50, 1800, 1050)
        self.setStyleSheet(self._get_stylesheet())

        self.agent = Agent()
        self.trade_log = TradeLog()
        self.simulation_mode = True
        self.last_scan_results = []
        self.recording_mode = False  # Only record on last 5 trading days

        # Check if we're in recording window (last 5 trading days)
        self._check_recording_window()

        # Setup UI
        self.setup_ui()

        # Check API health
        self.check_apis()

        # Auto-scan every 5 min
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(300000)

        # Live data update every 3 sec
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self.update_live_data)
        self.live_timer.start(3000)

        # Initial scan
        self.trigger_scan()

    def _check_recording_window(self):
        """Check if we're in last 5 trading days (recording window)"""
        last_5 = get_last_5_trading_days()
        today = datetime.now().date()
        self.recording_mode = today in last_5
        mode = "RECORDING" if self.recording_mode else "OBSERVATION"
        logger.info(f"Simulation mode: {mode} | Last 5 days: {last_5}")

    def _get_stylesheet(self) -> str:
        """Professional clean color scheme"""
        return """
QMainWindow {
    background-color: #ffffff;
    color: #1a1a1a;
}
QWidget {
    background-color: #ffffff;
    color: #1a1a1a;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    gridline-color: #e0e0e0;
}
QTableWidget::item {
    padding: 5px;
    border: none;
}
QHeaderView::section {
    background-color: #2c3e50;
    color: #ffffff;
    padding: 8px;
    border: none;
    font-weight: bold;
}
QLabel {
    color: #1a1a1a;
}
QPushButton {
    background-color: #3498db;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1f618d;
}
QStatusBar {
    background-color: #ecf0f1;
    color: #2c3e50;
    border-top: 1px solid #bdc3c7;
}
QTextEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #e0e0e0;
    font-family: Courier;
}
QCheckBox {
    color: #1a1a1a;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
"""

    def setup_ui(self):
        """Setup main window"""
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ── Header ──────────────────────────────────────────────────────
        header = self._create_header()
        main_layout.addWidget(header)

        # ── Market Data Bar ─────────────────────────────────────────────
        market_bar = self._create_market_bar()
        main_layout.addWidget(market_bar)

        # ── Main Content ────────────────────────────────────────────────
        self.screens = QStackedWidget()

        self.screen_desk = self._create_screen_desk()
        self.screens.addWidget(self.screen_desk)

        self.screen_alpha = self._create_screen_alpha()
        self.screens.addWidget(self.screen_alpha)

        self.screen_watchlist = self._create_screen_watchlist()
        self.screens.addWidget(self.screen_watchlist)

        self.screen_log = self._create_screen_log()
        self.screens.addWidget(self.screen_log)

        self.screen_info = self._create_screen_info()
        self.screens.addWidget(self.screen_info)

        main_layout.addWidget(self.screens, 1)

        # ── Navigation ──────────────────────────────────────────────────
        nav = self._create_navigation()
        main_layout.addWidget(nav)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

    def _create_header(self) -> QWidget:
        """Header with title and mode"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("INSTITUTIONAL TRADER")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50;")

        layout.addWidget(title)
        layout.addStretch()

        mode_text = f"MODE: {'RECORDING' if self.recording_mode else 'OBSERVATION'} (30-day history)"
        mode_label = QLabel(mode_text)
        mode_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        mode_label.setStyleSheet(f"color: {'#27ae60' if self.recording_mode else '#95a5a6'};")
        layout.addWidget(mode_label)

        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #ecf0f1; border-bottom: 2px solid #bdc3c7; padding: 10px;")
        return widget

    def _create_market_bar(self) -> QWidget:
        """Live Nifty, BankNifty, VIX"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(30)

        self.nifty_label = QLabel("NIFTY 50: —")
        self.nifty_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.nifty_label.setStyleSheet("color: #2c3e50;")

        self.banknifty_label = QLabel("BANKNIFTY: —")
        self.banknifty_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.banknifty_label.setStyleSheet("color: #2c3e50;")

        self.vix_label = QLabel("VIX: —")
        self.vix_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.vix_label.setStyleSheet("color: #e74c3c;")

        layout.addWidget(self.nifty_label)
        layout.addWidget(self.banknifty_label)
        layout.addWidget(self.vix_label)
        layout.addStretch()

        # API Health
        self.api_health = QLabel("API: ✓")
        self.api_health.setFont(QFont("Segoe UI", 10))
        self.api_health.setStyleSheet("color: #27ae60;")
        layout.addWidget(self.api_health)

        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #f8f9fa; border: 1px solid #e0e0e0; padding: 10px;")
        return widget

    def _create_screen_desk(self) -> QWidget:
        """DESK - Latest PM Decisions"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("► LATEST PM DECISIONS (TRADE-READY SIGNALS)")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;")
        layout.addWidget(title)

        self.desk_table = QTableWidget()
        self.desk_table.setColumnCount(9)
        self.desk_table.setHorizontalHeaderLabels([
            "TIME", "TICKER", "DIR", "ENTRY", "STOP", "TARGET", "QTY", "INSTRUMENT", "STATUS"
        ])
        self.desk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.desk_table.setAlternatingRowColors(True)
        self.desk_table.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.desk_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_alpha(self) -> QWidget:
        """ALPHA - All stocks"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("► ALPHA SCORES (95 STOCKS)")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;")
        layout.addWidget(title)

        self.alpha_table = QTableWidget()
        self.alpha_table.setColumnCount(7)
        self.alpha_table.setHorizontalHeaderLabels([
            "TICKER", "ALPHA-Z", "DIR", "BR", "TREND", "FLOW", "EVENT"
        ])
        self.alpha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alpha_table.setAlternatingRowColors(True)
        self.alpha_table.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.alpha_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_watchlist(self) -> QWidget:
        """WATCHLIST - Gate 1 passes"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("► WATCHLIST (AWAITING ORB CONFIRMATION)")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;")
        layout.addWidget(title)

        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(6)
        self.watchlist_table.setHorizontalHeaderLabels([
            "TICKER", "ALPHA-Z", "DIR", "BR", "ORB_HIGH", "ORB_LOW"
        ])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.watchlist_table.setAlternatingRowColors(True)
        self.watchlist_table.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.watchlist_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_log(self) -> QWidget:
        """TRADE LOG"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("► TRADE LOG (ALL HISTORY)")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;")
        layout.addWidget(title)

        self.log_stats = QTextEdit()
        self.log_stats.setReadOnly(True)
        self.log_stats.setFont(QFont("Courier", 10))
        self.log_stats.setMaximumHeight(100)
        layout.addWidget(self.log_stats)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(8)
        self.log_table.setHorizontalHeaderLabels([
            "TIME", "TICKER", "DIR", "ENTRY", "STOP", "TARGET", "OUTCOME", "P&L"
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.log_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_info(self) -> QWidget:
        """INFO screen"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("► SYSTEM INFORMATION")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;")
        layout.addWidget(title)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setFont(QFont("Courier", 10))
        info.setText(f"""
INSTITUTIONAL TRADER — Paper Trading Dashboard
═════════════════════════════════════════════════════════════════════════

SIMULATION MODE
  Status:          {'RECORDING (Last 5 trading days)' if self.recording_mode else 'OBSERVATION (30-day history)'}
  Paper Trading:   ✓ Manual order placement in Upstox
  Recording:       {'✓ ON' if self.recording_mode else '✗ OFF (use for backtesting)'}
  Trade Log:       Persistent across sessions

SIGNAL GENERATION (Every 5 minutes, Market hours 9:15–15:30 IST)
  Universe:        95 NSE stocks
  Scoring:         3-family alpha (TREND, FLOW, EVENT)
  Gate 1:          |alpha-z| > 0.55 + ≥2 families agree
  Gate 2:          ORB breakout + volume surge
  Position Size:   ₹2,000 risk/trade, 2:1 reward-risk

DECISION RULES (30+ signals over 20 trading days)
  Go-Live Bar:     Win Rate ≥ 52% AND Profit Factor > 1
  If Met:          Automation eligible
  If Not Met:      Redesign or continue paper trading

SCREENS
  [DESK]          → Latest signals ready to trade (MAIN)
  [ALPHA]         → All 95 stocks scored
  [WATCHLIST]     → Stocks awaiting ORB confirmation
  [TRADE LOG]     → History, statistics, outcomes
  [INFO]          → This screen

CONTROLS
  [SCAN NOW]      → Trigger immediate scan
  [REFRESH]       → Refresh current screen
  Tab buttons     → Switch screens

PAPER TRADING WORKFLOW
  1. Signal fires on DESK screen
  2. You manually place order in Upstox (same levels: entry, stop, target, qty)
  3. System tracks on live Upstox prices
  4. Closes when hits target, stop, or 3:10 PM
  5. TRADE LOG updates with outcome and P&L

═════════════════════════════════════════════════════════════════════════
Last 5 Trading Days (Recording Window): {get_last_5_trading_days()}
""")
        layout.addWidget(info)

        widget.setLayout(layout)
        return widget

    def _create_navigation(self) -> QWidget:
        """Bottom tab buttons"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_buttons = []
        tabs = [
            ("DESK", 0),
            ("ALPHA", 1),
            ("WATCHLIST", 2),
            ("TRADE LOG", 3),
            ("INFO", 4),
        ]

        for label, idx in tabs:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(120)
            btn.clicked.connect(lambda checked, i=idx: self.switch_screen(i))
            self.tab_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        self.scan_btn = QPushButton("► SCAN NOW")
        self.scan_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.scan_btn.setMinimumHeight(40)
        self.scan_btn.setMinimumWidth(140)
        self.scan_btn.setStyleSheet("background-color: #27ae60; color: #ffffff;")
        self.scan_btn.clicked.connect(self.trigger_scan)
        layout.addWidget(self.scan_btn)

        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #ecf0f1; border-top: 1px solid #bdc3c7; padding: 5px;")
        return widget

    def switch_screen(self, idx: int):
        """Switch screen and highlight tab"""
        self.screens.setCurrentIndex(idx)
        # Clear all buttons
        for btn in self.tab_buttons:
            btn.setStyleSheet("background-color: #3498db; color: #ffffff;")
        # Highlight selected
        if idx < len(self.tab_buttons):
            self.tab_buttons[idx].setStyleSheet(
                "background-color: #2c3e50; color: #ffffff; border: 3px solid #f39c12;"
            )

    def trigger_scan(self):
        """Start scan"""
        self.scan_btn.setText("SCANNING...")
        self.scan_btn.setEnabled(False)

        self.worker = ScanWorker(self.agent)
        self.worker.scan_complete.connect(self.on_scan_complete)
        self.worker.start()

    def on_scan_complete(self, signals: list):
        """Handle scan results"""
        self.last_scan_results = signals
        self.refresh_all()

        self.scan_btn.setText("► SCAN NOW")
        self.scan_btn.setEnabled(True)

    def refresh_all(self):
        """Refresh all screens"""
        self._refresh_desk()
        self._refresh_alpha()
        self._refresh_watchlist()
        self._refresh_log()

    def _refresh_desk(self):
        """Update DESK"""
        trade_ready = [s for s in self.last_scan_results if s.get("trade_ready")]
        self.desk_table.setRowCount(len(trade_ready))

        for row, sig in enumerate(trade_ready):
            from engine.portfolio import TradeCalculator
            entry = 100.0
            position = TradeCalculator.calculate_position(entry, sig.get("alpha_z"), None)

            items = [
                QTableWidgetItem(datetime.now(IST).strftime("%H:%M:%S")),
                QTableWidgetItem(sig.get("ticker", "")),
                QTableWidgetItem(sig.get("direction", "")),
                QTableWidgetItem(f"₹{position.get('entry', 0):.2f}"),
                QTableWidgetItem(f"₹{position.get('stop', 0):.2f}"),
                QTableWidgetItem(f"₹{position.get('target', 0):.2f}"),
                QTableWidgetItem(f"{position.get('qty', 0)}"),
                QTableWidgetItem(position.get("instrument", "")),
                QTableWidgetItem("MANUAL"),
            ]

            for col, item in enumerate(items):
                item.setBackground(QBrush(QColor(255, 235, 59)))  # Yellow
                self.desk_table.setItem(row, col, item)

    def _refresh_alpha(self):
        """Update ALPHA"""
        self.alpha_table.setRowCount(len(self.last_scan_results))

        for row, sig in enumerate(self.last_scan_results):
            families = sig.get("families_detail", {})
            trend_z = families.get("TREND", {}).get("z_score", 0)
            flow_z = families.get("FLOW", {}).get("z_score", 0)
            event_z = families.get("EVENT", {}).get("z_score", 0)

            bg = (
                QColor(200, 240, 200) if sig.get("direction") == "LONG"
                else QColor(240, 200, 200) if sig.get("direction") == "SHORT"
                else QColor(240, 240, 240)
            )

            items = [
                QTableWidgetItem(sig.get("ticker", "")),
                QTableWidgetItem(f"{sig.get('alpha_z', 0):.2f}"),
                QTableWidgetItem(sig.get("direction", "")),
                QTableWidgetItem(f"{sig.get('breadth', 0)}/3"),
                QTableWidgetItem(f"{trend_z:.2f}"),
                QTableWidgetItem(f"{flow_z:.2f}"),
                QTableWidgetItem(f"{event_z:.2f}"),
            ]

            for col, item in enumerate(items):
                item.setBackground(QBrush(bg))
                self.alpha_table.setItem(row, col, item)

    def _refresh_watchlist(self):
        """Update WATCHLIST"""
        watchlist = [s for s in self.last_scan_results if s.get("passes_gate_1")]
        self.watchlist_table.setRowCount(len(watchlist))

        for row, sig in enumerate(watchlist):
            items = [
                QTableWidgetItem(sig.get("ticker", "")),
                QTableWidgetItem(f"{sig.get('alpha_z', 0):.2f}"),
                QTableWidgetItem(sig.get("direction", "")),
                QTableWidgetItem(f"{sig.get('breadth', 0)}/3"),
                QTableWidgetItem("—"),
                QTableWidgetItem("—"),
            ]

            for col, item in enumerate(items):
                self.watchlist_table.setItem(row, col, item)

    def _refresh_log(self):
        """Update TRADE LOG"""
        stats = self.trade_log.get_all_time_stats()

        stats_text = (
            f"TRADES: {stats['num_trades']} | WINS: {stats['num_wins']} | LOSSES: {stats['num_losses']} | "
            f"WR: {stats['win_rate']:.1%} | PF: {stats['profit_factor']:.2f} | "
            f"P&L: ₹{stats['total_pnl']:+.0f} | EXP: ₹{stats['expectancy']:+.0f}/trade"
        )
        self.log_stats.setText(stats_text)

        trades = [t for t in self.trade_log.trades if t.get("outcome")][-20:]
        self.log_table.setRowCount(len(trades))

        for row, trade in enumerate(trades):
            bg = (
                QColor(200, 240, 200) if trade.get("outcome") == "WIN"
                else QColor(240, 200, 200) if trade.get("outcome") == "LOSS"
                else QColor(220, 220, 250)
            )

            items = [
                QTableWidgetItem(trade.get("signal_time", "")[:19]),
                QTableWidgetItem(trade.get("ticker", "")),
                QTableWidgetItem(trade.get("direction", "")),
                QTableWidgetItem(f"₹{trade.get('entry', 0):.2f}"),
                QTableWidgetItem(f"₹{trade.get('stop', 0):.2f}"),
                QTableWidgetItem(f"₹{trade.get('target', 0):.2f}"),
                QTableWidgetItem(trade.get("outcome", "")),
                QTableWidgetItem(f"₹{trade.get('realized_pnl_inr', 0):+.0f}"),
            ]

            for col, item in enumerate(items):
                item.setBackground(QBrush(bg))
                self.log_table.setItem(row, col, item)

    def update_live_data(self):
        """Fetch and update live market data"""
        try:
            nifty = get_nifty_close()
            banknifty = get_banknifty_close()
            vix = get_vix_close()

            self.nifty_label.setText(f"NIFTY 50: {nifty['price']:,.0f}")
            self.banknifty_label.setText(f"BANKNIFTY: {banknifty['price']:,.0f}")
            self.vix_label.setText(f"VIX: {vix['price']:.2f}")
        except Exception as e:
            logger.warning(f"Live data update failed: {e}")

    def check_apis(self):
        """Check API health"""
        health = check_api_health()
        keys = ["upstox_ltp", "upstox_intraday", "upstox_historical", "nifty", "banknifty", "vix"]
        active = sum(1 for k in keys if health.get(k))
        total = len(keys)
        self.api_health.setText(f"API: {active}/{total} ✓")
        color = "#27ae60" if active >= 4 else "#e74c3c"
        self.api_health.setStyleSheet(f"color: {color};")


def main():
    app = QApplication(sys.argv)
    window = ProfessionalTradingApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
