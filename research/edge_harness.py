"""
edge_harness.py — 汎用エッジ検定ハーネス（事前登録 docs/26 の6ゲート実装）

設計思想:
  - 候補ごとに変わるのは「シグナル（=トレード列の生成）」だけ。判定ゲートは全候補共通。
  - 各候補 runner (edge3a_..py 等) は generate_trades(data) -> Trades を実装し、
    本モジュールの evaluate_edge(...) に渡す。
  - 数値は JSON に単一スカラで書き出す（規律4: 表示破損のまま転記しない / JSON直読で転記）。

検定の中身（docs/26 §4 のゲート②③⑤⑥に対応）:
  ② 月次ブロック符号シャッフルの片側順列p（自己相関頑健）
  ③ 1年ずつ除外するジャックナイフの最大p
  ④ プラセボ（呼び出し側がプラセボ系列を渡す）
  ⑤ コスト後リターンで①②を再評価（呼び出し側がコスト計上済みリターンを渡す）
  ⑥ v7 週次リターンとの相関

依存: numpy, pandas, scipy（Colab 標準）。データ I/O は呼び出し側 / data_io.py。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# トレード表現
# --------------------------------------------------------------------------
@dataclass
class Trades:
    """1候補が生成するトレード列。

    必須列を持つ DataFrame をラップする:
      entry_time : pd.Timestamp (UTC)
      exit_time  : pd.Timestamp (UTC)
      symbol     : str
      direction  : +1 (long) / -1 (short)
      ret_gross  : float  グロス・リターン（建玉名目に対する小数。例: +0.004 = +0.4%）
      cost       : float  往復スプレッド+スワップのコスト（小数, >=0）。未計上なら 0。
    """
    df: pd.DataFrame

    REQUIRED = ("entry_time", "exit_time", "symbol", "direction", "ret_gross", "cost")

    def __post_init__(self):
        missing = [c for c in self.REQUIRED if c not in self.df.columns]
        if missing:
            raise ValueError(f"Trades is missing required columns: {missing}")
        self.df = self.df.sort_values("exit_time").reset_index(drop=True)

    @property
    def ret_net(self) -> pd.Series:
        return self.df["ret_gross"] - self.df["cost"].abs()

    def weekly_returns(self, use_net: bool = True) -> pd.Series:
        """ISO週ごとに合算したリターン系列（相関・順列検定の単位）。"""
        r = self.ret_net if use_net else self.df["ret_gross"]
        idx = pd.to_datetime(self.df["exit_time"], utc=True)
        s = pd.Series(r.values, index=idx)
        # 週次（月曜始まり）に合算
        return s.resample("W-MON").sum().fillna(0.0)

    def monthly_blocks(self, use_net: bool = True) -> pd.Series:
        r = self.ret_net if use_net else self.df["ret_gross"]
        idx = pd.to_datetime(self.df["exit_time"], utc=True)
        s = pd.Series(r.values, index=idx)
        return s.resample("MS").sum().fillna(0.0)


# --------------------------------------------------------------------------
# 統計検定
# --------------------------------------------------------------------------
def monthly_block_sign_permutation(
    monthly: pd.Series, n_perm: int = 20000, seed: int = 12345
) -> float:
    """月次ブロック符号シャッフルの片側順列p（自己相関頑健）。

    帰無: ブロック平均の符号はランダム。各置換で各月ブロックの符号を独立に±反転し、
    平均が観測値以上になる割合を p とする。月内の依存構造を壊さない（ブロック単位）。
    """
    x = monthly.values.astype(float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return 1.0
    obs = x.mean()
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, n))
    perm_means = (signs * x).mean(axis=1)
    # 片側（観測が正のエッジである前提）。+1 補正で 0 除去。
    p = (np.sum(perm_means >= obs) + 1) / (n_perm + 1)
    return float(p)


def jackknife_drop_year_maxp(
    monthly: pd.Series, n_perm: int = 20000, seed: int = 12345
) -> dict:
    """1年ずつ除外して順列pを再計算し、最大pと除外年を返す（特定年依存の検出）。"""
    monthly = monthly.copy()
    years = sorted({ts.year for ts in monthly.index})
    results = {}
    for y in years:
        sub = monthly[[ts.year != y for ts in monthly.index]]
        results[y] = monthly_block_sign_permutation(sub, n_perm=n_perm, seed=seed)
    if not results:
        return {"max_p": 1.0, "worst_year_excluded": None, "by_year": {}}
    worst_year = max(results, key=results.get)
    return {
        "max_p": float(results[worst_year]),
        "worst_year_excluded": int(worst_year),
        "by_year": {int(k): float(v) for k, v in results.items()},
    }


def corr_with_v7(strategy_weekly: pd.Series, v7_weekly: pd.Series) -> float:
    """v7 週次リターンとの相関（ゲート⑥）。共通週で揃えて Pearson。"""
    a, b = strategy_weekly.align(v7_weekly, join="inner")
    if len(a) < 8 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a.values, b.values)[0, 1])


def max_drawdown(weekly: pd.Series) -> float:
    """週次リターンの累積エクイティから最大ドローダウン（正の小数, 0.06=6%）。"""
    eq = (1.0 + weekly.fillna(0.0)).cumprod()
    peak = eq.cummax()
    dd = (eq - peak) / peak
    return float(-dd.min()) if len(dd) else 0.0


# --------------------------------------------------------------------------
# ゲート評価
# --------------------------------------------------------------------------
@dataclass
class GateResult:
    edge_id: str
    period: str
    alpha: float
    n_trades: int
    net_profit_10y: float          # ① 累積ネット（小数, 0.286 = +28.6%）
    perm_p_net: float              # ② / ⑤ コスト後ネットの順列p
    perm_p_gross: float            # 参考: グロス順列p
    jackknife_max_p: float         # ③
    placebo_pass: Optional[bool]   # ④ 呼び出し側判定（None=未評価）
    cost_survives: bool            # ⑤
    corr_v7: float                 # ⑥
    max_dd_at_budget: float        # 器(II) 実測 maxDD（採用予算）
    risk_budget_pct: float
    extra: dict = field(default_factory=dict)

    def gates(self) -> dict:
        g1 = self.net_profit_10y > 0
        g2 = self.perm_p_net < self.alpha
        g3 = self.jackknife_max_p <= 0.10
        g4 = bool(self.placebo_pass) if self.placebo_pass is not None else False
        g5 = self.cost_survives and g1 and g2
        g6 = (not np.isnan(self.corr_v7)) and abs(self.corr_v7) <= 0.30  # 低 or 負
        return {"g1_profit": g1, "g2_perm_p": g2, "g3_jackknife": g3,
                "g4_placebo": g4, "g5_cost": g5, "g6_independent": g6}

    def grade(self) -> str:
        g = self.gates()
        if all(g.values()):
            return "ADOPT"
        if self.net_profit_10y > 0 and self.perm_p_net < 0.10:
            return "LEAD"
        return "REJECT"

    def to_json(self) -> dict:
        out = asdict(self)
        out["gates"] = self.gates()
        out["grade"] = self.grade()
        return out


def evaluate_edge(
    edge_id: str,
    trades_net: Trades,
    v7_weekly: pd.Series,
    risk_budget_pct: float,
    placebo_fn: Optional[Callable[[], bool]] = None,
    period: str = "2016-01..2025-12",
    alpha: float = 0.0125,
    n_perm: int = 20000,
) -> GateResult:
    """1候補を全ゲートで評価し GateResult を返す。

    trades_net: cost 列にコストを計上済みの Trades。ret_gross はグロス。
    placebo_fn: ④の真偽を返す関数（曜日/他資産/SHORT対称などで対象だけ突出か）。
    """
    monthly_net = trades_net.monthly_blocks(use_net=True)
    monthly_gross = trades_net.monthly_blocks(use_net=False)
    weekly_net = trades_net.weekly_returns(use_net=True)

    p_net = monthly_block_sign_permutation(monthly_net, n_perm=n_perm)
    p_gross = monthly_block_sign_permutation(monthly_gross, n_perm=n_perm)
    jk = jackknife_drop_year_maxp(monthly_net, n_perm=n_perm)
    rho = corr_with_v7(weekly_net, v7_weekly)
    net_profit = float(trades_net.ret_net.sum())
    dd = max_drawdown(weekly_net)
    placebo = placebo_fn() if placebo_fn is not None else None

    return GateResult(
        edge_id=edge_id,
        period=period,
        alpha=alpha,
        n_trades=int(len(trades_net.df)),
        net_profit_10y=net_profit,
        perm_p_net=p_net,
        perm_p_gross=p_gross,
        jackknife_max_p=jk["max_p"],
        placebo_pass=placebo,
        cost_survives=(net_profit > 0 and p_net < alpha),
        corr_v7=rho,
        max_dd_at_budget=dd,
        risk_budget_pct=risk_budget_pct,
        extra={"jackknife_by_year": jk["by_year"],
               "worst_year_excluded": jk["worst_year_excluded"]},
    )


def write_result_json(result: GateResult, path: str) -> None:
    """規律4: 単一スカラの JSON を書き出す。docs へはここから直読・転記する。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_json(), f, ensure_ascii=False, indent=2)
    print(f"[WROTE] {path}  grade={result.grade()}  "
          f"p_net={result.perm_p_net:.4f}  net={result.net_profit_10y:+.4f}  "
          f"corr_v7={result.corr_v7:+.3f}  maxDD={result.max_dd_at_budget:.4f}")


if __name__ == "__main__":
    # 自己テスト: 既知の正エッジ（弱い正のドリフト）でゲートが動くか確認。
    rng = np.random.default_rng(0)
    idx = pd.date_range("2016-01-04", "2025-12-31", freq="W-MON", tz="UTC")
    # 真に正のドリフト + ノイズ
    rg = 0.0008 + rng.normal(0, 0.004, len(idx))
    df = pd.DataFrame({
        "entry_time": idx, "exit_time": idx + pd.Timedelta("1D"),
        "symbol": "TEST", "direction": 1, "ret_gross": rg,
        "cost": np.full(len(idx), 0.0001),
    })
    t = Trades(df)
    v7 = pd.Series(rng.normal(0, 0.004, len(idx)), index=idx)  # 無相関の偽v7
    res = evaluate_edge("SELFTEST", t, v7, risk_budget_pct=0.6,
                        placebo_fn=lambda: True, n_perm=5000)
    print(json.dumps(res.to_json(), ensure_ascii=False, indent=2))
