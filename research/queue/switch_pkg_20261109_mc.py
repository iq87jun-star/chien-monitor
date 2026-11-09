# -*- coding: utf-8 -*-
"""2026-11-09 ユーザー「数値で推奨切替後と前で比較してください」: 推奨切替パッケージ(docs/415)を段階別に同じ MC で比較(配備判断・セル 0)。
 現状     = EA_LEGS(14074882 は SKEW 門あり・v1.14 配備中を再現)
 第 1 弾  = Mon 系全口座に Q175(日銀火曜の月曜ショットを同日 20 UTC 手仕舞い)+ 14074882 の SKEW 門を無効化
 第 1+2 弾 = + トパーズ MonIdxIntra JP225(nas と同じ重み)・14166201 Hold JP225 0.35・14074882 Hold JP225 0.4
 第 1+2+3 弾 = + Fintokei 3 口座(ルビー・トパーズ・パール)に E 案 f=0.9 + Hold UK100/WTI(重み上限 1.0・最悪日と 5 年 DD を現状以下)
MC = account_cards.mc(N=6000・種 44・30 か月)。Mon レグは Q176 の H1 系列。出力: results/switch_pkg_20261109.csv・_portfolio.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, cur_legs, rescale, solve_w2, portfolio, mc, ea_book, daily_window, mdd_daily, EA_LEGS = (ns[k] for k in ("cfg", "cur_legs", "rescale", "solve_w2", "portfolio", "mc", "ea_book", "daily_window", "mdd_daily", "EA_LEGS"))
ac = ns["ns"]; S_orig = ac["S"]; acc_id = ac["acc_id"]; ps = ac["ps"]
from q175_boj_tuesday_exit20 import family, BOJ_MON
from q173_skew_vvix_gate import PR
from q114_mon_index_intraday import shot
_c = {}
def mon_boj(sym):
    if sym not in _c:
        b = S_orig("mon:" + sym); d = (family({sym: 1.0}, BOJ_MON) - family({sym: 1.0}, None)).dropna(); d = d[d != 0]
        s = b.copy(); idx = d.index.intersection(s.index); s.loc[idx] = s.loc[idx] + d.loc[idx].values; _c[sym] = s
    return _c[sym]
def mon_skew(sym):
    k = "sk" + sym
    if k not in _c:
        s = S_orig("mon:" + sym).copy(); mon = s.index[s.index.dayofweek == 0]; prev = PR["SKEW"].reindex(mon - pd.Timedelta(days=3), method="ffill").values; s.loc[mon[prev > 0.8]] = 0.0; _c[k] = s
    return _c[k]
def S2(key):
    fam, _, sym = key.partition(":")
    if fam == "mbj": return mon_boj(sym)
    if fam == "msk": return mon_skew(sym)
    if key == "mij:JP225":
        if key not in _c: _c[key] = ps.on_cal(shot("JP225", 13, 20))
        return _c[key]
    return S_orig(key)
ac["S"] = S2; ns["S"] = S2   # portfolio() は q162 側の S を使う
def remap(lg, pre): return {(pre + ":" + k.split(":")[1] if k.startswith("mon:") else k): w for k, w in lg.items()}
def add(lg, key, w): out = dict(lg); out[key] = out.get(key, 0.0) + w; return out
FINTOKEI = ("6104736", "6104739", "6071612")
def stage_legs(a, stage):
    aid = acc_id(a["name"]); EL = EA_LEGS[aid]; ev, fd = dict(EL["eval"]), dict(EL["funded"])
    if stage == 0:
        if aid == "14074882": ev, fd = remap(ev, "msk"), remap(fd, "msk")
        return ev, fd
    ev, fd = remap(ev, "mbj"), remap(fd, "mbj")
    if stage >= 2:
        if aid == "6104739": ev, fd = add(ev, "mij:JP225", ev["nas"]), add(fd, "mij:JP225", fd["nas"])
        if aid == "14166201": ev, fd = add(ev, "hold:JP225", 0.35), add(fd, "hold:JP225", 0.35)
        if aid == "14074882": ev, fd = add(ev, "hold:JP225", 0.4), add(fd, "hold:JP225", 0.4)
    if stage >= 3 and aid in FINTOKEI:
        sw = a.get("swap_xau_bps_m", 0.0); fn_ = a.get("funded_now", False); lg = fd if fn_ else ev
        w = min(solve_w2(lg, 0.9, sw), 1.0)
        if fn_: ev = fd = rescale(lg, 0.9, w)
        else: ev = rescale(ev, 0.9, w); fd = rescale(fd, 0.9, w * (list(fd.values())[0] / list(ev.values())[0]) if False else w)   # 資金化後も同じ Hold 重み(Mon は EL の比率のまま ×0.9)
    return ev, fd
def hist(rd):
    m = (1 + rd).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(mean_m=float(m.mean()), worst_m=float(m.min()), mdd=float((eq / eq.cummax() - 1).min()), worst_d=float(rd.min()), sharpe=float(m.mean() / m.std() * np.sqrt(12)))
STAGES = {0: "現状", 1: "第1弾(Q175+門無効)", 2: "第1+2弾(+日経)", 3: "第1+2+3弾(+E案0.9)"}
rows, prow = [], []
for st, nm in STAGES.items():
    d = {}
    for a in cfg["accounts"]:
        ev, fd = stage_legs(a, st); fn_ = a.get("funded_now", False); sw = a.get("swap_xau_bps_m", 0.0); d[a["name"]] = fd if fn_ else ev
        b = copy.deepcopy(a); b["eval"], b["funded"] = ev, fd; r = mc(b); h = hist(daily_window(ea_book(d[a["name"]], sw)))
        rows.append(dict(stage=st, stage_name=nm, account=acc_id(a["name"]), name=a["name"], legs=" + ".join(f"{k} ×{w:.2f}" for k, w in d[a["name"]].items()), p_reach=r["p_reach"], p_fail=r["p_fail"], p_pay=r["p_pay"], t_med=r["t_med"], c12_med=r["c12_med"], c30_mean=r["c30_mean"], **h))
        print(f"{nm} {acc_id(a['name'])}: 失格 {r['p_fail']*100:.0f}% 出金到達 {r['p_pay']*100:.0f}% 期待 {r['c30_mean']/1e4:,.0f} 万 最悪日 {h['worst_d']*100:.1f}% 最悪月 {h['worst_m']*100:.1f}% Sh {h['sharpe']:.2f}", flush=True)
    P = portfolio(d); P["stage"] = st; P["stage_name"] = nm; P["c30_total"] = sum(x["c30_mean"] for x in rows if x["stage"] == st); prow.append(P)
pd.DataFrame(rows).to_csv("results/switch_pkg_20261109.csv", index=False); PP = pd.DataFrame(prow); PP.to_csv("results/switch_pkg_20261109_portfolio.csv", index=False)
pd.set_option("display.width", 250); print(PP.round(3).to_string(index=False)); print("DONE")
