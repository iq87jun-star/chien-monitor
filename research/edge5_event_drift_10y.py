#!/usr/bin/env python3
"""E5 — イベント・ドリブン定型ドリフト（事前登録 docs/27）。

事前仮説: FOMC/BOJ 決定の翌営業日に、決定日当日リターンの符号へ順張り
          （post-announcement drift, PEAD 的）。USDJPY を対象とする。
判定: alpha = 0.0125、6 ゲート。

データ: events_cb_d.csv（列 time,kind  kind∈{FOMC,BOJ}）。
★承認前は実行しない（docs/27 の承認待ち）。承認後 Drive の実10年で回す。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0125


def _usdjpy_daily():
    if data.available("USDJPY", "d"):
        return data.load_daily("USDJPY")
    h1 = data.load_h1("USDJPY")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def _events():
    path = os.path.join(data.data_dir(), "events_cb_d.csv")
    ev = pd.read_csv(path)
    ev.columns = [c.strip().lower() for c in ev.columns]
    ev["time"] = pd.to_datetime(ev["time"], utc=True)
    return ev.sort_values("time")


def _trades(direction_map, cost_frac):
    px = _usdjpy_daily()
    entries = pd.DatetimeIndex(list(direction_map.keys()))
    return engine.event_trades_daily(px, entries, direction_map=direction_map, hold_d=1, cost_frac=cost_frac)


def _direction_map(px):
    ev = _events()
    ret = px["close"].astype(float).pct_change()
    dmap = {}
    idx = px.index
    for t in pd.DatetimeIndex(ev["time"]):
        pos = idx.searchsorted(t)
        if pos <= 0 or pos + 1 >= len(idx):
            continue
        day_ret = float(ret.iloc[pos]) if not np.isnan(ret.iloc[pos]) else 0.0
        sgn = 1 if day_ret > 0 else (-1 if day_ret < 0 else 0)
        if sgn != 0:
            dmap[idx[pos + 1]] = sgn          # 翌営業日に決定日符号へ順張り
    return dmap


def main():
    px = _usdjpy_daily()
    dmap = _direction_map(px)
    d = engine.daily_R(_trades(dmap, 0.00007))
    d_cost = engine.daily_R(_trades(dmap, 0.0003))

    # プラセボ: 決定日でないランダム日に同じ「前日符号順張り」を適用
    rng = np.random.default_rng(0)
    rand_days = pd.DatetimeIndex(rng.choice(px.index[5:-2], size=min(len(dmap) * 3, len(px) - 7), replace=False))
    ret = px["close"].astype(float).pct_change()
    pmap = {}
    for t in rand_days:
        pos = px.index.searchsorted(t)
        if 0 < pos < len(px) - 1:
            r = float(ret.iloc[pos]) if not np.isnan(ret.iloc[pos]) else 0.0
            if r != 0:
                pmap[px.index[pos + 1]] = 1 if r > 0 else -1
    placebo = {"random_days": engine.daily_R(_trades(pmap, 0.00007)).values}

    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "E5_cb_event_drift_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge5_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
