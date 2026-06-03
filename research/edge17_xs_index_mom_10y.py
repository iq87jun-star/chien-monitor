#!/usr/bin/env python3
"""J2 — 世界株価指数の断面モメンタム（事前登録 docs/35）。universe: SPX/NDX/N225/DAX/FTSE。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import engine, evaluate, v7_reference, xs  # noqa: E402

ALPHA = 0.0167
UNIVERSE = ["SPX", "NDX", "N225", "DAX", "FTSE"]


def main():
    _, rets = xs.load_universe(UNIVERSE)
    d = xs.cross_sectional_momentum(rets, lookback=63, frac=0.34, rebalance=21)
    placebo = {"reversed_LS": (-xs.cross_sectional_momentum(rets, 63, 0.34, 21)).values}
    v7_corr = v7_reference.corr_with_v7(d)
    res = evaluate.evaluate(
        "J2_xs_index_momentum", ALPHA, d.values, d.index,
        placebo_dailies=placebo, v7_corr=v7_corr,
    )
    res["mc_pass_rate_0.6pct"] = engine.mc_pass_rate(d, per_shot_risk_pct=0.6)
    evaluate.print_summary(res)
    out = evaluate.reports_path("edge17_result.json")
    evaluate.dump_json(res, out)
    print("->", out)


if __name__ == "__main__":
    main()
