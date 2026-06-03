#!/usr/bin/env python3
"""F3 — リスクオフ安全資産フロー（事前登録 docs/29）。

事前仮説: USDJPY。VIX 高分位(リスクオフ, 252日80%ile)翌日に SHORT、1日保有。
          円の逃避需要を狙う。v7(=円ショート方向)との【負相関】を期待する分散先候補。
判定: alpha = 0.0167、6 ゲート。

★承認前は実行しない（docs/29 の承認待ち）。
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
VIX_Q = 0.80
ROLL = 252


def _usdjpy_daily():
    if data.available("USDJPY", "d"):
        return data.load_daily("USDJPY")
    h1 = data.load_h1("USDJPY")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def build(direction=-1, cost_frac=0.00007):
    vix = data.load_daily("VIX")["close"].astype(float)
    thr = vix.rolling(ROLL).quantile(VIX_Q)
    entries = vix.index[(vix > thr).fillna(False)] + pd.Timedelta(days=1)
    px = _usdjpy_daily()
    return engine.daily_R(engine.event_trades_daily(px, entries, direction, 1, cost_frac=cost_frac))


def main():
    d = build(direction=-1)                       # リスクオフ→USDJPY SHORT
    d_cost = build(direction=-1, cost_frac=0.0003)
    # プラセボ: 低ボラ・レジーム(下位20%)翌日に同じ SHORT → 突出しないはず
    vix = data.load_daily("VIX")["close"].astype(float)
    lo = vix.rolling(ROLL).quantile(0.20)
    lo_entries = vix.index[(vix < lo).fillna(False)] + pd.Timedelta(days=1)
    placebo = {"low_vol_regime": engine.daily_R(
        engine.event_trades_daily(_usdjpy_daily(), lo_entries, -1, 1)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "F3_riskoff_haven_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge9_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
