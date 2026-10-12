"""
history.py — a lightweight, persistent log of intraday verdict CHANGES.

Every time the live intraday verdict flips (e.g. HOLD → BUY), we stamp it with the
time and price and append it to verdict_history.json. We record CHANGES only (not
every 30-second refresh), keep the last 60 days, and key changes by (ticker,
timeframe) so switching timeframes doesn't manufacture phantom flips. UI-free,
like signals.py — so the same log can later feed alerts or a CLI.
"""

from __future__ import annotations

import datetime as dt
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verdict_history.json")
_KEEP_DAYS = 60


def _load() -> list[dict]:
    try:
        with open(_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(rows: list[dict]) -> None:
    # Write atomically (temp file + os.replace) so a reader — or the other writer, since both
    # the app and watch.py can log — never sees a half-written file. os.replace is atomic on Windows.
    try:
        tmp = _FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        os.replace(tmp, _FILE)
    except Exception:
        pass


def _parse(ts: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return dt.datetime.now()


def record_verdict(ticker: str, interval: str, verdict: str, price: float | None,
                   bar_high: float | None = None, bar_low: float | None = None) -> bool:
    """Log verdict flips AND track the high/low reached AFTER each verdict.

    Called on every refresh (from the app, and from the standalone watch.py logger):
      • If the verdict CHANGED → append a new row (time, verdict, price, hi, lo) and return True.
      • If the verdict is UNCHANGED → just extend the current row's running high/low with the
        latest price/bar so we capture how far it ran before the next flip, and return False.

    So once a new verdict fires, the previous row is frozen with the full range that occurred
    during its life — letting you see whether a BUY actually went up (and how far it dipped).
    Prunes to 60 days. `hi`/`lo` are None on rows logged before this feature existed.
    """
    ticker = (ticker or "").upper()
    if not ticker or not verdict:
        return False

    # Highest / lowest price observed this poll (real-time price plus the latest bar's range).
    obs = [float(v) for v in (price, bar_high, bar_low) if v is not None]
    cur_hi = max(obs) if obs else None
    cur_lo = min(obs) if obs else None

    rows = _load()
    last = next((r for r in reversed(rows)
                 if r.get("ticker") == ticker and r.get("interval") == interval), None)

    if last and last.get("verdict") == verdict:
        # Same verdict still in force → keep its running high/low up to date.
        if cur_hi is None:
            return False
        prev_hi, prev_lo = last.get("hi"), last.get("lo")
        new_hi = round(cur_hi if prev_hi is None else max(prev_hi, cur_hi), 2)
        new_lo = round(cur_lo if prev_lo is None else min(prev_lo, cur_lo), 2)
        if new_hi != prev_hi or new_lo != prev_lo:
            last["hi"], last["lo"] = new_hi, new_lo
            _save(rows)
        return False

    # Verdict changed (or first ever) → append a new row, seeding its high/low at "now".
    now = dt.datetime.now()
    rows.append({
        "ts": now.isoformat(timespec="seconds"),
        "ticker": ticker,
        "interval": interval,
        "verdict": verdict,
        "price": round(float(price), 2) if price is not None else None,
        "hi": round(cur_hi, 2) if cur_hi is not None else None,
        "lo": round(cur_lo, 2) if cur_lo is not None else None,
    })
    cutoff = now - dt.timedelta(days=_KEEP_DAYS)
    rows = [r for r in rows if _parse(r.get("ts", "")) >= cutoff]
    _save(rows)
    return True


def history(ticker: str, days: int = _KEEP_DAYS) -> list[dict]:
    """All recorded changes for `ticker` within the last `days`, oldest → newest."""
    ticker = (ticker or "").upper()
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    return [r for r in _load()
            if r.get("ticker") == ticker and _parse(r.get("ts", "")) >= cutoff]
