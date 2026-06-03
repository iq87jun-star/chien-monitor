#!/usr/bin/env python3
"""I1 — 株式のターン・オブ・マンス（事前登録 docs/33）。

事前仮説: SPX。月末最終営業日〜翌月第3営業日に LONG 保有（機関リバランス・フロー）。
判定: alpha = 0.0167、6 ゲート + 分割標本。
★承認前は実行しない（docs/33 の承認待ち）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
VOLW = 20




def build(window="tom"):
    spx = data.load_daily("SPX")["close"].astype(float)
    ret = spx.pct_change()
    vol = np.log(spx / spx.shift()).rolling(VOLW).std()
    idx = pd.DatetimeIndex(spx.index)
    g = pd.Series(idx, index=idx)
    sel = pd.Series(False, index=idx)
    for _, grp in g.groupby(idx.to_period("M")):
        labels = list(grp.index)              # tz-aware ラベルのまま扱う
        if window == "tom":
            picks = [labels[-1]] + labels[:3]  # 月末最終日 + 第1〜3営業日
        else:                                  # プラセボ: 月中(第8〜12営業日)
            picks = labels[7:12]
        for t in picks:
            sel.loc[t] = True
    j = pd.concat([ret.rename("ret"), vol.rename("vol")], axis=1)
    j["m"] = sel.values
    s = j[j["m"] & (j["vol"] > 0)].dropna()
    d = (s["ret"] / s["vol"])
    d.index = pd.DatetimeIndex(s.index)
    return d.sort_index()


def main():
    d = build("tom")
    placebo = {"mid_month": build("mid").values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "I1_equity_turn_of_month_SPX", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge13_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
