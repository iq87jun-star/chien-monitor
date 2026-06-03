#!/usr/bin/env python3
"""H1 — 株式の分散リスクプレミアム VRP → SPX（事前登録 docs/31）。

事前仮説: VRP = VIX − 実現ボラ(20日年率) が高レジーム(60日中央値超)のとき SPX を LONG 保有。
          オプション需給(保険プレミアム)由来の株式リターンを狙う。
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
RVW = 20
MEDW = 60


def build(high_regime=True):
    spx = data.load_daily("SPX")["close"].astype(float)
    vix = data.load_daily("VIX")["close"].astype(float)
    ret = np.log(spx / spx.shift())
    rv = ret.rolling(RVW).std() * np.sqrt(252) * 100.0     # 実現ボラ(VIX と同単位)
    vrp = (vix - rv)
    thr = vrp.rolling(MEDW).median()
    j = pd.concat([vrp.rename("vrp"), thr.rename("thr"),
                   ret.rename("ret"), rv.rename("rv")], axis=1, join="inner").dropna()
    cond = (j["vrp"] > j["thr"]) if high_regime else (j["vrp"] <= j["thr"])
    sel = j[cond & (j["rv"] > 0)]
    vol = sel["rv"] / (np.sqrt(252) * 100.0)               # 日次ボラに戻す
    daily = (sel["ret"] / vol)
    daily.index = pd.DatetimeIndex(daily.index)
    return daily.sort_index()


def main():
    d = build(high_regime=True)
    placebo = {"low_vrp_regime": build(high_regime=False).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "H1_VRP_SPX", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge10_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
