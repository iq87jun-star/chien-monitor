"""統計検定: BH-FDR, ブートストラップ, DSR。"""
import numpy as np

from binary_options_edge import stats_tests


def test_benjamini_hochberg_basic():
    pv = {"a": 0.001, "b": 0.2, "c": 0.04, "d": 0.7}
    rej = stats_tests.benjamini_hochberg(pv, fdr=0.1)
    assert rej["a"] is True
    assert rej["d"] is False


def test_bootstrap_detects_positive_mean():
    rng = np.random.default_rng(0)
    x = rng.normal(0.5, 1.0, 2000)
    r = stats_tests.moving_block_bootstrap_mean(x, block=10)
    assert r.ci_low > 0
    assert r.p_value_gt0 < 0.05


def test_bootstrap_zero_mean_not_significant():
    rng = np.random.default_rng(1)
    x = rng.normal(0.0, 1.0, 2000)
    r = stats_tests.moving_block_bootstrap_mean(x, block=10)
    assert r.ci_low < 0 < r.ci_high


def test_deflated_sharpe_penalizes_many_trials():
    rng = np.random.default_rng(2)
    x = rng.normal(0.03, 1.0, 1000)
    one = stats_tests.deflated_sharpe_ratio(x, n_trials=1)["dsr"]
    many = stats_tests.deflated_sharpe_ratio(x, n_trials=500)["dsr"]
    assert many < one        # 試行数が多いほどDSRは下がる


def test_norm_inv_roundtrip():
    from math import erf, sqrt
    for p in (0.1, 0.5, 0.9, 0.975):
        z = stats_tests._norm_inv(p)
        back = 0.5 * (1 + erf(z / sqrt(2)))
        assert abs(back - p) < 1e-3
