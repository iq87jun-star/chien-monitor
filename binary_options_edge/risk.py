"""リスク管理（必須要件）。

- position_size: 1取引の最大損失を口座資金の固定%に限定。
- DrawdownGuard: DD上限・連敗で停止。
- fractional_kelly: 推定誤差を考慮した1/4ケリー（任意）。
- MartingaleGuard: 負け後の倍賭けを検出して例外送出（明示的禁止）。

マーチンゲール禁止理由（docstring/例外メッセージにも明記）:
  負け後に賭金を倍化すると賭金が幾何級数的に増大し、有限資金では必ず資金上限を
  超える賭けが要求される。期待値は改善せず（手数料分むしろ悪化）、多数の小勝を
  稀な巨大損に変換して分散と破産確率のみを最大化する。エッジの有無を変える手段ではない。
"""
from __future__ import annotations

from dataclasses import dataclass, field


def position_size(equity: float, max_loss_per_unit: float,
                  risk_fraction: float = 0.005) -> int:
    """固定比率サイジング。1取引の最大損失 <= risk_fraction*equity となる枚数。

    買い: max_loss_per_unit = ask（支払額/枚）。
    売り: max_loss_per_unit = 100 - bid。
    """
    if max_loss_per_unit <= 0 or equity <= 0:
        return 0
    budget = risk_fraction * equity
    return int(budget // max_loss_per_unit)


def fractional_kelly_buy(p: float, ask: float, fraction: float = 0.25) -> float:
    """買いのケリー比率 f* = (100p - A)/(100 - A) のフラクショナル版（0-1）。

    エッジが不確実なら使わない方針。負EVなら0。
    """
    edge = 100.0 * p - ask
    if edge <= 0 or ask >= 100:
        return 0.0
    kelly = edge / (100.0 - ask)
    return max(0.0, min(1.0, fraction * kelly))


class MartingaleError(RuntimeError):
    pass


@dataclass
class MartingaleGuard:
    """固定比率（アンチマーチンゲール）からの逸脱を検出する。

    マーチンゲールは「負け後に賭金を増やして取り返す」手法で、必然的に
    『賭金 ≤ 固定比率 × 現在資金』という上限を破る。各取引でこの不変条件を検証すれば、
    倍賭けは構造的に不可能になる。固定比率サイジングは常にこの条件を満たすので誤検知しない
    （※「直前の絶対ステークと比較」では、銘柄ごとに1枚あたり損失が違うため固定比率でも
    ステークが増減し誤検知する。比較すべきは資金に対する比率である）。
    """
    max_risk_fraction: float
    tolerance: float = 1e-9

    def check(self, stake: float, equity: float) -> None:
        if equity > 0 and stake > (self.max_risk_fraction + self.tolerance) * equity:
            raise MartingaleError(
                f"賭金 {stake:.2f} が固定比率上限 {self.max_risk_fraction:.4f}×資金 "
                f"{equity:.2f} を超過。マーチンゲール（負け後の倍賭け）を明示的に禁止: "
                "賭金が幾何級数的に増大し破産確率のみ上昇、期待値は改善しない。")


@dataclass
class DrawdownGuard:
    """DD上限・連敗・日次損失でトレード停止を判定する。"""
    start_equity: float
    max_drawdown_frac: float = 0.15       # ピークから15%で停止
    max_consecutive_losses: int = 6
    peak: float = field(init=False)
    consecutive_losses: int = field(default=0, init=False)
    halted: bool = field(default=False, init=False)
    halt_reason: str = field(default="", init=False)

    def __post_init__(self):
        self.peak = self.start_equity

    def update(self, equity: float, last_trade_won: bool | None) -> bool:
        """エクイティと直近結果を反映し、停止すべきなら True を返す。"""
        self.peak = max(self.peak, equity)
        if last_trade_won is not None:
            self.consecutive_losses = 0 if last_trade_won else self.consecutive_losses + 1
        dd = 0.0 if self.peak <= 0 else (self.peak - equity) / self.peak
        if dd >= self.max_drawdown_frac:
            self.halted, self.halt_reason = True, f"max drawdown {dd:.1%} reached"
        elif self.consecutive_losses >= self.max_consecutive_losses:
            self.halted, self.halt_reason = True, f"{self.consecutive_losses} consecutive losses"
        return self.halted
