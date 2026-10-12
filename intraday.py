"""
Fast intraday signals, tuned for volatile tickers like SOXL.

The short-timeframe counterpart to signals.py. signals.py judges the long-term picture
(50/200-day averages); this module judges the current session on minute bars, using the
indicators day traders watch:

  - VWAP: the session's volume-weighted average price, the main intraday reference
  - EMA 9 / 21: fast trend and crossovers
  - RSI / MACD: momentum on intraday bars
  - ATR: volatility, used for automatic stop-loss and profit targets

The "price vs VWAP / EMA" checks accept a real-time price (from live.py / Finnhub), so
they react straight away even when the bars are slightly delayed.

Nothing here is financial advice. Day trading a 3x leveraged ETF is very high risk, and
the suggested stop and target levels are illustrative risk math, not trade calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

# interval -> how much history to pull (enough bars for EMA21/MACD, capped by Yahoo limits)
_PERIOD = {"1m": "1d", "2m": "2d", "3m": "2d", "5m": "5d", "15m": "5d", "30m": "1mo", "60m": "1mo"}

# Yahoo has no native 3-minute interval, so we build it by resampling 1m bars.
# interval -> (interval to fetch, pandas resample rule)
_RESAMPLE = {"3m": ("1m", "3min")}


# --------------------------------------------------------------------------- #
# Indicator math
# --------------------------------------------------------------------------- #
def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(s: pd.Series, period: int = 14) -> pd.Series:
    d = s.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    al = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = ag / al
    return 100 - (100 / (1 + rs))


def _macd(s: pd.Series, fast=12, slow=26, signal=9):
    m = _ema(s, fast) - _ema(s, slow)
    sig = _ema(m, signal)
    return m, sig, m - sig


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    """Running VWAP anchored per trading day (resets each session). Computed for every
    day in the frame so backtests get a valid VWAP too."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"]
    days = df.index.normalize()
    cum_v = vol.groupby(days).cumsum().replace(0, np.nan)
    return (tp * vol).groupby(days).cumsum() / cum_v


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate finer bars into a coarser interval (e.g. 1m -> 3m)."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["Close"])


def _yahoo_raw(ticker: str, interval: str, period: str | None) -> pd.DataFrame | None:
    period = period or _PERIOD.get(interval, "5d")
    if interval in _RESAMPLE:                       # synthesise 3m from 1m bars
        base_iv, rule = _RESAMPLE[interval]
        raw = yf.Ticker(ticker).history(period=period, interval=base_iv,
                                        prepost=False, auto_adjust=False)
        if raw is None or raw.empty:
            return None
        return _resample(raw.dropna(subset=["Close"]), rule)
    return yf.Ticker(ticker).history(period=period, interval=interval,
                                     prepost=False, auto_adjust=False)


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Close"]).copy()
    df["EMA9"] = _ema(df["Close"], 9)
    df["EMA21"] = _ema(df["Close"], 21)
    df["RSI"] = _rsi(df["Close"], 14)
    df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = _macd(df["Close"])
    df["ATR"] = _atr(df, 14)
    df["VWAP"] = _session_vwap(df)
    return df


def fetch_intraday(ticker: str, interval: str = "5m", period: str | None = None,
                   alpaca: tuple | None = None) -> pd.DataFrame:
    """Intraday bars + indicators. Uses Alpaca's real-time IEX feed when `alpaca`
    (key, secret) is supplied. Otherwise, or if Alpaca fails, falls back to Yahoo."""
    ticker = ticker.strip().upper()
    raw = None
    if alpaca and alpaca[0] and alpaca[1]:
        try:
            import alpaca_data
            raw = alpaca_data.fetch_bars(ticker, interval, alpaca[0], alpaca[1])
        except Exception:
            raw = None
    if raw is None or raw.empty:
        raw = _yahoo_raw(ticker, interval, period)
    if raw is None or raw.empty:
        raise ValueError(f"No intraday data for '{ticker}' at {interval}.")
    return _add_indicators(raw)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    name: str
    direction: str            # bullish | bearish | neutral
    weight: float
    detail: str


@dataclass
class IntradayAnalysis:
    ticker: str
    interval: str
    price: float
    using_live_price: bool
    last_bar_time: str
    verdict: str
    strength: str
    score: float
    max_score: float
    confidence: int
    atr: float | None
    atr_pct: float | None
    stop: float | None
    target1: float | None
    target2: float | None
    signals: list = field(default_factory=list)
    snapshot: dict = field(default_factory=dict)
    df: pd.DataFrame | None = None

    @property
    def headline(self) -> str:
        return f"{self.strength}{self.verdict}".strip()


