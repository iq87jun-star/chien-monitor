#!/usr/bin/env python3
"""J3 — G10 FX の断面モメンタム（事前登録 docs/35）。対USDで相対強弱。
USDXXX 系(USDCAD/USDCHF/USDJPY)は符号反転して「XXX 通貨の対USDリターン」に直す。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import engine, evaluate, v7_reference, xs  # noqa: E402

ALPHA = 0.0167
UNIVERSE = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"]
INVERT = ["USDCAD", "USDCHF", "USDJPY"]      # 対USDの符号をそろえる


def main():
    _, rets = xs.load_universe(UNIVERSE, invert=INVERT)
    d = xs.cross_sectional_momentum(rets, lookback=63, frac=0.34, rebalance=21, cost_frac=0.0001)
    placebo = {"reversed_LS": (-xs.cross_sectional_momentum(rets, 63, 0.34, 21, cost_frac=0.0001)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "J3_xs_fx_momentum", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge18_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
