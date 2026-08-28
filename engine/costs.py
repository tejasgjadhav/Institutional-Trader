"""What a trade actually costs in India, charged leg by leg.

A backtest that ignores this is a chart, not a backtest. studies/COSTS_DECIDE.md says why: most
ideas died here and nowhere else.

The rates below are the published retail rates at the time of writing. They change. Check them
against your own contract notes before you trust a number that came out of this file, and edit
them if yours differ.

Study code. Not investment advice. See DISCLAIMER.md.
"""
from dataclasses import dataclass

# Published retail rates. Verify against your own broker's contract note.
BROKERAGE_PER_ORDER = 20.0     # flat, per executed order, typical discount broker
STT_EQUITY_DELIVERY = 0.001    # 0.1% on both buy and sell
STT_EQUITY_INTRADAY = 0.00025  # 0.025% on the sell side only
STT_OPTION_SELL_PREMIUM = 0.001   # 0.1% of premium, sell side
EXCHANGE_TXN_EQUITY = 0.0000297
EXCHANGE_TXN_OPTION = 0.0003503   # on premium
GST_RATE = 0.18                # on brokerage plus exchange charges
SEBI_FEES = 0.000001
STAMP_DUTY_EQUITY_BUY = 0.00015
STAMP_DUTY_OPTION_BUY = 0.00003


@dataclass
class Fill:
    """One side of one trade."""
    turnover: float        # price times quantity
    side: str              # "BUY" or "SELL"
    instrument: str        # "EQUITY_DELIVERY", "EQUITY_INTRADAY" or "OPTION"


def charges(fill: Fill) -> dict:
    """Return every charge on one fill, and the total, in rupees."""
    t, buy = fill.turnover, fill.side.upper() == "BUY"
    out = {"brokerage": BROKERAGE_PER_ORDER, "sebi": t * SEBI_FEES}

    if fill.instrument == "OPTION":
        out["exchange"] = t * EXCHANGE_TXN_OPTION
        out["stt"] = 0.0 if buy else t * STT_OPTION_SELL_PREMIUM
        out["stamp"] = t * STAMP_DUTY_OPTION_BUY if buy else 0.0
    else:
        out["exchange"] = t * EXCHANGE_TXN_EQUITY
        if fill.instrument == "EQUITY_DELIVERY":
            out["stt"] = t * STT_EQUITY_DELIVERY
        else:
            out["stt"] = 0.0 if buy else t * STT_EQUITY_INTRADAY
        out["stamp"] = t * STAMP_DUTY_EQUITY_BUY if buy else 0.0

    out["gst"] = (out["brokerage"] + out["exchange"]) * GST_RATE
    out["total"] = sum(out.values()) - out.get("total", 0.0)
    return out


def round_trip(entry_turnover: float, exit_turnover: float, instrument: str) -> float:
    """Total rupee cost of entering and exiting one position."""
    a = charges(Fill(entry_turnover, "BUY", instrument))["total"]
    b = charges(Fill(exit_turnover, "SELL", instrument))["total"]
    return a + b


def round_trip_pct(turnover: float, instrument: str = "EQUITY_INTRADAY") -> float:
    """Round-trip cost as a percent of turnover, for a quick sanity check.

    A spread is NOT included here, because a spread is not a charge. Add it separately from the
    quote you would actually have been given. studies/THE_SPREAD_YOU_ACTUALLY_GET.md explains why
    that number is the hard one.
    """
    if turnover <= 0:
        return 0.0
    return round_trip(turnover, turnover, instrument) / turnover * 100.0


def spread_cost_pct(bid: float, ask: float) -> float:
    """Cost of crossing the spread once, as a percent of the mid."""
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return 0.0
    return (ask - bid) / 2.0 / mid * 100.0
