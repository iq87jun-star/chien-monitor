# -*- coding: utf-8 -*-
"""docs/230: 候補を 2 本以上に拡張する規則と、その walk-forward。
規則(順位付け窓 2021-10〜2025-09 のみで決める): 未知セル × p<0.05 × Hold/暗号を除く → 窓内月次相関 |ρ|>0.5 の組は p の小さい方だけ残す(クラスタ代表)
→ 5年版 5 本に足して逆ボラ加重(cap40%)・校正 → 2025-10〜2026-09 を評価。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db
from forward.paper_forward import refresh_live, universe
from plusmonth_portfolio import rank, build, perf, monthly
from plusmonth_search import dow_cell, A, CUT, END, DOW
RHO = 0.5


def main():
    refresh_live(); rng = np.random.default_rng(7)
    sr = pd.read_csv(os.path.join(HERE, "results", "plusmonth_search.csv"))
    cand = sr[(~sr.known) & (sr.p_binom < 0.05) & (sr.family != "Hold") & (~sr.symbol.isin(["BTCUSD", "ETHUSD"]))].sort_values("p_binom")
    S = {}
    for f, s in universe(): x = db.leg_series(f, s); S[(f, s)] = x[x.index <= END]
    def cell(fam, sym):
        d = DOW.index(fam.rstrip("S")); return dow_cell(sym, d, fam.endswith("S"))
    for _, r in cand.iterrows(): S[(r.family, r.symbol)] = cell(r.family, r.symbol)
    # クラスタ代表(窓内月次相関)
    base5 = rank({k: v for k, v in S.items() if (k[0], k[1]) not in set(zip(cand.family, cand.symbol))}, A, CUT)
    keep = []
    M = pd.DataFrame({f"{k[0]} {k[1]}": monthly(S[k][(S[k].index >= A) & (S[k].index <= CUT)]) for k in [r["key"] for r in base5] + list(zip(cand.family, cand.symbol))}).fillna(0)
    C = M.corr()
    for _, r in cand.iterrows():
        nm = f"{r.family} {r.symbol}"; rivals = [f"{k[0]} {k[1]}" for k in keep] + [f"{k['key'][0]} {k['key'][1]}" for k in base5]
        mx = max(abs(C.loc[nm, x]) for x in rivals) if rivals else 0
        if mx <= RHO: keep.append((r.family, r.symbol)); tag = "採用"
        else: tag = f"除外(|ρ|={mx:.2f} 既採用と重複)"
        print(f"  {nm:14s} +{int(r.plus_in)}/48 p={r.p_binom:.4f}  OOS {r.cum_oos_pct:+.2f}% ({int(r.plus_oos)}/12)  → {tag}")
    print(f"\n候補 {len(cand)} → クラスタ代表 {len(keep)}: {[f'{f} {s}' for f, s in keep]}")
    # 段階的に足す(p 順)と、全部足す
    rows = []
    for n in range(0, len(keep) + 1):
        picks = base5 + [dict(key=k, plus=0, act=0) for k in keep[:n]]
        w, comp, mult, mw, m12 = build(S, picks, A, CUT); oos = comp[(comp.index > CUT) & (comp.index <= END)]; win = comp[(comp.index >= A) & (comp.index <= CUT)]
        po, pi, mc = perf(oos, mult), perf(win, mult), base.mc_challenge(oos, mult, rng)
        rows.append(dict(n_extra=n, last_added=(f"{keep[n-1][0]} {keep[n-1][1]}" if n else "-"), mult=mult, in_total=pi["total_pct"], in_dd=pi["max_dd_pct"],
                         oos_total=po["total_pct"], oos_dd=po["max_dd_pct"], oos_worst_m=po["worst_month_pct"], oos_plus=po["plus_months"], oos_sharpe=po["sharpe_act"], mc_funded=mc["funded"], mc_fail=mc["fail"]))
        print(f"  5本+{n} ({rows[-1]['last_added']:14s}) 倍率 {mult:4.2f} | 窓内 {pi['total_pct']:+6.1f}% DD {pi['max_dd_pct']:6.2f} | OOS {po['total_pct']:+6.2f}% DD {po['max_dd_pct']:6.2f} 最悪月 {po['worst_month_pct']:6.2f} +月 {po['plus_months']} Sharpe {po['sharpe_act']} | MC 資金化 {mc['funded']}% 失格 {mc['fail']}%")
    pd.DataFrame(rows).to_csv(os.path.join(HERE, "results", "plusmonth_extend.csv"), index=False)
    # 最終構成の重み
    w, comp, mult, mw, m12 = build(S, base5 + [dict(key=k, plus=0, act=0) for k in keep], A, CUT)
    print("\n拡張後の重み(2025-09 時点):", {f"{k[0]} {k[1]}": round(v, 3) for k, v in w.items()}, "倍率", mult)
    json.dump(dict(keep=[f"{f} {s}" for f, s in keep], weights={f"{k[0]} {k[1]}": round(v, 3) for k, v in w.items()}, mult=mult, steps=rows), open(os.path.join(HERE, "results", "plusmonth_extend.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__": main()
