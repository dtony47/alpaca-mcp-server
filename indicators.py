"""
indicators.py — Technical indicators built on top of OHLCV DataFrames.

Key concepts:
  - SMA  (Simple Moving Average):    Average close price over N periods. Smooth trend line.
  - EMA  (Exponential Moving Avg):   Like SMA but weights recent prices more heavily.
  - RSI  (Relative Strength Index):  0–100 oscillator. >70 = overbought, <30 = oversold.
  - MACD (Moving Avg Convergence/D): Momentum indicator. Signal line crossover = buy/sell.
  - Bollinger Bands:                 SMA ± 2 std deviations. Price near upper = expensive.
"""
import pandas as pd


def sma(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """Simple Moving Average over `period` bars."""
    return df[col].rolling(window=period).mean()


def ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """Exponential Moving Average over `period` bars."""
    return df[col].ewm(span=period, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.Series:
    """
    Relative Strength Index (RSI).
    - RSI > 70: potentially overbought (consider selling)
    - RSI < 30: potentially oversold (consider buying)
    """
    delta  = df[col].diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, col: str = "close"):
    """
    MACD indicator. Returns (macd_line, signal_line, histogram).
    - MACD crosses above signal → bullish (buy signal)
    - MACD crosses below signal → bearish (sell signal)
    """
    ema_fast   = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow   = df[col].ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, col: str = "close"):
    """
    Bollinger Bands. Returns (upper_band, middle_band, lower_band).
    - Price near upper band → potentially overbought
    - Price near lower band → potentially oversold
    """
    middle = df[col].rolling(window=period).mean()
    std    = df[col].rolling(window=period).std()
    upper  = middle + std_dev * std
    lower  = middle - std_dev * std
    return upper, middle, lower


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators as columns to a bars DataFrame. Useful for analysis."""
    df = df.copy()
    df["sma_20"]      = sma(df, 20)
    df["sma_50"]      = sma(df, 50)
    df["ema_12"]      = ema(df, 12)
    df["ema_26"]      = ema(df, 26)
    df["rsi_14"]      = rsi(df, 14)
    macd_l, sig_l, hist = macd(df)
    df["macd"]        = macd_l
    df["macd_signal"] = sig_l
    df["macd_hist"]   = hist
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = bollinger_bands(df)
    return df
