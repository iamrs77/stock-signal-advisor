"""Intraday verdict rules, tested on small frames with hand-picked indicator values."""

import numpy as np
import pandas as pd
import pytest

import intraday
from conftest import intraday_bars

# A steady bullish setup: price above VWAP and the 9-EMA, 9-EMA above 21-EMA, MACD above its signal.
BULLISH = dict(Open=100.0, High=100.5, Low=99.5, Close=100.0, Volume=1000.0,
               VWAP=99.0, EMA9=99.8, EMA21=99.5, MACD=0.2, MACD_SIGNAL=0.1, MACD_HIST=0.1,
               RSI=55.0, ATR=1.0)
# The mirror image.
BEARISH = dict(BULLISH, Close=98.0, EMA9=99.5, EMA21=99.8, MACD=0.1, MACD_SIGNAL=0.2, MACD_HIST=-0.1)


def frame(base=BULLISH, last=None, bars=5, **changes):
    """`bars` identical bars from `base` plus `changes`; `last` overrides values on the final bar only."""
    rows = [dict(base, **changes) for _ in range(bars)]
    if last:
        rows[-1].update(last)
    index = pd.date_range("2026-06-15 10:00", periods=bars, freq="5min", tz="America/New_York")
    return pd.DataFrame(rows, index=index)


def evaluate(df, **kwargs):
    return intraday.evaluate_intraday(df, "test", "5m", **kwargs)


def signal(analysis, name):
    return next(s for s in analysis.signals if s.name == name)


def test_all_bullish_signals_give_a_strong_buy():
    a = evaluate(frame())
    assert (a.verdict, a.strength, a.score) == ("BUY", "Strong ", 5)
    assert a.headline == "Strong BUY"
    assert a.ticker == "TEST"


def test_all_bearish_signals_give_a_strong_sell():
    a = evaluate(frame(BEARISH))
    assert (a.verdict, a.strength, a.score) == ("SELL", "Strong ", -5)


def test_a_fresh_ema_crossover_counts_double():
    a = evaluate(frame(EMA9=99.4, last={"EMA9": 99.8}))  # 9-EMA was below the 21-EMA, now above
    assert signal(a, "EMA 9/21").weight == 2
    assert signal(a, "EMA 9/21").direction == "bullish"


def test_a_fresh_macd_crossover_counts_double():
    a = evaluate(frame(BEARISH, MACD=0.3, last={"MACD": 0.1}))  # MACD was above its signal, now below
    assert signal(a, "MACD").weight == 2
    assert signal(a, "MACD").direction == "bearish"


def test_rsi_extremes_add_a_point_against_the_move():
    assert signal(evaluate(frame(RSI=80.0)), "RSI").direction == "bearish"
    assert signal(evaluate(frame(RSI=20.0)), "RSI").direction == "bullish"
    assert signal(evaluate(frame(RSI=50.0)), "RSI").direction == "neutral"


def test_a_mixed_read_next_to_vwap_says_wait():
    # +2 above VWAP, -1 EMAs, -1 below the 9-EMA, +1 MACD = +1 (HOLD), and price is within 0.25 ATR of VWAP.
    a = evaluate(frame(Close=99.1, EMA9=99.5, EMA21=99.8))
    assert a.score == 1
    assert a.verdict == "WAIT"
    assert "VWAP" in signal(a, "Conditions").detail


def test_conflicting_strong_signals_say_wait():
    # Above VWAP (+2 strong bullish) while MACD just crossed down (-2 strong bearish).
    a = evaluate(frame(MACD=0.3, last={"MACD": 0.05}))
    assert a.score == 2
    assert a.verdict == "WAIT"
    assert "conflict" in signal(a, "Conditions").detail


def test_a_daily_downtrend_blocks_a_buy():
    a = evaluate(frame(), htf_trend="down")
    assert a.verdict == "HOLD"
    assert signal(a, "Higher-timeframe trend").direction == "bearish"


def test_a_daily_uptrend_keeps_the_buy():
    a = evaluate(frame(), htf_trend="up")
    assert a.verdict == "BUY"
    assert signal(a, "Higher-timeframe trend").direction == "bullish"


def test_stop_and_targets_are_set_from_atr():
    a = evaluate(frame(ATR=2.0))
    assert (a.stop, a.target1, a.target2) == (pytest.approx(97.0), pytest.approx(103.0), pytest.approx(106.0))
    assert a.atr_pct == pytest.approx(2.0)


def test_a_live_price_replaces_the_last_close():
    a = evaluate(frame(), live_price=101.0)
    assert a.using_live_price
    assert a.price == 101.0
    assert a.stop == pytest.approx(99.5)


def test_agreement_is_not_100_percent_when_only_one_signal_is_available():
    sparse = frame(EMA9=np.nan, EMA21=np.nan, MACD=np.nan, MACD_SIGNAL=np.nan, RSI=np.nan)
    a = evaluate(sparse)
    assert (a.score, a.max_score) == (2, 2)
    assert a.confidence == 40  # 2 out of a floor of 5, not 2 out of 2


def test_fetch_intraday_adds_indicators_to_downloaded_bars(fake_yahoo):
    bars = intraday_bars(days=2)
    fake_yahoo(bars)
    df = intraday.fetch_intraday("test", "5m")
    for column in ["EMA9", "EMA21", "RSI", "MACD", "MACD_SIGNAL", "MACD_HIST", "ATR", "VWAP"]:
        assert column in df
    first_of_day_two = df[df.index.normalize() == df.index[-1].normalize()].iloc[0]
    typical = (first_of_day_two["High"] + first_of_day_two["Low"] + first_of_day_two["Close"]) / 3
    assert first_of_day_two["VWAP"] == pytest.approx(typical)  # VWAP restarts each session
    assert evaluate(df).verdict in {"BUY", "SELL", "HOLD", "WAIT"}


def test_fetch_intraday_fails_clearly_without_data(fake_yahoo):
    fake_yahoo(pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]))
    with pytest.raises(ValueError, match="No intraday data"):
        intraday.fetch_intraday("test", "5m")
