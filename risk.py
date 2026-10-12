"""
Money-management helpers for the intraday tab.

Two jobs, both about protecting the account:
  1. position_size(): how many shares to buy so that hitting the stop loses a fixed amount.
  2. A small daily trade log, so a "max daily loss" limit works without any broker
     integration. You log the result of each closed trade. It's saved to a JSON file, or to
     a dict you pass as `store` (the public demo passes each visitor's session state).

No UI code, so it can be reused and tested. Nothing here is financial advice.
"""

from __future__ import annotations

import datetime
import json
import os

_LOG = os.path.join(os.path.dirname(__file__), "daily_risk.json")


# --------------------------------------------------------------------------- #
# Position sizing
# --------------------------------------------------------------------------- #
def position_size(account: float | None, risk_pct: float, entry: float | None,
                  stop: float | None) -> dict | None:
    """Shares to buy so hitting the stop loses ~`risk_pct`% of the account.

    Also capped to what the account can actually afford (no margin assumed).
    Returns None if inputs are missing/invalid.
    """
    if not account or account <= 0 or not entry or not stop or entry <= stop:
        return None
    per_share = entry - stop                 # $ risk per share (entry to stop)
    target_risk = account * risk_pct / 100.0
    shares = int(target_risk // per_share)
    affordable = int(account // entry)
    capped = False
    if shares > affordable:
        shares, capped = affordable, True
    shares = max(shares, 0)
    return {
        "shares": shares,
        "per_share": per_share,
        "target_risk": target_risk,
        "risk_dollars": shares * per_share,
        "position_value": shares * entry,
        "capped": capped,
    }


# --------------------------------------------------------------------------- #
# Daily trade log (for the loss-limit guardrail)
# --------------------------------------------------------------------------- #
def _today() -> str:
    return datetime.date.today().isoformat()


_STORE_KEY = "daily_risk"


def _save(data: dict, store: dict | None = None) -> None:
    if store is not None:
        store[_STORE_KEY] = data
        return
    try:
        with open(_LOG, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_today(store: dict | None = None) -> dict:
    """Return today's log {date, trades:[pnl,...]}. Auto-resets on a new day."""
    try:
        if store is not None:
            data = store[_STORE_KEY]
        else:
            with open(_LOG) as f:
                data = json.load(f)
        if data.get("date") == _today():
            return data
    except Exception:
        pass
    return {"date": _today(), "trades": []}


def record_trade(pnl: float, store: dict | None = None) -> dict:
    data = load_today(store)
    data["trades"].append(round(float(pnl), 2))
    _save(data, store)
    return data


def reset_today(store: dict | None = None) -> dict:
    data = {"date": _today(), "trades": []}
    _save(data, store)
    return data
