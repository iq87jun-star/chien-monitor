"""エッジ候補仮説の特徴量・フィルタ。

各仮説は「この局面でだけトレードを許可する」フィルタ、または
「フェア確率の補正」という形でエッジを表現する。
重要: ここで仮説を増やすほど多重検定の偽陽性が増える。試行数を必ず記録すること
（backtest 側で n_hypotheses_tried として集計）。

すべての特徴量は decision_time 時点で観測可能なものだけを使う（先読み禁止）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .data import BinaryContract, CalendarSource, UnderlyingSource

# Context は意思決定時に観測可能な外部情報をまとめたもの
@dataclass
class Context:
    sigma_short: float          # 短窓実現ボラ
    sigma_long: float           # 長窓実現ボラ
    next_event_sec: Optional[float]   # 次の関連指標までの秒数
    hour: int                   # 意思決定時刻(UTC)の時間帯
    trend_strength: float       # |長窓ドリフト|/ボラ 等の簡易トレンド指標


def build_context(c: BinaryContract, underlying: UnderlyingSource,
                  calendar: Optional[CalendarSource],
                  short_lb: float = 600.0, long_lb: float = 7200.0) -> Context:
    sig_s = underlying.realized_vol(c.pair, c.decision_time, short_lb)
    sig_l = underlying.realized_vol(c.pair, c.decision_time, long_lb)
    nxt = calendar.next_event_seconds(c.pair, c.decision_time) if calendar else None
    # 簡易トレンド: 長窓の対数リターン平均/ボラ
    start = c.decision_time - __import__("pandas").Timedelta(seconds=long_lb)
    hist = underlying.history(c.pair, start, c.decision_time)
    if len(hist) > 5:
        lr = np.diff(np.log(hist["mid"].to_numpy()))
        trend = float(np.nanmean(lr) / (np.nanstd(lr) + 1e-12))
    else:
        trend = 0.0
    return Context(sig_s, sig_l, nxt, c.decision_time.hour, trend)


# フィルタは (contract, context) -> bool（True=トレード許可）
HypothesisFilter = Callable[[BinaryContract, Context], bool]


def h1_vol_regime(sigma_ratio_threshold: float = 1.3) -> HypothesisFilter:
    """H1: 短窓ボラ/長窓ボラ が高い=ボラ拡大局面でのみ取引（touch割安を狙う仮説）。"""
    def f(c, ctx):
        if not (np.isfinite(ctx.sigma_short) and np.isfinite(ctx.sigma_long)) or ctx.sigma_long <= 0:
            return False
        return (ctx.sigma_short / ctx.sigma_long) >= sigma_ratio_threshold
    return f


def h2_session(active_hours: tuple[int, ...] = (7, 8, 12, 13, 14, 15)) -> HypothesisFilter:
    """H2: 高ボラ時間帯（欧州/NY重複, UTC）に限定。"""
    return lambda c, ctx: ctx.hour in active_hours


def h3_pre_event(window_seconds: float = 1800.0) -> HypothesisFilter:
    """H3: 指標発表の window 秒前以内（ジャンプリスク過小評価を狙う）。

    ⚠️ 実運用ではこの局面でIGが提示停止/スプレッド急拡大するため取れない可能性大。
    """
    def f(c, ctx):
        return ctx.next_event_sec is not None and 0 <= ctx.next_event_sec <= window_seconds
    return f


def h4_avoid_event(min_distance_seconds: float = 3600.0) -> HypothesisFilter:
    """対照仮説: 指標を避け、平穏なレンジ局面のみ。"""
    def f(c, ctx):
        return ctx.next_event_sec is None or ctx.next_event_sec >= min_distance_seconds
    return f


def h_point_band(lo: float = 7.0, hi: float = 25.0,
                 symmetric: bool = True) -> HypothesisFilter:
    """構造フィルタ: 提示mid(ポイント)が指定帯にある提示のみ許可。

    ⚠️ これは「エッジの源泉」ではなく「どこを見るか」の絞り込み(THEORY.md §8)。
    価格帯だけを条件にエントリーしても期待値は必ず−半スプレッド
    (価格=損益分岐勝率なので、安い玉はその分当たらない)。
    正しい用途は h_combine で確率モデル系の仮説と併用し、
    ボラ感応度の高い帯(ラダーなら|d|≈0.8-1.5 ⇔ 約7-25pt/75-93pt)に
    エントリー候補を限定すること。ATM近辺(40-60pt)はボラ中立で理論上取れない。

    symmetric=True なら鏡像帯(100-hi, 100-lo)も許可
    (安い玉の買いと高い玉の売りは同じ歪みの表裏のため)。
    """
    def f(c, ctx):
        m = c.mid
        if lo <= m <= hi:
            return True
        return symmetric and (100.0 - hi) <= m <= (100.0 - lo)
    return f


def h_combine(*filters: HypothesisFilter) -> HypothesisFilter:
    return lambda c, ctx: all(fl(c, ctx) for fl in filters)


def h_all() -> HypothesisFilter:
    """ベースライン: 全件（EV>0判定のみに委ねる）。"""
    return lambda c, ctx: True


# レジストリ: 試した仮説を列挙し試行数を数えるために使う
def default_hypotheses() -> dict[str, HypothesisFilter]:
    return {
        "H0_all": h_all(),
        "H1_vol_regime": h1_vol_regime(),
        "H2_session": h2_session(),
        "H3_pre_event": h3_pre_event(),
        "H4_avoid_event": h4_avoid_event(),
        "H1xH2": h_combine(h1_vol_regime(), h2_session()),
    }
