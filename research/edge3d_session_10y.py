"""
edge3d_session_10y.py — E3D: ボラ条件付きセッション・ブレイク（docs/26 §3 E3D）

固定ルール（LOCK 済）:
  東京レンジ = 00:00-07:00 UTC の高安。07:00 UTC 以降、当日ATR が「過去60日ATRの上位50%分位」
  のときのみ、レンジ上抜けで LONG／下抜けで SHORT（1日1回・先に出た方、ストップ&リバースなし）。
  決済 = 15:00 UTC 時間決済 or 0.8×レンジ幅の逆行ストップ。
  対象 EURUSD/GBPUSD（非JPY＝v7 と通貨直交）。コスト厳格計上。
想定 v7 相関: 低（非JPY・ブレイク機構）。

プラセボ: 同ルールを「低ボラ分位（下位50%）」に適用 → 高ボラ条件だけが突出するか（④）。
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data_io import load_h1, to_daily, load_v7_weekly, load_costs, cost_for, pip_size, DATA_DIR, report_path
from edge_harness import Trades, evaluate_edge, write_result_json

TARGETS = ["EURUSD", "GBPUSD"]
RANGE_END = "07:00"
EXIT_TIME = "15:00"
STOP_K = 0.8
ATR_LEN = 14
RISK_BUDGET_PCT = 0.6


def daily_atr(h1: pd.DataFrame, n: int) -> pd.Series:
    d = to_daily(h1)
    h, l, c = d["high"], d["low"], d["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def generate_trades(regime: str = "high") -> pd.DataFrame:
    """regime='high' が本登録、'low' はプラセボ（低ボラ分位）。"""
    costs = load_costs()
    rows = []
    for sym in TARGETS:
        h1 = load_h1(sym)
        atr = daily_atr(h1, ATR_LEN)
        atr_q = atr.rolling(60).median()  # 過去60日の中位
        for day, g in h1.groupby(h1.index.normalize()):
            tokyo = g.between_time("00:00", RANGE_END)
            after = g.between_time(RANGE_END, "23:59")
            if len(tokyo) < 3 or len(after) < 2:
                continue
            av, aq = atr.get(day, np.nan), atr_q.get(day, np.nan)
            if np.isnan(av) or np.isnan(aq):
                continue
            is_high = av >= aq
            if (regime == "high") != is_high:
                continue
            hi, lo = tokyo["high"].max(), tokyo["low"].min()
            rng = hi - lo
            if rng <= 0:
                continue
            # 先に出たブレイクを採用
            direction, entry, entry_t = 0, np.nan, None
            for t, row in after.iterrows():
                if row["high"] >= hi:
                    direction, entry, entry_t = +1, hi, t
                    break
                if row["low"] <= lo:
                    direction, entry, entry_t = -1, lo, t
                    break
            if direction == 0:
                continue
            # 決済: 逆行 0.8×range ストップ or 15:00 時間決済
            stop = entry - direction * STOP_K * rng
            exit_px, exit_t = np.nan, None
            seg = after[after.index >= entry_t]
            for t, row in seg.iterrows():
                if t.strftime("%H:%M") >= EXIT_TIME:
                    exit_px, exit_t = row["close"], t
                    break
                if (direction == 1 and row["low"] <= stop) or (direction == -1 and row["high"] >= stop):
                    exit_px, exit_t = stop, t
                    break
            if np.isnan(exit_px):
                exit_px, exit_t = seg["close"].iloc[-1], seg.index[-1]
            ret = direction * (exit_px - entry) / entry
            rows.append((entry_t, exit_t, sym, direction, ret, cost_for(sym, 0, costs)))
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "symbol",
                                       "direction", "ret_gross", "cost"])


def main():
    high_df = generate_trades("high")
    low_df = generate_trades("low")
    trades = Trades(high_df)
    v7 = load_v7_weekly()

    def placebo():
        hm = (high_df["ret_gross"] - high_df["cost"]).mean()
        lm = (low_df["ret_gross"] - low_df["cost"]).mean()
        return bool(hm > 0 and hm > lm)  # 高ボラ条件だけが突出するか

    res = evaluate_edge("E3D_session", trades, v7, risk_budget_pct=RISK_BUDGET_PCT,
                        placebo_fn=placebo, alpha=0.0125)
    write_result_json(res, report_path("edge3d_result.json"))


if __name__ == "__main__":
    main()
