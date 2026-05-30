"""データ取得インターフェース。

実データ（IG実気配・原資産ティック・指標カレンダー）を差し込めるよう
抽象基底だけを定義する。利用者は各 Source を実装してバックテスタに渡す。

重要: 先読み防止のため、すべての取得メソッドは「as_of（基準時刻）まで」で
切ったデータのみを返す契約とする。実装側でこの契約を必ず守ること。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Literal, Optional

import numpy as np
import pandas as pd

PAIRS = ("USDJPY", "GBPJPY", "EURJPY", "AUDJPY", "EURUSD", "GBPUSD", "AUDUSD")
OptionType = Literal["ladder_above", "ladder_below", "one_touch", "range_in", "tunnel_no_touch"]


@dataclass(frozen=True)
class BinaryContract:
    """1つのバイナリオプション提示。strike/lower/upper は種別で使い分ける。"""
    pair: str
    option_type: OptionType
    decision_time: datetime      # 意思決定（提示採取）時刻
    expiry_time: datetime        # 判定時刻
    spot_at_decision: float      # 意思決定時の原資産mid
    bid: float                   # IG提示 bid（売り執行値, 0-100）
    ask: float                   # IG提示 ask（買い執行値, 0-100）
    strike: Optional[float] = None       # ladder/one_touch 用
    lower: Optional[float] = None        # range/tunnel 用
    upper: Optional[float] = None        # range/tunnel 用
    settled_yes: Optional[bool] = None   # 清算結果（バックテストでは既知）

    @property
    def ttm_seconds(self) -> float:
        return (self.expiry_time - self.decision_time).total_seconds()

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        return 0.5 * (self.bid + self.ask)


@dataclass(frozen=True)
class CalendarEvent:
    time: datetime
    pair_relevance: tuple[str, ...]   # 影響する通貨ペア
    name: str
    importance: int                   # 1-3
    surprise: Optional[float] = None  # 実績 - 予想（標準化済み推奨）


class UnderlyingSource(abc.ABC):
    """原資産スポット（bid/ask）系列。"""

    @abc.abstractmethod
    def history(self, pair: str, start: datetime, as_of: datetime) -> pd.DataFrame:
        """[start, as_of] のティック/1秒データを返す。

        列: ['ts','bid','ask','mid']（ts は tz-aware 推奨, 昇順）。
        as_of より後の行を返してはならない（先読み禁止）。
        """

    def realized_vol(self, pair: str, as_of: datetime, lookback_seconds: float,
                     annualize: bool = True) -> float:
        """as_of 直前 lookback の対数収益から実現ボラを推定（既定実装）。"""
        start = as_of - pd.Timedelta(seconds=lookback_seconds)
        df = self.history(pair, start, as_of)
        if len(df) < 3:
            return float("nan")
        logret = np.diff(np.log(df["mid"].to_numpy()))
        dt = df["ts"].diff().dt.total_seconds().to_numpy()[1:]
        dt = np.where(dt <= 0, np.nan, dt)
        # 単位時間あたり分散 -> 年率
        var_per_sec = np.nanmean(logret ** 2 / dt)
        from .pricing import SECONDS_PER_YEAR
        sigma = np.sqrt(var_per_sec * (SECONDS_PER_YEAR if annualize else 1.0))
        return float(sigma)


class IGQuoteSource(abc.ABC):
    """IGバイナリの提示気配＋清算結果。実気配が無い場合は SimulatedIGQuoteSource を使う。"""

    @abc.abstractmethod
    def contracts(self, start: datetime, end: datetime,
                  pairs: Iterable[str] | None = None) -> Iterable[BinaryContract]:
        """期間内に意思決定可能だった全提示を返す（settled_yes 充足済み）。"""


class CalendarSource(abc.ABC):
    @abc.abstractmethod
    def events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        ...

    def next_event_seconds(self, pair: str, as_of: datetime,
                           horizon_seconds: float = 24 * 3600) -> Optional[float]:
        """as_of から次の関連イベントまでの秒数（H3用）。無ければ None。"""
        evs = self.events(as_of, as_of + pd.Timedelta(seconds=horizon_seconds))
        upcoming = [e for e in evs if e.time >= as_of and pair in e.pair_relevance]
        if not upcoming:
            return None
        return min((e.time - as_of).total_seconds() for e in upcoming)


# --------------------------------------------------------------------------- #
# 仮定スプレッドモード: 実気配が無いときの「条件付き」検証用
# --------------------------------------------------------------------------- #
@dataclass
class SimulatedIGQuoteSource(IGQuoteSource):
    """フェアモデル + 仮定スプレッド/マークアップで提示を合成する。

    ⚠️ これで出る結果は「もしスプレッドが assumed_spread なら」という条件付きにすぎず、
    ライブのエッジ保証ではない。実気配 IGQuoteSource が手に入ったら必ず差し替えること。
    """
    underlying: UnderlyingSource
    contracts_spec: list[BinaryContract]      # strike/expiry 等の素案（bid/ask未設定可）
    assumed_spread_points: float = 6.0        # 仮定スプレッド（ポイント）
    assumed_markup_points: float = 0.0        # mid を fair からずらすマークアップ
    vol_lookback_seconds: float = 3600.0

    def contracts(self, start, end, pairs=None):
        from . import pricing
        out: list[BinaryContract] = []
        for c in self.contracts_spec:
            if not (start <= c.decision_time <= end):
                continue
            if pairs and c.pair not in pairs:
                continue
            sigma = self.underlying.realized_vol(c.pair, c.decision_time,
                                                 self.vol_lookback_seconds)
            p = _fair_prob(c, sigma)
            fair = 100.0 * p
            mid = fair + self.assumed_markup_points
            half = self.assumed_spread_points / 2.0
            bid = max(0.0, min(100.0, mid - half))
            ask = max(0.0, min(100.0, mid + half))
            out.append(BinaryContract(
                pair=c.pair, option_type=c.option_type, decision_time=c.decision_time,
                expiry_time=c.expiry_time, spot_at_decision=c.spot_at_decision,
                bid=bid, ask=ask, strike=c.strike, lower=c.lower, upper=c.upper,
                settled_yes=c.settled_yes))
        return out


def _fair_prob(c: BinaryContract, sigma: float) -> float:
    from . import pricing
    s, T = c.spot_at_decision, c.ttm_seconds
    if c.option_type == "ladder_above":
        return pricing.prob_finish_above(s, c.strike, sigma, T)
    if c.option_type == "ladder_below":
        return pricing.prob_finish_below(s, c.strike, sigma, T)
    if c.option_type == "one_touch":
        return pricing.prob_touch(s, c.strike, sigma, T)
    if c.option_type == "range_in":
        return pricing.prob_finish_in_range(s, c.lower, c.upper, sigma, T)
    if c.option_type == "tunnel_no_touch":
        return pricing.mc_prob(s, sigma, T, "double_no_touch",
                               lower=c.lower, upper=c.upper, n_paths=40_000, n_steps=128)
    raise ValueError(c.option_type)


def fair_prob(c: BinaryContract, sigma: float) -> float:
    """種別に応じたフェア成就確率（公開API）。"""
    return _fair_prob(c, sigma)
