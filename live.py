"""
Market-aware last-price quotes, including pre-market and after-hours.

Sources, in order:
  - Pre-market / after-hours: Yahoo's pre/post-market price (Finnhub's free tier doesn't
    cover extended hours, but Yahoo does).
  - Regular session with a Finnhub key: Finnhub's real-time price.
  - Otherwise: Yahoo's regular price (delayed about 15 minutes) or the last close.

Every quote carries the market `state` (PRE/REGULAR/POST/CLOSED) and a label so the UI can
show the right badge ("🌙 AFTER-HOURS", "🔴 LIVE", etc.).

Kept separate from signals.py so the price feed can change without touching the indicator
logic.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
import yfinance as yf

FINNHUB_URL = "https://finnhub.io/api/v1/quote"

# Yahoo marketState  ->  (label, price field, %-change field)
_EXT = {
    "PRE":      ("Pre-market",  "preMarketPrice",  "preMarketChangePercent"),
    "PREPRE":   ("Pre-market",  "preMarketPrice",  "preMarketChangePercent"),
    "POST":     ("After-hours", "postMarketPrice", "postMarketChangePercent"),
    "POSTPOST": ("After-hours", "postMarketPrice", "postMarketChangePercent"),
}


@dataclass
class Quote:
    ticker: str
    price: float | None
    change: float | None        # change vs the relevant reference (prev/regular close)
    percent: float | None
    prev_close: float | None
    source: str
    realtime: bool
    state: str = ""             # PRE / REGULAR / POST / POSTPOST / CLOSED
    regular_price: float | None = None   # regular-session price, shown for reference


def _f(x):
    return float(x) if x is not None else None


def _finnhub_quote(ticker: str, api_key: str) -> Quote | None:
    """Finnhub free real-time quote (US, regular session only)."""
    try:
        r = requests.get(FINNHUB_URL, params={"symbol": ticker, "token": api_key}, timeout=6)
        r.raise_for_status()
        d = r.json()
        if not d.get("c"):           # c == 0 → symbol not covered
            return None
        return Quote(ticker.upper(), _f(d["c"]), _f(d.get("d")), _f(d.get("dp")),
                     _f(d.get("pc")), "Finnhub · real-time", True, state="REGULAR")
    except Exception:
        return None


def _yahoo_info(ticker: str) -> dict | None:
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return None


def get_live_quote(ticker: str, api_key: str | None = None) -> Quote | None:
    ticker = ticker.strip().upper()
    if not ticker:
        return None

    info = _yahoo_info(ticker) or {}
    state = info.get("marketState")
    regular = info.get("regularMarketPrice")

    # 1) Pre-market / after-hours: show the extended-hours price.
    if state in _EXT:
        label, pkey, pctkey = _EXT[state]
        price = info.get(pkey)
        if price:
            change = (price - regular) if regular else None
            return Quote(ticker, _f(price), change, _f(info.get(pctkey)),
                         regular, f"Yahoo · {label}", False,
                         state=state, regular_price=regular)
        # No extended trade yet → fall through to last close.

    # 2) Regular session: prefer Finnhub's real-time price.
    if state == "REGULAR" and api_key:
        q = _finnhub_quote(ticker, api_key)
        if q:
            q.regular_price = regular
            return q

    # 3) Yahoo regular / last close.
    if regular:
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        change = (regular - prev) if prev else None
        src = ("Yahoo · delayed ~15 min" if state == "REGULAR"
               else "Yahoo · market closed" if state == "CLOSED" else "Yahoo")
        return Quote(ticker, _f(regular), change, _f(info.get("regularMarketChangePercent")),
                     prev, src, False, state=state or "", regular_price=regular)

    # 4) Last resort.
    if api_key:
        q = _finnhub_quote(ticker, api_key)
        if q:
            return q
    return _yahoo_fastinfo(ticker)


def _yahoo_fastinfo(ticker: str) -> Quote | None:
    try:
        fi = yf.Ticker(ticker).fast_info
        price = getattr(fi, "last_price", None)
        prev = getattr(fi, "previous_close", None)
        if price is None:
            return None
        change = (price - prev) if prev else None
        pct = (change / prev * 100) if (change is not None and prev) else None
        return Quote(ticker.upper(), _f(price), _f(change), _f(pct), _f(prev),
                     "Yahoo · delayed ~15 min", False)
    except Exception:
        return None
