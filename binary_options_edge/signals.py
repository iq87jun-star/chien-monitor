"""エントリーsignal自動生成。

⚠️ 設計の核（原則の強制）:
  本モジュールは「コスト控除後にEV>0の局面でのみエントリーsignalを出す」装置だが、
  さらに上位に **エッジ検証ゲート** を置く。すなわち、対象(種別×仮説)について
  バックテストで統計的に有意なエッジが *実証された証明書(EdgeCertificate)* が無い限り、
  signalは一切出さない（HOLD=エントリーなし）。

  これは恣意的な制約ではなく、ユーザーの大前提
  「エッジが見つからなければ『見つからない』と結論せよ。フィッティングで無理に作るな」
  をコードとして強制するもの。未実証のエッジに基づく自動エントリーは
  「統計的根拠のない推奨」であり禁止事項に当たるため、構造的に出せないようにする。

使い方:
  1. backtest で各 (仮説) の summarize を得る
  2. certify_edges() でゲートを通った仮説だけの EdgeCertificate 群を作る
  3. SignalEngine に証明書を渡し、ライブの提示(BinaryContract)に対し generate() を呼ぶ
  4. 証明書が無い/ゲート未通過なら、返るのは常に side="hold"（エントリーしない）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from . import pricing
from .data import BinaryContract, CalendarSource, UnderlyingSource, fair_prob
from .hypotheses import Context, HypothesisFilter, build_context
from .risk import position_size


# --------------------------------------------------------------------------- #
# エッジ検証証明書: これが無ければ signal は出ない
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EdgeCertificate:
    """ある仮説について「コスト控除後エッジが実証された」ことの証明。

    certify_edges() のゲート（CI下限>0, BH-FDR有意, Deflated Sharpe>閾値, 最低件数）を
    すべて満たした場合にのみ発行される。発行されなければ当該仮説の signal は出ない。
    """
    hypothesis_name: str
    mean_pnl_after_cost: float
    boot_ci_low: float
    deflated_sharpe: float
    n_trades: int
    significant_after_fdr: bool


def certify_edges(summaries: list[dict], fdr_significant: dict[str, bool],
                  min_trades: int = 200, min_dsr: float = 0.95,
                  ) -> dict[str, EdgeCertificate]:
    """summarize() 結果群から、ゲートを通った仮説の証明書を発行する。

    ゲート（全て満たす必要あり、論理AND）:
      - n_trades >= min_trades              （標本が小さすぎる見かけの勝ちを排除）
      - boot_ci95 下限 > 0                  （コスト控除後の平均EVが有意に正）
      - deflated_sharpe > min_dsr           （試行数補正後も有意）
      - BH-FDR で有意                        （多重検定の偽陽性を排除）
    1つでも欠ければ証明書は発行しない＝その仮説では自動エントリーしない。
    """
    certs: dict[str, EdgeCertificate] = {}
    for s in summaries:
        name = s.get("label", "")
        n = s.get("n_trades", 0) or 0
        ci = s.get("boot_ci95", (float("nan"), float("nan")))
        ci_low = ci[0] if isinstance(ci, (tuple, list)) else float("nan")
        dsr = s.get("deflated_sharpe(>0.95=signif)", float("nan"))
        sig = bool(fdr_significant.get(name, False))
        passed = (n >= min_trades
                  and ci_low > 0
                  and (dsr is not None and dsr == dsr and dsr > min_dsr)  # not NaN
                  and sig)
        if passed:
            certs[name] = EdgeCertificate(
                hypothesis_name=name, mean_pnl_after_cost=s["mean_pnl_points_after_cost"],
                boot_ci_low=ci_low, deflated_sharpe=dsr, n_trades=n,
                significant_after_fdr=sig)
    return certs


# --------------------------------------------------------------------------- #
# signal
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EntrySignal:
    """1つの提示に対するエントリー判断。side='hold' はエントリーしないことを意味する。"""
    decision_time: datetime
    pair: str
    option_type: str
    side: str                      # 'buy' / 'sell' / 'hold'
    model_p: float
    bid: float
    ask: float
    breakeven_prob: float          # 採用側の損益分岐 (buy:A/100, sell:B/100)
    edge_vs_mid: float             # p_model - mid/100
    ev_points: float               # コスト控除後の事前EV(ポイント)
    units: int                     # 固定比率サイジングの推奨枚数
    hypothesis: str                # 通過した仮説名（holdなら理由）
    reason: str

    @property
    def actionable(self) -> bool:
        return self.side in ("buy", "sell")


@dataclass
class SignalEngine:
    """検証済みエッジに基づくエントリーsignalを生成。証明書が無ければ常にhold。"""
    underlying: UnderlyingSource
    certificates: dict[str, EdgeCertificate]
    hypotheses: dict[str, HypothesisFilter]
    calendar: Optional[CalendarSource] = None
    vol_lookback_seconds: float = 3600.0
    min_ev_points: float = 0.0
    equity: float = 10_000.0
    risk_fraction: float = 0.005

    def _hold(self, c: BinaryContract, p: float, reason: str) -> EntrySignal:
        return EntrySignal(
            decision_time=c.decision_time, pair=c.pair, option_type=c.option_type,
            side="hold", model_p=p, bid=c.bid, ask=c.ask, breakeven_prob=c.mid / 100.0,
            edge_vs_mid=p - c.mid / 100.0, ev_points=0.0, units=0,
            hypothesis="", reason=reason)

    def generate(self, c: BinaryContract) -> EntrySignal:
        """ライブの1提示に対しエントリー判断を返す。

        ゲート順:
          0. 証明書が1つも無ければ即hold（エッジ未実証→自動エントリー禁止）
          1. ボラ推定不能なら hold
          2. 「証明書を持つ仮説」のフィルタを通過する局面か
          3. pricing.decide_trade でコスト控除後 EV>0 か
        すべて満たした場合のみ buy/sell を返す。
        """
        # ゲート0: エッジ未実証なら何も出さない（最重要）
        if not self.certificates:
            return self._hold(c, float("nan"),
                              "エッジ未実証: 検証で正のエッジが証明された仮説が無いため自動エントリーしない")

        sigma = self.underlying.realized_vol(c.pair, c.decision_time, self.vol_lookback_seconds)
        if not (sigma == sigma and sigma > 0):  # NaN/非正
            return self._hold(c, float("nan"), "ボラ推定不能: 安全側でhold")

        p = fair_prob(c, sigma)
        ctx = build_context(c, self.underlying, self.calendar)

        # ゲート2: 証明書を持つ仮説のうち、現局面で発火するものを探す
        active = [name for name, cert in self.certificates.items()
                  if name in self.hypotheses and self.hypotheses[name](c, ctx)]
        if not active:
            return self._hold(c, p, "検証済みエッジを持つ仮説のいずれも現局面で発火せず")

        # ゲート3: コスト控除後EV>0か
        decision = pricing.decide_trade(p, c.bid, c.ask, min_ev_points=self.min_ev_points)
        if not decision.tradable:
            return self._hold(c, p, "コスト控除後EV<=0（ノートレード帯）: 半スプレッドを超える優位なし")

        max_loss = c.ask if decision.side == "buy" else (100.0 - c.bid)
        units = position_size(self.equity, max_loss, self.risk_fraction)
        if units < 1:
            return self._hold(c, p, "固定比率サイジングで枚数0: 1取引リスク上限に収まらず")

        # 最も強い証明書（DSR最大）を採用仮説として記録
        best = max(active, key=lambda nm: self.certificates[nm].deflated_sharpe)
        return EntrySignal(
            decision_time=c.decision_time, pair=c.pair, option_type=c.option_type,
            side=decision.side, model_p=p, bid=c.bid, ask=c.ask,
            breakeven_prob=decision.breakeven, edge_vs_mid=decision.edge_vs_mid,
            ev_points=decision.ev_points, units=units, hypothesis=best,
            reason=f"検証済みエッジ[{best}]発火 & コスト控除後EV={decision.ev_points:.2f}pt>0")

    def generate_batch(self, contracts) -> list[EntrySignal]:
        return [self.generate(c) for c in contracts]
