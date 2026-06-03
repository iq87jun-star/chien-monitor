"""
edge3c_carry_10y.py — E3C: 横断キャリー（スポット超過収益のみ。docs/26 §3 E3C）

固定ルール（LOCK 済）:
  毎週月曜、G10 を「対USD政策金利差」で順位付け。上位3を LONG・下位3を SHORT（対USD）、
  週次リバランス・保有1週間。**PnL はスポット価格変化のみ**（受取スワップは 0 扱い＝価格エッジを分離）。
  受取スワップ込みは参考併記のみ（判定には使わない）。
想定 v7 相関: 低〜負（JPY は低金利で常時 SHORT になりがち → v7 の JPY-LONG と負相関の可能性）。
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data_io import load_h1, load_v7_weekly, load_costs, cost_for, DATA_DIR, report_path
from edge_harness import Trades, evaluate_edge, write_result_json

# 対USDペアのシンボルと、その通貨（USD が quote/ base かでスポット符号を合わせる）
# ここでは「対USD ロング = その通貨高で利益」になるよう ret を定義する。
G10 = {
    "EURUSD": ("EUR", +1), "GBPUSD": ("GBP", +1), "AUDUSD": ("AUD", +1),
    "NZDUSD": ("NZD", +1), "USDJPY": ("JPY", -1), "USDCHF": ("CHF", -1),
    "USDCAD": ("CAD", -1), "USDSEK": ("SEK", -1), "USDNOK": ("NOK", -1),
}
N_LEG = 3
RISK_BUDGET_PCT = 0.6


def load_policy_rates() -> pd.DataFrame:
    """policy_rates_monthly.csv: date, ccy, rate（対USDの差は USD 行から算出）。"""
    df = pd.read_csv(os.path.join(DATA_DIR, "policy_rates_monthly.csv"), comment="#")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.pivot(index="date", columns="ccy", values="rate").sort_index()


def weekly_spot_return(sym: str) -> pd.Series:
    """対USD週次スポットリターン（quote=USD のとき符号反転して『通貨高=正』に統一）。"""
    h = load_h1(sym)
    wk = h["close"].resample("W-MON").last()
    ret = wk.pct_change()
    return ret * G10[sym][1]


def generate_trades(shuffle_ranks: bool = False, seed: int = 0) -> pd.DataFrame:
    rates = load_policy_rates().reindex(columns=[v[0] for v in G10.values()])
    usd = load_policy_rates().get("USD")
    rets = {sym: weekly_spot_return(sym) for sym in G10}
    weeks = sorted(set.intersection(*[set(r.index) for r in rets.values()]))
    costs = load_costs()
    rng = np.random.default_rng(seed)
    rows = []
    for wk in weeks:
        # 月曜時点で有効な最新の月次金利差（対USD）
        rt = rates.loc[:wk]
        if rt.empty:
            continue
        last = rt.iloc[-1]
        u = usd.loc[:wk].iloc[-1] if usd is not None else 0.0
        diff = (last - u).dropna()
        if len(diff) < 2 * N_LEG:
            continue
        order = list(diff.sort_values(ascending=False).index)
        if shuffle_ranks:
            rng.shuffle(order)  # プラセボ: ランク無効化
        longs = order[:N_LEG]
        shorts = order[-N_LEG:]
        ccy2sym = {G10[s][0]: s for s in G10}
        for ccy, sgn in [(c, +1) for c in longs] + [(c, -1) for c in shorts]:
            sym = ccy2sym.get(ccy)
            if sym is None:
                continue
            r = rets[sym].get(wk, np.nan)
            if np.isnan(r):
                continue
            # スワップ除外（include_swap=False）＝スポット価格エッジのみ
            rows.append((wk, wk, sym, sgn, sgn * r,
                         cost_for(sym, 0, costs, include_swap=False)))
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "symbol",
                                       "direction", "ret_gross", "cost"])


def main():
    real = generate_trades(shuffle_ranks=False)
    placebo_df = generate_trades(shuffle_ranks=True, seed=42)
    trades = Trades(real)
    v7 = load_v7_weekly()

    def placebo():
        rm = (real["ret_gross"] - real["cost"]).mean()
        pm = (placebo_df["ret_gross"] - placebo_df["cost"]).mean()
        return bool(rm > 0 and rm > pm)  # ランク付けに意味があるか

    res = evaluate_edge("E3C_carry_spot", trades, v7, risk_budget_pct=RISK_BUDGET_PCT,
                        placebo_fn=placebo, alpha=0.0125)
    write_result_json(res, report_path("edge3c_result.json"))


if __name__ == "__main__":
    main()
