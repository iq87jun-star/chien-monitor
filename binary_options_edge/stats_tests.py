"""統計的有意性・多重検定補正・過剰最適化対策。

- moving_block_bootstrap_mean: 自己相関に頑健な平均EV/トレードのCI。
- t_test_mean: 平均EV>0 の片側t検定。
- benjamini_hochberg: 多重仮説のFDR補正。
- deflated_sharpe_ratio: 試行数・歪度・尖度を補正したSharpe有意性
  (Bailey & López de Prado, 2014)。
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Sequence

import numpy as np


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


@dataclass
class BootstrapResult:
    mean: float
    ci_low: float
    ci_high: float
    p_value_gt0: float   # 平均<=0 となるブートストラップ割合（片側）


def moving_block_bootstrap_mean(x: Sequence[float], block: int = 20,
                                n_boot: int = 5000, alpha: float = 0.05,
                                seed: int = 0) -> BootstrapResult:
    """移動ブロックブートストラップで平均のCIと p(mean<=0) を推定。"""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return BootstrapResult(float("nan"), float("nan"), float("nan"), 1.0)
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts_pool = np.arange(0, n - block + 1) if n - block + 1 > 0 else np.array([0])
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.choice(starts_pool, size=n_blocks, replace=True)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        idx = np.clip(idx, 0, n - 1)
        means[b] = x[idx].mean()
    lo = np.quantile(means, alpha / 2)
    hi = np.quantile(means, 1 - alpha / 2)
    p = float(np.mean(means <= 0.0))
    return BootstrapResult(float(x.mean()), float(lo), float(hi), p)


def t_test_mean_gt0(x: Sequence[float]) -> float:
    """H0: mean<=0 に対する片側tのp値（大標本正規近似）。"""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return 1.0
    se = x.std(ddof=1) / sqrt(n)
    if se == 0:
        return 0.0 if x.mean() > 0 else 1.0
    t = x.mean() / se
    return 1.0 - _norm_cdf(t)


def benjamini_hochberg(pvalues: dict[str, float], fdr: float = 0.1) -> dict[str, bool]:
    """BH手続き。返り値: 仮説名 -> 棄却(=有意)か。"""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    rejected: dict[str, bool] = {k: False for k in pvalues}
    max_k = -1
    for k, (_, p) in enumerate(items, start=1):
        if p <= (k / m) * fdr:
            max_k = k
    for k, (name, _) in enumerate(items, start=1):
        rejected[name] = k <= max_k
    return rejected


def probabilistic_sharpe_ratio(sr_hat: float, n: int, skew: float, kurt: float,
                               sr_benchmark: float = 0.0) -> float:
    """PSR: 観測Sharpeが基準SRを超える確率（非正規補正込み）。"""
    if n < 2:
        return 0.5
    denom = sqrt(max(1e-12, 1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2))
    z = (sr_hat - sr_benchmark) * sqrt(n - 1) / denom
    return _norm_cdf(z)


def deflated_sharpe_ratio(returns: Sequence[float], n_trials: int,
                          sr_trials_std: float | None = None) -> dict[str, float]:
    """Deflated Sharpe Ratio (Bailey & López de Prado, 2014)。

    n_trials 回の試行から最良を選んだ選択バイアスを、期待最大Sharpeを基準にして補正。
    返り値: {'sr','dsr','expected_max_sr','n_trials'}。dsr が有意性確率(>~0.95で有意)。
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 2:
        return {"sr": float("nan"), "dsr": 0.0, "expected_max_sr": float("nan"),
                "n_trials": n_trials}
    sr = r.mean() / (r.std(ddof=1) + 1e-12)
    g1 = float(((r - r.mean()) ** 3).mean() / (r.std() ** 3 + 1e-12))   # skew
    g2 = float(((r - r.mean()) ** 4).mean() / (r.std() ** 4 + 1e-12))   # kurtosis (not excess)
    # 試行間Sharpeのばらつき。未指定なら控えめに観測SRスケールで近似。
    v = sr_trials_std if sr_trials_std is not None else max(abs(sr), 0.5)
    emc = 0.5772156649  # Euler-Mascheroni
    e = max(2, n_trials)
    # 期待最大Sharpe (Bailey-LdP 近似)
    from math import log as _log
    z1 = _norm_inv(1 - 1.0 / e)
    z2 = _norm_inv(1 - 1.0 / e * np.e ** -1)
    expected_max_sr = v * ((1 - emc) * z1 + emc * z2)
    dsr = probabilistic_sharpe_ratio(sr, n, g1, g2, sr_benchmark=expected_max_sr)
    return {"sr": sr, "dsr": dsr, "expected_max_sr": float(expected_max_sr),
            "n_trials": n_trials}


def _norm_inv(p: float) -> float:
    """標準正規の逆CDF（Acklam近似）。"""
    p = min(max(p, 1e-12), 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = sqrt(-2 * np.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = sqrt(-2 * np.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
