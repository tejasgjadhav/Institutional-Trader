"""
Portfolio Manager — Position Sizing, Risk Management, Instrument Selection
"""
import json
from datetime import datetime
from engine.config import (
    CAPITAL, RISK_PER_TRADE_INR, REWARD_RISK_RATIO, MAX_TRADES_PER_DAY,
    CONSECUTIVE_LOSS_HALT, STOP_LOSS_CAP_PCT, OPTION_CONVICTION_THRESHOLD,
    OPTION_IV_THRESHOLD, IST, TARGET_PCT_EQUITY, TARGET_PCT_DERIVATIVE,
)
import logging

logger = logging.getLogger(__name__)


def decide_instrument(alpha_z: float, direction: str) -> dict:
    """
    Map conviction + direction to instrument and target %.

      |alpha-z| 0.55-0.70  LONG  -> EQUITY  (1% target, unleveraged)
                           SHORT -> FUTURE  (5% target, leveraged)
      |alpha-z| > 0.70     LONG  -> CALL    (5% target, leveraged)
                           SHORT -> PUT     (5% target, leveraged)

    Returns {'instrument': str, 'target_pct': float, 'leveraged': bool}.
    """
    strong = abs(alpha_z) > OPTION_CONVICTION_THRESHOLD
    if direction == "LONG":
        if strong:
            inst, tpct = "CALL", TARGET_PCT_DERIVATIVE
        else:
            inst, tpct = "EQUITY", TARGET_PCT_EQUITY
    else:  # SHORT — retail can't short cash, so always a derivative
        inst, tpct = ("PUT" if strong else "FUTURE"), TARGET_PCT_DERIVATIVE
    return {"instrument": inst, "target_pct": tpct, "leveraged": (inst != "EQUITY")}


class Portfolio:
    def __init__(self):
        self.capital = CAPITAL
        self.daily_pnl = 0.0
        self.trades_today = []  # List of open trades
        self.closed_trades = []  # Historical closed trades
        self.consecutive_losses = 0

    def add_trade(self, trade: dict):
        """Add a new open trade"""
        self.trades_today.append(trade)

    def close_trade(self, trade_idx: int, outcome: str, realized_pnl: float):
        """Close a trade (WIN / LOSS / FORCED)"""
        if 0 <= trade_idx < len(self.trades_today):
            trade = self.trades_today.pop(trade_idx)
            trade["outcome"] = outcome
            trade["realized_pnl"] = realized_pnl
            trade["close_time"] = datetime.now(IST).isoformat()

            self.closed_trades.append(trade)
            self.daily_pnl += realized_pnl

            if outcome == "LOSS":
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

    def can_trade(self) -> tuple:
        """Returns (allowed: bool, reason: str)"""
        if len(self.trades_today) >= MAX_TRADES_PER_DAY:
            return False, f"Max {MAX_TRADES_PER_DAY} trades/day reached"
        if self.consecutive_losses >= CONSECUTIVE_LOSS_HALT:
            return False, f"{CONSECUTIVE_LOSS_HALT} consecutive stops — halted for day"
        return True, "OK"

    def equity(self) -> float:
        """Current equity = capital + daily PnL"""
        return self.capital + self.daily_pnl

    def reset_daily(self):
        """Reset daily tracking (call at 15:10 each day)"""
        self.daily_pnl = 0.0
        self.trades_today = []
        self.consecutive_losses = 0


