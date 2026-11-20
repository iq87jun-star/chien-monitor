# -*- coding: utf-8 -*-
"""docs/244 Q169(配備 MC・セル 0・2026-11-08 登録「登録」→ 2026-11-09「つぎも進めて下さい」): 日経 2 本を既存口座に足す場合の MC。
(a) Hold JP225 = recentfit_screen.hold_cell('JP225')(Yahoo 日足・Q89/Q90 と同一)を Hold レグのある口座(14166201・531466484・531343523・14074882)に、既存 Hold レグの平均重みで追加。
(b) MonIdxIntra JP225 = q114.shot('JP225', 13, 20)(月曜 13 → 同日 20 UTC・H1)を 指数 Mon レグのある口座(11988011・6104739)に nas/spx と同じ重みで追加。
各口座 3 通り: 現状 / 単純追加(他レグ不変・同倍率)/ 規約揃え(追加後に 最悪日 ≤ dll・5 年 DD ≤ 規約 を満たす倍率 s へ再スケール)。MC = account_cards.mc(N=6000・種 44・30 か月)。Mon レグは Q176 の H1 系列。判定なし(配備は「切替」)。
使い方: cd research && python3 -W ignore queue/q169_jp225_deploy_mc.py   出力: results/q169_jp225_deploy_mc.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
src = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read().split("rows_a, rows_m = [], []")[0]
ns = {"__name__": "account_cards_head", "__file__": os.path.join(ROOT, "forward", "account_cards.py")}; exec(compile(src, "account_cards_head", "exec"), ns)
import numpy as np, pandas as pd
from q114_mon_index_intraday import shot, stats as q114stats
from q_common import PRE0, IS0, IS1, OOS0, END
cfg, EA_LEGS, S, ea_book, mc, daily_window, mdd_daily, solve_scale, acc_id, META, ps = (ns[k] for k in ("cfg", "EA_LEGS", "S", "ea_book", "mc", "daily_window", "mdd_daily", "solve_scale", "acc_id", "META", "ps"))
S_orig = S; _x = {}
def S2(key):
    if key == "mij:JP225":
        if key not in _x: _x[key] = ps.on_cal(shot("JP225", 13, 20))
        return _x[key]
    return S_orig(key)
ns["S"] = S2
HOLD_ACC = ("14166201", "531466484", "531343523", "14074882"); IDX_ACC = ("11988011", "6104739")
def add_leg(lg, key, w): out = dict(lg); out[key] = out.get(key, 0.0) + w; return out
def hist(rd):
    m = (1 + rd).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(mean_m=float(m.mean()), worst_m=float(m.min()), mdd=float((eq / eq.cummax() - 1).min()), worst_d=float(rd.min()), sharpe=float(m.mean() / m.std() * np.sqrt(12)))
def rule_scale(lg, sw, a):
    rd = daily_window(ea_book(lg, sw)); s_mdd = solve_scale(rd, a["mdd"]); wd = float(rd.min()); s_dll = a["dll"] / abs(wd) if wd < 0 else 20.0
    return min(s_mdd, s_dll)
# ---- 参考: 系列の性質 ----
hj = S2("hold:JP225"); mij = S2("mij:JP225")
ref = {"Mon4(H1)": sum(S2("mon:" + s) for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")) / 4, "Hold XAU": S2("hold:XAUUSD"), "Hold UK100": S2("hold:UK100"), "Hold WTI": S2("hold:WTI"), "nas+spx": S2("nas") + S2("spx"), "MonIdxIntra JP225": mij}
w5 = lambda s: s[(s.index >= "2021-08-01") & (s.index <= "2026-07-29")]
print("Hold JP225 5 年:", {k: round(v, 3) for k, v in hist(w5(hj)).items()}, "| 全期間:", {k: round(v, 3) for k, v in hist(hj[hj.index >= "2016-01-04"]).items()})
print("Hold JP225 と各レグの日次相関(5 年):", {k: round(float(w5(hj).corr(w5(v))), 2) for k, v in ref.items()})
print("MonIdxIntra JP225 (Sharpe 週次, 最悪月 %, 累積 %): 前窓", q114stats(mij[mij != 0], PRE0, IS0), "IS", q114stats(mij[mij != 0], IS0, IS1), "OOS", q114stats(mij[mij != 0], OOS0, END), "| docs/333 の値 IS 0.98 / OOS 1.52")
print("MonIdxIntra JP225 と nas+spx の相関(月曜・5 年):", round(float(w5(mij)[w5(mij) != 0].corr(w5(ref["nas+spx"]))), 2), "| Mon4(H1) と:", round(float(w5(mij)[w5(mij) != 0].corr(w5(ref["Mon4(H1)"]))), 2))
rows = []
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); EL = EA_LEGS.get(aid)
    if not EL or aid not in HOLD_ACC + IDX_ACC: continue
    fn = a.get("funded_now", False); sw = a.get("swap_xau_bps_m", 0.0); firm, label, ea = META[aid]
    if aid in HOLD_ACC:
        hk = [k for k in EL["eval"] if k.startswith("hold:")]; key = "hold:JP225"; w_e = float(np.mean([EL["eval"][k] for k in hk])); w_f = float(np.mean([EL["funded"][k] for k in hk])); tag = "Hold JP225"
    else:
        key = "mij:JP225"; w_e = float(EL["eval"]["nas"]); w_f = float(EL["funded"]["nas"]); tag = "MonIdxIntra JP225"
    forms = [("現状", EL, 1.0)]
    added = {"eval": add_leg(EL["eval"], key, w_e), "funded": add_leg(EL["funded"], key, w_f)}
    forms.append(("単純追加", added, 1.0))
    s = rule_scale(added["funded"] if fn else added["eval"], sw, a); forms.append(("規約揃え", added, s))
    s0 = rule_scale(EL["funded"] if fn else EL["eval"], sw, a)
    for form, lgs, sc in forms:
        b = copy.deepcopy(a); b["eval"] = {k: v * sc for k, v in lgs["eval"].items()}; b["funded"] = {k: v * sc for k, v in lgs["funded"].items()}
        r = mc(b); h = hist(daily_window(ea_book(b["funded"] if fn else b["eval"], sw)))
        rows.append(dict(account=aid, name=a["name"], add=tag, w_eval=w_e, w_funded=w_f, form=form, scale=sc, scale_cur_rule=s0, p_reach=r["p_reach"], p_fail=r["p_fail"], p_pay=r["p_pay"], t_med_m=r["t_med_m"], c12_med=r["c12_med"], c30_mean=r["c30_mean"], **h))
        print(f"{aid} {tag} {form} ×{sc:.2f}: 到達 {r['p_reach']*100:.0f}% 失格 {r['p_fail']*100:.0f}% 出金到達 {r['p_pay']*100:.0f}% 期待 {r['c30_mean']/1e4:,.0f} 万 | 月利 {h['mean_m']*100:.2f}% 最悪月 {h['worst_m']*100:.1f}% 最悪日 {h['worst_d']*100:.1f}% Sharpe {h['sharpe']:.2f}", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/q169_jp225_deploy_mc.csv", index=False); print("DONE")
