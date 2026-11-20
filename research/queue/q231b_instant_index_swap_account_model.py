# -*- coding: utf-8 -*-
"""docs/244 Q231 第 2 段(診断・セル 0): 第 1 段で成立した F(US30・JP225: 線の下 1.0 倍・24h / 線の上 0.5 倍・同日 20 UTC 決済)を、指数を持つ口座(本番中の FN Instant)の指数レグの差し替えとして口座モデルで確かめる。
モデルは Q222 / Q230 (C) と同じ(月曜 1.875 倍・2 つの縮小・終了線 = 失格線 + 2%・+10% を残して超過分を出金・乱数 187)。指数の建ては EA と同じ米国現物寄り後の最初の正時(夏 14・冬 15 UTC)。
比べる形: 現行(NAS100 + US500・常時・24h)/ V1 指数を US30 + JP225 の F に差し替え / V2 現行の指数のまま F(参考・第 1 段は不成立)/ M3 円クロスの線の上は 20 UTC 決済(Q230 の候補)/ M3 + V1。
使い方: cd research && python3 -W ignore queue/q231b_instant_index_swap_account_model.py   出力: results/q231_near_miss_instant_account.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table0, account_items, paths_fac, weak_flags, states_h1, WFN, build, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "account_items", "paths_fac", "weak_flags", "states_h1", "WFN", "build", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); n8["GRID"] = LV; NP = 20000; K = paths_fac.__globals__["K"]; X20 = 16
EXIT = {"fx": False, "idx": False}; _MX = {}; _FL = {}
def flags_of(s, idx):
    if (s, idx) not in _FL:
        dts = [pd.Timestamp(d) for d in table0(s, idx)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); _FL[(s, idx)] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
    return _FL[(s, idx)]
def table_x(sym, idx):
    if not EXIT["idx" if idx else "fx"]: return table0(sym, idx)
    if (sym, idx) in _MX: return _MX[(sym, idx)]
    M, res = table0(sym, idx); Rk = res[K]; weak = flags_of(sym, idx); o = q.load(sym)["open"]; mark = Rk["mark"].copy(); worst = Rk["worst"].copy(); r = Rk["r"].copy(); stop = Rk["stop"].copy(); n_ch = 0
    for i, (d, t, off) in enumerate(zip(M.date.values, M.t.values, M.off.values)):
        d = pd.Timestamp(d); t = pd.Timestamp(t)
        if weak.get(d, False) or stop[i] < X20 or off >= X20: continue
        e = o.get(t, np.nan); o20 = o.get(d + pd.Timedelta(hours=20), np.nan)
        if e != e or o20 != o20: continue
        r20 = float(o20) / float(e) - 1 - float(q.cost(sym, [float(e)])[0]); mark[i, X20:] = r20; worst[i, X20:] = r20; r[i] = r20; stop[i] = X20; n_ch += 1
    res2 = dict(res); res2[K] = dict(Rk, mark=mark, worst=worst, r=r, stop=stop); _MX[(sym, idx)] = (M, res2); print(f"  [20 UTC 決済] {sym}: {n_ch} / {len(M)} ショット", flush=True); return _MX[(sym, idx)]
paths_fac.__globals__["table"] = table_x
a = [x for x in cfg["accounts"] if "11988011" in x["name"]][0]; aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); tot = sum(w for s, i, w in items); START = 20338.37 / 2e4 - 1; ARM = 0.02; KEEP = 0.10; MM = 1.875
print("Instant の構成:", [(s, i, round(w / tot * MM, 4)) for s, i, w in items], "cap", cap, "guard", g)
fxs = [(s, w) for s, i, w in items if not i]; ixs = [(s, w) for s, i, w in items if i]; SWAP = {"NAS100": "US30", "US500": "JP225"}
def fac_state(s, idx, lo): return {d: (1.0 if wk else lo) for d, wk in flags_of(s, idx).items()}
def sim(T, cols, smin, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c - KEEP, 0.0), 0.0); paid += pay; c = c - pay
        floor = np.minimum(hwm - mdd, 0.0); idx = rng.integers(0, n, n_paths); s = np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + ARM); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100)
    return out
# 形: (表示名, 指数の銘柄の差し替え, 指数に F を掛けるか, 円クロスの線の上を 20 UTC 決済にするか)
V = [("現行(NAS100 + US500・常時・24h)", False, False, False), ("V1 指数を US30 + JP225 の F に差し替え", True, True, False), ("V2 現行の指数のまま F(参考)", False, True, False), ("M3 円クロスの線の上は 20 UTC 決済(Q230)", False, False, True), ("M3 + V1", True, True, True)]
rows = []
for nm, swap, fidx, m3 in V:
    it = [(s, False, w / tot * MM) for s, w in fxs] + [((SWAP[s] if swap else s), True, w / tot * MM) for s, w in ixs]; fac = {(s, False): fac_state(s, False, 0.5) for s, w in fxs}
    if fidx: fac.update({(s, True): fac_state(s, True, 0.5) for s, i, w in it if i})
    EXIT["fx"] = m3; EXIT["idx"] = fidx; T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, fac, P0, P1), g, None); EXIT["fx"] = EXIT["idx"] = False; dates = pd.DatetimeIndex(dates); call = np.arange(len(dates)); c2 = call[dates < PM]
    r = dict(variant=nm, weeks=len(dates), wk_mean=round(float(T["cl"][0][-1].mean()) * 100, 3), wk_sd=round(float(T["cl"][0][-1].std()) * 100, 3), guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2))
    for tag in ("lo", "cl"):
        m = sim(T[tag], call, 0.5, 520, NP); m2 = sim(T[tag], c2, 0.5, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
    rows.append(r); print("done", nm, flush=True)
D = pd.DataFrame(rows)
for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
b = D.iloc[0]; D["verdict"] = ["—"] + [("変更候補" if ((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0)) else "現行どおり") for _, v in D.iloc[1:].iterrows()]
D.to_csv("results/q231_near_miss_instant_account.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
print(D[["variant", "weeks", "wk_mean", "wk_sd", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "verdict"]].to_string(index=False))
