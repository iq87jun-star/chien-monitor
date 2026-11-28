# -*- coding: utf-8 -*-
"""docs/244 Q184(診断・セル 0・2026-11-12 登録): 口座の分け方で同時被弾を減らせるか。S0 現状 / S1 隔週 2 組 / S2 毎週 0.5 倍 / S3 通貨の割り振り。
系列 = EA 実レグの日次(q162 の ea_book・daily_window)。月曜レグ = mon:*・nas・spx。金額は現在の額面(config の balance_jpy)で円換算。
使い方: cd research && python3 -W ignore queue/q184_stagger_accounts.py   出力: results/q184_stagger_accounts.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
import numpy as np, pandas as pd
cfg, ea_book, daily_window, EA_LEGS = (ns[k] for k in ("cfg", "ea_book", "daily_window", "EA_LEGS")); acc_id = ns["ns"]["acc_id"]
GA = {"6104739", "521100397", "11988011", "14074882", "6071612"}; GB = {"6104736", "531466484", "531343523", "531407058"}
GX = {"6104736", "6071612", "11988011", "531466484"}; GY = {"6104739", "531343523", "521100397", "531407058", "14074882"}
ismon = lambda k: k.startswith("mon:") or k in ("nas", "spx")
acc = []
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); key = "funded" if (a.get("funded_now") and aid != "14074882") else "eval"; lg = EA_LEGS[aid][key]; sw = a.get("swap_xau_bps_m", 0.0)
    tot = daily_window(ea_book(lg, sw)); ml = {k: w for k, w in lg.items() if ismon(k)}
    mon = daily_window(ea_book(ml, 0.0)).reindex(tot.index).fillna(0.0) if ml else tot * 0.0
    fx = sum(w for k, w in lg.items() if k.startswith("mon:")); alt = None
    if fx > 0 and aid in (GX | GY):
        pairs = ("GBPJPY", "AUDJPY") if aid in GX else ("USDJPY", "EURJPY"); l3 = {k: w for k, w in lg.items() if not k.startswith("mon:")}
        for p_ in pairs: l3["mon:" + p_] = fx / 2
        alt = daily_window(ea_book(l3, sw)).reindex(tot.index).fillna(0.0)
    acc.append(dict(aid=aid, name=a["name"], jpy=a["balance_jpy"], dll=a["dll"], tot=tot, mon=mon, oth=tot - mon, s3=alt if alt is not None else tot))
idx = acc[0]["tot"].index; wk = pd.Series(idx.isocalendar().week.values, index=idx); even = (wk % 2 == 0).values
def series(x, scen):
    if scen == "S0 現状": return x["tot"]
    if scen == "S1 隔週 2 組":
        if x["aid"] in GA: return x["oth"] + x["mon"] * even
        if x["aid"] in GB: return x["oth"] + x["mon"] * (~even)
        return x["tot"]
    if scen == "S2 毎週 0.5 倍": return x["oth"] + x["mon"] * 0.5
    if scen == "S3 通貨の割り振り": return x["s3"]
rows = []
for scen in ("S0 現状", "S1 隔週 2 組", "S2 毎週 0.5 倍", "S3 通貨の割り振り"):
    R = pd.DataFrame({x["aid"]: series(x, scen).reindex(idx).fillna(0.0) for x in acc}); J = pd.Series({x["aid"]: x["jpy"] for x in acc}); DL = pd.Series({x["aid"]: x["dll"] for x in acc})
    raw = (R * J).sum(axis=1) / 1e4; cap = (R.clip(lower=-DL, axis=1) * J).sum(axis=1) / 1e4; n_over = R.lt(-DL, axis=1).sum(axis=1); yrs = len(R) / 252
    m = raw.resample("ME").sum(); c = R.loc[:, R.std() > 0].corr().values; avg_corr = float(c[np.triu_indices(len(c), 1)].mean())
    rows.append(dict(scenario=scen, month_mean_man=round(m.mean()), month_worst_man=round(m.min()), sharpe_m=round(float(m.mean() / m.std() * np.sqrt(12)), 2), worst_day_raw_man=round(raw.min()), worst_day_guard_man=round(cap.min()),
                     p1_day_guard_man=round(cap.quantile(.01)), days_5plus_over_guard_per_yr=round(float((n_over >= 5).sum() / yrs), 2), days_3plus_per_yr=round(float((n_over >= 3).sum() / yrs), 2), max_accounts_over_guard=int(n_over.max()),
                     guard_hits_per_yr_total=round(float(n_over.sum() / yrs), 1), avg_corr=round(avg_corr, 2)))
D = pd.DataFrame(rows); D.to_csv("results/q184_stagger_accounts.csv", index=False); pd.set_option("display.width", 260); print(D.to_string(index=False))
