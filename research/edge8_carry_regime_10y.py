#!/usr/bin/env python3
"""F2 — キャリー・レジーム条件付き保有（事前登録 docs/29）。

事前仮説: USDJPY。米2年金利(US2Y)が上昇レジーム(>120日MA)のときだけ LONG を継続保有、
          それ以外フラット。金利差キャリー(実需・スワップ)由来のドリフトを狙う。
          ※保守的に価格リターンのみで検定（正スワップが付けば上振れ方向）。
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
MA = 120
VOLW = 20


def _usdjpy_daily():
    if data.available("USDJPY", "d"):
        return data.load_daily("USDJPY")
    h1 = data.load_h1("USDJPY")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def build(regime_on=True):
    us2y = data.load_daily("US2Y")["close"].astype(float)
    ma = us2y.rolling(MA).mean()
    up = us2y > ma                       # 金利上昇レジーム
    px = _usdjpy_daily()["close"].astype(float)
    ret = px.pct_change()
    vol = np.log(px / px.shift()).rolling(VOLW).std()
    # 金利系列の日付に USDJPY をそろえる
    j = pd.concat([up.rename("up"), ret.rename("ret"), vol.rename("vol")], axis=1).dropna()
    mask = j["up"] if regime_on else ~j["up"]
    sel = j[mask & (j["vol"] > 0)]
    daily = (sel["ret"] / sel["vol"])    # LONG 保有の日次 R
    daily.index = pd.DatetimeIndex(daily.index)
    return daily.sort_index()


def main():
    d = build(regime_on=True)
    # プラセボ: 逆レジーム(金利下降局面)で同じ LONG 保有 → 突出しないはず
    placebo = {"rates_down_regime": build(regime_on=False).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "F2_carry_regime_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge8_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
