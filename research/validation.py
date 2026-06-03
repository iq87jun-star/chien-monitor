"""
validation.py — 過剰適合に強い検証ツール（docs/27 §4 の教訓を実装）。

今回 E3A が「全ゲート通過なのに実体はベータ」だった失敗を構造的に防ぐ:
  1) beta_neutralize : シグナルを市場リターンで回帰し、残差 alpha の t 値で「ベータか実力か」判定。
  2) deflated_sharpe : 試行回数 N を織り込んで見かけの Sharpe を割り引く（Bailey & Lopez de Prado 2014）。
  3) pbo_cscv        : Combinatorially Symmetric CV による過剰適合確率（PBO）。

依存: numpy, scipy。per-observation（週次など）のリターン系列を入力に取る。
"""
from __future__ import annotations

from itertools import combinations
import math

import numpy as np
from scipy import stats


# --------------------------------------------------------------------------
# 1) ベータ/ファクター中立化
# --------------------------------------------------------------------------
def beta_neutralize(strategy: np.ndarray, market: np.ndarray) -> dict:
    """strategy = alpha + beta*market + eps を OLS。残差 alpha の有意性を返す。

    返り値: alpha(切片/期間平均), beta, t_alpha, p_alpha(両側), resid(残差系列), r2。
    「市場で説明され尽くす（alpha が0と差が無い）」なら実力エッジではなくベータ。
    """
    s = np.asarray(strategy, float)
    m = np.asarray(market, float)
    mask = np.isfinite(s) & np.isfinite(m)
    s, m = s[mask], m[mask]
    n = len(s)
    if n < 8:
        return {"alpha": float("nan"), "beta": float("nan"), "t_alpha": float("nan"),
                "p_alpha": 1.0, "resid": np.array([]), "r2": float("nan"), "n": n}
    X = np.column_stack([np.ones(n), m])
    coef, *_ = np.linalg.lstsq(X, s, rcond=None)
    alpha, beta = coef
    resid = s - X @ coef
    dof = n - 2
    sigma2 = (resid @ resid) / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se_alpha = math.sqrt(sigma2 * xtx_inv[0, 0])
    t_alpha = alpha / se_alpha if se_alpha > 0 else 0.0
    p_alpha = 2 * (1 - stats.t.cdf(abs(t_alpha), dof))
    ss_tot = ((s - s.mean()) ** 2).sum()
    r2 = 1 - (resid @ resid) / ss_tot if ss_tot > 0 else float("nan")
    return {"alpha": float(alpha), "beta": float(beta), "t_alpha": float(t_alpha),
            "p_alpha": float(p_alpha), "resid": resid, "r2": float(r2), "n": n}


# --------------------------------------------------------------------------
# 2) Deflated Sharpe Ratio
# --------------------------------------------------------------------------
def _sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, float)
    r = r[np.isfinite(r)]
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def expected_max_sharpe(sr_trials_std: float, n_trials: int) -> float:
    """N 回試行で偶然得られる「期待最大 Sharpe」（per-observation, 帰無 SR=0）。"""
    if n_trials < 2 or sr_trials_std <= 0:
        return 0.0
    gamma = 0.5772156649  # Euler-Mascheroni
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / n_trials * math.e ** -1)
    return sr_trials_std * ((1 - gamma) * z1 + gamma * z2)


def deflated_sharpe(returns: np.ndarray, n_trials: int,
                    sr_trials_std: float | None = None,
                    all_trial_returns: list | None = None) -> dict:
    """観測 Sharpe を試行回数で割り引いた DSR（=これが真に>0である確率）。

    sr_trials_std: 試行間 Sharpe のばらつき。未指定なら all_trial_returns（各試行の
    per-observation リターン系列のリスト）から推定。どちらも無ければ観測SRの保守推定。
    """
    r = np.asarray(returns, float); r = r[np.isfinite(r)]
    T = len(r)
    if T < 8:
        return {"sharpe": float("nan"), "dsr": float("nan"), "sr0": float("nan"), "T": T}
    sr = _sharpe(r)
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))  # 正規=3
    if sr_trials_std is None and all_trial_returns:
        srs = [_sharpe(x) for x in all_trial_returns if len(np.asarray(x)) >= 8]
        sr_trials_std = float(np.std(srs, ddof=1)) if len(srs) >= 2 else abs(sr)
    if sr_trials_std is None:
        sr_trials_std = abs(sr)  # 保守: ばらつき情報が無いときの代用
    sr0 = expected_max_sharpe(sr_trials_std, n_trials)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    z = (sr - sr0) * math.sqrt(T - 1) / denom
    dsr = float(stats.norm.cdf(z))
    return {"sharpe": sr, "sr0": float(sr0), "dsr": dsr, "skew": skew,
            "kurtosis": kurt, "T": T, "n_trials": n_trials,
            "sr_trials_std": float(sr_trials_std)}


