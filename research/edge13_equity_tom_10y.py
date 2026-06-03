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


def _tom_mask(idx: pd.DatetimeIndex):
    """月末最終営業日(=その月の最後)＋翌月第1〜3営業日 を True。"""
    s = pd.Series(0, index=idx)
    months = idx.to_period("M")
    # 各月の最終営業日
    last = pd.Series(idx, index=idx).groupby(months).max()
    s.loc[last.values] = 1
    # 各月の最初の3営業日
    for _, g in pd.Series(idx, index=idx).groupby(months):
        for t in g.values[:3]:
            s.loc[t] = 1
    return s.astype(bool)


def build(window="tom"):
    spx = data.load_daily("SPX")["close"].astype(float)
    ret = spx.pct_change()
    vol = np.log(spx / spx.shift()).rolling(VOLW).std()
    idx = pd.DatetimeIndex(spx.index)
    tom = _tom_mask(idx)
    if window == "tom":
        mask = tom
    else:  # プラセボ: 月の中旬(第8〜12営業日)
        mid = pd.Series(False, index=idx)
        for _, g in pd.Series(idx, index=idx).groupby(idx.to_period("M")):
            for t in g.values[7:12]:
                mid.loc[t] = True
        mask = mid
    j = pd.concat([ret.rename("ret"), vol.rename("vol")], axis=1)
    j["m"] = mask.values
    sel = j[j["m"] & (j["vol"] > 0)].dropna()
    d = (sel["ret"] / sel["vol"])
    d.index = pd.DatetimeIndex(sel.index)
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
