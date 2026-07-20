"""IG実スプレッドの推定・マークアップ分解。

- estimate_spread: 実気配からバケット別 (種別/moneyness/残存時間/時間帯) のスプレッド統計。
- decompose_markup: mid と フェアモデルの差からマークアップ(スキュー)を分離。

直接採取(実気配)が唯一の厳密法。マークアップ分解はモデル誤差が混ざるため補助に留める。
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .data import BinaryContract, UnderlyingSource, fair_prob


def _moneyness_bucket(c: BinaryContract) -> str:
    """ストライクまでの距離をボラ正規化せずspot比で粗くバケット化。"""
    ref = c.strike if c.strike is not None else (
        0.5 * (c.lower + c.upper) if c.lower and c.upper else c.spot_at_decision)
    d = abs(ref - c.spot_at_decision) / c.spot_at_decision
    if d < 0.0005:
        return "atm"
    if d < 0.002:
        return "near"
    return "far"


def _ttm_bucket(seconds: float) -> str:
    if seconds <= 300:
        return "<=5m"
    if seconds <= 3600:
        return "<=1h"
    return ">1h"


def estimate_spread(contracts: Iterable[BinaryContract]) -> pd.DataFrame:
    """実気配からバケット別スプレッド統計を返す（中央値・平均・分位）。"""
    rows = []
    for c in contracts:
        rows.append({
            "pair": c.pair,
            "type": c.option_type,
            "moneyness": _moneyness_bucket(c),
            "ttm": _ttm_bucket(c.ttm_seconds),
            "hour": c.decision_time.hour,
            "spread": c.spread,
            "mid": c.mid,
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    g = df.groupby(["pair", "type", "moneyness", "ttm"])["spread"]
    return g.agg(n="count", mean="mean", median="median",
                 p10=lambda x: x.quantile(0.1),
                 p90=lambda x: x.quantile(0.9)).reset_index()


def decompose_markup(contracts: Iterable[BinaryContract],
                     underlying: UnderlyingSource,
                     vol_lookback_seconds: float = 3600.0) -> pd.DataFrame:
    """mid - fair(=100*p_model) をマークアップ/スキューとして測る（補助）。

    返り値: 各契約の fair, mid, markup(=mid-fair), half_spread。
    markup の符号は IG が買い/売りどちらに偏らせているかを示す。
    """
    rows = []
    for c in contracts:
        sigma = underlying.realized_vol(c.pair, c.decision_time, vol_lookback_seconds)
        if not np.isfinite(sigma):
            continue
        fair = 100.0 * fair_prob(c, sigma)
        rows.append({
            "pair": c.pair, "type": c.option_type,
            "moneyness": _moneyness_bucket(c), "ttm": _ttm_bucket(c.ttm_seconds),
            "fair": fair, "mid": c.mid, "markup": c.mid - fair,
            "half_spread": c.spread / 2.0,
        })
    return pd.DataFrame(rows)