def _nz(x) -> bool:
    return x is not None and not (isinstance(x, float) and np.isnan(x))


def daily_trend(ticker: str) -> str | None:
    """Current higher-timeframe (daily) trend: 'up' if the 20-day EMA is above the
    50-day EMA, else 'down'. Used to avoid buying against the bigger tide."""
    try:
        c = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)["Close"]
        if len(c) < 50:
            return None
        e20 = c.ewm(span=20, adjust=False).mean().iloc[-1]
        e50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
        return "up" if e20 > e50 else "down"
    except Exception:
        return None


def daily_trend_series(ticker: str) -> dict:
    """Per-date daily trend for backtests, shifted one day so a day's intraday bars
    only use the trend known at the prior daily close (no look-ahead)."""
    try:
        c = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)["Close"]
        e20 = c.ewm(span=20, adjust=False).mean()
        e50 = c.ewm(span=50, adjust=False).mean()
        up = (e20 > e50).shift(1)
        return {ts.date(): ("up" if bool(v) else "down") for ts, v in up.items() if pd.notna(v)}
    except Exception:
        return {}


def evaluate_intraday(df: pd.DataFrame, ticker: str, interval: str, live_price: float | None = None,
                      htf_trend: str | None = None) -> IntradayAnalysis:
    last = df.iloc[-1]
    using_live = live_price is not None and live_price > 0
    price = float(live_price) if using_live else float(last["Close"])
    signals: list[Signal] = []

    def add(name, direction, weight, detail):
        signals.append(Signal(name, direction, weight, detail))

    # 1) Price vs VWAP: the core intraday bias (heaviest weight).
    vwap = last["VWAP"]
    if _nz(vwap):
        if price > vwap:
            add("Price vs VWAP", "bullish", 2,
                f"Price {price:,.2f} is ABOVE VWAP {vwap:,.2f} — buyers control the session.")
        else:
            add("Price vs VWAP", "bearish", 2,
                f"Price {price:,.2f} is BELOW VWAP {vwap:,.2f} — sellers control the session.")

    # 2) EMA 9 vs EMA 21: fast trend and crossovers.
    e9, e21 = last["EMA9"], last["EMA21"]
    if _nz(e9) and _nz(e21):
        recent = df.tail(4)
        up = (recent["EMA9"].shift(1) <= recent["EMA21"].shift(1)) & (recent["EMA9"] > recent["EMA21"])
        dn = (recent["EMA9"].shift(1) >= recent["EMA21"].shift(1)) & (recent["EMA9"] < recent["EMA21"])
        if up.any():
            add("EMA 9/21", "bullish", 2, "EMA 9 just crossed ABOVE EMA 21 — fresh upward momentum.")
        elif dn.any():
            add("EMA 9/21", "bearish", 2, "EMA 9 just crossed BELOW EMA 21 — fresh downward momentum.")
        elif e9 > e21:
            add("EMA 9/21", "bullish", 1, "EMA 9 above EMA 21 — short-term uptrend intact.")
        else:
            add("EMA 9/21", "bearish", 1, "EMA 9 below EMA 21 — short-term downtrend intact.")

    # 3) Price vs EMA 9: immediate momentum.
    if _nz(e9):
        if price > e9:
            add("Price vs EMA 9", "bullish", 1, f"Price is above the 9-EMA ({e9:,.2f}) — pushing up.")
        else:
            add("Price vs EMA 9", "bearish", 1, f"Price is below the 9-EMA ({e9:,.2f}) — pulling back.")

    # 4) MACD: momentum and fresh crossovers.
    m, sg = last["MACD"], last["MACD_SIGNAL"]
    if _nz(m) and _nz(sg):
        recent = df.tail(4)
        up = (recent["MACD"].shift(1) <= recent["MACD_SIGNAL"].shift(1)) & (recent["MACD"] > recent["MACD_SIGNAL"])
        dn = (recent["MACD"].shift(1) >= recent["MACD_SIGNAL"].shift(1)) & (recent["MACD"] < recent["MACD_SIGNAL"])
        if up.any():
            add("MACD", "bullish", 2, "MACD crossed above its signal line — momentum turning up.")
        elif dn.any():
            add("MACD", "bearish", 2, "MACD crossed below its signal line — momentum turning down.")
        elif m > sg:
            add("MACD", "bullish", 1, "MACD above its signal line.")
        else:
            add("MACD", "bearish", 1, "MACD below its signal line.")

    # 5) RSI: intraday overbought / oversold.
    r = last["RSI"]
    if _nz(r):
        if r < 30:
            add("RSI", "bullish", 1, f"RSI {r:.0f} — oversold, bounce risk.")
        elif r > 70:
            add("RSI", "bearish", 1, f"RSI {r:.0f} — overbought, pullback risk.")
        else:
            add("RSI", "neutral", 0, f"RSI {r:.0f} — neutral.")

    # ---- aggregate into a signed score ----
    score = sum(s.weight if s.direction == "bullish"
                else -s.weight if s.direction == "bearish" else 0
                for s in signals)
    max_score = sum(s.weight for s in signals if s.direction != "neutral") or 1
    # Agreement = net score vs participating weight, but floored at 5 (the weight of the four
    # core signals) so a sparse read, e.g. only 1-2 signals available at the open, can't show
    # a misleading 100%.
    confidence = int(round(min(abs(score) / max(max_score, 5), 1.0) * 100))
    a = last["ATR"] if _nz(last["ATR"]) else None
    atr_pct = (a / price * 100) if a else None

    # ---- directional verdict on a 5-point scale ----
    if score >= 5:
        verdict, strength = "BUY", "Strong "
    elif score >= 2:
        verdict, strength = "BUY", ""
    elif score <= -5:
        verdict, strength = "SELL", "Strong "
    elif score <= -2:
        verdict, strength = "SELL", ""
    else:
        verdict, strength = "HOLD", ""

    # ---- chop / no-trade gate: don't trade intraday noise ----
    near_vwap = bool(a) and _nz(vwap) and abs(price - vwap) < 0.25 * a
    flat_emas = bool(a) and _nz(e9) and _nz(e21) and abs(e9 - e21) < 0.20 * a
    strong_bull = any(s.direction == "bullish" and s.weight >= 2 for s in signals)
    strong_bear = any(s.direction == "bearish" and s.weight >= 2 for s in signals)
    if strong_bull and strong_bear and abs(score) < 5:
        verdict, strength = "WAIT", ""
        add("Conditions", "neutral", 0,
            "Major signals conflict — a strong bullish and a strong bearish read at the same time. "
            "Low reliability; better to stand aside.")
    elif verdict == "HOLD" and (near_vwap or flat_emas):
        bits = []
        if near_vwap:
            bits.append("price is hugging VWAP")
        if flat_emas:
            bits.append("the EMAs are flat / tangled")
        verdict, strength = "WAIT", ""
        add("Conditions", "neutral", 0,
            "Choppy, rangebound tape — " + " and ".join(bits) + ". No clean setup; better to wait.")

    # ---- higher-timeframe trend filter (long-only): don't buy against the daily trend ----
    if htf_trend == "down" and verdict == "BUY":
        verdict, strength = "HOLD", ""
        add("Higher-timeframe trend", "bearish", 0,
            "Daily trend is DOWN — long blocked. Don't fight the bigger trend.")
    elif htf_trend == "up" and verdict == "BUY":
        add("Higher-timeframe trend", "bullish", 0,
            "Daily trend is UP — this long is aligned with the bigger trend.")

    # ---- ATR-based long levels (user trades long-only: stop below, profit targets above) ----
    stop = t1 = t2 = None
    if a:
        stop, t1, t2 = price - 1.5 * a, price + 1.5 * a, price + 3 * a

    snapshot = {
        "Price": f"{price:,.2f}",
        "VWAP": f"{vwap:,.2f}" if _nz(vwap) else "n/a",
        "EMA 9": f"{e9:,.2f}" if _nz(e9) else "n/a",
        "EMA 21": f"{e21:,.2f}" if _nz(e21) else "n/a",
        "RSI": f"{r:.0f}" if _nz(r) else "n/a",
        "ATR": f"{a:,.2f}" if a else "n/a",
    }

    tz = getattr(df.index[-1], "tzinfo", None)
    last_bar = df.index[-1].strftime("%b %d, %I:%M %p") + (f" {df.index[-1].tzname()}" if tz else "")

    return IntradayAnalysis(
        ticker=ticker.upper(), interval=interval, price=price, using_live_price=using_live,
        last_bar_time=last_bar, verdict=verdict, strength=strength, score=score,
        max_score=max_score, confidence=confidence, atr=a, atr_pct=atr_pct,
        stop=stop, target1=t1, target2=t2, signals=signals, snapshot=snapshot, df=df,
    )


def analyze_intraday(ticker: str, interval: str = "5m",
                     live_price: float | None = None) -> IntradayAnalysis:
    df = fetch_intraday(ticker, interval)
    return evaluate_intraday(df, ticker, interval, live_price=live_price)
