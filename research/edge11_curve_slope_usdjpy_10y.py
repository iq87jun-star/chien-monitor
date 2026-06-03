#!/usr/bin/env python3
"""H2 — 金利カーブの傾き 2s10s → USDJPY（事前登録 docs/31）。

事前仮説: 2s10s スロープ(US10Y−US2Y)が20日でスティープ化(Δ>0)→ USDJPY LONG /
          フラット化(Δ<0)→ SHORT。期間構造・景気期待由来。
判定: alpha = 0.0167、6 ゲート + 分割標本。E4(2Y水準の日次変化)とは別物。
★承認前は実行しない（docs/31 の承認待ち）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
LOOK = 20


def _usdjpy_daily():
    if data.available("USDJPY", "d"):
        return data.load_daily("USDJPY")
    h1 = data.load_h1("USDJPY")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def _signal():
    y2 = data.load_daily("US2Y")["close"].astype(float)
    y10 = data.load_daily("US10Y")["close"].astype(float)
    slope = (y10 - y2).dropna()
    dslope = slope - slope.shift(LOOK)
    direction = pd.Series(np.sign(dslope), index=slope.index)
    return direction[direction != 0].dropna()


def _trades(direction_series, cost_frac):
    px = _usdjpy_daily()
    entries = pd.DatetimeIndex(direction_series.index) + pd.Timedelta(days=1)
    dmap = {t + pd.Timedelta(days=1): int(v) for t, v in direction_series.items()}
    return engine.event_trades_daily(px, entries, direction_map=dmap, hold_d=1, cost_frac=cost_frac)


def main():
    sig = _signal()
    d = engine.daily_R(_trades(sig, 0.00007))
    d_cost = engine.daily_R(_trades(sig, 0.0003))
    rng = np.random.default_rng(0)
    shuffled = pd.Series(rng.permutation(sig.values), index=sig.index)
    placebo = {"shuffled_slope_dir": engine.daily_R(_trades(shuffled, 0.00007)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "H2_curve_slope_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge11_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
