"""Long-term (daily) data loading and verdicts."""

import pandas as pd
import pytest

import signals
from conftest import daily_bars


def test_get_data_adds_every_indicator_column(fake_yahoo):
    fake_yahoo(daily_bars(300))
    df = signals.get_data("aapl")
    for column in ["SMA20", "SMA50", "SMA200", "RSI", "MACD", "MACD_SIGNAL", "MACD_HIST",
                   "BB_MID", "BB_UPPER", "BB_LOWER"]:
        assert column in df
    assert df["SMA200"].iloc[-1] == pytest.approx(df["Close"].tail(200).mean())


def test_get_data_rejects_a_blank_ticker():
    with pytest.raises(ValueError, match="ticker"):
        signals.get_data("   ")


def test_get_data_explains_an_unknown_ticker(fake_yahoo):
    fake_yahoo(pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]))
    with pytest.raises(ValueError, match=r"\.TO"):
        signals.get_data("NOPE")


def _analyze(fake_yahoo, bars):
    fake_yahoo(bars)
    return signals.evaluate(signals.get_data("test"), "test")


def test_uptrend_above_the_200_day_average_is_a_buy(fake_yahoo):
    a = _analyze(fake_yahoo, daily_bars(300, drift=0.003))
    assert a.verdict == "BUY"
    assert a.ticker == "TEST"
    regime = next(s for s in a.signals if s.name == "Trend regime (200-day)")
    assert regime.direction == "bullish"
    assert a.price > a.df["SMA200"].iloc[-1]


def test_downtrend_below_the_200_day_average_is_a_sell(fake_yahoo):
    a = _analyze(fake_yahoo, daily_bars(300, drift=-0.003))
    assert a.verdict == "SELL"
    regime = next(s for s in a.signals if s.name == "Trend regime (200-day)")
    assert regime.direction == "bearish"


def test_short_history_falls_back_to_the_weighted_score(fake_yahoo):
    a = _analyze(fake_yahoo, daily_bars(120, drift=0.003))  # under 200 days: no 200-day average yet
    assert not any(s.name == "Trend regime (200-day)" for s in a.signals)
    assert next(s for s in a.signals if s.name == "Long-term trend").direction == "neutral"
    assert a.verdict == ("BUY" if a.score >= 2 else "SELL" if a.score <= -2 else "HOLD")


def test_score_is_the_sum_of_signed_signal_weights(fake_yahoo):
    a = _analyze(fake_yahoo, daily_bars(300, drift=0.001, seed=7))
    signed = {"bullish": 1, "bearish": -1, "neutral": 0}
    assert a.score == sum(signed[s.direction] * s.weight for s in a.signals)
    assert a.max_score == sum(s.weight for s in a.signals if s.direction != "neutral")
    assert 0 <= a.confidence <= 100


def test_strong_label_needs_a_score_of_at_least_four(fake_yahoo):
    for drift in (0.003, -0.003):
        a = _analyze(fake_yahoo, daily_bars(300, drift=drift))
        assert a.headline == (f"Strong {a.verdict}" if abs(a.score) >= 4 else a.verdict)
