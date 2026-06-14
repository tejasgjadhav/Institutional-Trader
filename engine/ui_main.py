"""
Desktop App — PySide6 Dashboard
3-Family Alpha NSE Intraday Trading System
Tabs: ALPHA, WATCHLIST, DESK, TRADE LOG
"""
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QLabel, QPushButton,
    QMessageBox, QHeaderView, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor, QBrush

from engine.config import IST, UNIVERSE, APP_LOG_PATH
from engine.agent import Agent
from engine.trade_log import TradeLog

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Run scans in background thread"""
    scan_complete = Signal(list)  # Emit list of all scanned results
    error_occurred = Signal(str)

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def run(self):
        try:
            if not self.agent.is_market_open():
                self.error_occurred.emit("Market closed")
                return
            signals = self.agent.run_scan()
            self.scan_complete.emit(signals)
        except Exception as e:
            self.error_occurred.emit(str(e))


class InstitutionalTraderApp(QMainWindow):
    """Main desktop application"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Institutional Trader — 3-Family Alpha NSE Intraday")
        self.setGeometry(100, 100, 1400, 900)

        self.agent = Agent()
        self.trade_log = TradeLog()
        self.last_scan_results = []
        self.watchlist = []  # Gate 1 passes
        self.trade_ready = []  # Both gates pass

        # Setup UI
        self.setup_ui()

        # Auto-scan every 5 min (300 sec)
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(300000)  # 5 minutes

        # Status updates every 10 sec
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(10000)

        # Initial scan on startup
        self.trigger_scan()

        logger.info("Desktop app started")

    def setup_ui(self):
        """Setup main window and tabs"""
        central = QWidget()
        layout = QVBoxLayout()

        # Header
        header = QLabel("Institutional Trader — NSE Intraday Paper Trading")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tab_alpha = QWidget()
        self.tab_watchlist = QWidget()
        self.tab_desk = QWidget()
        self.tab_log = QWidget()

        self.tabs.addTab(self.tab_alpha, "ALPHA — All Stocks Scored")
        self.tabs.addTab(self.tab_watchlist, "WATCHLIST — Gate 1 Pass (Awaiting ORB)")
        self.tabs.addTab(self.tab_desk, "DESK — Latest PM Decisions")
        self.tabs.addTab(self.tab_log, "TRADE LOG — Signals + Outcomes")

        # Setup each tab
        self._setup_alpha_tab()
        self._setup_watchlist_tab()
        self._setup_desk_tab()
        self._setup_log_tab()

        layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status()

        # Buttons
        button_layout = QHBoxLayout()
        self.scan_now_btn = QPushButton("Scan Now")
        self.scan_now_btn.clicked.connect(self.trigger_scan)
        self.stats_btn = QPushButton("Print Stats")
        self.stats_btn.clicked.connect(self.print_stats)
        self.refresh_btn = QPushButton("Refresh View")
        self.refresh_btn.clicked.connect(self.refresh_all)

        button_layout.addWidget(self.scan_now_btn)
        button_layout.addWidget(self.stats_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _setup_alpha_tab(self):
        """Tab 1: All stocks with alpha-z scores"""
        layout = QVBoxLayout()

        self.alpha_table = QTableWidget()
        self.alpha_table.setColumnCount(7)
        self.alpha_table.setHorizontalHeaderLabels([
            "Ticker", "Alpha-Z", "Direction", "Breadth", "TREND", "FLOW", "EVENT"
        ])
        self.alpha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.alpha_table)

        self.tab_alpha.setLayout(layout)

    def _setup_watchlist_tab(self):
        """Tab 2: Stocks passing Gate 1 (Alpha), awaiting ORB (Gate 2)"""
        layout = QVBoxLayout()

        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(6)
        self.watchlist_table.setHorizontalHeaderLabels([
            "Ticker", "Alpha-Z", "Direction", "Breadth", "ORB High", "ORB Low"
        ])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.watchlist_table)

        self.tab_watchlist.setLayout(layout)

    def _setup_desk_tab(self):
        """Tab 3: Live trade signals (ready to execute)"""
        layout = QVBoxLayout()

        self.desk_table = QTableWidget()
        self.desk_table.setColumnCount(8)
        self.desk_table.setHorizontalHeaderLabels([
            "Ticker", "Direction", "Entry", "Stop", "Target", "Qty", "Instrument", "Time"
        ])
        self.desk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.desk_table)

        self.tab_desk.setLayout(layout)

    def _setup_log_tab(self):
        """Tab 4: Trade log with outcomes"""
        layout = QVBoxLayout()

        # Stats header
        self.log_stats = QLabel()
        self.log_stats.setFont(QFont("Courier", 10))
        layout.addWidget(self.log_stats)

        # Trades table
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(8)
        self.log_table.setHorizontalHeaderLabels([
            "Time", "Ticker", "Direction", "Entry", "Stop", "Target", "Outcome", "P&L"
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.log_table)

        self.tab_log.setLayout(layout)

    def trigger_scan(self):
        """Start scan in background thread"""
        self.scan_now_btn.setEnabled(False)
        self.scan_now_btn.setText("Scanning...")

        self.worker = ScanWorker(self.agent)
        self.worker.scan_complete.connect(self.on_scan_complete)
        self.worker.error_occurred.connect(self.on_scan_error)
        self.worker.start()

    def on_scan_complete(self, signals: list):
        """Handle scan results"""
        self.last_scan_results = signals
        self.refresh_all()

        self.scan_now_btn.setEnabled(True)
        self.scan_now_btn.setText("Scan Now")

    def on_scan_error(self, error: str):
        """Handle scan errors"""
        self.statusBar().showMessage(f"Error: {error}")
        self.scan_now_btn.setEnabled(True)
        self.scan_now_btn.setText("Scan Now")

    def refresh_all(self):
        """Update all tabs from latest data"""
        self._refresh_alpha_tab()
        self._refresh_watchlist_tab()
        self._refresh_desk_tab()
        self._refresh_log_tab()

    def _refresh_alpha_tab(self):
        """Populate ALPHA tab with all scanned stocks"""
        self.alpha_table.setRowCount(len(self.last_scan_results))

        for row, sig in enumerate(self.last_scan_results):
            ticker = sig.get("ticker", "")
            alpha_z = sig.get("alpha_z", 0)
            direction = sig.get("direction", "NEUTRAL")
            breadth = sig.get("breadth", 0)

            families = sig.get("families_detail", {})
            trend_z = families.get("TREND", {}).get("z_score", 0)
            flow_z = families.get("FLOW", {}).get("z_score", 0)
            event_z = families.get("EVENT", {}).get("z_score", 0)

            # Color by direction
            if direction == "LONG":
                bg_color = QColor(200, 255, 200)  # Light green
            elif direction == "SHORT":
                bg_color = QColor(255, 200, 200)  # Light red
            else:
                bg_color = QColor(255, 255, 255)  # White

            items = [
                QTableWidgetItem(ticker),
                QTableWidgetItem(f"{alpha_z:.2f}"),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"{breadth}/3"),
                QTableWidgetItem(f"{trend_z:.2f}"),
                QTableWidgetItem(f"{flow_z:.2f}"),
                QTableWidgetItem(f"{event_z:.2f}"),
            ]

            for col, item in enumerate(items):
                item.setBackground(QBrush(bg_color))
                self.alpha_table.setItem(row, col, item)

    def _refresh_watchlist_tab(self):
        """Populate WATCHLIST (Gate 1 passes)"""
        watchlist = [s for s in self.last_scan_results if s.get("passes_gate_1")]
        self.watchlist_table.setRowCount(len(watchlist))

        for row, sig in enumerate(watchlist):
            ticker = sig.get("ticker", "")
            alpha_z = sig.get("alpha_z", 0)
            direction = sig.get("direction", "NEUTRAL")
            breadth = sig.get("breadth", 0)

            # Would fetch live ORB bounds here
            orb_high = sig.get("signal_details", {}).get("trend", {}).get("components", {}).get("microstructure", 0)
            orb_low = orb_high - 10 if orb_high > 0 else 0

            items = [
                QTableWidgetItem(ticker),
                QTableWidgetItem(f"{alpha_z:.2f}"),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"{breadth}/3"),
                QTableWidgetItem(f"{orb_high:.2f}"),
                QTableWidgetItem(f"{orb_low:.2f}"),
            ]

            for col, item in enumerate(items):
                self.watchlist_table.setItem(row, col, item)

    def _refresh_desk_tab(self):
        """Populate DESK (Trade ready signals)"""
        self.trade_ready = [s for s in self.last_scan_results if s.get("trade_ready")]
        self.desk_table.setRowCount(len(self.trade_ready))

        for row, sig in enumerate(self.trade_ready):
            ticker = sig.get("ticker", "")
            direction = sig.get("direction", "NEUTRAL")

            # Calculate position (would use real LTP here)
            from engine.portfolio import TradeCalculator
            entry = 100.0  # Placeholder
            position = TradeCalculator.calculate_position(entry, sig.get("alpha_z"), None)

            items = [
                QTableWidgetItem(ticker),
                QTableWidgetItem(direction),
                QTableWidgetItem(f"₹{position.get('entry', 0):.2f}"),
                QTableWidgetItem(f"₹{position.get('stop', 0):.2f}"),
                QTableWidgetItem(f"₹{position.get('target', 0):.2f}"),
                QTableWidgetItem(f"{position.get('qty', 0)}"),
                QTableWidgetItem(position.get("instrument", "EQ")),
                QTableWidgetItem(datetime.now(IST).strftime("%H:%M:%S")),
            ]

            # Highlight as ready
            for col, item in enumerate(items):
                item.setBackground(QBrush(QColor(255, 255, 150)))  # Yellow
                self.desk_table.setItem(row, col, item)

    def _refresh_log_tab(self):
        """Populate TRADE LOG with outcomes"""
        stats = self.trade_log.get_all_time_stats()

        stats_text = (
            f"{'='*60}\n"
            f"TRADE LOG STATISTICS\n"
            f"{'='*60}\n"
            f"Total trades:      {stats['num_trades']}\n"
            f"Wins / Losses:     {stats['num_wins']} / {stats['num_losses']}\n"
            f"Win rate:          {stats['win_rate']:.1%}\n"
            f"Profit factor:     {stats['profit_factor']:.2f}\n"
            f"Expectancy:        ₹{stats['expectancy']:+.0f}/trade\n"
            f"Total P&L:         ₹{stats['total_pnl']:+.0f}\n"
            f"\nGo-live eligible:  {self.trade_log.should_go_live()[0]}\n"
            f"{'='*60}\n"
        )
        self.log_stats.setText(stats_text)

        # Populate table with recent trades
        trades = [t for t in self.trade_log.trades if t.get("outcome") is not None][-20:]  # Last 20
        self.log_table.setRowCount(len(trades))

        for row, trade in enumerate(trades):
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

            # Color by outcome
            if trade.get("outcome") == "WIN":
                bg = QColor(200, 255, 200)
            elif trade.get("outcome") == "LOSS":
                bg = QColor(255, 200, 200)
            else:
                bg = QColor(200, 200, 255)

            for col, item in enumerate(items):
                item.setBackground(QBrush(bg))
                self.log_table.setItem(row, col, item)

    def update_status(self):
        """Update status bar"""
        now = datetime.now(IST)
        market_open = self.agent.is_market_open()
        trading_window = self.agent.is_trading_window()

        status_text = (
            f"Time: {now.strftime('%H:%M:%S')} IST | "
            f"Market: {'OPEN' if market_open else 'CLOSED'} | "
            f"Trading: {'YES' if trading_window else 'NO'} | "
            f"Last scan: {len(self.last_scan_results)} stocks | "
            f"Ready to trade: {len(self.trade_ready)}"
        )
        self.statusBar().showMessage(status_text)

    def print_stats(self):
        """Print detailed stats"""
        self.trade_log.print_status()
        QMessageBox.information(self, "Stats Printed", "Check console output for detailed statistics.")


def main():
    app = QApplication(sys.argv)
    window = InstitutionalTraderApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
