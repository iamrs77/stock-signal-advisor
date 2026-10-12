"""Position sizing and the daily trade log behind the max-daily-loss limit."""

import json

import pytest

import risk


def test_shares_are_sized_so_the_stop_loses_the_chosen_risk():
    # $10,000 account, 1% risk = $100. Entry 50, stop 48 = $2 a share, so 50 shares.
    size = risk.position_size(10_000, 1.0, 50.0, 48.0)
    assert size == {
        "shares": 50, "per_share": 2.0, "target_risk": 100.0,
        "risk_dollars": 100.0, "position_value": 2500.0, "capped": False,
    }


def test_shares_are_rounded_down_never_up():
    size = risk.position_size(10_000, 1.0, 50.0, 47.0)  # $100 / $3 = 33.3 shares
    assert size["shares"] == 33
    assert size["risk_dollars"] <= size["target_risk"]


def test_position_is_capped_at_what_the_account_can_afford():
    # A very tight stop would call for 1,000 shares, but $1,000 only buys 20 at $50.
    size = risk.position_size(1_000, 10.0, 50.0, 49.9)
    assert size["shares"] == 20
    assert size["capped"] is True


@pytest.mark.parametrize("account, entry, stop", [
    (0, 50.0, 48.0),       # no account
    (None, 50.0, 48.0),
    (10_000, None, 48.0),  # no entry
    (10_000, 50.0, None),  # no stop
    (10_000, 50.0, 50.0),  # stop not below entry (long-only)
    (10_000, 50.0, 52.0),
])
def test_invalid_inputs_return_none(account, entry, stop):
    assert risk.position_size(account, 1.0, entry, stop) is None


@pytest.fixture
def trade_log(tmp_path, monkeypatch):
    """Point the daily log at a temporary file instead of the real daily_risk.json."""
    path = tmp_path / "daily_risk.json"
    monkeypatch.setattr(risk, "_LOG", str(path))
    return path


def test_recorded_trades_are_saved_and_rounded(trade_log):
    risk.record_trade(-42.456)
    data = risk.record_trade(15)
    assert data["trades"] == [-42.46, 15.0]
    assert json.loads(trade_log.read_text())["trades"] == [-42.46, 15.0]


def test_the_log_starts_fresh_on_a_new_day(trade_log):
    trade_log.write_text(json.dumps({"date": "2000-01-01", "trades": [-500.0]}))
    assert risk.load_today()["trades"] == []


def test_reset_clears_todays_trades(trade_log):
    risk.record_trade(-100)
    assert risk.reset_today()["trades"] == []
    assert risk.load_today()["trades"] == []


def test_a_missing_or_corrupt_log_is_treated_as_empty(trade_log):
    assert risk.load_today()["trades"] == []
    trade_log.write_text("not json")
    assert risk.load_today()["trades"] == []


def test_a_store_keeps_the_log_out_of_the_file(trade_log):
    store = {}  # the public demo passes each visitor's session state here
    risk.record_trade(-25, store)
    assert risk.load_today(store)["trades"] == [-25.0]
    assert not trade_log.exists()
    assert risk.load_today()["trades"] == []
    assert risk.reset_today(store)["trades"] == []


def test_two_visitors_never_see_each_others_trades(trade_log):
    first_visitor, second_visitor = {}, {}
    risk.record_trade(-500, first_visitor)
    assert risk.load_today(second_visitor)["trades"] == []
