#!/usr/bin/env python3
"""J1 — 商品の断面モメンタム（事前登録 docs/35）。universe: 金/銀/WTI/銅。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import engine, evaluate, v7_reference, xs  # noqa: E402

ALPHA = 0.0167
UNIVERSE = ["GOLD", "SILVER", "WTI", "COPPER"]


def main():
    _, rets = xs.load_universe(UNIVERSE)
    d = xs.cross_sectional_momentum(rets, lookback=63, frac=0.34, rebalance=21)
    placebo = {"reversed_LS": (-xs.cross_sectional_momentum(rets, 63, 0.34, 21)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "J1_xs_commodity_momentum", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge16_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
