# -*- coding: utf-8 -*-
"""docs/244 Q208(診断・セル 0・2026-11-14 登録「登録して実行」): 本口座に月曜以外のレグ(GER40 ブレイクアウト・金の保有・水曜ロール)を残した場合の 5 年・10 年。
月曜 = Q198 の H1 経路(2 つの縮小は月曜のみ。1-Step は縮小なし・追随型 + EA の全停止線)。非月曜レグは Q190 の方法で日次系列を重ねる(縮小なし)。
本口座の月曜倍率は合意済み(docs/241 §1ax)。非月曜レグ = 予定の大きさ × {0, 0.5, 1.0}。4 週ごとに全額出金・失格後は買い直さない・出金は分配前。
抽選: 全期間 2016-11〜2026-07(20,000 本 × 520 週)・W2 のみ(10,000 本 × 260 週)。
使い方: cd research && python3 -W ignore queue/q208_funded_non_monday_legs.py   出力: results/q208_funded_non_monday_legs.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
def head(fn, marker):
    src = open(os.path.join(HERE, fn), encoding="utf-8").read().split(marker)[0]; ns = {"__name__": fn[:4] + "_head", "__file__": os.path.join(HERE, fn)}; exec(compile(src, fn[:4] + "_head", "exec"), ns); return ns
n198 = head("q198_weak_tilt_plus_buffer_sizing.py", "\nrows = []\nfor a in cfg"); n190 = head("q190_add_non_monday_legs.py", "\nrows = []\nfor a in cfg")
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, GRID, PRK = (n198[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "GRID", "PRK")); S = n190["S"]
import q205_roll5_sma200_state as q205
from q20_wed_swap_carry import rate_series
P0, PM, P1 = pd.Timestamp("2016-11-01"), pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")
def roll_daily():
    """配備形のロール(5 本・各 1/5・政策金利差 2.0pp の門)の 1 倍あたり損益。index = 水曜。"""
    L = {s: q205.leg(s) for s in q205.PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(L[s].index) for s in q205.PAIRS]))); jp = rate_series("JPY", days)
    return pd.DataFrame({s: L[s] * (rate_series(s[:3], days) - jp >= q205.GATE).reindex(L[s].index).fillna(False).astype(float) for s in q205.PAIRS}).fillna(0.0).sum(axis=1) / len(q205.PAIRS)
ROLL = roll_daily(); BRK = S("brk"); XAU = S("hold:XAUUSD")
# 口座: 名前, 月曜 s, SKEW, 追随型, 月曜の構成 (200 日線, 損失枠比例の下限), 予定の非月曜レグ
ACC = {"521100397": ("FTMO 50k(0397)", 0.75, False, False, (True, 0.5), {"brk": 2.0}), "531343523": ("宝くじ", 0.625, True, False, (True, 0.5), {"brk": 3.0, "xau": 0.45}),
       "531466484": ("1-Step", round(1.25 / 3.0, 4), True, True, (False, None), {"xau": 0.15}), "6104739": ("トパーズ", 0.375, True, False, (True, 0.5), {"roll": 4.5}),
       "6104736": ("ルビー", 0.375, False, False, (True, 0.5), {"roll": 4.5}), "6071612": ("パール", 0.5, False, False, (True, 0.5), {"roll": 4.5})}
LAB = {"brk": "GER40 ブレイクアウト", "xau": "金の保有", "roll": "水曜ロール"}
def others(legs, swap_bps_m):
    s = None
    for k, w in legs.items():
        if w == 0: continue
        x = {"brk": BRK, "xau": XAU, "roll": ROLL}[k] * w
        if k == "xau" and swap_bps_m: x = x + w * swap_bps_m / 1e4 / 21.0
        s = x if s is None else s.add(x, fill_value=0)
    return s
def build(mon_paths_at, g, O):
    out = {"lo": [], "cl": []}; dates = None
    for lv in GRID:
        P = mon_paths_at(lv); dates = [pd.Timestamp(p["d"]) for p in P]
        ds_all = [[(float(O.get(d + pd.Timedelta(days=j), 0.0)) if O is not None else 0.0) for j in range(7)] for d in dates]; ds_all = [[0.0 if x != x else x for x in ds] for ds in ds_all]
        for p, ds in zip(P, ds_all):
            for tag in ("lo", "cl"): p["tot"][tag] = p["tot"][tag] + ds[0]; p["met"][tag] = p["met"][tag] + min(0.0, ds[0])
            p["fin"] += ds[0]
        R = run_guard(P, g)
        for tag in ("lo", "cl"):
            pnl, fired = R[tag][:2]; wp, wf = [], []
            for i, ds in enumerate(ds_all):
                c = float(pnl[i]); f = int(fired[i])
                for x in ds[1:]:
                    if x <= -g: x = -g * 1.1; f += 1
                    c += x
                wp.append(c); wf.append(f)
            out[tag].append((np.array(wp), np.array(wf)))
    return {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(2)) for tag in out}, np.array(dates)
def funded(T, cols, mdd, smin, trail, pad, n_paths, weeks, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); hwm = np.zeros(n_paths); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c, 0.0), 0.0); paid += pay; c = c - pay; hwm = np.where(pay > 0, c, hwm)
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd)
        gi = np.full(n_paths, len(GRID) - 1) if smin is None else np.abs(GRID[None, :] - np.clip((c - floor) / mdd, smin, 1.0)[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + pad); hwm = np.maximum(hwm, c)
        if w + 1 in (260, 520): tot = paid + np.where(alive, np.maximum(c, 0.0), 0.0); out[w + 1] = (round(float(alive.mean()) * 100, 1), round(float(tot.mean()) * 100, 1))
    return out
rows = []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if aid not in ACC: continue
    nm, sf, skew, trail, (tilt, smin), plan = ACC[aid]; mdd = float(a["mdd"]); pad = 0.01 if trail else 0.0; sw = float(a.get("swap_xau_bps_m", 0.0) or 0.0); fx = [(s, w) for s, idxf, w in items if not idxf]; flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if skew:
            pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    fac = {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
    PA = None if cap else paths_fac(items, cap, fac, P0, P1)
    def mon_at(lv): return scaled(PA, lv * sf) if PA is not None else paths_fac([(sy, ix, w * lv * sf) for sy, ix, w in items], cap, fac, P0, P1)
    variants = [("× 0(月曜のみ)", {k: 0.0 for k in plan}), ("× 0.5", {k: w * 0.5 for k, w in plan.items()}), ("× 1.0(予定)", dict(plan))]
    if len(plan) > 1: variants += [(f"参考: {LAB[k]}のみ × 1.0", {k2: (w if k2 == k else 0.0) for k2, w in plan.items()}) for k in plan]
    for vn, legs in variants:
        O = others(legs, sw); T, dates = build(mon_at, g, O); call = np.arange(len(dates)); c2 = call[dates < PM]
        ow = (float(O[(O.index >= P0) & (O.index <= P1)].sum()) / ((P1 - P0).days / 7) * 1e4) if O is not None else 0.0; od = int((O[(O.index >= P0) & (O.index <= P1)] <= -g).sum()) if O is not None else 0
        r = dict(acct=nm, mon_mult=round(sum(w for _, w in fx) * sf, 2), legs=" + ".join(f"{LAB[k]} {w:g} 倍" for k, w in legs.items() if w) or "—", level=vn, others_week_bps=round(ow, 1), others_days_le_guard=od, hits_lo=int(T["lo"][1][-1].sum()))
        for tag in ("lo", "cl"):
            m = funded(T[tag], call, mdd, smin, trail, pad, 20000, 520); m2 = funded(T[tag], c2, mdd, smin, trail, pad, 10000, 260); r.update({f"surv5_{tag}": m[260][0], f"surv10_{tag}": m[520][0], f"mean5_{tag}": m[260][1], f"mean10_{tag}": m[520][1], f"w2_surv5_{tag}": m2[260][0], f"w2_mean5_{tag}": m2[260][1]})
        rows.append(r)
    print(nm, "done", flush=True)
D = pd.DataFrame(rows)
for k in ("surv5", "surv10", "mean5", "mean10", "w2_surv5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1)
D.to_csv("results/q208_funded_non_monday_legs.csv", index=False); picks = []
for acct, g_ in D.groupby("acct", sort=False):
    plan = g_[g_.level == "× 1.0(予定)"].iloc[0]; low = g_[g_.level.isin(["× 0(月曜のみ)", "× 0.5"])]; cand = low[(low.surv10 >= plan.surv10 + 5.0) & (low.mean10 >= plan.mean10 - 3.0)].sort_values(["surv10", "mean10"], ascending=[False, False])
    picks.append(dict(acct=acct, plan_legs=plan.legs, plan=f"{plan.surv10:.1f} / {plan.mean10:.1f}", half=f"{g_[g_.level == '× 0.5'].iloc[0].surv10:.1f} / {g_[g_.level == '× 0.5'].iloc[0].mean10:.1f}", none=f"{g_[g_.level == '× 0(月曜のみ)'].iloc[0].surv10:.1f} / {g_[g_.level == '× 0(月曜のみ)'].iloc[0].mean10:.1f}", verdict=(f"変更候補: {cand.iloc[0].level}" if len(cand) else "予定どおり")))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q208_funded_non_monday_legs_pick.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print("\n== 推奨(10 年存続 / 累計出金) ==\n" + Pk.to_string(index=False))
print("\n== 全行 ==\n" + D[["acct", "mon_mult", "legs", "level", "others_week_bps", "others_days_le_guard", "hits_lo", "surv5", "surv10", "mean5", "mean10", "w2_surv5", "surv10_lo", "surv10_cl", "mean10_lo", "mean10_cl"]].to_string(index=False))
