"""observation.py の判定ロジックのテスト。"""
from datetime import datetime

from binary_options_edge import observation, theory
from binary_options_edge.pricing import prob_finish_above


def _snap(**kw):
    base = dict(
        timestamp=datetime(2026, 8, 7, 20, 30),
        expiry=datetime(2026, 8, 7, 22, 0),
        pair="USDJPY", spot=150.0, option_type="ladder_above",
        level=150.35, bid=4.0, ask=10.0, halted=False, hypothesis="H3",
        sigma_ann=0.10, jump_std_log=0.003,
        sigma_trailing_ann=0.06, sigma_seasonal_ann=0.16)
    base.update(kw)
    return observation.Snapshot(**base)


def test_h3_halted_is_rejected():
    v = observation.evaluate(_snap(bid=None, ask=None, halted=True))
    assert v.status == "棄却" and "提示停止" in v.reason


def test_h3_wide_spread_is_rejected():
    v = observation.evaluate(_snap(bid=30.0, ask=50.0))
    assert v.status == "棄却" and "スプレッド" in v.reason


def test_h3_diffusion_priced_mid_survives():
    s = _snap()
    p_diff = prob_finish_above(s.spot, s.level, s.sigma_ann, s.ttm_seconds)
    mid = p_diff * 100.0
    v = observation.evaluate(_snap(bid=mid - 2.0, ask=mid + 2.0))
    assert v.status == "生存"


def test_h3_jump_priced_mid_is_rejected():
    s = _snap()
    st_eff = theory.effective_horizon_sigma(s.sigma_ann, s.ttm_seconds, s.jump_std_log)
    sigma_eff = st_eff / theory.horizon_sigma(1.0, s.ttm_seconds)
    mid = prob_finish_above(s.spot, s.level, sigma_eff, s.ttm_seconds) * 100.0
    v = observation.evaluate(_snap(bid=mid - 2.0, ask=mid + 2.0))
    assert v.status == "棄却" and "織り込み済み" in v.reason


def test_h2_seasonal_mid_rejected_trailing_mid_survives():
    s = _snap(hypothesis="H2", level=150.25)
    p_seas = prob_finish_above(s.spot, s.level, s.sigma_seasonal_ann, s.ttm_seconds)
    v = observation.evaluate(_snap(hypothesis="H2", level=150.25,
                                   bid=p_seas * 100 - 2, ask=p_seas * 100 + 2))
    assert v.status == "棄却" and "カレンダー実装済み" in v.reason
    p_trail = prob_finish_above(s.spot, s.level, s.sigma_trailing_ann, s.ttm_seconds)
    v2 = observation.evaluate(_snap(hypothesis="H2", level=150.25,
                                    bid=p_trail * 100 - 2, ask=p_trail * 100 + 2))
    assert v2.status == "生存"


def test_template_csv_loads_and_reports(capsys):
    snaps = observation.load_csv("binary_options_edge/observations_template.csv")
    assert len(snaps) == 3
    observation.report(snaps)
    out = capsys.readouterr().out
    assert "判定レポート" in out and "集計" in out
