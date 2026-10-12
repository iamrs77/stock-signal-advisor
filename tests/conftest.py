"""Shared test data. Prices are generated, so the tests need no internet connection or API keys."""

import numpy as np
import pandas as pd
import pytest


def daily_bars(n: int = 300, drift: float = 0.002, seed: int = 1, start: float = 100.0) -> pd.DataFrame:
    """Business-day OHLCV bars with a steady drift (positive for an uptrend) plus small noise."""
    rng = np.random.default_rng(seed)
    close = start * np.cumprod(1 + drift + rng.normal(0, 0.005, n))
    index = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame(
        {"Open": close * 0.999, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1_000_000},
        index=index,
    )


def intraday_bars(days: int = 2, drift: float = 0.0, seed: int = 2, start: float = 100.0) -> pd.DataFrame:
    """5-minute regular-session bars (9:30 to 16:00 New York time) for `days` sessions."""
    rng = np.random.default_rng(seed)
    parts = [
        pd.date_range(f"{day.date()} 09:30", f"{day.date()} 15:55", freq="5min", tz="America/New_York")
        for day in pd.bdate_range("2026-06-15", periods=days)
    ]
    index = parts[0].append(parts[1:]) if len(parts) > 1 else parts[0]
    close = start * np.cumprod(1 + drift + rng.normal(0, 0.001, len(index)))
    open_ = np.concatenate([[start], close[:-1]])
    return pd.DataFrame(
        {
            "Open": open_,
            "High": np.maximum(open_, close) * 1.001,
            "Low": np.minimum(open_, close) * 0.999,
            "Close": close,
            "Volume": rng.integers(1_000, 5_000, len(index)),
        },
        index=index,
    )


class FakeTicker:
    """Stands in for yfinance.Ticker and returns prepared bars from history()."""

    def __init__(self, bars: pd.DataFrame):
        self._bars = bars

    def history(self, *args, **kwargs) -> pd.DataFrame:
        return self._bars.copy()


@pytest.fixture
def fake_yahoo(monkeypatch):
    """Call fake_yahoo(bars) to make every yfinance.Ticker(...).history() return `bars`."""
    import yfinance

    def install(bars: pd.DataFrame) -> None:
        monkeypatch.setattr(yfinance, "Ticker", lambda *args, **kwargs: FakeTicker(bars))

    return install
