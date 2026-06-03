#!/usr/bin/env python3
"""F1 — 東京→欧州 セッション・ブレイクアウト（事前登録 docs/29）。

事前仮説: USDJPY。東京レンジ(00-06 UTC)の高安を欧州開始(07-09 UTC)がブレイクした方向に
          建て、20 UTC に時間決済。往復1.5pip厳格計上。リスク単位=東京レンジ幅。
判定: alpha = 0.0167、6 ゲート。

★承認前は実行しない（docs/29 の承認待ち）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
PIP = 0.01
RT_COST_PIPS = 1.5            # 往復コスト(厳格)
TOKYO = range(0, 6)          # 00-05 UTC
ENTRY_HOURS = (7, 8, 9)      # 欧州開始
EXIT_HOUR = 20


def build(direction_sign=+1):
    """direction_sign=+1: ブレイク方向に順張り（本仮説）。-1: 逆張り（プラセボ）。"""
    h1 = data.load_h1("USDJPY").copy()
    df = h1[["high", "low", "close"]].astype(float)
    df["hour"] = pd.DatetimeIndex(df.index).hour
    df["day"] = pd.DatetimeIndex(df.index).normalize()
    rows = []
    for day, g in df.groupby("day"):
        tok = g[g["hour"].isin(list(TOKYO))]
        if len(tok) < 3:
            continue
        t_hi, t_lo = tok["high"].max(), tok["low"].min()
        rng = t_hi - t_lo
        if not (rng > 0):
            continue
        win = g[g["hour"].isin(ENTRY_HOURS)]
        entered = None
        for t, row in win.iterrows():
            if row["close"] > t_hi:
                entered = (t, +1); break
            if row["close"] < t_lo:
                entered = (t, -1); break
        if entered is None:
            continue
        et, brk_dir = entered
        d_ = brk_dir * direction_sign
        after = g[g.index > et]
        ex_rows = after[after["hour"] == EXIT_HOUR]
        if len(ex_rows) == 0:
            if len(after) == 0:
                continue
            ex_t = after.index[-1]
        else:
            ex_t = ex_rows.index[0]
        entry_px, exit_px = float(g.loc[et, "close"]), float(g.loc[ex_t, "close"])
        cost = RT_COST_PIPS * PIP
        rows.append((et, (d_ * (exit_px - entry_px) - cost) / rng))
    return engine.daily_R(pd.DataFrame(rows, columns=["time", "ret_R"]))


def main():
    d = build(+1)
    placebo = {"fade_breakout": build(-1).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "F1_session_breakout_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge7_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
