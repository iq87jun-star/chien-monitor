# -*- coding: utf-8 -*-
"""
twobook_median3.py — 「2口座並走」を中央3ヶ月で最良化(docs/69)。

目的: ユーザー「2本組むなら望ましい構成は? 中央3ヶ月で最良の2本」。
   2口座の本質(docs/52)=高収益でなく『分散・全損回避』。∴評価軸は:
     ① ≥1通過率(最低1口座は資金化) ② 両喪失率(2口座とも失う最悪事故) ③ A⇄B相関(低=独立)。
   候補エッジ(v4/v7/E-Mon[RG3]/E5/CRYPTO)で口座A(FX/v4系)×口座B(指数/E-Mon系)のペアを、
   各々を中央3ヶ月へスケールし、同月ブロック・ブートストラップで A,B を同時に審査して共倒れ率を測る。
出所: portfolio_optimize.aligned + edge_regime_gate_10y(E-Mon=RG3) + 自前ジョイントMC。
規律: 月次解像度=失格/共倒れは楽観。中央3ヶ月=口座喪失前提の速攻。最終はDrive+デモ。
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("RG_ALLOW_YAHOO", "1")
from portfolio_optimize import aligned
from pstar_challenge_mc import find_scale
import edge_regime_gate_10y as RG

HERE = os.path.dirname(os.path.abspath(__file__))
R = aligned(["v7", "v4", "E5", "E-Mon", "CRYPTO"]).copy()
R.index = pd.PeriodIndex(pd.to_datetime(R.index.astype(str)), freq="M")


def to_m(w):
    s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()


EMON_RG3 = to_m(RG.emon_weekly_gated("riskoff"))
B = R.drop(columns=["E-Mon"]).join(EMON_RG3.rename("E-Mon"), how="inner").dropna()
Z = B / B.std()
S10 = None


def port(w):
    w = pd.Series(w); return (Z[w.index] * w).sum(axis=1).dropna()


def scale_med(s, want=3, t=0.08, lo=.2, hi=10):
    def med(sc):
        n = len(s.values); rng = np.random.default_rng(11); P = np.empty((8000, 72))
        for p in range(8000):
            seq = []
            while len(seq) < 72:
                st = rng.integers(0, n); seq.extend(s.values[(st + k) % n] * sc for k in range(3))
            P[p] = seq[:72]
        m = []
        for i in range(8000):
            eq = 1.0
            for k in range(72):
                eq *= 1 + P[i, k]
                if eq <= .9: m.append(72); break
                if eq >= 1 + t: m.append(k + 1); break
            else: m.append(72)
        return int(np.median(m))
    for _ in range(22):
        mid = (lo + hi) / 2
        if med(mid * S10) <= want: hi = mid
        else: lo = mid
    return hi * S10


def joint(wa, wb, t=0.08, npath=25000):
    sa = port(wa); sb = port(wb); Sa = scale_med(sa); Sb = scale_med(sb)
    J = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
    corr = float(J["a"].corr(J["b"])); a = J["a"].values * Sa; b = J["b"].values * Sb; n = len(a)
    rng = np.random.default_rng(7); bp = bb = one = 0; ma = []; mb = []
    for _ in range(npath):
        idx = []
        while len(idx) < 72:
            st = rng.integers(0, n); idx.extend((st + k) % n for k in range(3))
        idx = idx[:72]; ea = eb = 1.0; da = db = 0
        for k in range(72):
            if da == 0:
                ea *= 1 + a[idx[k]]
                if ea <= .9: da = -1
                elif ea >= 1 + t: da = 1; ma.append(k + 1)
            if db == 0:
                eb *= 1 + b[idx[k]]
                if eb <= .9: db = -1
                elif eb >= 1 + t: db = 1; mb.append(k + 1)
            if da != 0 and db != 0: break
        passed = (da == 1) + (db == 1); blown = (da == -1) + (db == -1)
        if passed == 2: bp += 1
        elif passed == 1: one += 1
        if blown == 2: bb += 1
    return dict(corr=round(corr, 2), multA=round(Sa / S10, 2), multB=round(Sb / S10, 2),
                both_pass=round(bp / npath * 100, 1), atleast1=round((bp + one) / npath * 100, 1),
                both_blown=round(bb / npath * 100, 1),
                medA=int(np.median(ma)) if ma else 0, medB=int(np.median(mb)) if mb else 0)


def main():
    global S10
    S10 = find_scale(port({"v7": .40, "v4": .40, "E5": .20}), -10.0)
    AA = {"A:v4core(v4:v7:E5 45:35:20)": {"v4": .45, "v7": .35, "E5": .20},
          "A:PA(v7:v4:E5:E-Mon 30:30:20:20)": {"v7": .30, "v4": .30, "E5": .20, "E-Mon": .20}}
    BB = {"B:E-Mon[RG3]:E5 65:35": {"E-Mon": .65, "E5": .35},
          "B:E-Mon[RG3]:CRYPTO 80:20": {"E-Mon": .80, "CRYPTO": .20},
          "B:E-Mon[RG3]:E5:CRYPTO 60:25:15": {"E-Mon": .60, "E5": .25, "CRYPTO": .15}}
    out = {}
    print("=== 2口座ペア(各中央3ヶ月) ===")
    for an, aw in AA.items():
        for bn, bw in BB.items():
            r = joint(aw, bw); out[f"{an} || {bn}"] = r
            print(f"{an[:20]:20s}∥ {bn:30s} corr{r['corr']:+.2f} 両通過{r['both_pass']:4.1f}% ≥1通過{r['atleast1']:4.1f}% 両喪失{r['both_blown']:3.1f}% 中央A{r['medA']}/B{r['medB']}")
    r = joint(AA["A:PA(v7:v4:E5:E-Mon 30:30:20:20)"], AA["A:PA(v7:v4:E5:E-Mon 30:30:20:20)"])
    out["(参考)複製 P-A∥P-A"] = r
    print(f"\n(参考)複製 P-A∥P-A corr{r['corr']:+.2f} 両通過{r['both_pass']}% ≥1通過{r['atleast1']}% 両喪失{r['both_blown']}%")
    json.dump(out, open(os.path.join(HERE, "results", "twobook_median3.json"), "w"), ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/twobook_median3.json")


if __name__ == "__main__":
    main()
