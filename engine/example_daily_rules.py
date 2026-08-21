"""Three simple daily rules, written out so you can read them and run them.

These are the three most commonly taught mechanical rules. A moving-average crossover, an
oversold dip buy, and a gap fill. Each one is about twenty lines, computes from daily bars, and
needs nothing but a price history.

They have been tested. studies/THREE_SIMPLE_RULES_TESTED.md has the numbers: twenty liquid NSE
names, daily bars from December 2018 to October 2026, long only, costs charged at 0.10 percent
round trip. In short, the crossover has the only convincing statistic and most of its trades lose,
the dip buy wins often and barely pays, and the gap fill is a coin after costs.

So none of them is recommended, and the author trades none of them. They are here because they are
short enough to read in one sitting, because the measured result is honest, and because the shapes
they produce cover most of what you will meet when you test your own ideas.

If you run any of them, that is your decision and your risk. Study code, not investment advice.
See DISCLAIMER.md.
"""
import logging

import numpy as np
import pandas as pd

from engine import config
from engine.indicators import sma, rsi

log = logging.getLogger(__name__)


def crossover_signal(df: pd.DataFrame):
    """Buy when the fast average crosses above the slow one. Sell when it crosses back.

    Measured: 431 trades, 42.5% win, +2.56% mean and -1.27% median per trade after cost, t = 3.59.
    Most trades lose. A few long holds pay for all of them.

    Returns "BUY", "SELL" or None for the latest bar.
    """
    fast = sma(df["Close"], config.RULE_CROSS_FAST)
    slow = sma(df["Close"], config.RULE_CROSS_SLOW)
    if len(df) < config.RULE_CROSS_SLOW + 1:
        return None
    now_above = fast.iloc[-1] > slow.iloc[-1]
    was_above = fast.iloc[-2] > slow.iloc[-2]
    if now_above and not was_above:
        return "BUY"
    if was_above and not now_above:
        return "SELL"
    return None


def dip_buy_signal(df: pd.DataFrame):
    """Buy a short-term oversold reading while the longer trend is still up.

    Sell on the first close above the previous day's high. Measured: 946 trades, 65.5% win,
    +0.20% mean per trade after cost, t = 1.84, so not significant. Worst trade -26.9%, because
    there is no stop.

    Returns "BUY", "SELL" or None for the latest bar.
    """
    if len(df) < config.RULE_DIP_TREND_LEN + 2:
        return None
    r = rsi(df["Close"], config.RULE_DIP_RSI_LEN)
    trend = sma(df["Close"], config.RULE_DIP_TREND_LEN)
    close = float(df["Close"].iloc[-1])
    if close > float(df["High"].iloc[-2]):
        return "SELL"
    if r.iloc[-1] < config.RULE_DIP_RSI_MAX and close > trend.iloc[-1]:
        return "BUY"
    return None


def gap_fill_signal(df: pd.DataFrame):
    """Buy the open when the stock gaps down, and sell at that day's close.

    Measured: 2,238 trades, 50.8% win, +0.08% mean per trade after cost, t = 1.57. A coin once the
    round trip is paid.

    Returns "BUY" or None. The exit is the close of the same session, so there is no sell signal.
    """
    if len(df) < 2:
        return None
    prev_close = float(df["Close"].iloc[-2])
    today_open = float(df["Open"].iloc[-1])
    if prev_close <= 0:
        return None
    gap_pct = (today_open - prev_close) / prev_close * 100.0
    if gap_pct <= -config.RULE_GAP_MIN_PCT:
        return "BUY"
    return None


RULES = {
    "crossover": crossover_signal,
    "dip_buy": dip_buy_signal,
    "gap_fill": gap_fill_signal,
}


def scan(df: pd.DataFrame) -> dict:
    """Run all three rules on one price history and return what each one says."""
    out = {}
    for name, fn in RULES.items():
        try:
            out[name] = fn(df)
        except Exception as e:
            log.warning("rule %s failed: %s", name, e)
            out[name] = None
    return out
