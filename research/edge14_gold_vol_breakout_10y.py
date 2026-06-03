#!/usr/bin/env python3
"""I2 — 金のボラ点火モメンタム（事前登録 docs/33）。

事前仮説: XAUUSD。当日レンジ>1.5×ATR20 かつ陽線→翌日 LONG / 陰線→翌日 SHORT。
          ボラ拡大の翌日継続を狙う。リスク単位=ATR、往復コスト実測(≈0.35USD)。
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
THRESH = 1.5
ATRW = 20
COST_USD = 0.35


def _gold_daily():
    if data.available("XAUUSD", "d"):
        return data.load_daily("XAUUSD")
    h1 = data.load_h1("XAUUSD")
    return h1.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def build(invert=False):
    d = _gold_daily()
    o, h, l, c = (d["open"].astype(float), d["high"].astype(float),
                  d["low"].astype(float), d["close"].astype(float))
    rng = (h - l)
    atr = rng.rolling(ATRW).mean()
    idx = d.index
    rows = []
    for i in range(ATRW, len(idx) - 1):
        a = float(atr.iloc[i])
        if not (a > 0) or not (rng.iloc[i] > THRESH * a):
            continue
        thrust = np.sign(c.iloc[i] - o.iloc[i])     # 陽線/陰線
        if thrust == 0:
            continue
        d_ = int(thrust) * (-1 if invert else 1)
        nxt = (c.iloc[i + 1] - c.iloc[i])           # 翌日リターン(USD)
        rows.append((idx[i + 1], (d_ * nxt - COST_USD) / a))
    return engine.daily_R(pd.DataFrame(rows, columns=["time", "ret_R"]))


def main():
    d = build(invert=False)
    placebo = {"inverted": build(invert=True).values}   # 逆方向が突出しないこと
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "I2_gold_vol_breakout", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge14_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
