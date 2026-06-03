#!/usr/bin/env python3
"""I3 — 実質金利→金（事前登録 docs/33）。

事前仮説: XAUUSD。US10Y が20日で低下→翌日 LONG / 上昇→翌日 SHORT（金の実質金利感応）。
判定: alpha = 0.0167、6 ゲート + 分割標本。E4/H2(金利→円)とは別＝金利→金。
★承認前は実行しない（docs/33 の承認待ち）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0167
LOOK = 20


def _gold_daily():
    if data.available("XAUUSD", "d"):
        return data.load_daily("XAUUSD")
    h1 = data.load_h1("XAUUSD")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def _signal():
    y10 = data.load_daily("US10Y")["close"].astype(float)
    d10 = y10 - y10.shift(LOOK)
    # 金利低下→金LONG(+1)、上昇→SHORT(-1)
    direction = pd.Series(np.where(d10 < 0, 1, np.where(d10 > 0, -1, 0)), index=y10.index)
    return direction[direction != 0].dropna()


def _trades(direction_series, cost_frac):
    px = _gold_daily()
    entries = pd.DatetimeIndex(direction_series.index) + pd.Timedelta(days=1)
    dmap = {t + pd.Timedelta(days=1): int(v) for t, v in direction_series.items()}
    return engine.event_trades_daily(px, entries, direction_map=dmap, hold_d=1, cost_frac=cost_frac)


def main():
    sig = _signal()
    d = engine.daily_R(_trades(sig, 0.0002))         # 金は ~1.8bp/片道
    d_cost = engine.daily_R(_trades(sig, 0.0004))
    rng = np.random.default_rng(0)
    shuffled = pd.Series(rng.permutation(sig.values), index=sig.index)
    placebo = {"shuffled_dir": engine.daily_R(_trades(shuffled, 0.0002)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "I3_rates_to_gold", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge15_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
