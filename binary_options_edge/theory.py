"""仮説の理論的定量化（H1/H2/H3 深堀り）。

このモジュールは「どの局面・どの商品構造で・どれだけの歪みが理論上生じうるか」を
解析的に計算する。フィルタ(hypotheses.py)が「いつ取引するか」を決めるのに対し、
ここは「その歪みは半スプレッドを超えうるか」を事前に見積もる理論層。

核となる恒等式（THEORY.md で導出）:
  - ラダーのフェア確率 p = Φ(d), d = ln(S/K)/(σ√T)（短期・ドリフト0近似）
  - 相対ボラ誤差 ε = Δσ/σ に対する確率誤差: δp ≈ φ(d)·|d|·ε
  - 取引正当化条件: δp > s/200（s=スプレッド, ポイント）
  ⇒ 必要な相対ボラ予測優位 ε* = (s/200) / (φ(d)·|d|)

すべて確率(0-1)スケール。ポイント換算は×100。
"""
from __future__ import annotations

from math import erf, exp, log, pi, sqrt

import numpy as np

from .pricing import SECONDS_PER_YEAR, prob_finish_above, prob_touch


def _phi(x: float) -> float:
    """標準正規PDF。"""
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def horizon_sigma(sigma_ann: float, ttm_seconds: float) -> float:
    """満期までの対数リターン標準偏差 σ√T（無次元）。"""
    return sigma_ann * sqrt(ttm_seconds / SECONDS_PER_YEAR)


def standardized_moneyness(spot: float, strike: float, sigma_ann: float,
                           ttm_seconds: float) -> float:
    """d = ln(S/K)/(σ√T)。strike>spot なら負（アウトオブザマネーの上側ラダー）。"""
    st = horizon_sigma(sigma_ann, ttm_seconds)
    if st <= 0:
        raise ValueError("sigma*sqrt(T) must be positive")
    return log(spot / strike) / st


# --------------------------------------------------------------------------- #
# 定理1・2: ボラ感応度と必要ボラ予測優位
# --------------------------------------------------------------------------- #
def ladder_vol_sensitivity(d: float) -> float:
    """ラダー確率の相対ボラ誤差感応度 |∂p/∂lnσ| = φ(d)·|d|。

    d=0 (ATM) で厳密に 0（ATMラダーはボラ中立）、|d|=1 で最大 φ(1)≈0.242。
    """
    return _phi(d) * abs(d)


def touch_vol_sensitivity(x: float) -> float:
    """ワンタッチ確率の相対ボラ誤差感応度（ドリフト0近似）。

    p_touch = 2Φ(-x), x = |ln(B/S)|/(σ√T) ⇒ |∂p/∂lnσ| = 2φ(x)·x。
    同じ規格化距離のラダーのちょうど2倍。x=1 で最大 ≈0.484。
    """
    return 2.0 * _phi(x) * x


def range_vol_sensitivity(k: float) -> float:
    """対称レンジ(±k·σ√T, 満期判定) p = 2Φ(k)-1 の感応度 |∂p/∂lnσ| = 2φ(k)·k。

    符号は負（ボラ上昇でレンジ内確率は低下）= 「ボラ売り」構造。大きさはタッチと同型。
    """
    return 2.0 * _phi(k) * k


def required_rel_vol_edge(spread_points: float, d: float) -> float:
    """スプレッド s のもとで取引を正当化する最小の相対ボラ予測優位 ε*。

    ε* = (s/200) / (φ(d)·|d|)。d→0 で発散（ATMではボラ優位は無意味）。
    """
    sens = ladder_vol_sensitivity(d)
    if sens <= 0:
        return float("inf")
    return (spread_points / 200.0) / sens


def vol_misprice_prob_edge(d: float, rel_vol_error: float) -> float:
    """相対ボラ誤差 ε がもたらす確率エッジの厳密値 |Φ(d/(1+ε)) − Φ(d)|。

    線形近似 φ(d)|d|ε の裏取り用（εが大きい場合は厳密値を使う）。
    """
    return abs(_cdf(d / (1.0 + rel_vol_error)) - _cdf(d))


# --------------------------------------------------------------------------- #
# H3: 予定イベントのジャンプ混合モデル
# --------------------------------------------------------------------------- #
def effective_horizon_sigma(sigma_ann: float, ttm_seconds: float,
                            jump_std_log: float) -> float:
    """満期変動の実効標準偏差 √(σ²T + σ_J²)。

    予定イベント（指標発表）を「発表時刻に一度だけ入る平均0・標準偏差 σ_J の
    対数ジャンプ」とみなすと、満期分布の分散は加法的に増える。
    """
    st = horizon_sigma(sigma_ann, ttm_seconds)
    return sqrt(st * st + jump_std_log * jump_std_log)


