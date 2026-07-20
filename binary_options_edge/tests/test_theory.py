"""theory.py の健全性テスト。"""
from math import exp, pi, sqrt

import pytest

from binary_options_edge import theory


def test_atm_ladder_is_vol_neutral():
    assert theory.ladder_vol_sensitivity(0.0) == 0.0
    assert theory.required_rel_vol_edge(4.0, 0.0) == float("inf")


def test_ladder_sensitivity_peaks_at_d_one():
    phi1 = exp(-0.5) / sqrt(2.0 * pi)
    assert theory.ladder_vol_sensitivity(1.0) == pytest.approx(phi1)
    assert theory.ladder_vol_sensitivity(1.0) > theory.ladder_vol_sensitivity(0.5)
    assert theory.ladder_vol_sensitivity(1.0) > theory.ladder_vol_sensitivity(1.5)


def test_touch_is_twice_ladder():
    for x in (0.5, 1.0, 2.0):
        assert theory.touch_vol_sensitivity(x) == pytest.approx(
            2.0 * theory.ladder_vol_sensitivity(x))


def test_linear_approx_matches_exact_for_small_error():
    d, eps = 1.0, 0.02
    approx = theory.ladder_vol_sensitivity(d) * eps
    exact = theory.vol_misprice_prob_edge(d, eps)
    assert exact == pytest.approx(approx, rel=0.05)


def test_effective_sigma_reduces_to_base_without_jump():
    st = theory.horizon_sigma(0.10, 7200.0)
    assert theory.effective_horizon_sigma(0.10, 7200.0, 0.0) == pytest.approx(st)
    assert theory.effective_horizon_sigma(0.10, 7200.0, 0.004) > st


def test_event_ladder_edge_positive_for_otm():
    spot = 150.0
    st = theory.horizon_sigma(0.10, 7200.0)
    strike = spot * exp(1.5 * st)   # 上側OTM
    r = theory.event_ladder_edge(spot, strike, 0.10, 7200.0, 0.004)
    assert r["edge_prob"] > 0.10           # ジャンプでOTM到達確率が大幅増
    assert r["breakeven_spread_points"] > 20.0


def test_mc_touch_with_zero_jump_matches_analytic():
    spot, sig, ttm = 150.0, 0.10, 7200.0
    st = theory.horizon_sigma(sig, ttm)
    barrier = spot * exp(1.0 * st)
    from binary_options_edge.pricing import prob_touch
    mc = theory.mc_prob_touch_with_jump(spot, barrier, sig, ttm, 0.0,
                                        n_paths=100_000, seed=1)
    # 離散監視MCは連続監視解析解よりわずかに下振れする（監視粒度バイアス）
    assert mc == pytest.approx(prob_touch(spot, barrier, sig, ttm), abs=0.03)


def test_seasonal_boundary_sign():
    # MMが低ボラ(トレーリング)で価格付け・実際は高ボラ窓 → OTM買いが割安(エッジ正)
    r = theory.seasonal_boundary_misprice(-1.0, 0.6, 1.6)
    assert r["edge_prob"] > 0
    # 逆(高→低)ならOTMは割高(売りエッジ)
    r2 = theory.seasonal_boundary_misprice(-1.0, 1.6, 0.6)
    assert r2["edge_prob"] < 0
