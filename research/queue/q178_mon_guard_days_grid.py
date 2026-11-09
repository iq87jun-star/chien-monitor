# -*- coding: utf-8 -*-
"""docs/244 Q178(診断・セル 0・2026-11-09 登録「登録でお願いします」→「実行」): ガード依存度で決める Mon 倍率の格子。
規約揃え倍率(ガード無しで歴史最悪日 ≤ ガード水準・docs/411 §4)は現行の 11〜36% だが、それは「ガードが一切効かない」前提。代わりに
 [a] ガード無しの日次が −dll(EA 日次ガード水準)を超える日数/年、[b] −限度(規約の日次限度・暫定 5%)を超える日数/年 を f ごとに数え、
 基準 = [b] ≤ 1 回/年 かつ [a] ≤ 3 回/年 を満たす最大の Mon 倍率 f(1.0〜0.4)。MC は 現状規則(account_cards.mc・ガードで −dll 頭打ち)と
 滑り入り(ガード発動日 = −dll − 1.0%・ガード無し日次が −限度 を超えた日は失格)の 2 通り。E 案(Mon ×f + Hold UK100/WTI)は Hold 重み上限 1.0 で引き直す。
 参考列 = Q175(日銀火曜 20 UTC 手仕舞い)適用後の [a][b] と基準 f。
使い方: cd research && python3 -W ignore queue/q178_mon_guard_days_grid.py   出力: results/q178_mon_guard_days_grid.csv・q178_eplan.csv・q178_portfolio.csv"""
import os, sys, copy, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, cur_legs, rescale, solve_w2, portfolio, mc, ea_book, daily_window, mdd_daily, EA_LEGS, SWING = (ns[k] for k in ("cfg", "cur_legs", "rescale", "solve_w2", "portfolio", "mc", "ea_book", "daily_window", "mdd_daily", "EA_LEGS", "SWING"))
ac = ns["ns"]; S_orig = ac["S"]; META = ac["META"]; acc_id = ac["acc_id"]
LIMIT = 0.05; SLIP = 0.01; FS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4)
# ---- 滑り入り MC: account_cards.mc の損失行だけ差し替え ----
acsrc = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read()
fn = acsrc[acsrc.index("def mc(a):"):acsrc.index("\ngen = dict(")]
old = "ret = np.clip(np.where(funded, cf[:, t] * f, ce[:, t]), -dll, None); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)"
new = "raw = np.where(funded, cf[:, t] * f, ce[:, t]); ret = np.where(raw < -dll, -dll - SLIP, raw); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & ((e <= fl) | (raw < -LIMIT))"
assert old in fn; fn = fn.replace(old, new).replace("def mc(a):", "def mc_slip(a):")
ac["SLIP"], ac["LIMIT"] = SLIP, LIMIT; exec(compile(fn, "mc_slip", "exec"), ac); mc_slip = ac["mc_slip"]
def scale_mon(lg, f): return {k: (v * f if k.startswith("mon:") else v) for k, v in lg.items()}
def build(a, f, legs=None):
    b = copy.deepcopy(a); EL = EA_LEGS[acc_id(a["name"])]
    if legs is None: b["eval"], b["funded"] = scale_mon(EL["eval"], f), scale_mon(EL["funded"], f)
    else:   # E 案: 現段階のレグを与え、評価中なら funded は同比率
        fn_ = a.get("funded_now", False)
        if fn_: b["eval"] = legs; b["funded"] = legs
        else:
            ratio = {k: EL["funded"].get(k, 0) / v if v else 0 for k, v in EL["eval"].items()}
            b["eval"] = legs; b["funded"] = {k: v * (ratio.get(k) if ratio.get(k) else list(ratio.values())[0]) for k, v in legs.items()}
    return b
def days(rd, dll):
    yrs = (rd.index[-1] - rd.index[0]).days / 365.25
    return float((rd <= -dll).sum() / yrs), float((rd <= -LIMIT).sum() / yrs), float(rd.min())
def ok(a_, b_): return b_ <= 1.0 and a_ <= 3.0
# ---- Q175 適用後の Mon 系列(参考列用): 日銀火曜の月曜だけ 24h → 同日 20 UTC の差分を H1 系列に足す ----
from q175_boj_tuesday_exit20 import family, BOJ_MON
# (portfolio_sim は不要・q175.family の index は暦日)
_boj = {}
def S_boj(key):
    fam_, _, sym = key.partition(":")
    if fam_ != "mon": return S_orig(key)
    if sym not in _boj:
        base_ = S_orig(key); d = (family({sym: 1.0}, BOJ_MON) - family({sym: 1.0}, None)).dropna(); d = d[d != 0]
        s = base_.copy(); idx = d.index.intersection(s.index); s.loc[idx] = s.loc[idx] + d.loc[idx].values; _boj[sym] = s
    return _boj[sym]
