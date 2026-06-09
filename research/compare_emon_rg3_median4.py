# -*- coding: utf-8 -*-
"""
compare_emon_rg3_median4.py — E-Mon raw vs E-Mon RG3(非対称リスクオフ・ゲート) を
   中央4ヶ月運用点で比較(docs/68)。RG3定義は research/edge_regime_gate_10y.py(別ブランチ由来)を流用。

問い: ユーザー「E-Mon を RG3版にした方が良ければ差し替え」。本スクリプトは P-A / 分散案D の2構成で、
      E-Mon を raw / RG3 に差し替え、中央4ヶ月になる倍率・p95年DD・失格%・分散度を比較する。
出所: portfolio_optimize.aligned(v7/v4/E5/CRYPTO) + edge_regime_gate_10y(E-Mon raw/RG3) + pstar_challenge_mc。
規律: 月次解像度=失格は楽観。RG3 は "良い週も少し見送る" ゆえ純益は下がるが maxDD を買う保険。最終はDrive+デモ。
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("RG_ALLOW_YAHOO", "1")
from portfolio_optimize import aligned
from pstar_challenge_mc import find_scale, p95_annual_maxdd, simulate, block_paths
import edge_regime_gate_10y as RG

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = aligned(["v7", "v4", "E5", "E-Mon", "CRYPTO"]).copy()
RAW.index = pd.PeriodIndex(pd.to_datetime(RAW.index.astype(str)), freq="M")
PORTS = {"P-A(30:30:20:20)": {"v7": .30, "v4": .30, "E5": .20, "E-Mon": .20},
         "分散案D(30:25:25:20)": {"v4": .30, "v7": .25, "E-Mon": .25, "E5": .20}}


def to_m(w):
    s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()


def build(emon_monthly):
    B = RAW.drop(columns=["E-Mon"]).join(emon_monthly.rename("E-Mon"), how="inner").dropna()
    return B / B.std()


def port(B, w): w = pd.Series(w); return (B[w.index] * w).sum(axis=1).dropna()


def divm(B, w):
    w = pd.Series(w); C = B[w.index].cov().values; wv = w.values
    rc = wv * (C @ wv); rc = rc / rc.sum(); return round(rc.max() * 100, 0), round(1 / (rc ** 2).sum(), 2)


def scale_for_median(s, ref, want=4, t=0.08, lo=.2, hi=8.0):
    def med(sc):
        P = block_paths(s.values * sc, 9000, 72, 3, 11); m = []
        for i in range(9000):
            eq = 1.0
            for k in range(72):
                eq *= 1 + P[i, k]
                if eq <= .9: m.append(72); break
                if eq >= 1 + t: m.append(k + 1); break
            else: m.append(72)
        return int(np.median(m))
    for _ in range(26):
        mid = (lo + hi) / 2
        if med(mid * ref) <= want: hi = mid
        else: lo = mid
    return hi * ref


def main():
    emon = {"raw": to_m(RG.emon_weekly_raw()), "RG3": to_m(RG.emon_weekly_gated("riskoff"))}
    out = {"sleeve": {}, "portfolio": {}}
    print("E-Mon スリーブ(共通期間):")
    for k, s in emon.items():
        eq = (1 + s).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
        out["sleeve"][k] = dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), maxDD_pct=round(dd, 1))
        print(f"  {k:3s}: net{(eq.iloc[-1]-1)*100:6.1f}% maxDD{dd:6.1f}%")
    for k, em in emon.items():
        B = build(em); S10 = find_scale(port(B, {"v7": .40, "v4": .40, "E5": .20}), -10.0)
        print(f"\n=== E-Mon {k} (n={len(B)}月) ===")
        for nm, w in PORTS.items():
            s = port(B, w); mc, enb = divm(B, w); S4 = scale_for_median(s, S10)
            r = simulate(s, S4, 0.08, n_paths=20000)
            out["portfolio"][f"{k}|{nm}"] = dict(max_contrib=mc, eff_bets=enb, mult=round(S4 / S10, 2),
                                                 p95DD=round(p95_annual_maxdd(s, S4), 0), fail_pct=r["fail_pct"], med=r["med_month"])
            print(f"  {nm:18s} 寄与{mc:3.0f}% 有効{enb:.2f} ×{S4/S10:.2f} p95DD{p95_annual_maxdd(s,S4):4.0f}% 失格{r['fail_pct']:4.1f}% 中央{r['med_month']}ヶ")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "results", "compare_emon_rg3_median4.json"), "w"), ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/compare_emon_rg3_median4.json")


if __name__ == "__main__":
    main()