# --------------------------------------------------------------------------
# 3) PBO via CSCV（Probability of Backtest Overfitting）
# --------------------------------------------------------------------------
def pbo_cscv(returns_matrix: np.ndarray, n_splits: int = 10) -> dict:
    """M (T×N: T期間 × N構成のper-obsリターン) から PBO を推定。

    時系列を S 個に分割→半分IS/半分OOSの全組合せで、IS最良構成のOOS順位を見る。
    OOS順位が中央値未満（=過剰適合で崩れる）割合が PBO。低いほど頑健。
    """
    M = np.asarray(returns_matrix, float)
    T, N = M.shape
    if N < 2 or T < n_splits * 2:
        return {"pbo": float("nan"), "n_combos": 0, "N": N, "T": T}
    S = n_splits if n_splits % 2 == 0 else n_splits - 1
    bounds = np.array_split(np.arange(T), S)
    logits = []
    for is_idx in combinations(range(S), S // 2):
        is_rows = np.concatenate([bounds[i] for i in is_idx])
        oos_rows = np.concatenate([bounds[i] for i in range(S) if i not in is_idx])
        is_sr = np.array([_sharpe(M[is_rows, j]) for j in range(N)])
        oos_sr = np.array([_sharpe(M[oos_rows, j]) for j in range(N)])
        best = int(np.argmax(is_sr))
        # OOS でのその構成の相対順位（0..1, 1=最良）
        rank = (oos_sr < oos_sr[best]).sum() / (N - 1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.array(logits)
    pbo = float((logits <= 0).mean())  # OOSで中央値以下に落ちる割合
    return {"pbo": pbo, "n_combos": len(logits), "S": S, "N": N, "T": T,
            "median_logit": float(np.median(logits))}


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    T = 520
    # --- beta test: 戦略 = 0.8*market + 弱いalpha + noise ---
    market = rng.normal(0.001, 0.01, T)
    strat_beta = 0.8 * market + rng.normal(0, 0.003, T)          # alpha無し
    strat_alpha = 0.8 * market + 0.0008 + rng.normal(0, 0.003, T) # alpha有り
    bn0 = beta_neutralize(strat_beta, market)
    bn1 = beta_neutralize(strat_alpha, market)
    print("beta-only : t_alpha=%.2f p=%.3f beta=%.2f r2=%.2f" %
          (bn0["t_alpha"], bn0["p_alpha"], bn0["beta"], bn0["r2"]))
    print("with-alpha: t_alpha=%.2f p=%.3f beta=%.2f r2=%.2f" %
          (bn1["t_alpha"], bn1["p_alpha"], bn1["beta"], bn1["r2"]))
    # --- DSR: 真の正ドリフト, 試行20 vs 200 ---
    good = rng.normal(0.0009, 0.004, T)
    for nt in (1, 20, 200):
        d = deflated_sharpe(good, n_trials=nt, sr_trials_std=0.05)
        print(f"DSR n_trials={nt:3d}: SR={d['sharpe']:.3f} SR0={d['sr0']:.3f} DSR={d['dsr']:.3f}")
    # --- PBO: N構成のうち1本だけ本物 ---
    M = rng.normal(0, 0.004, (T, 12))
    M[:, 0] += 0.0009  # 構成0だけ本物
    print("PBO(1 real of 12):", round(pbo_cscv(M)["pbo"], 3))
    M2 = rng.normal(0, 0.004, (T, 12))  # 全部ノイズ
    print("PBO(all noise)   :", round(pbo_cscv(M2)["pbo"], 3))
