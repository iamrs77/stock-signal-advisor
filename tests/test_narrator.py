"""Plain-English session summary, outlook and live metrics."""

import pytest

import intraday
import narrator
from conftest import intraday_bars


@pytest.fixture(scope="module")
def two_days():
    return intraday._add_indicators(intraday_bars(days=2, drift=0.0003, seed=5))


def test_day_summary_describes_only_the_latest_session(two_days):
    today = two_days[two_days.index.normalize() == two_days.index[-1].normalize()]
    s = narrator.day_summary(two_days)
    assert s["n_bars"] == len(today) == 78  # 5-minute bars from 9:30 to 15:55
    assert s["open"] == pytest.approx(today["Open"].iloc[0])
    assert s["high"] == pytest.approx(today["High"].max())
    assert s["low"] == pytest.approx(today["Low"].min())
    assert s["change_pct"] == pytest.approx((today["Close"].iloc[-1] / today["Open"].iloc[0] - 1) * 100)
    assert 0 <= s["pos_in_range"] <= 1
    assert [x["name"] for x in s["sessions"]] == ["Open", "Midday", "Power hour"]
    assert {x["word"] for x in s["sessions"]} <= {"rallied", "sold off", "chopped"}


def test_day_summary_needs_at_least_two_bars(two_days):
    assert narrator.day_summary(two_days.tail(1)) is None


def test_day_outlook_gives_a_bias_reasons_and_levels(two_days):
    o = narrator.day_outlook(two_days)
    assert o["bias"] in {"leaning bullish", "leaning bearish", "mixed — no clear edge"}
    assert -4 <= o["score"] <= 4
    assert len(o["reasons"]) == 4
    assert set(o["levels"]) == {"Prior-day high", "Prior-day low", "Close", "VWAP"}


@pytest.mark.parametrize("minutes_to_close, phase", [
    (360, "opening hour"), (200, "midday lull"), (100, "late session"), (60, "power hour"), (None, None),
])
def test_live_metrics_names_the_part_of_the_day(two_days, minutes_to_close, phase):
    assert narrator.live_metrics(two_days, minutes_to_close=minutes_to_close)["phase"] == phase


def test_live_metrics_sorts_price_levels_from_high_to_low(two_days):
    levels = narrator.live_metrics(two_days)["levels"]
    prices = [price for _, _, price in levels]
    assert prices == sorted(prices, reverse=True)
    assert {key for _, key, _ in levels} == {"res", "now", "sup", "vwap"}


def test_live_read_returns_labelled_sentences(two_days):
    read = narrator.live_read(two_days, headline="BUY", htf_trend="up", minutes_to_close=120)
    assert read
    assert all(isinstance(label, str) and isinstance(text, str) and text for label, text in read)
