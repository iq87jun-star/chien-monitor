#!/usr/bin/env python3
"""E3 — ボラ・レジーム条件付き安全資産（事前登録 docs/27）。

事前仮説: VIX が高分位(リスクオフ)に入った翌営業日、XAUUSD を LONG・1日保有。
          レジームでオン/オフするので常時建てない（v7 と駆動因子が別）。
判定: alpha = 0.0125、6 ゲート（lib/evaluate）。

★承認前は実行しない（docs/27 の承認待ち）。承認後 Drive の実10年で回す。
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data, engine, evaluate, v7_reference  # noqa: E402

ALPHA = 0.0125
VIX_QUANTILE = 0.80      # 上位20%をリスクオフ・レジームとみなす
ROLL = 252               # 分位の参照窓（約1年）


def build():
    vix = data.load_daily("VIX")["close"].astype(float)
    thr = vix.rolling(ROLL).quantile(VIX_QUANTILE)
    risk_off = vix > thr                                   # その日の判定 → 翌日エントリー
    entries = vix.index[risk_off.fillna(False)]
    entries = entries + pd.Timedelta(days=1)               # 翌営業日（searchsorted が前進補正）

    xau = data.load_daily("XAUUSD")
    trades = engine.event_trades_daily(xau, entries, direction_map=+1, hold_d=1, cost_frac=0.0001)
    trades_cost = engine.event_trades_daily(xau, entries, direction_map=+1, hold_d=1, cost_frac=0.0005)
    return trades, trades_cost


def main():
    trades, trades_cost = build()
    d = engine.daily_R(trades)
    d_cost = engine.daily_R(trades_cost)

    # プラセボ: 低ボラ・レジーム(下位20%)では出ないはず & ランダム日では出ないはず
    vix = data.load_daily("VIX")["close"].astype(float)
    lo_thr = vix.rolling(ROLL).quantile(0.20)
    lo_entries = (vix.index[(vix < lo_thr).fillna(False)] + pd.Timedelta(days=1))
    xau = data.load_daily("XAUUSD")
    placebo_lo = engine.daily_R(engine.event_trades_daily(xau, lo_entries, +1, 1))
    placebo = {"low_vol_regime": placebo_lo}

    # v7 相関（週次）
    v7_corr = v7_reference.corr_with_v7(d)

    res = evaluate.evaluate(
        "E3_vol_regime_XAUUSD", ALPHA, d.values, d.index,
        placebo_dailies={k: v.values for k, v in placebo.items()},
        v7_corr=v7_corr, daily_cost_adjusted=d_cost.values,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    os.makedirs("reports", exist_ok=True)
    evaluate.dump_json(res, "reports/edge3_result.json")
    print("-> reports/edge3_result.json")


if __name__ == "__main__":
    main()
