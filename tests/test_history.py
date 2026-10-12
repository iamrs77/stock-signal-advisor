"""The verdict-change log shared by the app and watch.py."""

import datetime as dt
import json

import pytest

import history


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    """Point the log at a temporary file instead of the real verdict_history.json."""
    path = tmp_path / "verdict_history.json"
    monkeypatch.setattr(history, "_FILE", str(path))
    return path


def rows(path):
    return json.loads(path.read_text())


def test_the_first_verdict_is_logged(log_file):
    assert history.record_verdict("soxl", "5m", "BUY", 100.0) is True
    (row,) = rows(log_file)
    assert (row["ticker"], row["interval"], row["verdict"], row["price"]) == ("SOXL", "5m", "BUY", 100.0)


def test_an_unchanged_verdict_only_updates_the_running_high_and_low(log_file):
    history.record_verdict("SOXL", "5m", "BUY", 100.0)
    assert history.record_verdict("SOXL", "5m", "BUY", 103.0, bar_high=104.0, bar_low=99.0) is False
    (row,) = rows(log_file)
    assert (row["hi"], row["lo"]) == (104.0, 99.0)
    assert row["price"] == 100.0  # the entry price stays as it was


def test_a_flip_adds_a_new_row(log_file):
    history.record_verdict("SOXL", "5m", "BUY", 100.0)
    assert history.record_verdict("SOXL", "5m", "SELL", 98.0) is True
    assert [r["verdict"] for r in rows(log_file)] == ["BUY", "SELL"]


def test_each_timeframe_is_tracked_separately(log_file):
    history.record_verdict("SOXL", "5m", "BUY", 100.0)
    assert history.record_verdict("SOXL", "15m", "BUY", 100.0) is True  # first verdict on 15m
    assert history.record_verdict("SOXL", "5m", "BUY", 101.0) is False  # 5m is unchanged


def test_history_returns_one_ticker_oldest_first(log_file):
    history.record_verdict("SOXL", "5m", "BUY", 100.0)
    history.record_verdict("TQQQ", "5m", "SELL", 50.0)
    history.record_verdict("SOXL", "5m", "HOLD", 101.0)
    assert [r["verdict"] for r in history.history("soxl")] == ["BUY", "HOLD"]


def test_entries_older_than_60_days_are_dropped(log_file):
    old = (dt.datetime.now() - dt.timedelta(days=61)).isoformat(timespec="seconds")
    log_file.write_text(json.dumps([{"ts": old, "ticker": "OLD", "interval": "5m", "verdict": "BUY",
                                     "price": 1.0, "hi": 1.0, "lo": 1.0}]))
    history.record_verdict("SOXL", "5m", "BUY", 100.0)
    assert [r["ticker"] for r in rows(log_file)] == ["SOXL"]


def test_blank_ticker_or_verdict_is_ignored(log_file):
    assert history.record_verdict("", "5m", "BUY", 100.0) is False
    assert history.record_verdict("SOXL", "5m", "", 100.0) is False
    assert not log_file.exists()
