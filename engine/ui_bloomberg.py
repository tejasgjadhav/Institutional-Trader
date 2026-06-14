"""
Institutional Trader — Bloomberg Terminal-Style Dashboard
Professional dark theme, live market data, simulation mode
Screen 1: Latest PM Decisions (DESK)
"""
import sys
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QMessageBox,
    QHeaderView, QStatusBar, QStackedWidget, QScrollArea, QTextEdit,
    QComboBox, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize
from PySide6.QtGui import QFont, QColor, QBrush, QIcon, QPixmap
from PySide6.QtCharts import QChart, QChartView, QLineSeries

from engine.config import IST
from engine.agent import Agent
from engine.trade_log import TradeLog
from engine.data_fetcher import get_cached_ltp, get_cached_vix, get_cached_nifty_pct

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


class BloombergTerminalApp(QMainWindow):
    """Professional Bloomberg-style trading dashboard"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Institutional Trader Terminal — Bloomberg Style")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet(self._get_dark_stylesheet())

        self.agent = Agent()
        self.trade_log = TradeLog()
        self.simulation_mode = True
        self.last_scan_results = []

        # Setup UI
        self.setup_ui()

        # Auto-refresh every 5 min
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.trigger_scan)
        self.scan_timer.start(300000)  # 5 min

        # Status update every 2 sec
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_live_data)
        self.status_timer.start(2000)

        # Initial scan
        self.trigger_scan()

    def _get_dark_stylesheet(self) -> str:
        """Bloomberg Terminal dark theme"""
        return """
