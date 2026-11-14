# -*- coding: utf-8 -*-
"""docs/244 Q210(診断・セル 0・2026-11-15 登録「登録して実行」): 本番中の FN Instant に水曜ロールを足す場合の 1〜10 年。
月曜 = Q198 の H1 経路(2 つの縮小・SL リスク合計上限 2.4%)。ロール = 配備形(5 本・各 1/5・金利差 2.0pp の門)の日次系列を重ねる(縮小なし)。
失格線 = min(最高残高 − 6%, 額面)。終了の判定は EA の新規停止線(失格線 + 2%)。開始 = 現在地 +1.69%。4 週ごとに「+k% を残して超過分を出金」。
抽選: 全期間 2016-11〜2026-07(20,000 本 × 520 週)・2016〜21 年のみ(10,000 本 × 260 週)。乱数 187。
使い方: cd research && python3 -W ignore queue/q210_instant_add_wed_roll.py   出力: results/q210_instant_add_wed_roll.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table, account_items, paths_fac, weak_flags, states_h1, WFN, GRID, build, ROLL, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "account_items", "paths_fac", "weak_flags", "states_h1", "WFN", "GRID", "build", "ROLL", "P0", "PM", "P1"))
a = [x for x in cfg["accounts"] if "11988011" in x["name"]][0]; aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); fx = [(s, w) for s, idxf, w in items if not idxf]; tot = sum(w for s, i, w in items)
START = 20338.37 / 2e4 - 1; ARM = 0.02; N = 20000
BASE = 5.0   # items の合計倍率は config 次第なので、配備時点の 5.0 倍(円クロス 4.0 + 指数 1.0)に正規化して倍率を掛ける
flags = {}
for s, w in fx:
    dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
FAC = {(s, False): {d: (1.0 if wk else 0.5) for d, wk in flags[s].items()} for s, w in fx}
MON = (1.5, 1.875, 2.5); RW = (0.0, 1.5, 3.0, 4.5); KEEP = (0.08, 0.10)
def sim(T, cols, keep, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c - keep, 0.0), 0.0); paid += pay; c = c - pay
        floor = np.minimum(hwm - mdd, 0.0); idx = rng.integers(0, n, n_paths)
        gi = np.abs(GRID[None, :] - np.clip((c - floor) / mdd, 0.5, 1.0)[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + ARM); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 156, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100, float(np.median(paid)) * 100)
    return out
rs = ROLL[(ROLL.index >= P0) & (ROLL.index <= P1)]; eq = rs.cumsum(); r2 = rs[rs.index < PM]
print(f"ロール 1 倍あたり: 全期間 週 {rs.sum() / ((P1 - P0).days / 7) * 1e4:+.2f} bps・建てた日 {int((rs != 0).sum())}・最悪日 {rs.min() * 1e4:.0f} bps・最深 {(eq - eq.cummax()).min() * 100:.2f}% / 2016〜21 年 週 {r2.sum() / ((PM - P0).days / 7) * 1e4:+.2f} bps・建てた日 {int((r2 != 0).sum())}", flush=True)
rows = []
for mm in MON:
    it = [(sy, ix, w / tot * BASE * (mm / BASE)) for sy, ix, w in items]
    for rw in RW:
        T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, FAC, P0, P1), g, (ROLL * rw if rw else None)); call = np.arange(len(dates)); c2 = call[dates < PM]
        for keep in KEEP:
            r = dict(mon_mult=mm, roll=rw, keep=int(keep * 100))
            for tag in ("lo", "cl"):
                m = sim(T[tag], call, keep, 520, N); m2 = sim(T[tag], c2, keep, 260, 10000)
                for wk, yy in ((52, 1), (156, 3), (260, 5), (520, 10)): r[f"s{yy}_{tag}"] = m[wk][0]; r[f"p{yy}_{tag}"] = m[wk][1]
                r[f"med10_{tag}"] = m[520][2]; r[f"w2s5_{tag}"] = m2[260][0]; r[f"w2p5_{tag}"] = m2[260][1]
            rows.append(r)
        print("done", mm, rw, flush=True)
D = pd.DataFrame(rows)
for k in ("s1", "s3", "s5", "s10", "p1", "p3", "p5", "p10", "med10", "w2s5", "w2p5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
D.to_csv("results/q210_instant_add_wed_roll.csv", index=False)
picks = []
for (mm, keep), x in D.groupby(["mon_mult", "keep"]):
    b = x[x.roll == 0].iloc[0]; c = x[(x.roll > 0) & (x.s10 >= b.s10 - 2.0) & (x.p10 >= b.p10 + 3.0) & (x.w2s5 >= b.w2s5 - 2.0)].sort_values("roll")
    picks.append(dict(mon_mult=mm, keep=keep, base=f"{b.s1:.0f} / {b.s5:.0f} / {b.s10:.0f}・+{b.p5:.0f} / +{b.p10:.0f}", pick=(f"ロール {c.iloc[0].roll} 倍: {c.iloc[0].s1:.0f} / {c.iloc[0].s5:.0f} / {c.iloc[0].s10:.0f}・+{c.iloc[0].p5:.0f} / +{c.iloc[0].p10:.0f}" if len(c) else "—"), verdict=("追加候補" if len(c) else "足さない")))
PK = pd.DataFrame(picks); PK.to_csv("results/q210_instant_add_wed_roll_pick.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200); pd.set_option("display.max_columns", 40)
print(D[["mon_mult", "roll", "keep", "s1", "s3", "s5", "s10", "w2s5", "p1", "p3", "p5", "p10", "med10", "w2p5"]].to_string(index=False)); print(); print(PK.to_string(index=False))
