"""フェアバリュー（成就確率）モデルと期待値・損益分岐の計算。

設計方針:
- 原資産は短期ゆえドリフト≈0の幾何ブラウン運動（GBM）で近似する。
- すべての確率は「真の確率（physical）」の推定であり、IG提示mid(=100*p_market)と
  比較してエッジ δ = p_model - p_market を測るために使う。
- 解析解（ラダー/ワンタッチ/finish-in-range）に加え、連続監視ダブルバリア等の
  難しいペイオフ用にモンテカルロ・エンジンを ground truth として用意する。

注意: ここで返すのは確率(0-1)。提示価格はポイント(0-100)。100*p がフェアの目安。
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, sqrt
from typing import Literal

import numpy as np

SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0


def _norm_cdf(x: float) -> float:
    """標準正規CDF（scipy非依存）。"""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def years(seconds: float) -> float:
    """秒→年（年率ボラと整合させるため）。"""
    return seconds / SECONDS_PER_YEAR


# --------------------------------------------------------------------------- #
# 解析的フェアバリュー（成就確率）
# --------------------------------------------------------------------------- #
def prob_finish_above(spot: float, strike: float, sigma: float, ttm_seconds: float,
                      drift: float = 0.0) -> float:
    """ラダー: 満期時 S_T > K の確率（buy/CALLデジタル）。

    X = ln(S_T/S0) ~ N((drift - 0.5*sigma^2)*T, sigma^2*T)
    P(S_T>K) = Phi( (ln(S0/K) + (drift-0.5*sigma^2)*T) / (sigma*sqrt(T)) )
    """
    T = years(ttm_seconds)
    if T <= 0 or sigma <= 0:
        return float(spot > strike)
    m = (drift - 0.5 * sigma * sigma) * T
    d = (log(spot / strike) + m) / (sigma * sqrt(T))
    return _norm_cdf(d)


def prob_finish_below(spot: float, strike: float, sigma: float, ttm_seconds: float,
                      drift: float = 0.0) -> float:
    return 1.0 - prob_finish_above(spot, strike, sigma, ttm_seconds, drift)


def prob_finish_in_range(spot: float, lower: float, upper: float, sigma: float,
                         ttm_seconds: float, drift: float = 0.0) -> float:
    """レンジ(満期内判定): P(lower < S_T < upper)。"""
    if upper <= lower:
        raise ValueError("upper must be > lower")
    return (prob_finish_above(spot, lower, sigma, ttm_seconds, drift)
            - prob_finish_above(spot, upper, sigma, ttm_seconds, drift))


def prob_touch(spot: float, barrier: float, sigma: float, ttm_seconds: float,
               drift: float = 0.0) -> float:
    """ワンタッチ: 満期までにバリアに「触れる」確率。

    対数座標 X_t=ln(S_t/S0), ドリフト m=drift-0.5*sigma^2, b=ln(barrier/spot)。
    上バリア(b>0)について running max の分布（鏡像原理）:
      P(max X >= b) = Phi((-b+mT)/(s√T)) + exp(2mb/s^2) * Phi((-b-mT)/(s√T))
    下バリア(b<0)は P(min X <= b) = Phi((b-mT)/(s√T)) + exp(2mb/s^2)*Phi((b+mT)/(s√T))。
    m=0 のとき上下とも 2*Phi(-|b|/(s√T)) に一致。
    """
    T = years(ttm_seconds)
    if T <= 0 or sigma <= 0:
        return float((barrier >= spot and spot >= barrier) or (barrier <= spot and spot <= barrier))
    s_sqrt_t = sigma * sqrt(T)
    m = drift - 0.5 * sigma * sigma
    b = log(barrier / spot)
    if b >= 0:  # 上バリア
        p = (_norm_cdf((-b + m * T) / s_sqrt_t)
             + exp(2.0 * m * b / (sigma * sigma)) * _norm_cdf((-b - m * T) / s_sqrt_t))
    else:       # 下バリア
        p = (_norm_cdf((b - m * T) / s_sqrt_t)
             + exp(2.0 * m * b / (sigma * sigma)) * _norm_cdf((b + m * T) / s_sqrt_t))
    return float(min(max(p, 0.0), 1.0))


def prob_no_touch(spot: float, barrier: float, sigma: float, ttm_seconds: float,
                  drift: float = 0.0) -> float:
    return 1.0 - prob_touch(spot, barrier, sigma, ttm_seconds, drift)


# --------------------------------------------------------------------------- #
# モンテカルロ（連続監視ダブルバリア / 検証用 ground truth）
# --------------------------------------------------------------------------- #
def mc_prob(spot: float, sigma: float, ttm_seconds: float, payoff: str,
            level: float | None = None, lower: float | None = None,
            upper: float | None = None, drift: float = 0.0,
            n_paths: int = 200_000, n_steps: int = 256,
            seed: int | None = 0) -> float:
    """モンテカルロで成就確率を推定。連続監視のtunnel(double no-touch)等に使用。

    payoff in {"finish_above","finish_below","finish_in_range",
               "touch","no_touch","double_no_touch","double_touch"}
    """
    T = years(ttm_seconds)
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    m = (drift - 0.5 * sigma * sigma) * dt
    vol = sigma * sqrt(dt)
    logS = np.full(n_paths, log(spot))
    running_max = logS.copy()
    running_min = logS.copy()
    for _ in range(n_steps):
        logS += m + vol * rng.standard_normal(n_paths)
        running_max = np.maximum(running_max, logS)
        running_min = np.minimum(running_min, logS)
    ST = np.exp(logS)
    hi = np.exp(running_max)
    lo = np.exp(running_min)
    if payoff == "finish_above":
        hit = ST > level
    elif payoff == "finish_below":
        hit = ST < level
    elif payoff == "finish_in_range":
        hit = (ST > lower) & (ST < upper)
    elif payoff == "touch":
        hit = (hi >= level) if level >= spot else (lo <= level)
    elif payoff == "no_touch":
        hit = ~((hi >= level) if level >= spot else (lo <= level))
    elif payoff == "double_no_touch":  # tunnel: 全期間 band 内に留まる
        hit = (hi < upper) & (lo > lower)
    elif payoff == "double_touch":
        hit = (hi >= upper) | (lo <= lower)
    else:
        raise ValueError(f"unknown payoff {payoff}")
    return float(hit.mean())


# --------------------------------------------------------------------------- #
# 期待値・損益分岐・トレード判定
# --------------------------------------------------------------------------- #
Side = Literal["buy", "sell", "none"]


def ev_buy(p: float, ask: float) -> float:
    """買い期待値(ポイント) = 100p - A。"""
    return 100.0 * p - ask


def ev_sell(p: float, bid: float) -> float:
    """売り期待値(ポイント) = B - 100p。"""
    return bid - 100.0 * p


def breakeven_prob_buy(ask: float) -> float:
    return ask / 100.0


def breakeven_prob_sell(bid: float) -> float:
    return bid / 100.0


def required_prob_edge(spread_points: float) -> float:
    """midに対して必要な確率エッジ δ > s/200。"""
    return spread_points / 200.0


@dataclass(frozen=True)
class TradeDecision:
    side: Side
    ev_points: float          # 選んだ側のEV(ポイント)。noneなら0
    model_p: float
    bid: float
    ask: float
    edge_vs_mid: float        # p_model - mid/100
    breakeven: float          # 採用側の損益分岐勝率

    @property
    def tradable(self) -> bool:
        return self.side != "none" and self.ev_points > 0.0


def decide_trade(model_p: float, bid: float, ask: float,
                 min_ev_points: float = 0.0) -> TradeDecision:
    """フェア確率と気配から、EV>0かつ最低EV閾値を満たす側を選ぶ。

    買いも売りもEV<=min ならノートレード（ノートレード帯）。
    """
    e_buy = ev_buy(model_p, ask)
    e_sell = ev_sell(model_p, bid)
    mid = 0.5 * (bid + ask)
    edge = model_p - mid / 100.0
    if e_buy >= e_sell and e_buy > min_ev_points:
        return TradeDecision("buy", e_buy, model_p, bid, ask, edge, breakeven_prob_buy(ask))
    if e_sell > min_ev_points:
        return TradeDecision("sell", e_sell, model_p, bid, ask, edge, breakeven_prob_sell(bid))
    return TradeDecision("none", 0.0, model_p, bid, ask, edge, mid / 100.0)


def realized_pnl_points(side: Side, settled_yes: bool, bid: float, ask: float) -> float:
    """清算後の実現損益(ポイント)。コスト(スプレッド)は約定値A/Bに内包済み。"""
    if side == "buy":
        return (100.0 if settled_yes else 0.0) - ask
    if side == "sell":
        return bid - (100.0 if settled_yes else 0.0)
    return 0.0