QMainWindow {
    background-color: #0a0e27;
    color: #ffffff;
}
QWidget {
    background-color: #0a0e27;
    color: #ffffff;
}
QTableWidget {
    background-color: #1a1f3a;
    alternate-background-color: #0f1429;
    border: 1px solid #2d3561;
    gridline-color: #2d3561;
}
QTableWidget::item {
    padding: 5px;
    border: none;
}
QHeaderView::section {
    background-color: #1f2540;
    color: #00ff41;
    padding: 5px;
    border: 1px solid #2d3561;
    font-weight: bold;
}
QLabel {
    color: #ffffff;
}
QPushButton {
    background-color: #2d3561;
    color: #00ff41;
    border: 1px solid #00ff41;
    border-radius: 3px;
    padding: 5px 15px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00ff41;
    color: #0a0e27;
}
QStatusBar {
    background-color: #1a1f3a;
    color: #00ff41;
    border-top: 1px solid #2d3561;
}
QScrollArea {
    background-color: #0a0e27;
    border: none;
}
QTextEdit {
    background-color: #1a1f3a;
    color: #00ff41;
    border: 1px solid #2d3561;
    font-family: Courier;
}
QComboBox {
    background-color: #2d3561;
    color: #00ff41;
    border: 1px solid #00ff41;
    padding: 3px;
}
QCheckBox {
    color: #00ff41;
}
"""

    def setup_ui(self):
        """Setup main window"""
        central = QWidget()
        main_layout = QVBoxLayout()

        # ── Header ──────────────────────────────────────────────────────
        header = self._create_header()
        main_layout.addWidget(header)

        # ── Live Market Data (Nifty, BankNifty, VIX) ────────────────────
        market_bar = self._create_market_bar()
        main_layout.addWidget(market_bar)

        # ── Main Content (Stacked screens) ──────────────────────────────
        self.screens = QStackedWidget()

        # Screen 0: DESK (Latest PM Decisions) — MAIN
        self.screen_desk = self._create_screen_desk()
        self.screens.addWidget(self.screen_desk)

        # Screen 1: ALPHA (All stocks)
        self.screen_alpha = self._create_screen_alpha()
        self.screens.addWidget(self.screen_alpha)

        # Screen 2: WATCHLIST (Gate 1 passes)
        self.screen_watchlist = self._create_screen_watchlist()
        self.screens.addWidget(self.screen_watchlist)

        # Screen 3: TRADE LOG
        self.screen_log = self._create_screen_log()
        self.screens.addWidget(self.screen_log)

        # Screen 4: README/INFO
        self.screen_readme = self._create_screen_readme()
        self.screens.addWidget(self.screen_readme)

        main_layout.addWidget(self.screens, 1)

        # ── Bottom Navigation ───────────────────────────────────────────
        nav = self._create_navigation()
        main_layout.addWidget(nav)

        # ── Status Bar ──────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status_bar()

        central.setLayout(main_layout)
        self.setCentralWidget(central)

    def _create_header(self) -> QWidget:
        """Header with title and mode toggle"""
        widget = QWidget()
        layout = QHBoxLayout()

        title = QLabel("INSTITUTIONAL TRADER TERMINAL")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")

        layout.addWidget(title)
        layout.addStretch()

        # Simulation mode toggle
        self.sim_checkbox = QCheckBox("SIMULATION MODE")
        self.sim_checkbox.setChecked(True)
        self.sim_checkbox.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.sim_checkbox.setStyleSheet("color: #ffaa00;")
        self.sim_checkbox.toggled.connect(self.toggle_simulation)
        layout.addWidget(self.sim_checkbox)

        widget.setLayout(layout)
        return widget

    def _create_market_bar(self) -> QWidget:
        """Live Nifty, BankNifty, VIX ticker"""
        widget = QWidget()
        layout = QHBoxLayout()

        self.nifty_label = QLabel("NIFTY 50: —")
        self.nifty_label.setFont(QFont("Courier", 12, QFont.Weight.Bold))
        self.nifty_label.setStyleSheet("color: #00ff41;")

        self.banknifty_label = QLabel("BANKNIFTY: —")
        self.banknifty_label.setFont(QFont("Courier", 12, QFont.Weight.Bold))
        self.banknifty_label.setStyleSheet("color: #00ff41;")

        self.vix_label = QLabel("VIX: —")
        self.vix_label.setFont(QFont("Courier", 12, QFont.Weight.Bold))
        self.vix_label.setStyleSheet("color: #ffaa00;")

        layout.addWidget(self.nifty_label)
        layout.addWidget(self.banknifty_label)
        layout.addWidget(self.vix_label)
        layout.addStretch()

        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #1a1f3a; border-bottom: 1px solid #2d3561; padding: 10px;")
        return widget

    def _create_screen_desk(self) -> QWidget:
        """Screen 0: DESK - Latest PM Decisions (MAIN)"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("◆ LATEST PM DECISIONS")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")
        layout.addWidget(title)

        self.desk_table = QTableWidget()
        self.desk_table.setColumnCount(9)
        self.desk_table.setHorizontalHeaderLabels([
            "TIME", "TICKER", "DIR", "ENTRY", "STOP", "TARGET", "QTY", "INSTR", "STATUS"
        ])
        self.desk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.desk_table.setAlternatingRowColors(True)
        layout.addWidget(self.desk_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_alpha(self) -> QWidget:
        """Screen 1: ALPHA - All stocks scored"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("◆ ALPHA SCORES (95 STOCKS)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")
        layout.addWidget(title)

        self.alpha_table = QTableWidget()
        self.alpha_table.setColumnCount(7)
        self.alpha_table.setHorizontalHeaderLabels([
            "TICKER", "α-Z", "DIR", "BR", "TREND", "FLOW", "EVENT"
        ])
        self.alpha_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alpha_table.setAlternatingRowColors(True)
        layout.addWidget(self.alpha_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_watchlist(self) -> QWidget:
        """Screen 2: WATCHLIST - Gate 1 passes"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("◆ WATCHLIST (AWAITING ORB CONFIRMATION)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")
        layout.addWidget(title)

        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(6)
        self.watchlist_table.setHorizontalHeaderLabels([
            "TICKER", "α-Z", "DIR", "BR", "ORB_H", "ORB_L"
        ])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.watchlist_table.setAlternatingRowColors(True)
        layout.addWidget(self.watchlist_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_log(self) -> QWidget:
        """Screen 3: TRADE LOG"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("◆ TRADE LOG (ALL-TIME)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")
        layout.addWidget(title)

        self.log_stats = QTextEdit()
        self.log_stats.setReadOnly(True)
        self.log_stats.setFont(QFont("Courier", 10))
        self.log_stats.setMaximumHeight(120)
        layout.addWidget(self.log_stats)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(8)
        self.log_table.setHorizontalHeaderLabels([
            "TIME", "TICKER", "DIR", "ENTRY", "STOP", "TARGET", "OUTCOME", "P&L"
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.setAlternatingRowColors(True)
        layout.addWidget(self.log_table)

        widget.setLayout(layout)
        return widget

    def _create_screen_readme(self) -> QWidget:
        """Screen 4: README/INFO"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("◆ SYSTEM INFO & README")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ff41;")
        layout.addWidget(title)

        readme = QTextEdit()
        readme.setReadOnly(True)
        readme.setFont(QFont("Courier", 10))
        readme.setText("""
═══════════════════════════════════════════════════════════════════════════════
INSTITUTIONAL TRADER — 3-Family Alpha NSE Intraday Trading System
═══════════════════════════════════════════════════════════════════════════════

MODE: SIMULATION (Paper Trading) — All signals are tracked but NO orders are sent to broker.
You manually place orders in Upstox when signals appear on DESK screen.

═══════════════════════════════════════════════════════════════════════════════
SCREENS
═══════════════════════════════════════════════════════════════════════════════
1. DESK           → Latest PM Decisions (trade-ready signals, highlighted yellow)
2. ALPHA          → All 95 stocks scored by 3-family system
3. WATCHLIST      → Stocks passing Gate 1 (Alpha score), awaiting ORB confirmation
4. TRADE LOG      → All historical trades + statistics
5. README         → This info panel

═══════════════════════════════════════════════════════════════════════════════
HOW IT WORKS
═══════════════════════════════════════════════════════════════════════════════

EVERY 5 MINUTES (Market Hours 9:15–15:30 IST):
  1. Scan all 95 stocks
  2. Score via 3-family system (TREND, FLOW, EVENT)
  3. Check Gate 1 (|α-z| > 0.55 + ≥2 families agree) → WATCHLIST
  4. Check Gate 2 (ORB breakout + volume) → DESK (trade-ready)

WHEN SIGNAL FIRES (YELLOW highlight on DESK):
  → Ticker, Entry, Stop, Target, Qty shown
  → MANUALLY place order in Upstox app (same levels)
  → System tracks on live Upstox prices
  → Updates TRADE LOG when trade closes (WIN/LOSS/FORCED_CLOSE at 3:10 PM)

PAPER TRADING PHASE (First Month):
  Decision bar: Win Rate ≥ 52% AND Profit Factor > 1 across 30+ signals
  If met → automation eligible. Otherwise → redesign or keep paper trading.

═══════════════════════════════════════════════════════════════════════════════
LIVE DATA
═══════════════════════════════════════════════════════════════════════════════
NIFTY 50    → Top market index, used for regime check
BANKNIFTY   → Banking sector index (alternative signal source)
VIX         → Market volatility gauge (affects position sizing)

═══════════════════════════════════════════════════════════════════════════════
SIMULATION MODE (Enabled)
═══════════════════════════════════════════════════════════════════════════════
✓ All signals generated and logged
✓ NO orders sent to Upstox (you decide manually)
✓ Paper trade log builds evidence
✓ Full back-testing before automation

═══════════════════════════════════════════════════════════════════════════════
CONTROLS
═══════════════════════════════════════════════════════════════════════════════
[SCAN NOW]    → Trigger immediate scan (otherwise auto-scans every 5 min)
[REFRESH]     → Refresh current screen
[SIMULATION MODE] → Toggle ON/OFF (OFF = would auto-execute, not ready)

═══════════════════════════════════════════════════════════════════════════════
""")
        layout.addWidget(readme)

        widget.setLayout(layout)
        return widget

    def _create_navigation(self) -> QWidget:
        """Bottom navigation buttons"""
        widget = QWidget()
        layout = QHBoxLayout()

        buttons = [
            ("DESK", 0, "Latest signals (MAIN)"),
            ("ALPHA", 1, "All stocks scored"),
            ("WATCHLIST", 2, "Gate 1 passes"),
            ("TRADE LOG", 3, "History & stats"),
            ("README", 4, "System info"),
        ]

        for label, screen_idx, tooltip in buttons:
            btn = QPushButton(label)
            btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            btn.setMinimumWidth(120)
            btn.clicked.connect(lambda checked, idx=screen_idx: self.switch_screen(idx))
            layout.addWidget(btn)

        layout.addStretch()

        self.scan_btn = QPushButton("SCAN NOW")
        self.scan_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.scan_btn.setStyleSheet(
            "background-color: #00ff41; color: #0a0e27; border: 2px solid #00ff41; padding: 10px;"
        )
        self.scan_btn.clicked.connect(self.trigger_scan)
        layout.addWidget(self.scan_btn)

        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #1a1f3a; border-top: 1px solid #2d3561; padding: 10px;")
        return widget

    def switch_screen(self, screen_idx: int):
        """Switch to different screen"""
        self.screens.setCurrentIndex(screen_idx)

    def trigger_scan(self):
        """Start background scan"""
        self.scan_btn.setText("SCANNING...")
        self.scan_btn.setEnabled(False)

        self.worker = ScanWorker(self.agent)
        self.worker.scan_complete.connect(self.on_scan_complete)
        self.worker.start()

    def on_scan_complete(self, signals: list):
        """Handle scan results"""
        self.last_scan_results = signals
        self.refresh_all()

        self.scan_btn.setText("SCAN NOW")
        self.scan_btn.setEnabled(True)

    def refresh_all(self):
        """Refresh all screens"""
        self._refresh_desk()
        self._refresh_alpha()
        self._refresh_watchlist()
        self._refresh_log()

    def _refresh_desk(self):
        """Update DESK with trade-ready signals"""
        trade_ready = [s for s in self.last_scan_results if s.get("trade_ready")]
        self.desk_table.setRowCount(len(trade_ready))

        for row, sig in enumerate(trade_ready):
            from engine.portfolio import TradeCalculator
            entry = 100.0  # Placeholder
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
                QTableWidgetItem("READY" if self.simulation_mode else "AUTO"),
            ]

            for col, item in enumerate(items):
                item.setBackground(QBrush(QColor(200, 150, 0)))  # Yellow
                self.desk_table.setItem(row, col, item)

    def _refresh_alpha(self):
        """Update ALPHA with all scored stocks"""
        self.alpha_table.setRowCount(len(self.last_scan_results))

        for row, sig in enumerate(self.last_scan_results):
            families = sig.get("families_detail", {})
            trend_z = families.get("TREND", {}).get("z_score", 0)
            flow_z = families.get("FLOW", {}).get("z_score", 0)
            event_z = families.get("EVENT", {}).get("z_score", 0)

            bg = (
                QColor(0, 100, 0) if sig.get("direction") == "LONG"
                else QColor(100, 0, 0) if sig.get("direction") == "SHORT"
                else QColor(30, 30, 50)
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
                QColor(0, 100, 0) if trade.get("outcome") == "WIN"
                else QColor(100, 0, 0) if trade.get("outcome") == "LOSS"
                else QColor(50, 50, 100)
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
        """Update live market data (Nifty, BankNifty, VIX)"""
        try:
            nifty = get_cached_ltp("^NSEI") or "—"
            banknifty = get_cached_ltp("^NSEBANK") or "—"
            vix = get_cached_vix()

            nifty_pct = get_cached_nifty_pct()

            self.nifty_label.setText(f"NIFTY 50: {nifty:.0f} ({nifty_pct:+.2f}%)")
            self.banknifty_label.setText(f"BANKNIFTY: {banknifty:.0f}")
            self.vix_label.setText(f"VIX: {vix:.2f}")
        except Exception as e:
            logger.warning(f"Live data update failed: {e}")

    def update_status_bar(self):
        """Update status bar"""
        now = datetime.now(IST)
        status = (
            f"Time: {now.strftime('%H:%M:%S')} IST | "
            f"Market: {'OPEN' if self.agent.is_market_open() else 'CLOSED'} | "
            f"Mode: {'SIMULATION' if self.simulation_mode else 'AUTO'} | "
            f"Signals: {len(self.last_scan_results)}"
        )
        self.statusBar().showMessage(status)

    def toggle_simulation(self, checked: bool):
        """Toggle simulation mode"""
        self.simulation_mode = checked
        mode_text = "SIMULATION (Safe)" if checked else "AUTO (Orders sent)"
        self.sim_checkbox.setText(mode_text)
        self.update_status_bar()


def main():
    app = QApplication(sys.argv)
    window = BloombergTerminalApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
