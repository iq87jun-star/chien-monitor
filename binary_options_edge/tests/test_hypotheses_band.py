"""h_point_band(価格帯フィルタ)のテスト。"""
from datetime import datetime, timedelta, timezone

from binary_options_edge.data import BinaryContract
from binary_options_edge.hypotheses import h_combine, h_point_band


def _c(bid, ask):
    t = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    return BinaryContract(pair="USDJPY", option_type="ladder_above",
                          decision_time=t, expiry_time=t + timedelta(hours=2),
                          spot_at_decision=150.0, bid=bid, ask=ask,
                          strike=150.3, lower=None, upper=None, settled_yes=None)


def test_band_accepts_inside_and_mirror():
    f = h_point_band(7, 25)
    assert f(_c(12, 18), None)          # mid=15: 帯内
    assert f(_c(82, 88), None)          # mid=85: 鏡像帯(75-93)
    assert not f(_c(47, 53), None)      # mid=50: ATMは除外


def test_band_asymmetric():
    f = h_point_band(40, 60, symmetric=False)
    assert f(_c(47, 53), None)
    assert not f(_c(12, 18), None)


def test_band_composes_with_other_filters():
    f = h_combine(h_point_band(7, 25), lambda c, ctx: c.pair == "USDJPY")
    assert f(_c(12, 18), None)