class TradeCalculator:
    """Position sizing and trade parameters"""

    @staticmethod
    def calculate_position(entry: float, alpha_z: float, df_5min, direction: str = "LONG") -> dict:
        """
        Calculate stop, target, quantity, instrument and target % based on:
        - Entry price
        - Alpha-z strength + direction → instrument (EQUITY/FUTURE/CALL/PUT)
        - Target %: 1% equity, 5% futures/options (see decide_instrument)
        - Risk per trade (₹2,000 fixed), stop capped at 1%
        """
        if entry <= 0:
            return {"error": "Invalid entry price"}

        decision = decide_instrument(alpha_z, direction)
        tpct = decision["target_pct"]

        # Stop = 1% away (intraday cap)
        if direction == "LONG":
            stop = entry * (1 - STOP_LOSS_CAP_PCT / 100)
            target = entry * (1 + tpct / 100)
        else:
            stop = entry * (1 + STOP_LOSS_CAP_PCT / 100)
            target = entry * (1 - tpct / 100)

        risk_amount = RISK_PER_TRADE_INR
        risk_per_share = abs(entry - stop)
        if risk_per_share <= 0:
            return {"error": "Invalid stop (too close to entry)"}

        qty = max(1, int(risk_amount / risk_per_share))
        reward_risk = round(tpct / STOP_LOSS_CAP_PCT, 1)  # e.g. 5%/1% = 5:1

        return {
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "qty": qty,
            "risk_amount_inr": risk_amount,
            "reward_amount_inr": round(risk_amount * reward_risk, 0),
            "reward_risk_ratio": reward_risk,
            "instrument": decision["instrument"],
            "target_pct": tpct,
            "alpha_z_conviction": abs(alpha_z),
        }

    @staticmethod
    def get_instrument_string(ticker: str, alpha_z: float, direction: str, df_options=None) -> str:
        """
        Map alpha-z conviction to instrument (EQUITY, FUTURE, CALL, PUT)
        """
        symbol = ticker.replace(".NS", "")

        if abs(alpha_z) <= 0.70:
            # Moderate conviction: equity for LONG, future for SHORT
            if direction == "LONG":
                return f"{symbol} EQUITY"
            else:
                return f"{symbol} JUN FUT"  # Placeholder contract month
        else:
            # High conviction: CALL/PUT
            if direction == "LONG":
                return f"{symbol} JUN CALL"  # ATM strike would be selected live
            else:
                return f"{symbol} JUN PUT"

    @staticmethod
    def estimate_premium(alpha_z: float, iv: float = 20.0) -> float:
        """
        Rough option premium estimate (for paper trading display).
        This would be fetched live from NSE options chain.
        """
        # Placeholder: would fetch ATM strike premium
        return 100.0  # Example


class RiskManager:
    """Track daily risk and enforce limits"""

    def __init__(self):
        self.daily_loss_limit_pct = 0.05  # 5% daily loss limit
        self.daily_pnl = 0.0
        self.max_concurrent_trades = MAX_TRADES_PER_DAY

    def is_loss_limit_breached(self, capital: float) -> bool:
        """Check if daily loss exceeds limit"""
        loss_pct = abs(self.daily_pnl) / capital if capital > 0 else 0
        return self.daily_pnl < 0 and loss_pct > self.daily_loss_limit_pct

    def update_daily_pnl(self, trade_pnl: float):
        """Record trade outcome"""
        self.daily_pnl += trade_pnl

    def reset(self):
        """Reset daily tracking"""
        self.daily_pnl = 0.0


def format_trade_for_log(signal: dict, portfolio_calc: dict) -> dict:
    """
    Format signal + portfolio calc into trade log entry.
    """
    return {
        "timestamp": datetime.now(IST).isoformat(),
        "ticker": signal.get("ticker"),
        "direction": signal.get("direction"),
        "alpha_z": signal.get("alpha_z"),
        "breadth": signal.get("breadth"),
        "entry": portfolio_calc.get("entry"),
        "stop": portfolio_calc.get("stop"),
        "target": portfolio_calc.get("target"),
        "qty": portfolio_calc.get("qty"),
        "instrument": portfolio_calc.get("instrument"),
        "reward_risk": portfolio_calc.get("reward_risk_ratio"),
        "status": "OPEN",
        "outcome": None,  # WIN / LOSS / FORCED_CLOSE
        "realized_pnl": None,
    }
