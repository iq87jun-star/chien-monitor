# -*- coding: utf-8 -*-
"""
portfolio_median4_compare.py — 確定P1と3案(P-A/分散案D/P-C)を「中央4ヶ月版」で横並び比較(docs/65)。

目的: ユーザー要望「確定ポートと3案を中央値4ヶ月版でそれぞれ比較」。
   既存候補(v4/v7/E-Mon/E5)のみで、P1と同等成績かつリスク分散を高めたポートを並べる。
比較軸:
  ① 分散度   : 最大リスク寄与率 / 有効ベット数(1/HHI of risk contributions)
  ② 審査     : 中央4ヶ月になる倍率・p95年DD・失格%・3ヶ月以内通過%・平均月(FundedNext +8%/-10%・7月開始)
  ③ 本番収益 : 資金化後を -6%(保守)/-8%(中庸)枠で回した時の年収(分配95%・¥155・$100k)
データ/エンジン: portfolio_optimize.aligned(Yahoo再構築) / pstar_challenge_mc(MC)。
規律: 数字は盛らない。月次解像度=失格は楽観。Yahoo近似・v4は日足簡易再現。最終はDrive+デモで確定。
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portfolio_optimize import aligned, znorm
from pstar_challenge_mc import find_scale, p95_annual_maxdd, simulate, block_paths

HERE = os.path.dirname(os.path.abspath(__file__))
A = znorm(aligned(["v7", "v4", "E5", "E-Mon", "CRYPTO"]))

PORTS = {
    "P1 確定(v7:v4:E5 40:40:20)":            {"v7": .40, "v4": .40, "E5": .20},
    "P-A(+E-Mon 30:30:20:20)":               {"v7": .30, "v4": .30, "E5": .20, "E-Mon": .20},
    "分散案D(v4:v7:E-Mon:E5 30:25:25:20)":    {"v4": .30, "v7": .25, "E-Mon": .25, "E5": .20},
    "P-C(v4厚 v4:v7:E-Mon 50:30:20)":         {"v4": .50, "v7": .30, "E-Mon": .20},
}


def port(w):
    w = pd.Series(w); return (A[w.index] * w).sum(axis=1).dropna()


def divmetric(w):
    w = pd.Series(w); C = A[w.index].cov().values; wv = w.values
    rc = wv * (C @ wv); rc = rc / rc.sum()
    return round(rc.max() * 100, 0), round(1 / (rc ** 2).sum(), 2)


def scale_for_median(s, ref, target, want, lo=0.2, hi=8.0):
    def med(sc):
        P = block_paths(s.values * sc, 12000, 72, 3, 11); m = []
        for i in range(12000):
            eq = 1.0
            for k in range(72):
                eq *= 1 + P[i, k]
                if eq <= 0.9: m.append(72); break
                if eq >= 1 + target: m.append(k + 1); break
            else: m.append(72)
        return int(np.median(m))
    for _ in range(28):
        mid = (lo + hi) / 2
        if med(mid * ref) <= want: hi = mid
        else: lo = mid
    return hi * ref


def annual_ret(s, scale):
    P = block_paths(s.values * scale, 8000, 12, 3, 5)
    return float(np.mean([(np.prod(1 + P[i]) - 1) for i in range(8000)]))


def pass_within3(s, scale, target):
    P = block_paths(s.values * scale, 30000, 72, 3, 7); le3 = 0
    for i in range(30000):
        eq = 1.0
        for k in range(72):
            eq *= 1 + P[i, k]
            if eq <= 0.9: break
            if eq >= 1 + target: le3 += (k + 1) <= 3; break
    return round(le3 / 30000 * 100, 1)


def main():
    S10ref = find_scale(port(PORTS["P1 確定(v7:v4:E5 40:40:20)"]), -10.0)  # 共通基準=P1の-10%枠
    out = {}
    hdr = f"{'ポートフォリオ':36s}{'最大寄与':>7}{'有効数':>6}{'倍率':>7}{'p95DD':>7}{'失格%':>6}{'3内%':>6}{'平均月':>6}{'本番-6%':>11}{'-8%':>11}"
    print(hdr)
    for nm, w in PORTS.items():
        s = port(w); mc, enb = divmetric(w)
        S4 = scale_for_median(s, S10ref, 0.08, 4)
        r = simulate(s, S4, 0.08, n_paths=30000)
        inc6 = annual_ret(s, find_scale(s, -6.0)) * 100000 * 0.95 * 155
        inc8 = annual_ret(s, find_scale(s, -8.0)) * 100000 * 0.95 * 155
        le3 = pass_within3(s, S4, 0.08)
        out[nm] = dict(max_contrib_pct=mc, effective_bets=enb, mult_vs_p1=round(S4 / S10ref, 2),
                       p95DD=round(p95_annual_maxdd(s, S4), 0), fail_pct=r["fail_pct"],
                       pass3_pct=le3, med_month=r["med_month"],
                       funded_income_6pct=int(inc6), funded_income_8pct=int(inc8))
        print(f"{nm:36s}{mc:>6}%{enb:>6}{'×'+format(S4/S10ref,'.2f'):>7}{p95_annual_maxdd(s,S4):>6.0f}%{r['fail_pct']:>6}{le3:>6}{r['med_month']:>5}ヶ{('¥'+format(int(inc6),',')):>11}{('¥'+format(int(inc8),',')):>11}")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "portfolio_median4_compare.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n注: 失格/月数=FundedNext+8%/-10%・7月開始MC近似。本番年収=資金化後を-6%/-8%枠で回した時(分配95%・¥155・$100k)。")
    print("保存: research/results/portfolio_median4_compare.json")


if __name__ == "__main__":
    main()
