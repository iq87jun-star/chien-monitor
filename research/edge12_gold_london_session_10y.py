#!/usr/bin/env python3
"""H3 — 金の日内シーズナリティ（ロンドン午前）（事前登録 docs/31）。

事前仮説: XAUUSD。ロンドン午前(07-11 UTC)に LONG（金フィックス・フロー由来の定型ドリフト）、
          時間決済。リスク単位=直近日次ATR。往復コスト厳格(実測スプレッド≈1.84bp相当)。
判定: alpha = 0.0167、6 ゲート + 分割標本。
★承認前は実行しない（docs/31 の承認待ち）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
ENTRY_H, EXIT_H = 7, 11          # ロンドン午前
COST_USD = 0.35                  # 往復 ~0.35 USD(実測スプレッド由来)


def build(entry_h=ENTRY_H, exit_h=EXIT_H, direction=+1):
    h1 = data.load_h1("XAUUSD").copy()
    df = h1[["high", "low", "close"]].astype(float)
    df["hour"] = pd.DatetimeIndex(df.index).hour
    df["day"] = pd.DatetimeIndex(df.index).normalize()
    # 日次ATR(直近20日)をリスク単位に
    daily_close = df.groupby("day")["close"].last()
    daily_ret = daily_close.diff().abs()
    atr = daily_ret.rolling(20).mean()
    rows = []
    for day, g in df.groupby("day"):
        ent = g[g["hour"] == entry_h]
        ex = g[g["hour"] == exit_h]
        if len(ent) == 0 or len(ex) == 0:
            continue
        a = float(atr.get(day, np.nan))
        if not (a > 0):
            continue
        entry_px = float(ent["close"].iloc[0])
        exit_px = float(ex["close"].iloc[0])
        rows.append((ent.index[0], (direction * (exit_px - entry_px) - COST_USD) / a))
    return engine.daily_R(pd.DataFrame(rows, columns=["time", "ret_R"]))


def main():
    d = build()
    # プラセボ: アジア時間(00-04)に同じ LONG → ロンドン特異性なら突出しないはず
    placebo = {"asia_session": build(entry_h=0, exit_h=4).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "H3_gold_london_session", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge12_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
