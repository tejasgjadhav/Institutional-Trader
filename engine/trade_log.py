"""
Trade Log — Paper Trading Tracking, Win%, Expectancy, Decision Rules
"""
import json
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging

from engine.config import TRADE_LOG_PATH, IST

logger = logging.getLogger(__name__)


class TradeLog:
    """
    Manages paper trading log: signals, outcomes, P&L, statistics.
    Persisted to JSON for cross-session tracking.
    """

    def __init__(self, log_path: str = TRADE_LOG_PATH):
        self.log_path = log_path
        self.trades = []
        self._load()

    def _load(self):
        """Load existing trades from JSON"""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get("trades", [])
                    logger.info(f"Loaded {len(self.trades)} trades from {self.log_path}")
            except Exception as e:
                logger.warning(f"Failed to load trade log: {e}")
                self.trades = []
        else:
            self.trades = []

    def _save(self):
        """Persist trades to JSON. Atomic write (tmp + os.replace) so the read-only viewer,
        which reads this file in a separate process, never sees a half-written file."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        try:
            tmp = self.log_path + ".tmp"
            with open(tmp, 'w') as f:
                json.dump({"trades": self.trades, "last_updated": datetime.now(IST).isoformat()}, f, indent=2)
            os.replace(tmp, self.log_path)
        except Exception as e:
            logger.error(f"Failed to save trade log: {e}")

    def add_signal(self, trade_dict: dict):
        """Log a new signal (paper mode: not executing)"""
        trade_dict["signal_time"] = datetime.now(IST).isoformat()
        trade_dict["outcome"] = None
        trade_dict["outcome_time"] = None
        trade_dict["realized_pnl_inr"] = None
        trade_dict["status"] = "PENDING"
        self.trades.append(trade_dict)
        self._save()
        logger.info(f"Signal logged: {trade_dict['ticker']} {trade_dict['direction']} @ {trade_dict['entry']}")

    def log_signal_once(self, trade_dict: dict) -> bool:
        """
        Append a signal IF not already logged for (ticker, date, direction). Idempotent —
        used for both 3-Family and ORB+VWAP signals so re-scans don't duplicate. Returns
        True if a new row was added.
        """
        st = trade_dict.get("signal_time") or datetime.now(IST).isoformat()
        trade_dict["signal_time"] = st
        dstr = str(st)[:10]
        tk, dr = trade_dict.get("ticker"), trade_dict.get("direction")
        for t in self.trades:
            if (t.get("ticker") == tk and str(t.get("signal_time", ""))[:10] == dstr
                    and t.get("direction") == dr):
                return False
        trade_dict.setdefault("outcome", None)
        trade_dict.setdefault("outcome_time", None)
        trade_dict.setdefault("realized_pnl_inr", None)
        trade_dict.setdefault("status", "PENDING")
        self.trades.append(trade_dict)
        self._save()
        logger.info(f"Signal logged ({trade_dict.get('strategy','?')}): {tk} {dr}")
        return True

    def update_trade_outcome(self, signal_time: str, outcome: str, realized_pnl: float):
        """
        Update a trade outcome (WIN / LOSS / FORCED_CLOSE)
        outcome: "WIN" if hit target, "LOSS" if hit stop, "FORCED_CLOSE" if 3:10 PM
        """
        for trade in self.trades:
            if trade.get("signal_time") == signal_time:
                trade["outcome"] = outcome
                trade["outcome_time"] = datetime.now(IST).isoformat()
                trade["realized_pnl_inr"] = round(realized_pnl, 2)
                trade["status"] = "CLOSED"
                self._save()
                logger.info(f"{trade['ticker']} {outcome}: ₹{realized_pnl:+.0f}")
                return True
        return False

    def get_today_stats(self) -> dict:
        """Statistics for trades closed today"""
        today = datetime.now(IST).date().isoformat()
        today_trades = [
            t for t in self.trades
            if t.get("outcome_time") and t["outcome_time"].startswith(today)
        ]

        if not today_trades:
            return {
                "num_trades": 0,
                "num_wins": 0,
                "num_losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }

        wins = [t for t in today_trades if t["outcome"] == "WIN"]
        losses = [t for t in today_trades if t["outcome"] == "LOSS"]

        num_trades = len(today_trades)
        num_wins = len(wins)
        num_losses = len(losses)
        win_rate = num_wins / num_trades if num_trades > 0 else 0.0

        win_pnls = [t["realized_pnl_inr"] for t in wins]
        loss_pnls = [t["realized_pnl_inr"] for t in losses]

        total_pnl = sum(win_pnls) + sum(loss_pnls)
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0

        # Profit Factor = gross_wins / gross_losses
        gross_wins = sum(win_pnls) if win_pnls else 0.0
        gross_losses = abs(sum(loss_pnls)) if loss_pnls else 1.0
        pf = gross_wins / gross_losses if gross_losses > 0 else 0.0

        # Expectancy = (WR × avg_win) - ((1-WR) × avg_loss)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return {
            "num_trades": num_trades,
            "num_wins": num_wins,
            "num_losses": num_losses,
            "win_rate": round(win_rate, 3),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(pf, 2),
            "expectancy": round(expectancy, 2),
        }

    def get_all_time_stats(self) -> dict:
        """All-time statistics (cumulative)"""
        closed_trades = [t for t in self.trades if t["outcome"] is not None]

        if not closed_trades:
            return {
                "num_trades": 0,
                "num_wins": 0,
                "num_losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
            }

        wins = [t for t in closed_trades if t["outcome"] == "WIN"]
        losses = [t for t in closed_trades if t["outcome"] == "LOSS"]

        num_trades = len(closed_trades)
        num_wins = len(wins)
        num_losses = len(losses)
        win_rate = num_wins / num_trades if num_trades > 0 else 0.0

        win_pnls = [t["realized_pnl_inr"] for t in wins]
        loss_pnls = [t["realized_pnl_inr"] for t in losses]

        total_pnl = sum(win_pnls) + sum(loss_pnls)
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0

        gross_wins = sum(win_pnls) if win_pnls else 0.0
        gross_losses = abs(sum(loss_pnls)) if loss_pnls else 1.0
        pf = gross_wins / gross_losses if gross_losses > 0 else 0.0

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return {
            "num_trades": num_trades,
            "num_wins": num_wins,
            "num_losses": num_losses,
            "win_rate": round(win_rate, 3),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(pf, 2),
            "expectancy": round(expectancy, 2),
        }

    @staticmethod
    def pnl_summary(trades: list) -> dict:
        """
        Capital invested, realized P&L and % return for a list of trades.
        Capital per trade = entry option premium x lot (qty). P&L = realized_pnl_inr.
        % return = total P&L / total capital invested x 100. Computed over CLOSED trades.
        """
        closed = [t for t in trades if t.get("outcome") in ("WIN", "LOSS")]

        def _cap(t):
            ep = t.get("entry_premium")
            if ep is None:
                ep = t.get("entry") or 0
            # OPTION lot (resolver stores it); fall back to qty only if absent
            lot = t.get("lot") if t.get("lot") is not None else t.get("qty")
            return float(ep or 0) * float(lot or 0)

        capital = sum(_cap(t) for t in closed)
        pnl = sum(float(t.get("realized_pnl_inr") or 0) for t in closed)
        pct = (pnl / capital * 100.0) if capital else 0.0
        return {
            "n_closed": len(closed),
            "capital": round(capital, 2),
            "pnl": round(pnl, 2),
            "pct": round(pct, 2),
        }

    def should_go_live(self) -> tuple:
        """
        Decision: should we automate and go live?
        With +10%/-20% the breakeven win rate is ~67%, so the bar is 70%.
        Rule: win_rate >= 70% AND profit_factor > 1.0 across >= 30 signals.
        Returns: (go_live: bool, reason: str, stats: dict)
        """
        from engine.config import (PAPER_TRADING_MIN_SIGNALS, PAPER_TRADING_MIN_WIN_RATE,
                                    PAPER_TRADING_MIN_PF)
        stats = self.get_all_time_stats()

        if stats["num_trades"] < PAPER_TRADING_MIN_SIGNALS:
            return False, f"Need {PAPER_TRADING_MIN_SIGNALS} signals, have {stats['num_trades']}", stats

        if stats["win_rate"] < PAPER_TRADING_MIN_WIN_RATE:
            return False, f"Win rate {stats['win_rate']:.0%} < {PAPER_TRADING_MIN_WIN_RATE:.0%}", stats

        if stats["profit_factor"] <= PAPER_TRADING_MIN_PF:
            return False, f"Profit factor {stats['profit_factor']:.2f} <= {PAPER_TRADING_MIN_PF}", stats

        return True, "Go live: all gates passed", stats

    def print_status(self):
        """Print live status to console"""
        today = self.get_today_stats()
        alltime = self.get_all_time_stats()

        print("\n" + "="*60)
        print("TODAY")
        print("="*60)
        print(f"Trades closed:     {today['num_trades']}")
        print(f"Wins:              {today['num_wins']}")
        print(f"Losses:            {today['num_losses']}")
        print(f"Win rate:          {today['win_rate']:.1%}")
        print(f"Profit factor:     {today['profit_factor']:.2f}")
        print(f"Total P&L:         ₹{today['total_pnl']:+.0f}")
        print(f"Expectancy:        ₹{today['expectancy']:+.0f}/trade")

        print("\n" + "="*60)
        print("ALL-TIME")
        print("="*60)
        print(f"Total trades:      {alltime['num_trades']}")
        print(f"Wins / Losses:     {alltime['num_wins']} / {alltime['num_losses']}")
        print(f"Win rate:          {alltime['win_rate']:.1%}")
        print(f"Profit factor:     {alltime['profit_factor']:.2f}")
        print(f"Total P&L:         ₹{alltime['total_pnl']:+.0f}")
        print(f"Expectancy:        ₹{alltime['expectancy']:+.0f}/trade")

        go_live, reason, _ = self.should_go_live()
        print(f"\nGo live decision:  {go_live}")
        print(f"Reason:            {reason}")
        print("="*60 + "\n")
