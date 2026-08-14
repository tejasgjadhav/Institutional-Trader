"""A toolbox of standard indicators, for your own research.

Nothing in this file is wired into a strategy. These are the ordinary building blocks you
find in any technical-analysis textbook, written once here so you do not have to write them
again. Import what you need, ignore the rest, and add your own.

They all take a pandas DataFrame of bars with the columns Open, High, Low, Close and Volume,
or a plain Series of prices where the docstring says so. They all return a Series or a plain
number. None of them fetches data and none of them places anything.

An indicator is not an edge. A moving average tells you what the average was. A pivot tells
you where yesterday's range sat. Whether either one predicts anything is the question your
backtest has to answer, and the answer is usually no. Use these to build a test, not to
decide a trade.

Study code. Not investment advice. See DISCLAIMER.md.
"""
import numpy as np
import pandas as pd


# ── Averages ────────────────────────────────────────────────────────────────────────

def sma(series: pd.Series, length: int) -> pd.Series:
    """Simple moving average over `length` bars."""
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average. Weights recent bars more heavily than old ones."""
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-weighted average price, accumulated from the first bar of the frame.

    Pass one session of intraday bars. The value at each bar is the average price paid up
    to that bar, weighted by volume. Reset it every session by passing one session at a time.
    """
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    cum_vol = df["Volume"].cumsum()
    cum_pv = (typical * df["Volume"]).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def anchored_vwap(df: pd.DataFrame, start_index) -> pd.Series:
    """VWAP accumulated from a bar you choose rather than from the open.

    Anchor it to an event, such as a results date or a gap, when you want the average price
    paid since that event.
    """
    sub = df.loc[start_index:]
    return vwap(sub)


# ── Range and volatility ────────────────────────────────────────────────────────────

def true_range(df: pd.DataFrame) -> pd.Series:
    """The larger of today's range, the gap up and the gap down."""
    prev_close = df["Close"].shift(1)
    a = df["High"] - df["Low"]
    b = (df["High"] - prev_close).abs()
    c = (df["Low"] - prev_close).abs()
    return pd.concat([a, b, c], axis=1).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average true range. A plain measure of how far price moves in a bar."""
    return true_range(df).rolling(length, min_periods=length).mean()


def realised_vol(series: pd.Series, length: int = 20, annualise: bool = True) -> pd.Series:
    """Standard deviation of log returns over `length` bars.

    With `annualise` set, the result is scaled by the square root of 252, so a daily series
    reads as an annual figure.
    """
    rets = np.log(series / series.shift(1))
    out = rets.rolling(length, min_periods=length).std()
    return out * np.sqrt(252) if annualise else out


def zscore(series: pd.Series, length: int = 20) -> pd.Series:
    """How many standard deviations the latest value sits from its own rolling mean."""
    mean = series.rolling(length, min_periods=length).mean()
    sd = series.rolling(length, min_periods=length).std()
    return (series - mean) / sd.replace(0, np.nan)


# ── Bands and levels ─────────────────────────────────────────────────────────────

def bollinger(series: pd.Series, length: int = 20, n_sd: float = 2.0):
    """A moving average with a band `n_sd` standard deviations either side of it."""
    mid = sma(series, length)
    sd = series.rolling(length, min_periods=length).std()
    return mid + n_sd * sd, mid, mid - n_sd * sd


def floor_pivots(prev_high: float, prev_low: float, prev_close: float) -> dict:
    """Classic floor-trader pivot levels from the previous session's range.

    Returns the pivot, three resistances and three supports. These are arithmetic, not a
    forecast. They are widely watched, which is the only argument for them.
    """
    p = (prev_high + prev_low + prev_close) / 3.0
    rng = prev_high - prev_low
    return {
        "P": p,
        "R1": 2 * p - prev_low,
        "S1": 2 * p - prev_high,
        "R2": p + rng,
        "S2": p - rng,
        "R3": prev_high + 2 * (p - prev_low),
        "S3": prev_low - 2 * (prev_high - p),
    }


# ── Oscillators ─────────────────────────────────────────────────────────────────────

def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's relative strength index, on a 0 to 100 scale."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD line, signal line and the histogram between them."""
    line = ema(series, fast) - ema(series, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


# ── Volume ──────────────────────────────────────────────────────────────────────────

def volume_ratio(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """This bar's volume divided by the average volume of the last `length` bars."""
    base = df["Volume"].rolling(length, min_periods=length).mean()
    return df["Volume"] / base.replace(0, np.nan)
