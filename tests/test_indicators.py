"""Indicator math, checked against values worked out by hand."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_series_equal

import intraday
import signals


# --------------------------------------------------------------------------- RSI
def test_rsi_needs_a_full_period_before_it_has_a_value():
    rsi = signals.rsi(pd.Series(np.arange(1.0, 41.0)))
    assert rsi.iloc[:14].isna().all()
    assert rsi.iloc[14:].notna().all()


def test_rsi_is_100_when_price_only_rises_and_0_when_it_only_falls():
    rising = pd.Series(np.arange(1.0, 41.0))
    assert (signals.rsi(rising).iloc[14:] == 100).all()
    assert (signals.rsi(rising[::-1].reset_index(drop=True)).iloc[14:] == 0).all()


def test_rsi_sits_near_50_when_gains_and_losses_balance():
    alternating = pd.Series(100 + np.tile([1.0, -1.0], 50).cumsum())  # 101, 100, 101, 100, ...
    assert signals.rsi(alternating).iloc[-1] == pytest.approx(50, abs=5)


def test_rsi_stays_between_0_and_100():
    walk = pd.Series(100 + np.random.default_rng(0).normal(0, 1, 500).cumsum())
    values = signals.rsi(walk).dropna()
    assert values.between(0, 100).all()


def test_intraday_rsi_matches_daily_rsi():
    walk = pd.Series(100 + np.random.default_rng(1).normal(0, 1, 200).cumsum())
    assert_series_equal(intraday._rsi(walk), signals.rsi(walk))


# --------------------------------------------------------------------------- MACD
def test_macd_is_zero_for_a_flat_price():
    for series in signals.macd(pd.Series([50.0] * 100)):
        assert series.to_numpy() == pytest.approx(0.0, abs=1e-9)


def test_macd_settles_at_seven_times_the_slope_of_a_steady_ramp():
    # A 12-period EMA lags a ramp by 5.5 steps and a 26-period EMA by 12.5, so MACD -> 7 x slope.
    line, signal, hist = signals.macd(pd.Series(np.arange(300.0)))
    assert line.iloc[-1] == pytest.approx(7.0, abs=1e-6)
    assert signal.iloc[-1] == pytest.approx(7.0, abs=1e-6)
    assert hist.iloc[-1] == pytest.approx(0.0, abs=1e-6)


def test_macd_histogram_is_line_minus_signal():
    walk = pd.Series(100 + np.random.default_rng(2).normal(0, 1, 200).cumsum())
    line, signal, hist = signals.macd(walk)
    assert_series_equal(hist, line - signal)


def test_intraday_macd_matches_daily_macd():
    walk = pd.Series(100 + np.random.default_rng(3).normal(0, 1, 200).cumsum())
    for a, b in zip(intraday._macd(walk), signals.macd(walk)):
        assert_series_equal(a, b)


# --------------------------------------------------------------------------- Bollinger Bands
def test_bollinger_bands_on_1_to_20():
    middle, upper, lower = signals.bollinger(pd.Series(np.arange(1.0, 21.0)))
    std = np.sqrt(35.0)  # sample standard deviation of 1..20
    assert middle.iloc[-1] == pytest.approx(10.5)
    assert upper.iloc[-1] == pytest.approx(10.5 + 2 * std)
    assert lower.iloc[-1] == pytest.approx(10.5 - 2 * std)
    assert middle.iloc[:19].isna().all()


def test_bollinger_bands_collapse_for_a_flat_price():
    middle, upper, lower = signals.bollinger(pd.Series([20.0] * 30))
    assert (upper.dropna() == 20).all() and (lower.dropna() == 20).all()


# --------------------------------------------------------------------------- ATR
def _ohlc(rows):
    return pd.DataFrame(rows, columns=["High", "Low", "Close"], dtype=float)


def test_true_range_includes_gaps_from_the_previous_close():
    bars = _ohlc([(11, 9, 10), (15, 14, 14.5), (13, 12, 12.5)])
    true_range = intraday._atr(bars, period=1)  # with period 1, ATR is just the true range
    assert list(true_range) == [2.0, 5.0, 2.5]  # bar 2 gapped up from 10, bar 3 gapped down from 14.5


def test_atr_equals_the_bar_range_when_every_bar_is_the_same_size():
    bars = _ohlc([(101, 99, 100)] * 30)
    atr = intraday._atr(bars, period=14)
    assert atr.iloc[:13].isna().all()
    assert atr.iloc[13:].to_numpy() == pytest.approx(2.0)


# --------------------------------------------------------------------------- VWAP and resampling
def test_vwap_is_volume_weighted_and_resets_each_day():
    index = pd.DatetimeIndex(["2026-06-15 09:30", "2026-06-15 09:35", "2026-06-16 09:30"], tz="America/New_York")
    bars = pd.DataFrame(
        {"High": [11, 21, 31], "Low": [9, 19, 29], "Close": [10, 20, 30], "Volume": [100, 300, 50]},
        index=index, dtype=float,
    )
    vwap = intraday._session_vwap(bars)
    assert vwap.iloc[0] == pytest.approx(10.0)
    assert vwap.iloc[1] == pytest.approx((10 * 100 + 20 * 300) / 400)  # 17.5
    assert vwap.iloc[2] == pytest.approx(30.0)  # a new day starts fresh


def test_vwap_is_missing_until_there_is_volume():
    index = pd.DatetimeIndex(["2026-06-15 09:30", "2026-06-15 09:35"], tz="America/New_York")
    bars = pd.DataFrame({"High": [11, 11], "Low": [9, 9], "Close": [10, 10], "Volume": [0, 100]},
                        index=index, dtype=float)
    vwap = intraday._session_vwap(bars)
    assert np.isnan(vwap.iloc[0])
    assert vwap.iloc[1] == pytest.approx(10.0)


def test_resampling_1_minute_bars_into_3_minute_bars():
    index = pd.date_range("2026-06-15 09:30", periods=6, freq="1min", tz="America/New_York")
    bars = pd.DataFrame({
        "Open": [1, 2, 3, 4, 5, 6], "High": [10, 12, 11, 20, 22, 21],
        "Low": [0.5, 0.4, 0.6, 3, 2, 4], "Close": [2, 3, 4, 5, 6, 7], "Volume": [1, 2, 3, 4, 5, 6],
    }, index=index, dtype=float)
    out = intraday._resample(bars, "3min")
    assert len(out) == 2
    assert out.iloc[0].to_dict() == {"Open": 1, "High": 12, "Low": 0.4, "Close": 4, "Volume": 6}
    assert out.iloc[1].to_dict() == {"Open": 4, "High": 22, "Low": 2, "Close": 7, "Volume": 15}