rows = []; stars = {}
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); EL = EA_LEGS.get(aid)
    if not EL or not any(k.startswith("mon:") for k in EL["eval"]): continue
    fn_ = a.get("funded_now", False); sw = a.get("swap_xau_bps_m", 0.0); dll = a["dll"]; firm, label, ea = META[aid]
    best, best_boj = None, None
    for f in FS:
        b = build(a, f); lg = b["funded"] if fn_ else b["eval"]
        ac["S"] = S_orig; rd = daily_window(ea_book(lg, sw)); ga, gb, wd = days(rd, dll)
        ac["S"] = S_boj; rd2 = daily_window(ea_book(lg, sw)); ga2, gb2, wd2 = days(rd2, dll); ac["S"] = S_orig
        r1 = mc(b); r2 = mc_slip(b)
        if ok(ga, gb) and best is None: best = f
        if ok(ga2, gb2) and best_boj is None: best_boj = f
        rows.append(dict(account=aid, name=a["name"], stage="資金化済" if fn_ else "評価中", f=f, dll=dll, guard_days=ga, limit_days=gb, worst_day=wd, ok=ok(ga, gb),
                         p_reach=r1["p_reach"], p_fail=r1["p_fail"], p_pay=r1["p_pay"], t_med_m=r1["t_med_m"], c12_med=r1["c12_med"], c30_mean=r1["c30_mean"],
                         s_p_fail=r2["p_fail"], s_p_pay=r2["p_pay"], s_c12_med=r2["c12_med"], s_c30_mean=r2["c30_mean"],
                         q175_guard_days=ga2, q175_limit_days=gb2, q175_worst_day=wd2, q175_ok=ok(ga2, gb2)))
        print(f"{aid} f={f:.1f} ガード {ga:.1f}/年 限度 {gb:.1f}/年 最悪 {wd*100:.1f}% | MC 失格 {r1['p_fail']*100:.0f}% 期待 {r1['c30_mean']/1e4:,.0f} 万 | 滑り 失格 {r2['p_fail']*100:.0f}% 期待 {r2['c30_mean']/1e4:,.0f} 万 | Q175 後 ガード {ga2:.1f} 限度 {gb2:.1f} 最悪 {wd2*100:.1f}%", flush=True)
    stars[aid] = (best, best_boj)
G = pd.DataFrame(rows); G.to_csv("results/q178_mon_guard_days_grid.csv", index=False)
print("\n== 基準(限度超え ≤ 1/年 かつ ガード ≤ 3/年)を満たす最大 f: 現状系列 / Q175 適用後 ==")
for aid, (b1, b2) in stars.items(): print(f"  {aid}: {b1 if b1 is not None else '0.4 未満'} / {b2 if b2 is not None else '0.4 未満'}")
# ---- E 案の引き直し(Hold 重み上限 1.0)----
erows, prow = [], []
for f in (1.0, 0.9, 0.8, 0.7):
    d = {}; wn = {}
    for a in cfg["accounts"]:
        aid = acc_id(a["name"]); lg = cur_legs(a); sw = a.get("swap_xau_bps_m", 0.0)
        if aid in SWING and f < 1.0: w = min(solve_w2(lg, f, sw), 1.0); d[a["name"]] = rescale(lg, f, w); wn[a["name"]] = w
        else: d[a["name"]] = dict(lg); wn[a["name"]] = 0.0
    P = portfolio(d); P["f"] = f; prow.append(P)
    for a in cfg["accounts"]:
        aid = acc_id(a["name"])
        if aid not in SWING: continue
        b = build(a, f, legs=d[a["name"]]); sw = a.get("swap_xau_bps_m", 0.0); lg = b["funded"] if a.get("funded_now") else b["eval"]
        rd = daily_window(ea_book(lg, sw)); ga, gb, wd = days(rd, a["dll"]); r1 = mc(b); r2 = mc_slip(b)
        erows.append(dict(f=f, account=aid, name=a["name"], hold_w=wn[a["name"]], guard_days=ga, limit_days=gb, worst_day=wd, p_fail=r1["p_fail"], p_pay=r1["p_pay"], c30_mean=r1["c30_mean"], s_p_fail=r2["p_fail"], s_c30_mean=r2["c30_mean"]))
        print(f"E 案 f={f:.1f} {aid} hold_w {wn[a['name']]:.2f} ガード {ga:.1f} 限度 {gb:.1f} 最悪 {wd*100:.1f}% 失格 {r1['p_fail']*100:.0f}% 期待 {r1['c30_mean']/1e4:,.0f} 万 滑り失格 {r2['p_fail']*100:.0f}%", flush=True)
E = pd.DataFrame(erows); E.to_csv("results/q178_eplan.csv", index=False); PP = pd.DataFrame(prow); PP.to_csv("results/q178_portfolio.csv", index=False)
pd.set_option("display.width", 250); print("\n== E 案(Hold 上限 1.0)帳簿全体 =="); print(PP.round(3).to_string(index=False))
print("DONE")
