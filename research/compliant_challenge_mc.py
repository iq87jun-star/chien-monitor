# -*- coding: utf-8 -*-
"""
compliant_challenge_mc.py — FTMO準拠版(v4full+E-Mon 55:45)でFTMO審査を回した通過月数MC。

docs/59の準拠最適を、FTMOルールで判定:
  Phase1(Challenge)   : +10% 到達で通過 / 静的 −10% 抵触で失格
  Phase2(Verification): +5% 到達で通過 / 同 −10%
  ※FTMOは2026更新で時間無制限・最小取引日緩和(要確認)。FN(+8%)より目標が高い分やや遅い。
手法はpstar_challenge_mc準拠(ブロックBS・サイズはp95年DDで−10%枠に合わせる)。
規律: 数字は盛らない。月次解像度=失格は楽観。Yahoo近似=Drive+デモで確定。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v4_monthly, emon_monthly, z
from pstar_challenge_mc import find_scale, simulate, p95_annual_maxdd

HERE = os.path.dirname(os.path.abspath(__file__))


def compliant_monthly():
    M = pd.DataFrame({"v4full": v4_monthly(), "E-Mon": emon_monthly()}).dropna()
    return (0.55 * z(M["v4full"]) + 0.45 * z(M["E-Mon"])).dropna()


def main():
    s = compliant_monthly()
    ann = (1 + s).prod() ** (12 / len(s)) - 1
    print(f"準拠版(v4full:E-Mon=55:45) 月次系列: n={len(s)} 年率(素)≈{ann*100:.1f}% 月次σ={s.std()*100:.2f}%")

    out = {}
    print("\n" + "=" * 96)
    print("FTMO準拠版 通過月数MC（FTMO: Phase1 +10% / Phase2 +5% / 静的−10% / ブロックBS 2万パス）")
    print("=" * 96)
    print(f"{'サイズ(目標p95年DD)':22s}{'P1通過%':>8}{'P1失格%':>8}{'P1中央月':>9}{'P1 25-75%':>11}{'2段通過%':>9}{'2段中央月':>9}")
    S10 = None
    for tag, tdd in [("保守 (−6%)", -6.0), ("中庸 (−8%)", -8.0), ("攻め (−10%)", -10.0)]:
        S = find_scale(s, tdd)
        if tag.startswith("攻め"):
            S10 = S
        p1 = simulate(s, S, 0.10)                 # FTMO Phase1 +10%
        p2 = simulate(s, S, 0.05, seed=23)        # Phase2 +5%
        both_pct = round(p1["pass_pct"] / 100 * p2["pass_pct"] / 100 * 100, 1)
        both_med = p1["med_month"] + p2["med_month"]
        out[tag] = dict(scale=round(S, 3), p95_annual_maxDD=round(p95_annual_maxdd(s, S), 1),
                        P1=p1, P2=p2, both_pass_pct=both_pct, both_med_month=both_med)
        print(f"{tag:22s}{p1['pass_pct']:>8}{p1['fail_pct']:>8}{p1['med_month']:>9}"
              f"{str(p1['p25'])+'-'+str(p1['p75']):>11}{both_pct:>9}{both_med:>9}")

    print("\n" + "-" * 96)
    print("【超攻め】攻め(−10%枠)基準にレバ倍化。⚠月次解像度で失格は大幅過小評価(日次−5%/月内で実際は高い)。")
    print(f"{'超攻め':22s}{'実p95年DD':>10}{'P1通過%':>8}{'P1失格%':>8}{'P1中央月':>9}{'2段通過%':>9}")
    for tag, mult in [("×1.5", 1.5), ("×2.0", 2.0)]:
        S = S10 * mult
        p1 = simulate(s, S, 0.10)
        p2 = simulate(s, S, 0.05, seed=23)
        both = round(p1["pass_pct"] / 100 * p2["pass_pct"] / 100 * 100, 1)
        out["超攻め" + tag] = dict(scale=round(S, 3), p95_annual_maxDD=round(p95_annual_maxdd(s, S), 1), P1=p1, both_pass_pct=both)
        print(f"{'超攻め '+tag:22s}{p95_annual_maxdd(s,S):>10.0f}{p1['pass_pct']:>8}{p1['fail_pct']:>8}{p1['med_month']:>9}{both:>9}")

    print("\n[読み方] FTMOはP1目標+10%(FN+8%より高い)＝同サイズでFNより1〜2ヶ月遅い。時間無制限ゆえ失格しなければ通過。")
    with open(os.path.join(HERE, "results", "compliant_challenge_mc.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/compliant_challenge_mc.json")


if __name__ == "__main__":
    main()
