"""
alpaca_data.py — real-time intraday bars from Alpaca's FREE IEX feed.

Yahoo's intraday bars can lag ~15 min; Alpaca's IEX feed is real-time, so the live
indicators (VWAP/EMA/RSI/MACD) finally match the live price. Plain REST via `requests`
(no SDK). Free with any Alpaca account (a paper account is fine).

Caveat: the free feed is IEX-only volume (a subset of the whole market), so VWAP is a
bit less complete than full-market data — but it's real-time, which is the point.
Returns a regular-session OHLCV frame (ET index) or None; callers fall back to Yahoo.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import requests

_URL = "https://data.alpaca.markets/v2/stocks/{sym}/bars"
_TF = {"1m": "1Min", "2m": "2Min", "3m": "3Min", "5m": "5Min", "15m": "15Min", "30m": "30Min"}


def fetch_bars(ticker: str, interval: str, api_key: str, secret_key: str, days: int = 5) -> pd.DataFrame | None:
    tf = _TF.get(interval, "5Min")
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    params = {"timeframe": tf, "start": start, "feed": "iex", "limit": 10000, "adjustment": "raw"}
    r = requests.get(_URL.format(sym=ticker), headers=headers, params=params, timeout=10)
    r.raise_for_status()
    bars = r.json().get("bars") or []
    if not bars:
        return None
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York")
    df = df.set_index("t").rename(columns={"o": "Open", "h": "High", "l": "Low",
                                           "c": "Close", "v": "Volume"})
    df = df.between_time("09:30", "16:00")          # regular session only (match Yahoo/backtest)
    return df[["Open", "High", "Low", "Close", "Volume"]] if not df.empty else None


def fetch_bars_history(ticker: str, interval: str, api_key: str, secret_key: str,
                       days: int = 365, feed: str = "iex") -> pd.DataFrame | None:
    """Paginated historical bars — follows Alpaca's `next_page_token`, so a FULL year of
    intraday data comes back instead of just the first 10k-bar page (the limitation that
    made the plain `fetch_bars` return ~1 month for a year-long 15m request). Split-adjusted,
    regular-session ET frame, or None. Powers the 'Know your ticker' microstructure profile."""
    tf = _TF.get(interval, "15Min")
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    rows, token = [], None
    for _ in range(60):                              # safety cap on pages
        params = {"timeframe": tf, "start": start, "feed": feed,
                  "limit": 10000, "adjustment": "split"}
        if token:
            params["page_token"] = token
        r = requests.get(_URL.format(sym=ticker), headers=headers, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        rows += j.get("bars") or []
        token = j.get("next_page_token")
        if not token:
            break
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York")
    df = df.set_index("t").rename(columns={"o": "Open", "h": "High", "l": "Low",
                                           "c": "Close", "v": "Volume"})
    df = df.between_time("09:30", "16:00")
    return df[["Open", "High", "Low", "Close", "Volume"]] if not df.empty else None
