# -*- coding: utf-8 -*-
"""docs/244 Q222(診断・セル 0・2026-11-15 登録): 本番中の FN Instant で損失枠比例の縮小の下限を {0.5, 0.375, 0.25} に変えた 1〜10 年。
モデルは Q210 と同じ(失格線 = min(最高残高 − 6%, 額面)・終了 = 失格線 + 2%・開始 +1.69%・+10% を残して超過分を出金)。数量の段階を LV(0.1〜1.0)に細分。
月曜の倍率 {1.5, 1.875, 2.5} × ロール {0, 3.0}。全期間 20,000 × 520 週・2016〜21 年のみ 10,000 × 260 週。乱数 187。
使い方: cd research && python3 -W ignore queue/q222_instant_shrink_floor.py   出力: results/q222_instant_shrink_floor.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table, account_items, paths_fac, weak_flags, states_h1, WFN, build, ROLL, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "account_items", "paths_fac", "weak_flags", "states_h1", "WFN", "build", "ROLL", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); n8["GRID"] = LV          # build は n8 の GRID を回す
a = [x for x in cfg["accounts"] if "11988011" in x["name"]][0]; aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); fx = [(s, w) for s, idxf, w in items if not idxf]; tot = sum(w for s, i, w in items)
START = 20338.37 / 2e4 - 1; ARM = 0.02; KEEP = 0.10; N = 20000
flags = {}
for s, w in fx:
    dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
FAC = {(s, False): {d: (1.0 if wk else 0.5) for d, wk in flags[s].items()} for s, w in fx}
def sim(T, cols, smin, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); ssum = np.zeros(n_paths); scnt = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c - KEEP, 0.0), 0.0); paid += pay; c = c - pay
        floor = np.minimum(hwm - mdd, 0.0); idx = rng.integers(0, n, n_paths); s = np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); ssum += np.where(act, LV[gi], 0.0); scnt += act; alive &= ~(c <= floor + ARM); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 156, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100, float(np.median(paid)) * 100, float((ssum / np.maximum(scnt, 1)).mean()))
    return out
rows = []
for mm in (1.5, 1.875, 2.5):
    it = [(sy, ix, w / tot * mm) for sy, ix, w in items]
    for rw in (0.0, 3.0):
        T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, FAC, P0, P1), g, (ROLL * rw if rw else None)); call = np.arange(len(dates)); c2 = call[dates < PM]
        for smin in (0.5, 0.375, 0.25):
            r = dict(mon_mult=mm, roll=rw, smin=smin, deployed=bool(mm == 1.875 and rw == 0.0 and smin == 0.5))
            for tag in ("lo", "cl"):
                m = sim(T[tag], call, smin, 520, N); m2 = sim(T[tag], c2, smin, 260, 10000)
                for wk, yy in ((52, 1), (156, 3), (260, 5), (520, 10)): r[f"s{yy}_{tag}"] = m[wk][0]; r[f"p{yy}_{tag}"] = m[wk][1]
                r[f"med10_{tag}"] = m[520][2]; r[f"size_{tag}"] = m[520][3]; r[f"w2s5_{tag}"] = m2[260][0]; r[f"w2p5_{tag}"] = m2[260][1]
            rows.append(r)
        print("done", mm, rw, flush=True)
D = pd.DataFrame(rows)
for k in ("s1", "s3", "s5", "s10", "p1", "p3", "p5", "p10", "med10", "w2s5", "w2p5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
D["size"] = D[["size_lo", "size_cl"]].mean(axis=1).round(3); D.to_csv("results/q222_instant_shrink_floor.csv", index=False); picks = []
for (mm, rw), x in D.groupby(["mon_mult", "roll"]):
    b = x[x.smin == 0.5].iloc[0]; pick = None
    for sm in (0.375, 0.25):
        v = x[x.smin == sm].iloc[0]
        if v.s10 >= b.s10 + 5.0 and v.p10 >= b.p10 and v.w2s5 >= b.w2s5: pick = v; break
    picks.append(dict(mon_mult=mm, roll=rw, base=f"{b.s1:.0f} / {b.s5:.0f} / {b.s10:.0f}・{b.w2s5:.0f}・+{b.p5:.0f} / +{b.p10:.0f}", verdict=(f"変更候補: 下限 {pick.smin}" if pick is not None else "現行どおり"), pick=(f"{pick.s1:.0f} / {pick.s5:.0f} / {pick.s10:.0f}・{pick.w2s5:.0f}・+{pick.p5:.0f} / +{pick.p10:.0f}" if pick is not None else "—")))
PK = pd.DataFrame(picks); PK.to_csv("results/q222_instant_shrink_floor_pick.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200); pd.set_option("display.max_columns", 40)
print(D[["mon_mult", "roll", "smin", "deployed", "s1", "s3", "s5", "s10", "w2s5", "p1", "p3", "p5", "p10", "med10", "w2p5", "size"]].to_string(index=False)); print(); print(PK.to_string(index=False))
