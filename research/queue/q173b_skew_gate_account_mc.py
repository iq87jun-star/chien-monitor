# -*- coding: utf-8 -*-
"""docs/409 Q173 の派生(セル 0・2026-11-08 ユーザー「門の影響を数値で教えて下さい」): Mon4 × SKEW 門(前金曜 SKEW 252 日 80 分位超の月曜を見送り)を
各口座の EA 実レグ(mon:GBPJPY/EURJPY/AUDJPY/USDJPY のみ・他レグ不変)に掛け、account_cards.mc(N=6000・種 44・30 か月)で 現状 / 門あり を 同倍率・規約揃えで比較。
使い方: cd research && python3 -W ignore queue/q173b_skew_gate_account_mc.py   出力: results/q173b_skew_gate_account_mc.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
src = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read().split("rows_a, rows_m = [], []")[0]
ns = {"__name__": "account_cards_head", "__file__": os.path.join(ROOT, "forward", "account_cards.py")}; exec(compile(src, "account_cards_head", "exec"), ns)
import numpy as np, pandas as pd
from q173_skew_vvix_gate import PR
cfg, EA_LEGS, S, ea_book, mc, daily_window, mdd_daily, solve_scale, acc_id, META = (ns[k] for k in ("cfg", "EA_LEGS", "S", "ea_book", "mc", "daily_window", "mdd_daily", "solve_scale", "acc_id", "META"))
SESS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")
S_orig = S; _g = {}
def gated(sym):
    if sym not in _g:
        s = S_orig("mon:" + sym).copy(); mon = s.index[s.index.dayofweek == 0]
        prev = PR["SKEW"].reindex(mon - pd.Timedelta(days=3), method="ffill").values; hi = mon[prev > 0.8]
        s.loc[hi] = 0.0; _g[sym] = s
    return _g[sym]
def S2(key):
    fam, _, sym = key.partition(":"); return gated(sym) if fam == "msk" else S_orig(key)
ns["S"] = S2
def swap(lg): return {("msk:" + k.split(":")[1] if k.startswith("mon:") and k.split(":")[1] in SESS else k): w for k, w in lg.items()}
def rule_scale(lg, sw, a):
    rd = daily_window(ea_book(lg, sw)); s_mdd = solve_scale(rd, a["mdd"]); wd = float(rd.min()); s_dll = a["dll"] / abs(wd) if wd < 0 else 20.0
    return min(s_mdd, s_dll), rd
def hist(rd):
    m = (1 + rd).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(mean_m=float(m.mean()), worst_m=float(m.min()), mdd=float((eq / eq.cummax() - 1).min()), worst_d=float(rd.min()), sharpe=float(m.mean() / m.std() * np.sqrt(12)))
# 門の発動状況
mons = pd.DatetimeIndex([d for d in pd.date_range("2016-01-04", "2026-11-09", freq="W-MON")]); prev = PR["SKEW"].reindex(mons - pd.Timedelta(days=3), method="ffill"); hi = pd.Series(prev.values > 0.8, index=mons)
print("門の発動(見送り)月曜の割合 年別:", (hi.groupby(hi.index.year).mean() * 100).round(0).astype(int).to_dict())
print("直近 12 週の見送り:", [str(d.date()) for d in hi[-12:][hi[-12:]].index], "| 次の月曜 2026-11-09:", "見送り" if bool(hi.iloc[-1]) else "建てる", f"(前金曜 SKEW 分位 {prev.iloc[-1]:.2f}・値 {PR['SKEW'].index[-1].date()} 時点)")
rows = []
for a in cfg["accounts"]:
    if not a.get("active", True): continue
    aid = acc_id(a["name"]); EL = EA_LEGS.get(aid)
    if not EL or not any(k.startswith("mon:") and k.split(":")[1] in SESS for k in EL["eval"]): continue
    fn = a.get("funded_now", False); sw = a.get("swap_xau_bps_m", 0.0); firm, label, ea = META[aid]
    for form, lgs in (("現状", EL), ("SKEW 門", {"eval": swap(EL["eval"]), "funded": swap(EL["funded"])})):
        cur = lgs["funded"] if fn else lgs["eval"]; sc, rd = rule_scale(cur, sw, a)
        for mode, s_ in (("同倍率", 1.0), ("規約揃え", sc)):
            ar = copy.deepcopy(a); ar["eval"] = {k: w * s_ for k, w in lgs["eval"].items()}; ar["funded"] = {k: w * s_ for k, w in lgs["funded"].items()}
            r = mc(ar); h = hist(rd * s_)
            rows.append(dict(account=aid, name=a["name"], stage="資金化済" if fn else "評価中", form=form, mode=mode, scale=round(s_, 3), p_reach=r["p_reach"], p_fail=r["p_fail"], p_pay=r["p_pay"], t_med_m=r["t_med_m"], c12_med=r["c12_med"], c30_mean=r["c30_mean"], **h))
            print(aid, form, mode, f"×{s_:.2f}", {k: round(v, 3) for k, v in r.items() if k in ("p_reach", "p_fail", "p_pay", "c30_mean")}, flush=True)
T = pd.DataFrame(rows); T.to_csv("results/q173b_skew_gate_account_mc.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
print(T[["account", "stage", "form", "mode", "scale", "p_reach", "p_fail", "p_pay", "t_med_m", "c12_med", "c30_mean", "mean_m", "worst_m", "mdd", "worst_d", "sharpe"]].round(3).to_string(index=False))
