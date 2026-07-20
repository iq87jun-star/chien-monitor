"""配管確認用の合成データ。

重要な健全性チェック:
  原資産はドリフト0のGBMで生成し、IG提示は『真のフェア確率 + スプレッド』で作る。
  すなわち DGP（データ生成過程）にエッジを一切入れていない。
  したがって本来 *コスト控除後の期待値は負（=半スプレッド負け）になるはず*。
  もし合成データで「有意なエッジ検出」が出たら、それはコードのバグか過剰最適化の兆候。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .data import BinaryContract, CalendarSource, UnderlyingSource
from .pricing import SECONDS_PER_YEAR


class GBMUnderlying(UnderlyingSource):
    """1秒刻みのドリフト0 GBMスポット。realized_vol は基底実装を継承。"""

    def __init__(self, pair: str = "USDJPY", s0: float = 150.0,
                 sigma: float = 0.08, start: datetime | None = None,
                 days: int = 60, seed: int = 7):
        self.pair = pair
        self.sigma = sigma          # 真の生成ボラ（市場のフェア価格付けに使用）
        start = start or datetime(2025, 1, 1, tzinfo=timezone.utc)
        n = days * 24 * 3600
        rng = np.random.default_rng(seed)
        dt = 1.0 / SECONDS_PER_YEAR
        shocks = rng.standard_normal(n) * sigma * np.sqrt(dt) - 0.5 * sigma**2 * dt
        logs = np.log(s0) + np.cumsum(shocks)
        mid = np.exp(logs)
        # start は tz-aware(UTC)。tz引数を併用すると衝突するため freq のみ指定。
        ts = pd.date_range(start, periods=n, freq="s")
        half = 0.005  # 原資産スプレッド(price)
        self._df = pd.DataFrame({"ts": ts, "bid": mid - half, "ask": mid + half, "mid": mid})
        self._df_idx = self._df.set_index("ts")

    def history(self, pair, start, as_of):
        # ソート済みDatetimeIndexのラベルスライス（二分探索, O(log n)）で全走査を避ける
        d = self._df_idx.loc[start:as_of]
        return d.reset_index().rename(columns={"ts": "ts"})

    def settle_value(self, t: datetime) -> float:
        return float(self._df_idx["mid"].asof(t))

    def path_between(self, t0: datetime, t1: datetime) -> np.ndarray:
        return self._df_idx.loc[t0:t1, "mid"].to_numpy()


class EmptyCalendar(CalendarSource):
    def events(self, start, end):
        return []


def make_contracts(u: GBMUnderlying, n: int = 600, ttm_seconds: float = 1800.0,
                   assumed_spread: float = 6.0, seed: int = 11) -> list[BinaryContract]:
    """ラダー/ワンタッチ/レンジの提示を合成（フェア+スプレッド, エッジ無し）。"""
    from . import pricing
    rng = np.random.default_rng(seed)
    df = u._df_idx
    start_idx = 3600
    end_idx = len(df) - int(ttm_seconds) - 1
    times = pd.to_datetime(df.index[rng.integers(start_idx, end_idx, size=n)])
    out: list[BinaryContract] = []
    for dt_ in sorted(times):
        spot = float(df["mid"].asof(dt_))
        expiry = dt_ + pd.Timedelta(seconds=ttm_seconds)
        # 市場(IG)は真のボラでフェアを付ける。バックテスト側は実現ボラ推定(ノイズ有り)を使うため
        # 両者がズレてトレードが発生するが、真のエッジは無いのでコスト控除後EVは負(≈半スプレッド)になるはず。
        sigma = u.sigma
        kind = rng.choice(["ladder_above", "one_touch", "range_in"])
        path = u.path_between(dt_, expiry)
        if len(path) < 2:
            continue
        if kind == "ladder_above":
            strike = spot * (1 + rng.normal(0, 0.001))
            settled = path[-1] > strike
            p = pricing.prob_finish_above(spot, strike, sigma, ttm_seconds)
            lo = up = None
        elif kind == "one_touch":
            up_barrier = rng.random() < 0.5
            strike = spot * (1 + (0.0015 if up_barrier else -0.0015))
            settled = (path.max() >= strike) if up_barrier else (path.min() <= strike)
            p = pricing.prob_touch(spot, strike, sigma, ttm_seconds)
            lo = up = None
        else:  # range_in
            w = spot * 0.0015
            lo, up, strike = spot - w, spot + w, None
            settled = lo < path[-1] < up
            p = pricing.prob_finish_in_range(spot, lo, up, sigma, ttm_seconds)
        fair = 100.0 * p
        bid = max(0.0, min(100.0, fair - assumed_spread / 2))
        ask = max(0.0, min(100.0, fair + assumed_spread / 2))
        out.append(BinaryContract(
            pair=u.pair, option_type=kind, decision_time=dt_, expiry_time=expiry,
            spot_at_decision=spot, bid=bid, ask=ask, strike=strike, lower=lo, upper=up,
            settled_yes=bool(settled)))
    return out
