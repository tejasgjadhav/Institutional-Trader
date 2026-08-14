"""The dashboard. A dark terminal that reads what the engine wrote.

It is read-only on purpose. The headless engine does all the scanning, fetching, marking and
booking, and writes it to disk. This window reads those files every fifteen seconds and draws
them. Closing the window does not stop the engine, and nothing you click here can place or
change a position.

Four screens. MARKET shows the index snapshot. BOOK shows the example strategy's positions,
open and closed. STUDIES shows the research notes that ship with this edition. ABOUT explains
what this repository is and what it is not.

Study code. Not investment advice. See DISCLAIMER.md.
"""
import os
import json
import sys
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QStatusBar,
    QHeaderView, QStackedWidget, QTextEdit, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from engine.config import IST, DATA_DIR
from engine.agent import Agent
from engine.reader_edition import DISCLAIMER

logger = logging.getLogger(__name__)

MARKET_SNAP = os.path.join(DATA_DIR, "market_snapshot.json")
EXAMPLE_BOOK = os.path.join(DATA_DIR, "example_vwap_positions.json")
EXAMPLE_SNAP = os.path.join(DATA_DIR, "example_vwap.json")

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#000000"
PANEL       = "#0a0e14"
PANEL_LIGHT = "#11161f"
BORDER      = "#1c2433"
GREEN       = "#00e676"
RED         = "#ff5252"
AMBER       = "#ffb300"
CYAN        = "#29b6f6"
TEXT        = "#d7dde5"
TEXT_DIM    = "#6b7785"


def _read_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


