#!/usr/bin/env python3
"""E4 — 金利→円 リード・ラグ（事前登録 docs/27）。

事前仮説: 米 US2Y の日次変化が +1σ 超 → 翌日 USDJPY LONG / −1σ未満 → SHORT。
          中間帯は見送り。外生変数(金利)→FX のクロスアセット先行を検定する。
判定: alpha = 0.0125、6 ゲート。

★承認前は実行しない（docs/27 の承認待ち）。承認後 Drive の実10年で回す。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0125
SIGMA = 1.0
ROLL = 60


def _signal():
    y = data.load_daily("US2Y")["close"].astype(float)
    dy = y.diff()
    z = (dy - dy.rolling(ROLL).mean()) / dy.rolling(ROLL).std()
    direction = pd.Series(np.where(z > SIGMA, 1, np.where(z < -SIGMA, -1, 0)), index=y.index)
    sig = direction[direction != 0]
    return sig


def _trades(direction_series, cost_frac):
    # USDJPY 日足上で、シグナル日の翌営業日に建て1日保有
    usdjpy = data.load_daily("USDJPY") if data.available("USDJPY", "d") else None
    if usdjpy is None:
        # H1 しか無い場合は日足に変換
        h1 = data.load_h1("USDJPY")
        usdjpy = h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    entries = pd.DatetimeIndex(direction_series.index) + pd.Timedelta(days=1)
    dmap = {t + pd.Timedelta(days=1): int(v) for t, v in direction_series.items()}
    return engine.event_trades_daily(usdjpy, entries, direction_map=dmap, hold_d=1, cost_frac=cost_frac)


def main():
    sig = _signal()
    d = engine.daily_R(_trades(sig, 0.00007))
    d_cost = engine.daily_R(_trades(sig, 0.0003))

    # プラセボ: シグナルをシャッフルした方向（先行性が本物なら符号一致が必要）
    rng = np.random.default_rng(0)
    shuffled = pd.Series(rng.permutation(sig.values), index=sig.index)
    placebo = {"shuffled_direction": engine.daily_R(_trades(shuffled, 0.00007)).values}

    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "E4_rates_to_USDJPY", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    os.makedirs("reports", exist_ok=True)
    evaluate.dump_json(res, "reports/edge4_result.json")
    print("-> reports/edge4_result.json")


if __name__ == "__main__":
    main()
