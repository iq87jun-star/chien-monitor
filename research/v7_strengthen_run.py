#!/usr/bin/env python3
"""v7 強化: baseline vs VF1/VF2/VF3 を比較（事前登録 docs/37）。

成功条件: ベースライン比で maxDD 縮小 ∧ Calmar 改善 ∧ MC合格率向上 ∧ 前後半とも改善。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import engine, evaluate, v7_strengthen as v7  # noqa: E402

WR = 1.5   # 評価予算(weekly%)


def assess(name, filt):
    d = v7.v7_daily_R(filt=filt)
    es = v7.equity_stats(d, WR)
    sh = v7.split_half_equity(d, WR)
    mc = engine.mc_pass_rate(d, per_shot_risk_pct=WR / v7.SHOTS,
                             target_pct=8.0, dd_pct=10.0, daily_dd_pct=None)
    return {
        "name": name, "n_trade_days": es["n_days"],
        "net_total_pct": es["net_total_pct"], "maxDD_pct": es["maxDD_pct"],
        "calmar": es["calmar"], "sharpe": es["sharpe"],
        "mc_pass": mc["pass_rate"],
        "half1_maxDD": sh["first"]["maxDD_pct"] if sh["first"] else None,
        "half1_calmar": sh["first"]["calmar"] if sh["first"] else None,
        "half2_maxDD": sh["second"]["maxDD_pct"] if sh["second"] else None,
        "half2_calmar": sh["second"]["calmar"] if sh["second"] else None,
    }


def main():
    cands = [
        ("baseline", None),
        ("VF1_vix_skip", v7.filter_vix(0.80)),
        ("VF2_trend_ma50", v7.filter_trend(50)),
        ("VF3_pairvol_skip", v7.filter_pair_vol(0.80)),
    ]
    rows = [assess(n, f) for n, f in cands]
    base = rows[0]

    print(f"\n=== v7 強化比較 (weekly {WR}%) ===")
    hdr = f"{'variant':<18}{'days':>5}{'net%':>8}{'maxDD%':>8}{'Calmar':>7}{'Sharpe':>7}{'MCpass':>7}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<18}{r['n_trade_days']:>5}{r['net_total_pct']:>8.1f}"
              f"{r['maxDD_pct']:>8.1f}{r['calmar']:>7.2f}{r['sharpe']:>7.2f}{r['mc_pass']:>7.3f}")
    print("\n-- 前後半 maxDD/Calmar (頑健性) --")
    for r in rows:
        print(f"{r['name']:<18} H1 DD={r['half1_maxDD']} Cal={r['half1_calmar']} | "
              f"H2 DD={r['half2_maxDD']} Cal={r['half2_calmar']}")

    print("\n-- 採用判定(4要件: maxDD縮小 ∧ Calmar改善 ∧ MC向上 ∧ 前後半とも改善) --")
    verdict = {}
    for r in rows[1:]:
        dd_better = r["maxDD_pct"] > base["maxDD_pct"]            # 負の値→大きい方が浅い
        cal_better = r["calmar"] > base["calmar"]
        mc_better = r["mc_pass"] > base["mc_pass"]
        half_better = (r["half1_calmar"] is not None and base["half1_calmar"] is not None
                       and r["half1_calmar"] > base["half1_calmar"]
                       and r["half2_calmar"] is not None and base["half2_calmar"] is not None
                       and r["half2_calmar"] > base["half2_calmar"])
        ok = dd_better and cal_better and mc_better and half_better
        verdict[r["name"]] = "採用候補" if ok else "不採用"
        print(f"  {r['name']:<18} DD改善={dd_better} Calmar改善={cal_better} "
              f"MC改善={mc_better} 前後半とも={half_better} -> {verdict[r['name']]}")

    out = evaluate.reports_path("v7_strengthen_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"weekly_risk_pct": WR, "rows": rows, "verdict": verdict}, f, ensure_ascii=False, indent=2)
    print("->", out)


if __name__ == "__main__":
    main()
