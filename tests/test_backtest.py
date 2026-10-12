"""Backtest statistics and both backtest engines, on generated price data."""

import math

import pandas as pd
import pytest

import backtest
import intraday
from conftest import daily_bars, intraday_bars


def _bars(n=3):
    return pd.DataFrame({"Close": [100.0, 105.0, 110.0][:n]}, index=pd.bdate_range("2026-01-05", periods=n))


def test_stats_from_three_hand_made_trades():
    trades = [{"ret": 0.10, "R": 1.0}, {"ret": -0.05, "R": -0.5}, {"ret": 0.20, "R": 2.0}]
    s = backtest._stats(trades, _bars(), "5m")
    assert s["trades"] == 3
    assert s["win_rate"] == pytest.approx(200 / 3)
    assert s["total_return"] == pytest.approx((1.10 * 0.95 * 1.20 - 1) * 100)  # 25.4%
    assert s["profit_factor"] == pytest.approx(0.30 / 0.05)
    assert s["expectancy_R"] == pytest.approx(2.5 / 3)
    assert s["avg_win"] == pytest.approx(15.0)
    assert s["avg_loss"] == pytest.approx(-5.0)
    assert s["max_drawdown"] == pytest.approx(-5.0)  # 1.10 down to 1.045
    assert s["curve"] == pytest.approx([1.0, 1.10, 1.045, 1.254])
    assert s["buy_hold"] == pytest.approx(10.0)


def test_stats_with_no_trades():
    s = backtest._stats([], _bars(), "5m")
    assert (s["trades"], s["win_rate"], s["total_return"], s["profit_factor"], s["max_drawdown"]) == (0, 0, 0, 0, 0)


def test_profit_factor_is_infinite_when_nothing_lost():
    s = backtest._stats([{"ret": 0.02, "R": 1.0}], _bars(), "5m")
    assert math.isinf(s["profit_factor"])


def test_long_term_backtest_holds_a_steady_uptrend(fake_yahoo):
    fake_yahoo(daily_bars(400, drift=0.003))
    s = backtest.run_backtest_lt("test")
    # Above its 200-day average the whole time: one entry, still open at the end.
    assert s["trades"] == 1
    assert s["trade_list"][0]["reason"] == "open (marked to last close)"
    assert s["total_return"] > 0


def test_long_term_backtest_needs_about_a_year_of_data(fake_yahoo):
    fake_yahoo(daily_bars(200))
    with pytest.raises(ValueError, match="Not enough daily history"):
        backtest.run_backtest_lt("test")


@pytest.fixture
def five_days_of_bars(monkeypatch):
    """Serve five sessions of generated 5-minute bars (with indicators) to the intraday backtest."""
    df = intraday._add_indicators(intraday_bars(days=5, drift=0.0002, seed=11))
    monkeypatch.setattr(intraday, "fetch_intraday", lambda *args, **kwargs: df)
    return df


def test_intraday_backtest_only_exits_by_stop_signal_or_end_of_day(five_days_of_bars):
    s = backtest.run_backtest("test", "5m", use_htf=False)
    assert s["trades"] == len(s["trade_list"])
    assert {t["reason"] for t in s["trade_list"]} <= {"stop", "signal", "end of day"}
    assert 0 <= s["win_rate"] <= 100


def test_intraday_backtest_takes_no_trades_against_a_daily_downtrend(five_days_of_bars, monkeypatch):
    days = {ts.date() for ts in five_days_of_bars.index}
    monkeypatch.setattr(intraday, "daily_trend_series", lambda ticker: {d: "down" for d in days})
    assert backtest.run_backtest("test", "5m", use_htf=True)["trades"] == 0


def test_intraday_backtest_needs_enough_bars(monkeypatch):
    short = intraday._add_indicators(intraday_bars(days=1)).head(30)
    monkeypatch.setattr(intraday, "fetch_intraday", lambda *args, **kwargs: short)
    with pytest.raises(ValueError, match="Not enough history"):
        backtest.run_backtest("test", "5m")
