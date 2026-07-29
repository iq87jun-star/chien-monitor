# -*- coding: utf-8 -*-
"""
median3_target.py — 「Phase1中央値3ヶ月」を狙う倍率と、その目標での最適構成比。

問い: (1) 確定スペック(v4:E-Mon 55:45)で中央3ヶ月にするには何倍必要か。
      (2) 中央3ヶ月に持ってくる場合、どの構成比が一番"失格が少ない"か。
方法: FTMO条件(P1 +10%/−10%)。各構成について、中央月が3になる最小スケールを探索し、その時の失格%/通過%を比較。
      倍率は「55:45の−10%枠スケール(S10ref)」基準で表示。低スケールで中央3を達成＝高効率＝失格が少ない。
規律: 数字は盛らない。月次解像度=失格は楽観(実値はガード/ギャップで変わる)。Yahoo近似=Drive+デモで確定。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v4_monthly, emon_monthly, z
from portfolio_patterns import crypto_monthly
from pstar_challenge_mc import find_scale, simulate, p95_annual_maxdd

HERE = os.path.dirname(os.path.abspath(__file__))


def series_for(w):
    cols = {"v4": v4_monthly(), "E-Mon": emon_monthly(), "CRYPTO": crypto_monthly()}
    M = pd.DataFrame({k: cols[k] for k in w if w[k] > 0}).dropna()
    return sum(z(M[k]) * w[k] for k in w if w[k] > 0).dropna()


def median_month(s, scale, target=0.10):
    return simulate(s, scale, target, n_paths=12000)["med_month"]


def scale_for_median3(s, ref_scale, lo=0.2, hi=6.0):
    """中央月==3 になる最小スケールを二分探索(高スケールほど速い=中央月小)。"""
    # 中央月は段階的。median<=3 となる最小スケールを探す。
    for _ in range(34):
        mid = (lo + hi) / 2
        if median_month(s, mid * ref_scale) <= 3:
            hi = mid
        else:
            lo = mid
    return hi * ref_scale


def main():
    base = series_for({"v4": .55, "E-Mon": .45})
    S10ref = find_scale(base, -10.0)     # 55:45の−10%枠スケール(倍率の基準)

    print("=" * 96)
    print("Q1: 確定スペック v4:E-Mon 55:45 で『中央値3ヶ月』に必要な倍率(−10%枠=1.0x基準)")
    print("=" * 96)
    S3 = scale_for_median3(base, S10ref)
    r = simulate(base, S3, 0.10)
    print(f"  必要倍率 ≈ ×{S3/S10ref:.2f}（−10%枠の{S3/S10ref:.2f}倍）/ 実p95年DD {p95_annual_maxdd(base,S3):.0f}% "
          f"/ P1通過{r['pass_pct']}% 失格{r['fail_pct']}% 中央{r['med_month']}ヶ月")

    print("\n" + "=" * 96)
    print("Q2: 『中央3ヶ月』を各構成比で達成した時の成績（失格が少ない＝3ヶ月狙いに最適な構成比）")
    print("=" * 96)
    print(f"{'構成比':28s}{'必要倍率':>9}{'実p95DD':>9}{'P1通過%':>9}{'P1失格%':>9}{'中央月':>7}")
    cands = {
        "v4:E-Mon 55:45 (確定)": {"v4": .55, "E-Mon": .45},
        "v4:E-Mon 70:30 (v4厚)": {"v4": .70, "E-Mon": .30},
        "v4:E-Mon 40:60 (指数厚)": {"v4": .40, "E-Mon": .60},
        "v4 単独 100": {"v4": 1.0},
        "E-Mon 単独 100": {"E-Mon": 1.0},
        "v4:E-Mon:暗号 50:35:15": {"v4": .50, "E-Mon": .35, "CRYPTO": .15},
        "v4:E-Mon:暗号 45:30:25": {"v4": .45, "E-Mon": .30, "CRYPTO": .25},
    }
    out = {"Q1_mult_55_45": round(S3 / S10ref, 2), "Q1": r}
    rows = []
    for nm, w in cands.items():
        s = series_for(w)
        S = scale_for_median3(s, S10ref)
        rr = simulate(s, S, 0.10)
        mult = S / S10ref; dd = p95_annual_maxdd(s, S)
        rows.append((nm, mult, dd, rr))
        out[nm] = dict(mult=round(mult, 2), p95DD=round(dd, 1), pass_pct=rr["pass_pct"], fail_pct=rr["fail_pct"], med=rr["med_month"])
        print(f"{nm:28s}{('×'+format(mult,'.2f')):>9}{dd:>9.0f}{rr['pass_pct']:>9}{rr['fail_pct']:>9}{rr['med_month']:>7}")

    best = min(rows, key=lambda x: x[3]["fail_pct"])
    print(f"\n→ 中央3ヶ月で最も失格が少ない構成比 = 【{best[0]}】 失格{best[3]['fail_pct']}%（倍率×{best[1]:.2f}）")
    print("[読み方] 低倍率で中央3を出せる構成ほど効率的=失格少。倍率は55:45の−10%枠=1.0x基準。")
    print("  ⚠ 月次解像度=失格は楽観(日次−5%/月内/ギャップで実際は高い)。中央3ヶ月狙いは本質的に高失格=ガード必須(docs/60)。")

    with open(os.path.join(HERE, "results", "median3_target.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/median3_target.json")


if __name__ == "__main__":
    main()
