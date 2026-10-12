"""
Daily price data, technical indicators and the long-term BUY / SELL / HOLD verdict.

This module has no UI code. It fetches price data, calculates the indicators and turns
them into a verdict with reasons, so the same logic can also power the watchlist scanner,
the backtester, or future alerts and a CLI.

The indicators are calculated directly with pandas instead of a third-party TA library,
so they keep working across numpy/pandas versions and every number is easy to trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf

Direction = Literal["bullish", "bearish", "neutral"]


# --------------------------------------------------------------------------- #
# Indicator math
# --------------------------------------------------------------------------- #
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Moving Average Convergence Divergence. Returns (macd, signal, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """Bollinger Bands. Returns (middle, upper, lower)."""
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return middle, middle + num_std * std, middle - num_std * std


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def get_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV history from Yahoo Finance and attach indicator columns.

    `ticker` examples: AAPL, MSFT, NVDA  (US)   |   SHOP.TO, TD.TO  (Canadian / TSX)
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Please enter a ticker symbol.")

    tk = yf.Ticker(ticker)
    df = tk.history(period=period, interval=interval, auto_adjust=True)

    if df is None or df.empty:
        raise ValueError(
            f"No data found for '{ticker}'. Check the symbol — "
            f"Canadian stocks need a .TO suffix (e.g. SHOP.TO)."
        )

    # Keep only the rows we need and drop any with no close price.
    df = df.dropna(subset=["Close"]).copy()

    close = df["Close"]
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    df["RSI"] = rsi(close, 14)
    df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = macd(close)
    df["BB_MID"], df["BB_UPPER"], df["BB_LOWER"] = bollinger(close)
    return df


# --------------------------------------------------------------------------- #
# Signal evaluation
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    name: str
    direction: Direction
    weight: float
    detail: str


@dataclass
class Analysis:
    ticker: str
    price: float
    currency: str
    verdict: str                 # "BUY" | "SELL" | "HOLD"
    strength: str                # "" | "Strong "
    score: float                 # signed: + bullish, - bearish
    max_score: float
    confidence: int              # 0-100
    signals: list[Signal] = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)
    df: pd.DataFrame | None = None

    @property
    def headline(self) -> str:
        return f"{self.strength}{self.verdict}".strip()


def _fmt(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{nd}f}"


def evaluate(df: pd.DataFrame, ticker: str, currency: str = "") -> Analysis:
    """Combine the indicators into a transparent, weighted BUY/SELL/HOLD call."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    signals: list[Signal] = []

    def add(name, direction, weight, detail):
        signals.append(Signal(name, direction, weight, detail))

    # 0) Trend regime: price vs the 200-day average. This is what drives the verdict:
    #    invested above the 200-day, step aside below it (validated to ~halve drawdowns).
    sma200 = latest["SMA200"]
    if not np.isnan(sma200):
        if price > sma200:
            add("Trend regime (200-day)", "bullish", 3,
                f"Price ({_fmt(price)}) is ABOVE the 200-day average ({_fmt(sma200)}) — "
                "long-term uptrend; stay invested.")
        else:
            add("Trend regime (200-day)", "bearish", 3,
                f"Price ({_fmt(price)}) is BELOW the 200-day average ({_fmt(sma200)}) — "
                "long-term downtrend; step aside to cash.")

    # 1) Primary trend: 50-day vs 200-day moving average (heaviest weight).
    if not np.isnan(latest["SMA200"]):
        if latest["SMA50"] > latest["SMA200"]:
            add("Long-term trend", "bullish", 2,
                f"50-day avg ({_fmt(latest['SMA50'])}) is ABOVE the 200-day avg "
                f"({_fmt(latest['SMA200'])}) — classic uptrend ('golden cross' territory).")
        else:
            add("Long-term trend", "bearish", 2,
                f"50-day avg ({_fmt(latest['SMA50'])}) is BELOW the 200-day avg "
                f"({_fmt(latest['SMA200'])}) — downtrend ('death cross' territory).")
    else:
        add("Long-term trend", "neutral", 0,
            "Not enough history (need ~200 days) to judge the long-term trend.")

    # 2) Price vs the 50-day average: medium-term momentum.
    if not np.isnan(latest["SMA50"]):
        if price > latest["SMA50"]:
            add("Price vs 50-day avg", "bullish", 1,
                f"Price ({_fmt(price)}) is above its 50-day average — buyers in control.")
        else:
            add("Price vs 50-day avg", "bearish", 1,
                f"Price ({_fmt(price)}) is below its 50-day average — sellers in control.")

    # 3) RSI: overbought / oversold.
    rsi_val = latest["RSI"]
    if not np.isnan(rsi_val):
        if rsi_val < 30:
            add("RSI (momentum)", "bullish", 1,
                f"RSI is {rsi_val:.0f} — oversold (<30). Often precedes a bounce.")
        elif rsi_val > 70:
            add("RSI (momentum)", "bearish", 1,
                f"RSI is {rsi_val:.0f} — overbought (>70). Pullback risk is elevated.")
        else:
            add("RSI (momentum)", "neutral", 0,
                f"RSI is {rsi_val:.0f} — neutral zone (30–70), no extreme.")

    # 4) MACD: trend momentum and fresh crossovers.
    macd_val, sig_val = latest["MACD"], latest["MACD_SIGNAL"]
    if not np.isnan(macd_val) and not np.isnan(sig_val):
        # Detect a crossover within the last 3 bars (a fresh signal carries more weight).
        recent = df.tail(4)
        crossed_up = (recent["MACD"].shift(1) <= recent["MACD_SIGNAL"].shift(1)) & \
                     (recent["MACD"] > recent["MACD_SIGNAL"])
        crossed_dn = (recent["MACD"].shift(1) >= recent["MACD_SIGNAL"].shift(1)) & \
                     (recent["MACD"] < recent["MACD_SIGNAL"])
        if crossed_up.any():
            add("MACD", "bullish", 2,
                "MACD just crossed ABOVE its signal line — a fresh bullish momentum signal.")
        elif crossed_dn.any():
            add("MACD", "bearish", 2,
                "MACD just crossed BELOW its signal line — a fresh bearish momentum signal.")
        elif macd_val > sig_val:
            add("MACD", "bullish", 1, "MACD is above its signal line — upward momentum.")
        else:
            add("MACD", "bearish", 1, "MACD is below its signal line — downward momentum.")

    # 5) Bollinger Bands: stretched away from the mean.
    bb_up, bb_lo = latest["BB_UPPER"], latest["BB_LOWER"]
    if not np.isnan(bb_up) and not np.isnan(bb_lo):
        if price < bb_lo:
            add("Bollinger Bands", "bullish", 1,
                "Price is below the lower band — stretched low, mean-reversion bounce possible.")
        elif price > bb_up:
            add("Bollinger Bands", "bearish", 1,
                "Price is above the upper band — stretched high, due for a cool-off.")
        else:
            add("Bollinger Bands", "neutral", 0,
                "Price is within its normal volatility band — no extreme.")

    # ---- Aggregate into a signed score --------------------------------------
    score = sum(s.weight if s.direction == "bullish"
                else -s.weight if s.direction == "bearish"
                else 0
                for s in signals)
    max_score = sum(s.weight for s in signals if s.direction != "neutral") or 1

    # The verdict is driven by the 200-day trend regime (validated as far better than
    # pure scoring): invested above the 200-day, cash below. The other indicators are
    # context: they set how strong the call is, not its direction.
    if np.isnan(sma200):
        # Not enough history for a regime read, so fall back to the weighted score.
        verdict = "BUY" if score >= 2 else "SELL" if score <= -2 else "HOLD"
    elif price > sma200:
        verdict = "BUY"
    else:
        verdict = "SELL"

    strength = "Strong " if abs(score) >= 4 and verdict != "HOLD" else ""
    confidence = int(round(min(abs(score) / max_score, 1.0) * 100))

    snapshot = {
        "Price": _fmt(price),
        "RSI (14)": _fmt(rsi_val, 0),
        "50-day avg": _fmt(latest["SMA50"]),
        "200-day avg": _fmt(latest["SMA200"]),
        "MACD": _fmt(macd_val, 3),
        "MACD signal": _fmt(sig_val, 3),
    }

    return Analysis(
        ticker=ticker.upper(),
        price=price,
        currency=currency,
        verdict=verdict,
        strength=strength,
        score=score,
        max_score=max_score,
        confidence=confidence,
        signals=signals,
        snapshot=snapshot,
        df=df,
    )


def analyze(ticker: str, period: str = "1y") -> Analysis:
    """Convenience: fetch + evaluate in one call."""
    df = get_data(ticker, period=period)
    currency = ""
    try:
        fi = yf.Ticker(ticker).fast_info
        currency = getattr(fi, "currency", "") or fi.get("currency", "")  # type: ignore
    except Exception:
        currency = ""
    return evaluate(df, ticker, currency=currency)