class TerminalApp(QMainWindow):
    BOOK_COLS = ["DATE", "TIME", "UNDERLYING", "CONTRACT", "LOTS", "ENTRY", "NOW/EXIT",
                 "P&L %", "STATUS"]

    def __init__(self):
        super().__init__()
        self.agent = Agent()
        self.setWindowTitle("Institutional Trader — reader edition")
        self.resize(1280, 820)
        self.setStyleSheet(self._qss())
        self._build_ui()
        self._refresh_all()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_all)
        self.timer.start(15000)

    # ── look ──────────────────────────────────────────────────────────────────
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
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(8)
        v.addWidget(self._banner())
        v.addWidget(self._header())
        v.addWidget(self._market_bar())
        v.addWidget(self._tab_bar())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._screen_book())
        self.stack.addWidget(self._screen_studies())
        self.stack.addWidget(self._screen_about())
        v.addWidget(self.stack, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("read-only viewer · the engine writes, this window reads")

    def _banner(self) -> QLabel:
        lbl = QLabel("READER EDITION · the strategy below is an untested teaching example · "
                     "the author does not trade it · running it is your decision and your risk")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{AMBER}; background:{PANEL}; border:1px solid {BORDER};"
                          f"padding:7px; font-size:13px;")
        return lbl

    def _header(self) -> QWidget:
        w = QFrame()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        title = QLabel("INSTITUTIONAL TRADER")
        title.setStyleSheet(f"color:{GREEN}; font-size:21px; font-weight:bold; letter-spacing:3px;")
        h.addWidget(title)
        h.addStretch()
        self.clock = QLabel("")
        self.clock.setStyleSheet(f"color:{TEXT_DIM};")
        h.addWidget(self.clock)
        return w

    def _market_bar(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"background:{PANEL}; border:1px solid {BORDER};")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 8, 12, 8)
        self.tick_nifty = QLabel("NIFTY —")
        self.tick_bnf = QLabel("BANKNIFTY —")
        self.tick_vix = QLabel("VIX —")
        self.tick_state = QLabel("")
        for lbl in (self.tick_nifty, self.tick_bnf, self.tick_vix):
            lbl.setStyleSheet(f"color:{TEXT}; font-size:16px;")
            h.addWidget(lbl)
            h.addSpacing(26)
        h.addStretch()
        self.tick_state.setStyleSheet(f"color:{TEXT_DIM};")
        h.addWidget(self.tick_state)
        return w

    def _tab_bar(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.tab_buttons = []
        for i, label in enumerate(["BOOK", "STUDIES", "ABOUT"]):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.switch(idx))
            self.tab_buttons.append(b)
            h.addWidget(b)
        h.addStretch()
        self._highlight(0)
        return w

    def _highlight(self, idx: int):
        for i, b in enumerate(self.tab_buttons):
            on = (i == idx)
            b.setStyleSheet(
                f"QPushButton {{ background:{GREEN if on else PANEL};"
                f"color:{'#000000' if on else TEXT_DIM};"
                f"border:1px solid {GREEN if on else BORDER}; padding:7px 18px;"
                f"font-weight:{'bold' if on else 'normal'}; letter-spacing:1px; }}")

    def switch(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self._highlight(idx)

    # ── screens ───────────────────────────────────────────────────────────────
    def _panel_title(self, text, color=GREEN) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{color}; font-weight:bold; letter-spacing:2px; padding:6px 0;")
        return lbl

    def _table(self, cols) -> QTableWidget:
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    def _screen_book(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._panel_title("EXAMPLE BOOK — VWAP PULLBACK (UNTESTED)"))
        self.book_state = QLabel("")
        self.book_state.setWordWrap(True)
        self.book_state.setStyleSheet(f"color:{CYAN}; padding-bottom:6px;")
        v.addWidget(self.book_state)
        self.book_table = self._table(self.BOOK_COLS)
        v.addWidget(self.book_table, 1)
        self.book_stats = QLabel("")
        self.book_stats.setStyleSheet(f"color:{TEXT_DIM}; padding-top:6px;")
        v.addWidget(self.book_stats)
        return w

    def _screen_studies(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._panel_title("STUDIES — THE RESEARCH NOTES IN THIS EDITION"))
        box = QTextEdit()
        box.setReadOnly(True)
        box.setHtml(self._studies_html())
        v.addWidget(box, 1)
        return w

    def _screen_about(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._panel_title("ABOUT THIS EDITION", AMBER))
        box = QTextEdit()
        box.setReadOnly(True)
        box.setHtml(self._about_html())
        v.addWidget(box, 1)
        return w

    def _studies_html(self) -> str:
        rows = []
        folder = "studies"
        try:
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".md") or name == "README.md":
                    continue
                title = name
                try:
                    with open(os.path.join(folder, name)) as fh:
                        for line in fh:
                            if line.startswith("# "):
                                title = line[2:].strip()
                                break
                except Exception:
                    pass
                rows.append(f"<tr><td style='padding:6px 14px 6px 0;color:{TEXT_DIM}'>{name}</td>"
                            f"<td style='padding:6px 0'>{title}</td></tr>")
        except Exception as e:
            return f"<p style='color:{RED}'>studies folder not readable: {e}</p>"
        body = "".join(rows) or f"<tr><td style='color:{TEXT_DIM}'>no notes found</td></tr>"
        return (f"<div style='color:{TEXT};font-family:Menlo,monospace;font-size:14px'>"
                f"<p>These are the write-ups that ship with this edition. Each one states the "
                f"question that was asked, how it was tested and what the answer turned out to "
                f"be. The parameter values are not in them. Open the files in "
                f"<code>studies/</code> to read them in full.</p>"
                f"<table>{body}</table></div>")

    def _about_html(self) -> str:
        return (f"<div style='color:{TEXT};font-family:Menlo,monospace;font-size:14px'>"
                f"<p style='color:{AMBER}'>{DISCLAIMER}</p>"
                f"<h3 style='color:{GREEN}'>What this repository is</h3>"
                f"<p>It is the machine from the book: the data layer, the option resolver, the "
                f"paper book, the scheduler and this viewer. You can read all of it and change "
                f"all of it.</p>"
                f"<h3 style='color:{GREEN}'>What ships with it</h3>"
                f"<p>One strategy, a VWAP pullback bought as an index call. It is written out in "
                f"full in <code>engine/example_vwap.py</code> with every number visible. It has "
                f"never been backtested on real data and it has never been validated out of "
                f"sample. It is there so you can watch the parts work together.</p>"
                f"<h3 style='color:{GREEN}'>What does not ship with it</h3>"
                f"<p>The strategies the author trades. They are not in this repository in any "
                f"form. The book explains how the research was done. Do your own, and write your "
                f"own book beside the example.</p>"
                f"<h3 style='color:{GREEN}'>Where to start</h3>"
                f"<p>Read <code>engine/example_vwap.py</code> end to end. Then read "
                f"<code>engine/indicators.py</code>, which is a toolbox and nothing more. Then "
                f"copy the example to a new file and change the rule.</p></div>")

    # ── refresh ───────────────────────────────────────────────────────────────
    def _refresh_all(self):
        self.clock.setText(datetime.now(IST).strftime("%a %d %b %Y  %H:%M:%S IST"))
        self._refresh_market()
        self._refresh_book()

    def _refresh_market(self):
        snap = _read_json(MARKET_SNAP, {})
        if not snap:
            self.tick_state.setText("no snapshot yet — start the engine")
            return
        self._set_tick(self.tick_nifty, "NIFTY", snap.get("nifty"))
        self._set_tick(self.tick_bnf, "BANKNIFTY", snap.get("banknifty"))
        self._set_tick(self.tick_vix, "VIX", snap.get("vix"))
        if snap.get("holiday"):
            state = "market holiday"
        elif snap.get("trading"):
            state = "market open" if self.agent.is_market_open() else "market closed"
        else:
            state = "market closed"
        ts = snap.get("ts", "")[11:19]
        self.tick_state.setText(f"{state} · snapshot {ts}")

    def _set_tick(self, lbl, name, d):
        if not isinstance(d, dict):
            lbl.setText(f"{name} —")
            return
        price = d.get("price") or d.get("close")
        pct = d.get("change_pct")
        if price is None:
            lbl.setText(f"{name} —")
            return
        colour = TEXT
        if isinstance(pct, (int, float)):
            colour = GREEN if pct > 0 else RED if pct < 0 else TEXT
            lbl.setText(f"{name} {price:,.2f}  {pct:+.2f}%")
        else:
            lbl.setText(f"{name} {price:,.2f}")
        lbl.setStyleSheet(f"color:{colour}; font-size:16px;")

    def _refresh_book(self):
        snap = _read_json(EXAMPLE_SNAP, {})
        state = snap.get("state", "")
        detail = snap.get("detail", "")
        if state:
            self.book_state.setText(f"{state} — {detail}" if detail else state)
        else:
            self.book_state.setText("no scan recorded yet — start the engine")

        rows = _read_json(EXAMPLE_BOOK, [])
        self.book_table.setRowCount(0)
        wins = losses = 0
        for r in reversed(rows):
            i = self.book_table.rowCount()
            self.book_table.insertRow(i)
            outcome = r.get("outcome")
            now_px = r.get("exit_premium") if outcome else r.get("last_premium")
            pnl = r.get("pnl_pct") if outcome else r.get("mtm_pct")
            status = outcome or "OPEN"
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            values = [
                str(r.get("entry_date", "")), str(r.get("entry_time", "")),
                str(r.get("symbol_underlying", "")), str(r.get("symbol", "")),
                str(r.get("lots", "")), self._num(r.get("entry_premium")),
                self._num(now_px), ("" if pnl is None else f"{pnl:+.2f}%"), status,
            ]
            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                if c == 8:
                    item.setForeground(QColor(GREEN if outcome == "WIN"
                                              else RED if outcome == "LOSS" else AMBER))
                self.book_table.setItem(i, c, item)
        done = wins + losses
        rate = f"{wins / done * 100:.0f}%" if done else "—"
        self.book_stats.setText(
            f"{len(rows)} position(s) · {done} closed · {wins} win / {losses} loss · {rate} · "
            f"paper only, untested example")

    @staticmethod
    def _num(v):
        try:
            return f"{float(v):,.2f}"
        except Exception:
            return "" if v is None else str(v)


def run():
    app = QApplication(sys.argv)
    app.setFont(QFont("Menlo", 13))
    win = TerminalApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
