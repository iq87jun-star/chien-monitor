# -*- coding: utf-8 -*-
"""docs/402 Q162 の E 案(Mon ×f + Hold UK100/WTI・最悪日と 5 年 DD を現状以下に保つ)を f ∈ {1.0, 0.9, 0.8, 0.7, 0.6, 0.5} の格子で回し、
帳簿全体の Mon 寄与・Sharpe・30 か月期待と、口座別の到達 / 失格 / 出金を並べる(診断・セル 0・2026-11-08 ユーザー「比率はどの程度にするのが良いと思いますか」)。
使い方: cd research && python3 -W ignore queue/q162b_mon_ratio_grid.py   出力: results/q162b_mon_ratio_grid.csv・_portfolio.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, cur_legs, rescale, solve_w2, portfolio, mc, ea_book, daily_window, mdd_daily, EA_LEGS, SWING = (ns[k] for k in ("cfg", "cur_legs", "rescale", "solve_w2", "portfolio", "mc", "ea_book", "daily_window", "mdd_daily", "EA_LEGS", "SWING"))
FS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)
rows, prow = [], []
base_mc = {}
for f in FS:
    d = {}; wnote = {}
    for a in cfg["accounts"]:
        aid = a["name"].split()[-1]; lg = cur_legs(a); sw = a.get("swap_xau_bps_m", 0.0)
        if aid in SWING and f < 1.0: w = solve_w2(lg, f, sw); d[a["name"]] = rescale(lg, f, w); wnote[a["name"]] = w
        else: d[a["name"]] = dict(lg); wnote[a["name"]] = 0.0
    P = portfolio(d); P["f"] = f; prow.append(P)
    for a in cfg["accounts"]:
        aid = a["name"].split()[-1]; lg = d[a["name"]]
        def build(lg):
            b = copy.deepcopy(a); fn = a.get("funded_now", False)
            if fn: b["eval"] = lg; b["funded"] = lg
            else:
                ratio = {k: EA_LEGS[aid]["funded"].get(k, 0) / v if v else 0 for k, v in EA_LEGS[aid]["eval"].items()}
                b["eval"] = lg; b["funded"] = {k: v * (ratio.get(k) if ratio.get(k) else (list(ratio.values())[0])) for k, v in lg.items()}
            return b
        if aid not in SWING or f == 1.0:   # 基準行も EA 実レグ(docs/402 の B と同じ)
            if a["name"] not in base_mc: base_mc[a["name"]] = mc(build(lg))
            s = base_mc[a["name"]]
        else:
            b = build(lg); s = mc(b)
        sw = a.get("swap_xau_bps_m", 0.0); rd = daily_window(ea_book(lg, sw))
        rows.append(dict(f=f, account=a["name"], swing=aid in SWING, hold_w=round(wnote[a["name"]], 3), worst_day=float(rd.min()), mdd_d=mdd_daily(rd), m_mean=float(((1 + rd).resample("ME").prod() - 1).mean()),
                         p_reach=s["p_reach"], p_fail=s["p_fail"], p_pay=s["p_pay"], c30_mean=s["c30_mean"]))
    print("f", f, "done", flush=True)
df = pd.DataFrame(rows); df.to_csv("results/q162b_mon_ratio_grid.csv", index=False); pt = pd.DataFrame(prow).set_index("f"); pt.to_csv("results/q162b_mon_ratio_grid_portfolio.csv")
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
print("\n=== 帳簿全体 ===")
print((pt[["rc_mon", "rc_hold", "var_mon", "avg_corr", "m_mean", "m_worst", "m_mdd", "d_mdd"]] * 100).round(1).assign(Sharpe=pt.m_sharpe.round(2), 期待30万=df.groupby("f").c30_mean.sum().div(1e4).round(0)).to_string())
print("\n=== 口座別(変更 5 口座) ===")
sw_ = df[df.swing].assign(失格=(df.p_fail * 100).round(0), 到達=(df.p_reach * 100).round(0), 出金=(df.p_pay * 100).round(0), 期待30万=(df.c30_mean / 1e4).round(0), 月利=(df.m_mean * 100).round(2))
print(sw_.pivot_table(index="account", columns="f", values=["失格", "期待30万"]).to_string())
print("\n変更 5 口座の合計 期待30万:", sw_.groupby("f").c30_mean.sum().div(1e4).round(0).to_dict())
print("変更 5 口座の平均 失格:", sw_.groupby("f").p_fail.mean().mul(100).round(1).to_dict())
