"""バックテスト本体。

設計の核:
- 評価は必ず「コスト控除後」= 実約定値(A/B)を使った realized_pnl_points のみ。
  スプレッド控除前の見かけ成績は一切集計しない。
- 先読み禁止: フェア確率は decision_time 時点の実現ボラのみで算出。
- 多重検定: 試した仮説名の集合 n_hypotheses_tried を保持し DSR/BH に渡す。
- レジーム別安定性: ボラ3分位・時間帯・トレンドでサブサンプルし符号一貫性を確認。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from . import pricing, stats_tests
from .data import BinaryContract, CalendarSource, IGQuoteSource, UnderlyingSource, fair_prob
from .hypotheses import Context, HypothesisFilter, build_context, h_all
from .risk import DrawdownGuard, MartingaleGuard, position_size


@dataclass
class Trade:
    contract: BinaryContract
    side: str
    model_p: float
    ev_ex_ante: float       # 事前EV(ポイント)
    pnl_points: float       # 実現損益(ポイント, コスト控除後)
    won: bool
    sigma: float
    ctx: Context


@dataclass
class BacktestResult:
    trades: list[Trade]
    n_hypotheses_tried: int

    @property
    def pnl(self) -> np.ndarray:
        return np.array([t.pnl_points for t in self.trades], dtype=float)

    @property
    def n(self) -> int:
        return len(self.trades)

    def to_frame(self) -> pd.DataFrame:
        rows = []
        for t in self.trades:
            rows.append({
                "decision_time": t.contract.decision_time,
                "pair": t.contract.pair, "type": t.contract.option_type,
                "side": t.side, "model_p": t.model_p, "breakeven": t.contract.mid / 100.0,
                "ev_ex_ante": t.ev_ex_ante, "pnl_points": t.pnl_points, "won": t.won,
                "sigma": t.sigma, "hour": t.ctx.hour, "trend": t.ctx.trend_strength,
            })
        return pd.DataFrame(rows)


def run_backtest(contracts: Iterable[BinaryContract],
                 underlying: UnderlyingSource,
                 calendar: Optional[CalendarSource] = None,
                 hypothesis: HypothesisFilter | None = None,
                 vol_lookback_seconds: float = 3600.0,
                 min_ev_points: float = 0.0,
                 n_hypotheses_tried: int = 1) -> BacktestResult:
    """1つの仮説フィルタでバックテストを実行（コスト控除後損益のみ集計）。"""
    hyp = hypothesis or h_all()
    trades: list[Trade] = []
    for c in contracts:
        if c.settled_yes is None:
            continue
        sigma = underlying.realized_vol(c.pair, c.decision_time, vol_lookback_seconds)
        if not np.isfinite(sigma) or sigma <= 0:
            continue
        ctx = build_context(c, underlying, calendar)
        if not hyp(c, ctx):
            continue
        p = fair_prob(c, sigma)
        decision = pricing.decide_trade(p, c.bid, c.ask, min_ev_points=min_ev_points)
        if not decision.tradable:
            continue
        pnl = pricing.realized_pnl_points(decision.side, c.settled_yes, c.bid, c.ask)
        trades.append(Trade(c, decision.side, p, decision.ev_points, pnl,
                            pnl > 0, sigma, ctx))
    return BacktestResult(trades, n_hypotheses_tried)


def equity_curve(result: BacktestResult, start_equity: float = 10_000.0,
                 risk_fraction: float = 0.005,
                 max_drawdown_frac: float = 0.15) -> pd.DataFrame:
    """固定比率サイジング＋DD/連敗停止＋マーチンゲール監視でエクイティ曲線を生成。"""
    equity = start_equity
    dd = DrawdownGuard(start_equity, max_drawdown_frac=max_drawdown_frac)
    mart = MartingaleGuard(max_risk_fraction=risk_fraction)
    rows = []
    last_won: bool | None = None
    for t in result.trades:
        if dd.update(equity, last_won):
            rows.append({"decision_time": t.contract.decision_time, "equity": equity,
                         "halted": True, "reason": dd.halt_reason})
            break
        max_loss_per_unit = t.contract.ask if t.side == "buy" else (100.0 - t.contract.bid)
        units = position_size(equity, max_loss_per_unit, risk_fraction)
        stake = units * max_loss_per_unit
        mart.check(stake, equity)         # 固定比率上限を超えたら例外（倍賭け検出）
        # pnl_points は1枚あたり。100ポイント=1単位額面と仮定し units 枚分。
        equity += units * t.pnl_points
        last_won = t.won
        rows.append({"decision_time": t.contract.decision_time, "equity": equity,
                     "units": units, "pnl": units * t.pnl_points, "halted": False})
    return pd.DataFrame(rows)


_SUMMARY_KEYS = (
    "label", "n_trades", "mean_pnl_points_after_cost", "boot_ci95",
    "boot_p(mean<=0)", "t_pvalue_mean>0", "win_rate", "avg_breakeven_prob",
    "win_rate_minus_breakeven", "sharpe_per_trade", "deflated_sharpe(>0.95=signif)",
    "n_hypotheses_tried", "edge_detected_after_cost",
)


def summarize(result: BacktestResult, label: str = "") -> dict:
    """コスト控除後の総括統計（CI, t検定, Deflated Sharpe）。

    トレード0件でも常に同じキー集合を返す（呼び出し側の DataFrame 列選択を壊さないため）。
    """
    pnl = result.pnl
    if result.n == 0:
        # 全キーをNaN/Falseで埋める。「トレード機会なし=エッジ検出なし」が正しい結論。
        empty = {k: float("nan") for k in _SUMMARY_KEYS}
        empty.update(label=label, n_trades=0,
                     n_hypotheses_tried=result.n_hypotheses_tried,
                     edge_detected_after_cost=False, boot_ci95=(float("nan"), float("nan")))
        return empty
    boot = stats_tests.moving_block_bootstrap_mean(pnl)
    dsr = stats_tests.deflated_sharpe_ratio(pnl, n_trials=result.n_hypotheses_tried)
    win_rate = float(np.mean([t.won for t in result.trades]))
    avg_breakeven = float(np.mean([t.contract.mid / 100.0 for t in result.trades]))
    return {
        "label": label,
        "n_trades": result.n,
        "mean_pnl_points_after_cost": float(pnl.mean()),
        "boot_ci95": (boot.ci_low, boot.ci_high),
        "boot_p(mean<=0)": boot.p_value_gt0,
        "t_pvalue_mean>0": stats_tests.t_test_mean_gt0(pnl),
        "win_rate": win_rate,
        "avg_breakeven_prob": avg_breakeven,
        "win_rate_minus_breakeven": win_rate - avg_breakeven,
        "sharpe_per_trade": dsr["sr"],
        "deflated_sharpe(>0.95=signif)": dsr["dsr"],
        "n_hypotheses_tried": result.n_hypotheses_tried,
        "edge_detected_after_cost": bool(boot.ci_low > 0 and dsr["dsr"] > 0.95),
    }


def regime_stability(result: BacktestResult) -> pd.DataFrame:
    """ボラ3分位・時間帯ブロック・トレンド符号で部分集計し、符号一貫性を確認。"""
    df = result.to_frame()
    if df.empty:
        return df
    out = []
    # ボラ3分位（ビンが潰れても落ちないよう labels=False で整数コード化）
    try:
        df["vol_bucket"] = pd.qcut(df["sigma"], 3, labels=False, duplicates="drop")
    except (ValueError, IndexError):
        df["vol_bucket"] = 0
    for name, sub in df.groupby("vol_bucket", observed=True):
        out.append(_regime_row(f"vol_q={name}", sub))
    # 時間帯ブロック
    df["sess"] = pd.cut(df["hour"], [-1, 6, 12, 18, 24],
                        labels=["asia", "eu_open", "eu_us", "us_late"])
    for name, sub in df.groupby("sess", observed=True):
        out.append(_regime_row(f"sess={name}", sub))
    # トレンド符号
    for name, sub in df.groupby(np.sign(df["trend"]), observed=True):
        out.append(_regime_row(f"trend_sign={int(name)}", sub))
    return pd.DataFrame(out)


def _regime_row(name: str, sub: pd.DataFrame) -> dict:
    pnl = sub["pnl_points"].to_numpy()
    boot = stats_tests.moving_block_bootstrap_mean(pnl, n_boot=2000)
    return {"regime": name, "n": len(sub), "mean_pnl_after_cost": float(pnl.mean()),
            "ci_low": boot.ci_low, "ci_high": boot.ci_high,
            "positive": boot.ci_low > 0}


def walk_forward(contracts: list[BinaryContract], underlying: UnderlyingSource,
                 calendar: Optional[CalendarSource],
                 hypothesis: HypothesisFilter,
                 train_days: int = 180, test_days: int = 30,
                 n_hypotheses_tried: int = 1) -> pd.DataFrame:
    """ローリング・ウォークフォワード。

    本フレームワークの仮説はパラメータ学習を伴わない閾値式なので、ここでは
    各 test 窓ごとに OOS 成績を出し、窓間の安定性を見る（IS/OOS乖離検知の土台）。
    パラメータ学習を導入する場合は train 窓内で閾値を決め test 窓で評価するよう拡張する。
    """
    if not contracts:
        return pd.DataFrame()
    contracts = sorted(contracts, key=lambda c: c.decision_time)
    t0 = contracts[0].decision_time
    t_end = contracts[-1].decision_time
    rows = []
    cur = t0 + pd.Timedelta(days=train_days)
    while cur < t_end:
        test_start, test_end = cur, cur + pd.Timedelta(days=test_days)
        window = [c for c in contracts if test_start <= c.decision_time < test_end]
        res = run_backtest(window, underlying, calendar, hypothesis,
                           n_hypotheses_tried=n_hypotheses_tried)
        s = summarize(res, label=f"OOS {test_start.date()}..{test_end.date()}")
        rows.append(s)
        cur = test_end
    return pd.DataFrame(rows)
