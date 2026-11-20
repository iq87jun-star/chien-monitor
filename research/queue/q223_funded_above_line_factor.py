# -*- coding: utf-8 -*-
"""docs/244 Q223(診断・セル 0・2026-11-15 登録「登録して実行」): 本口座後の決定済みの構成で、200 日線より上にいる円クロスの倍率を {0.5, 0.25, 0} に変える。月曜の倍率は決定済みの {1.0, 1.25, 1.5, 2.0} 倍(SL リスク上限のある口座は {1.0, 1.5})。
モデルは Q221 と同じ(縮小の下限 0.25・停止線は現行・4 週ごとに全額出金)。全期間 20,000 × 520 週・2016〜21 年のみ 10,000 × 260 週。乱数 187。
使い方: cd research && python3 -W ignore queue/q223_funded_above_line_factor.py   出力: results/q223_funded_above_line_factor.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, PRK, ROLL, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "PRK", "ROLL", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); NP = 20000; SMIN = 0.25
def acct(k): return [x for x in cfg["accounts"] if k in x["name"]][0]
def norm_items(key):
    a = acct(key); aid, items, cap, g = account_items(a); fxs = sum(w for s, i, w in items if not i); return [(s, i, w / fxs) for s, i, w in items], cap, g
MON4, _, _ = norm_items("521100397"); RD = {pd.Timestamp(d): float(v) for d, v in ROLL.items() if v == v}
def make_fac(items, skew, lo):
    """lo = 200 日線より上にいる通貨の倍率(None = 縮小なし)。戻り値: (fac, 月曜 × 通貨のうち建てる割合, 平均の倍率)"""
    fx = [(s, w) for s, i, w in items if not i]; flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if skew: pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    fac = {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or lo is None) else lo) for d, wk in flags[s].items()} for s, w in fx}
    allv = np.array([v for k in fac for d, v in fac[k].items() if P0 <= d <= P1]); return fac, float((allv > 0).mean()) * 100, float(allv.mean())
def build_full(items, cap, g, fac, mult):
    PA = paths_fac(items, None, fac, P0, P1) if cap is None else None; out = {"lo": [], "cl": []}; dates = None
    for lv in LV:
        P = scaled(PA, lv * mult) if PA is not None else paths_fac([(sy, ix, w * lv * mult) for sy, ix, w in items], cap, fac, P0, P1); dates = np.array([pd.Timestamp(p["d"]) for p in P]); R = run_guard(P, g)
        for tag in ("lo", "cl"): out[tag].append(R[tag][:2])
    return {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(2)) for tag in out}, dates
def roll_week(dates, rw, g):
    add = []
    for d in dates:
        c = 0.0
        for j in range(1, 7):
            x = RD.get(pd.Timestamp(d) + pd.Timedelta(days=j), 0.0) * rw; c += (-g * 1.1 if x <= -g else x)
        add.append(c)
    return np.array(add)
def sim(T, add, cols, mdd, pad, trail, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; add = add[cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); hwm = np.zeros(n_paths); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c, 0.0), 0.0); paid += pay; c = c - pay; hwm = np.where(pay > 0, c, hwm) if trail else hwm
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd); s = np.clip((c - floor) / mdd, SMIN, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0) + np.where(alive, add[idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + pad); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100)
    return out
# 表示名, 口座キー, 月曜の構成(None = 口座のもの), cap("acct" = 口座のもの), SKEW, 追随型, 決定済みの線の上の倍率(None = 縮小なし), 停止線の手前幅, 決定済みの円クロス倍率, ロール
A = [("FTMO 50k ×2", "521100397", None, None, False, False, 0.5, 0.01, 3.75, 0.0), ("宝くじ", "531343523", None, None, True, False, 0.5, 0.005, 4.0, 0.0), ("トパーズ", "6104739", None, None, True, False, 0.5, 0.01, 3.0, 4.5),
     ("ルビー / パール", "6104736", None, None, False, False, 0.5, 0.01, 2.78, 4.5), ("1-Step", "531466484", None, "acct", True, True, None, 0.01, 2.43, 0.0),
     ("FN 14074882", "14074882", None, (0.024, "A"), True, False, 0.5, 0.01, 4.0, 0.0), ("FN 14166201", "14166201", MON4, (0.024, "A"), False, False, 0.5, 0.01, 3.0, 4.5)]
rows = []
for nm, key, itov, capov, skew, trail, lo0, pad, m0, rw in A:
    if itov is None: items, cap, g = norm_items(key)
    else: items, cap, g = itov, None, 0.04
    cap = cap if capov == "acct" else capov; scales = (1.0, 1.25, 1.5, 2.0) if cap is None else (1.0, 1.5); los = ([None] if lo0 is None else []) + [0.5, 0.25, 0.0]
    for lo in los:
        fac, share, avgf = make_fac(items, skew, lo)
        for sc in scales:
            mm = m0 * sc; T, dates = build_full(items, cap, g, fac, mm); call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
            r = dict(acct=nm, above=("なし" if lo is None else lo), scale=sc, mon=round(mm, 2), roll=rw, decided=bool(lo == lo0 and sc == 1.0), trade_share=round(share, 1), avg_factor=round(avgf, 3))
            for tag in ("lo", "cl"):
                m = sim(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim(T[tag], add, c2, 0.10, pad, trail, 260, 10000)
                r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
            rows.append(r)
        print("done", nm, lo, flush=True)
    D = pd.DataFrame(rows)
    for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
    D.to_csv("results/q223_funded_above_line_factor.csv", index=False)
picks = []
for nm, x in D.groupby("acct", sort=False):
    b = x[x.decided].iloc[0]; c = x[(~x.decided) & (x.s10 >= b.s10 - 1.0) & (x.w2s5 >= b.w2s5 - 1.0) & (x.p10 >= b.p10 + 3.0)].sort_values("p10", ascending=False)
    picks.append(dict(acct=nm, base=f"上 {b.above}・{b.mon:g} 倍: {b.s1:.0f} / {b.s5:.0f} / {b.s10:.0f}・{b.w2s5:.0f}・+{b.p5:.0f} / +{b.p10:.0f}・弱い時期 5 年 +{b.w2p5:.0f}", verdict=("変更候補" if len(c) else "現行どおり"),
                      pick=(f"上 {c.iloc[0].above}・{c.iloc[0].mon:g} 倍: {c.iloc[0].s1:.0f} / {c.iloc[0].s5:.0f} / {c.iloc[0].s10:.0f}・{c.iloc[0].w2s5:.0f}・+{c.iloc[0].p5:.0f} / +{c.iloc[0].p10:.0f}・弱い時期 5 年 +{c.iloc[0].w2p5:.0f}" if len(c) else "—")))
PK = pd.DataFrame(picks); PK.to_csv("results/q223_funded_above_line_factor_pick.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 600); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 120)
print(D[["acct", "above", "scale", "mon", "roll", "decided", "trade_share", "avg_factor", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5"]].to_string(index=False)); print(); print(PK.to_string(index=False))
