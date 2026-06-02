#!/usr/bin/env python3
"""E6 — 多資産（株価指数）平均回帰（事前登録 docs/27）。

事前仮説: SPX の前日リターンが極端分位（下位/上位 q）なら翌日は反対方向
          （オーバーナイト・リバーサル）。docs/21 は FX 平均回帰で全滅したが、
          指数の平均回帰は未検（未踏リスト明記）。
判定: alpha = 0.0125、6 ゲート。

★承認前は実行しない（docs/27 の承認待ち）。承認後 Drive の実10年で回す。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0125
Q = 0.10            # 下位/上位 10% を極端とみなす
ROLL = 252


def _direction_map(px):
    ret = px["close"].astype(float).pct_change()
    lo = ret.rolling(ROLL).quantile(Q)
    hi = ret.rolling(ROLL).quantile(1 - Q)
    idx = px.index
    dmap = {}
    for i in range(ROLL, len(idx) - 1):
        r = ret.iloc[i]
        if np.isnan(r):
            continue
        if r <= lo.iloc[i]:
            dmap[idx[i + 1]] = +1      # 急落翌日に買い戻し
        elif r >= hi.iloc[i]:
            dmap[idx[i + 1]] = -1      # 急騰翌日に売り
    return dmap


def _trades(px, dmap, cost_frac):
    entries = pd.DatetimeIndex(list(dmap.keys()))
    return engine.event_trades_daily(px, entries, direction_map=dmap, hold_d=1, cost_frac=cost_frac)


def main():
    px = data.load_daily("SPX")
    dmap = _direction_map(px)
    d = engine.daily_R(_trades(px, dmap, 0.0001))
    d_cost = engine.daily_R(_trades(px, dmap, 0.0005))

    # プラセボ: 同じ極端日に「順張り」（=回帰でなく継続）したら負ける/突出しないはず
    cont = {t: -v for t, v in dmap.items()}
    placebo = {"momentum_instead": engine.daily_R(_trades(px, cont, 0.0001)).values}

    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "E6_index_meanrev_SPX", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge6_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