def event_ladder_edge(spot: float, strike: float, sigma_ann: float,
                      ttm_seconds: float, jump_std_log: float) -> dict:
    """ラダーの「拡散のみ価格」対「ジャンプ込みフェア」の確率差（満期判定なので解析的）。

    返り値: p_diffusion（IGが定常拡散で価格付けした場合のmid想定）,
            p_with_jump（ジャンプ込みの真のフェア）,
            edge_prob = p_with_jump − p_diffusion,
            breakeven_spread_points = 200·|edge|（このスプレッド未満なら理論上取引可能）。
    """
    p_diff = prob_finish_above(spot, strike, sigma_ann, ttm_seconds)
    st_eff = effective_horizon_sigma(sigma_ann, ttm_seconds, jump_std_log)
    # 実効ボラを年率に戻して既存の解析式を再利用
    sigma_eff_ann = st_eff / sqrt(ttm_seconds / SECONDS_PER_YEAR)
    p_jump = prob_finish_above(spot, strike, sigma_eff_ann, ttm_seconds)
    edge = p_jump - p_diff
    return {"p_diffusion": p_diff, "p_with_jump": p_jump,
            "edge_prob": edge, "breakeven_spread_points": 200.0 * abs(edge)}


def mc_prob_touch_with_jump(spot: float, barrier: float, sigma_ann: float,
                            ttm_seconds: float, jump_std_log: float,
                            event_frac: float = 0.5, n_paths: int = 200_000,
                            n_steps: int = 240, seed: int | None = 0) -> float:
    """ワンタッチ確率（経路依存）をジャンプ込みMCで推定。

    イベントは窓の event_frac 時点に1回。ジャンプは平均 −σ_J²/2（マルチンゲール整合）
    の正規対数ジャンプ。ギャップがバリアを跳び越えた場合もタッチ扱い
    （max/min にジャンプ後の水準を含める＝実務のタッチ判定と同じ保守側）。
    """
    T = ttm_seconds / SECONDS_PER_YEAR
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    m = -0.5 * sigma_ann * sigma_ann * dt
    vol = sigma_ann * sqrt(dt)
    jump_step = int(event_frac * n_steps)
    logS = np.full(n_paths, log(spot))
    run_max = logS.copy()
    run_min = logS.copy()
    for i in range(n_steps):
        logS = logS + m + vol * rng.standard_normal(n_paths)
        if i == jump_step and jump_std_log > 0:
            logS = logS + (-0.5 * jump_std_log ** 2
                           + jump_std_log * rng.standard_normal(n_paths))
        run_max = np.maximum(run_max, logS)
        run_min = np.minimum(run_min, logS)
    b = log(barrier)
    hit = (run_max >= b) if barrier >= spot else (run_min <= b)
    return float(hit.mean())


def event_touch_edge(spot: float, barrier: float, sigma_ann: float,
                     ttm_seconds: float, jump_std_log: float,
                     event_frac: float = 0.5, seed: int | None = 0) -> dict:
    """ワンタッチの「拡散のみ価格」対「ジャンプ込みフェア」の確率差（MC）。"""
    p_diff = prob_touch(spot, barrier, sigma_ann, ttm_seconds)
    p_jump = mc_prob_touch_with_jump(spot, barrier, sigma_ann, ttm_seconds,
                                     jump_std_log, event_frac, seed=seed)
    edge = p_jump - p_diff
    return {"p_diffusion": p_diff, "p_with_jump": p_jump,
            "edge_prob": edge, "breakeven_spread_points": 200.0 * abs(edge)}


# --------------------------------------------------------------------------- #
# H2: 日内季節性の境界効果
# --------------------------------------------------------------------------- #
def seasonal_boundary_misprice(d: float, trailing_seasonal_factor: float,
                               window_seasonal_factor: float) -> dict:
    """「トレーリング実現ボラで価格付けするMM」対「季節カレンダーを知る側」の確率差。

    trailing_seasonal_factor: 直近参照窓の日内係数（例: 東京昼 0.6）
    window_seasonal_factor:   オプション満期窓の日内係数（例: ロンドン序盤 1.6）
    MM が σ_trailing = σ̄·trailing を使い、真は σ_true = σ̄·window のとき、
    ラダー確率誤差 = Φ(d/r) − Φ(d), r = window/trailing。
    """
    r = window_seasonal_factor / trailing_seasonal_factor
    p_mm = _cdf(d)
    p_true = _cdf(d / r)
    edge = p_true - p_mm
    return {"vol_ratio": r, "p_market_maker": p_mm, "p_true": p_true,
            "edge_prob": edge, "breakeven_spread_points": 200.0 * abs(edge)}
