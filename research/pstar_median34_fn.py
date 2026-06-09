# -*- coding: utf-8 -*-
"""
pstar_median34_fn.py — 最強P★(フル4戦略)をFundedNextで中央値3/4ヶ月にした時の成績。

最強P★ = v4:35 / v7:25 / E-Mon:25 / E5:15(docs/55最適)。FundedNextは同一口座内ヘッジOK(docs/64)ゆえ
このフル構成を1口座で運用可(FTMO準拠版より強い)。FN条件: Phase1 +8% / Phase2 +5% / 静的−10% / 時間無制限。
中央3/4ヶ月になるスケールを探索し、必要倍率・p95DD・通過/失格・funded収益を表示。
口座 FN $100k・分配95%(base80%+アドオン15%)・¥160/$。
規律: 数字は盛らない。月次解像度=失格は楽観。Yahoo近似=Drive+デモで確定。"""
import os, sys, json, numpy as np, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pstar_challenge_mc import pstar_monthly, find_scale, simulate, p95_annual_maxdd, block_paths

HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNT, SPLIT, FX = 100000.0, 0.95, 160.0


def ann_return(s, sc): x = s.values * sc; return float(np.prod(1 + x) ** (12 / len(x)) - 1)
def annual_fail(s, sc, n=20000, seed=5):
    P = block_paths(s.values * sc, n, 12, seed=seed); f = 0
    for i in range(n):
        eq = np.cumprod(1 + P[i]); dd = (eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)
        if dd.min() <= -0.10: f += 1
    return f / n
def med(s, sc): return simulate(s, sc, 0.08, n_paths=12000)["med_month"]
def scale_for(s, ref, tm, lo=0.2, hi=6.0):
    for _ in range(32):
        mid = (lo + hi) / 2
        if med(s, mid * ref) <= tm: hi = mid
        else: lo = mid
    return hi * ref


def main():
    s = pstar_monthly()
    S10 = find_scale(s, -10.0)
    win = round(float((s > 0).mean() * 100), 0)
    print("=" * 100)
    print(f"最強P★(v4:35/v7:25/E-Mon:25/E5:15) ─ FundedNext 中央値3/4ヶ月の成績")
    print(f"  FN 2-step: P1+8% / P2+5% / 静的−10% / 時間無制限 ・ 口座${ACCOUNT:,.0f} 分配{SPLIT*100:.0f}% ¥{FX} ・ 月勝率{win:.0f}%")
    print("=" * 100)
    print(f"{'目標':12s}{'必要倍率':>9}{'p95年DD':>9}{'P1通過%':>9}{'P1失格%':>9}{'P1中央':>8}{'2段通過%':>9}{'2段中央':>8}{'年失格%':>8}{'手取/月':>12}{'期待手取/年':>14}")
    out = {}
    rows = [("攻め(−10%枠)", S10), ("中央4ヶ月", scale_for(s, S10, 4)), ("中央3ヶ月", scale_for(s, S10, 3))]
    for tag, S in rows:
        p1 = simulate(s, S, 0.08); p2 = simulate(s, S, 0.05, seed=23)
        both = round(p1["pass_pct"] / 100 * p2["pass_pct"] / 100 * 100, 1)
        ar = ann_return(s, S); af = annual_fail(s, S)
        gm = ACCOUNT * ar * SPLIT * FX / 12; ey = ACCOUNT * ar * SPLIT * FX * (1 - af)
        out[tag] = dict(mult=round(S / S10, 2), p95DD=round(p95_annual_maxdd(s, S), 1), P1=p1, P2=p2,
                        both_pass=both, ann=round(ar * 100, 1), annual_fail=round(af * 100, 1),
                        net_m=round(gm), exp_y=round(ey))
        print(f"{tag:12s}{('×'+format(S/S10,'.2f')):>9}{p95_annual_maxdd(s,S):>9.0f}{p1['pass_pct']:>9}{p1['fail_pct']:>9}"
              f"{str(p1['med_month'])+'ヶ月':>8}{both:>9}{str(p1['med_month']+p2['med_month'])+'ヶ月':>8}"
              f"{af*100:>8.1f}{('¥'+format(round(gm),',')):>12}{('¥'+format(round(ey),',')):>14}")

    print("\n[読み方] P1=Challenge(+8%)/2段=P1+Verification(+5%)。手取/月=funded生存時。期待手取/年=失格(口座喪失)考慮。")
    print("  ※FN同一口座ヘッジOKゆえフルP★(4戦略)が使える=FTMO準拠版より強い。中央3/4ヶ月は高失格=ガード必須(docs/60)。")
    print("  ⚠ 月次解像度=失格は楽観(日次−5%/月内/ギャップで実際は高い)。funded後は中庸へ減サイズ(docs/57)。")
    with open(os.path.join(HERE, "results", "pstar_median34_fn.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/pstar_median34_fn.json")


if __name__ == "__main__":
    main()
